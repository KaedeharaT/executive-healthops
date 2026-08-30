"""Official, on-demand public medical knowledge providers.

Providers return a small, attributable search result only.  They never create
clinical rules, diagnoses, medication changes, or full-site mirrors.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Protocol
from urllib.parse import quote_plus
from xml.etree import ElementTree

import requests


@dataclass(frozen=True)
class KnowledgeSourceDefinition:
    source_code: str
    display_name: str
    provider: str
    source_type: str
    official_url: str
    api_type: str
    license_or_terms: str
    attribution_requirement: str
    commercial_use_note: str
    cache_policy: str
    language: str
    version: str | None
    review_status: str
    enabled: bool


@dataclass(frozen=True)
class KnowledgeSearchResult:
    """Provider-neutral, product-safe result for the knowledge-library UI.

    The raw HTTP response stays inside the provider.  Renderers receive a
    stable result model instead of having to know API routes or payload shape.
    """

    provider_code: str
    external_id: str
    title: str
    subtitle: str
    summary: str | None
    category: str
    source_name: str
    source_organization: str
    official_url: str
    version: str | None
    retrieved_at: datetime
    structured_metadata: dict[str, str | None]
    language: str
    attribution: str
    license_note: str
    raw_payload_reference: str | None = None
    saveable: bool = True

    # Compatibility aliases for the service boundary introduced in VNext.
    @property
    def source_code(self) -> str:
        return self.provider_code

    @property
    def source_url(self) -> str:
        return self.official_url

    @property
    def source_version(self) -> str | None:
        return self.version


# Kept as a source-compatible import for existing integrations. New code uses
# KnowledgeSearchResult explicitly.
KnowledgeSourceResult = KnowledgeSearchResult


SOURCE_DEFINITIONS: tuple[KnowledgeSourceDefinition, ...] = (
    KnowledgeSourceDefinition(
        "MEDLINEPLUS", "MedlinePlus", "U.S. National Library of Medicine / NIH",
        "PATIENT_EDUCATION", "https://medlineplus.gov/about/developers/webservices/", "HTTPS search API",
        "免费 Web Service；按官方可接受使用政策调用，不批量镜像页面。",
        "界面须注明信息来自 MedlinePlus.gov；不得使用 MedlinePlus 标识或暗示官方背书。",
        "可显示 API 返回的标题、摘要和链接；结果缓存 12–24 小时，限速 85 请求/分钟/IP。",
        "24 hours", "en/es", None, "APPROVED_SOURCE", True,
    ),
    KnowledgeSourceDefinition(
        "RXNORM", "RxNorm / RxNav", "U.S. National Library of Medicine / NIH",
        "TERMINOLOGY", "https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html", "HTTPS REST API",
        "RxNorm API 的非专有 RxNorm 词汇通常无需单独许可；不调用 proprietary endpoint。",
        "产品须说明使用 NLM/NIH 公开数据，且 NLM 不对本产品背书。",
        "仅按需查询药物概念；遵守 API 请求限制；缓存 30 天。",
        "30 days", "en", None, "APPROVED_SOURCE", True,
    ),
    KnowledgeSourceDefinition(
        "OPENFDA", "openFDA 药品标签", "U.S. Food and Drug Administration",
        "REGULATORY_DRUG_INFORMATION", "https://open.fda.gov/apis/drug/label/", "HTTPS REST API",
        "受 openFDA Terms of Service 与免责声明约束；标签内容未经 FDA 逐项核验。",
        "结果须标示为 openFDA/FDA 监管资料，并保留“不应用于医疗决定”的边界。",
        "仅按需查询少量标签摘要；不作为处方或个体医疗决定；缓存 7 天。",
        "7 days", "en", None, "APPROVED_SOURCE", True,
    ),
    KnowledgeSourceDefinition(
        "WHO_ICD11", "WHO ICD-11", "World Health Organization",
        "CLASSIFICATION", "https://icd.who.int/icdapi", "HTTPS REST API with credentials",
        "ICD-11 使用 CC BY-ND 3.0 IGO；使用 API 需要 WHO 注册和访问凭证。",
        "发布时使用 WHO ICD-11 标准引文；不得将分类术语混同为自动诊断。",
        "仅在安全配置了 WHO API 凭证后按需查询；未配置时禁用。",
        "On demand", "en / configured languages", "ICD-11 2026 release", "RESTRICTED", False,
    ),
    KnowledgeSourceDefinition(
        "LOINC", "LOINC", "Regenstrief Institute",
        "TERMINOLOGY", "https://loinc.org/license", "License-reviewed; not connected",
        "可在商业和非商业系统中按其公开许可使用；使用时须保留版本与 LOINC 版权/许可声明。",
        "若将 LOINC 内容纳入产品，须提供许可声明并附代码及显示名称。",
        "本轮不接入或下载完整 LOINC 表；待单独术语治理审核。",
        "Not connected", "en", None, "CANDIDATE", False,
    ),
    KnowledgeSourceDefinition(
        "SNOMED_CT", "SNOMED CT", "SNOMED International",
        "TERMINOLOGY", "https://www.snomed.org/get-snomed", "License required by territory",
        "成员地区与非成员地区有不同注册、许可和可能的费用要求。",
        "未完成地区许可审查前不得导入、缓存或展示 SNOMED CT 内容。",
        "在非成员地区部署可能需要年度 Affiliate License、使用报告和费用审查。",
        "Disabled until territory/license review", "configured", None, "RESTRICTED", False,
    ),
)


class KnowledgeProviderError(RuntimeError):
    """An expected provider/configuration error, safe for user-facing recovery."""


class KnowledgeSourceProvider(Protocol):
    source_code: str

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]: ...

    def fetch_detail(self, external_id: str) -> KnowledgeSearchResult: ...


class _OfficialProvider:
    source_code: str
    definition: KnowledgeSourceDefinition

    def __init__(self, *, http: requests.Session | None = None) -> None:
        self.http = http or requests.Session()

    def _result(
        self, *, external_id: str, title: str, subtitle: str, summary: str | None,
        official_url: str, category: str, structured_metadata: dict[str, str | None] | None = None,
        version: str | None = None,
    ) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            provider_code=self.source_code, external_id=external_id, title=title.strip(), subtitle=subtitle,
            summary=summary.strip() if summary else None, category=category,
            source_name=self.definition.display_name, source_organization=self.definition.provider,
            official_url=official_url, version=version or self.definition.version,
            retrieved_at=datetime.now(timezone.utc), structured_metadata=structured_metadata or {},
            language=self.definition.language, attribution=self.definition.attribution_requirement,
            license_note=self.definition.license_or_terms,
        )

    def fetch_detail(self, external_id: str) -> KnowledgeSearchResult:
        raise KnowledgeProviderError("当前来源暂不支持按编号获取详情，请先使用平台内搜索结果。")


class MedlinePlusProvider(_OfficialProvider):
    source_code = "MEDLINEPLUS"
    definition = next(item for item in SOURCE_DEFINITIONS if item.source_code == "MEDLINEPLUS")

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]:
        response = self.http.get(
            "https://wsearch.nlm.nih.gov/ws/query",
            params={"db": "healthTopics", "term": query, "retmax": min(max(limit, 1), 10), "rettype": "brief", "tool": "executive_healthops"},
            timeout=12,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        results: list[KnowledgeSearchResult] = []
        for item in root.findall(".//document"):
            # The NLM search response puts the canonical URL on <document>, not
            # in a content child.  Its FullSummary is often a full HTML topic,
            # so retain only a small plain-text excerpt instead of mirroring it.
            title = _plain_excerpt(item.findtext("content[@name='title']") or "", limit=240)
            url = (item.get("url") or item.findtext("content[@name='url']") or "").strip()
            summary = _plain_excerpt(
                item.findtext("content[@name='snippet']") or item.findtext("content[@name='FullSummary']") or "",
                limit=900,
            )
            if title and url:
                results.append(self._result(
                    external_id=item.get("rank") or url, title=title, subtitle="健康主题",
                    summary=summary, official_url=url, category="PATIENT_EDUCATION",
                    structured_metadata={"topic": title},
                ))
        return results


def _plain_excerpt(value: str, *, limit: int) -> str:
    """Return an attributable snippet, not source-page HTML or full content."""
    plain = re.sub(r"<[^>]+>", " ", unescape(value))
    return " ".join(plain.split())[:limit].strip()


class RxNormProvider(_OfficialProvider):
    source_code = "RXNORM"
    definition = next(item for item in SOURCE_DEFINITIONS if item.source_code == "RXNORM")

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]:
        response = self.http.get("https://rxnav.nlm.nih.gov/REST/drugs.json", params={"name": query}, timeout=12)
        response.raise_for_status()
        groups = response.json().get("drugGroup", {}).get("conceptGroup", [])
        results: list[KnowledgeSearchResult] = []
        for group in groups:
            for concept in group.get("conceptProperties", []) or []:
                rxcui, name = str(concept.get("rxcui") or ""), str(concept.get("name") or "")
                if rxcui and name:
                    synonym = str(concept.get("synonym") or "").strip()
                    summary = "RxNorm 药物概念；仅用于名称标准化，不自动修改成员用药。"
                    if synonym:
                        summary += f" 同义名称/品牌映射：{synonym}。"
                    results.append(self._result(
                        external_id=rxcui, title=name, subtitle="标准药物名称", summary=summary,
                        official_url=f"https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={quote_plus(rxcui)}",
                        category="MEDICATION", structured_metadata={"rxcui": rxcui, "term_type": str(concept.get("tty") or "") or None, "synonym": synonym or None},
                    ))
                if len(results) >= limit:
                    return results
        return results


class OpenFDAProvider(_OfficialProvider):
    source_code = "OPENFDA"
    definition = next(item for item in SOURCE_DEFINITIONS if item.source_code == "OPENFDA")

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSearchResult]:
        response = self.http.get(
            "https://api.fda.gov/drug/label.json",
            params={"search": f'openfda.generic_name:"{query}"', "limit": min(max(limit, 1), 10)},
            timeout=12,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        results: list[KnowledgeSearchResult] = []
        for item in response.json().get("results", []):
            openfda = item.get("openfda") or {}
            name = next(iter(openfda.get("brand_name") or openfda.get("generic_name") or []), query)
            set_id = str(item.get("set_id") or next(iter(openfda.get("spl_set_id") or []), "") or item.get("id") or name)
            generic_name = next(iter(openfda.get("generic_name") or []), None)
            manufacturer = next(iter(openfda.get("manufacturer_name") or []), None)
            summary = next(iter(item.get("boxed_warning") or item.get("warnings") or item.get("indications_and_usage") or []), None)
            results.append(self._result(
                external_id=set_id, title=f"{name} · FDA 药品标签", subtitle="药品标签资料", summary=summary,
                official_url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={quote_plus(set_id)}",
                category="MEDICATION", structured_metadata={"generic_name": generic_name, "brand_name": name, "manufacturer": manufacturer},
            ))
        return results


class WHOICD11Provider(_OfficialProvider):
    source_code = "WHO_ICD11"
    definition = next(item for item in SOURCE_DEFINITIONS if item.source_code == "WHO_ICD11")

    def search(self, query: str, *, limit: int = 5) -> list[KnowledgeSourceResult]:
        if not os.getenv("WHO_ICD11_CLIENT_ID") or not os.getenv("WHO_ICD11_CLIENT_SECRET"):
            raise KnowledgeProviderError("WHO ICD-11 API 尚未配置访问凭证。")
        raise KnowledgeProviderError("WHO ICD-11 provider 已预留，需在已登记凭证环境中完成 OAuth 令牌配置后使用。")


def provider_for(source_code: str, *, http: requests.Session | None = None) -> KnowledgeSourceProvider:
    providers = {
        "MEDLINEPLUS": MedlinePlusProvider,
        "RXNORM": RxNormProvider,
        "OPENFDA": OpenFDAProvider,
        "WHO_ICD11": WHOICD11Provider,
    }
    try:
        return providers[source_code.upper()](http=http)
    except KeyError as error:
        raise KnowledgeProviderError("该来源尚未配置按需查询。") from error
