"""Governed source catalog and retrieval taxonomy for Knowledge Foundation V1.

The catalog is metadata, not an approval of every document at a source.  It is
deliberately conservative: protected sources are link/metadata only and no
entry can create a clinical rule.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from sqlalchemy.orm import Session

from executive_health_ai.models import KnowledgeSourceRegistry


STRATEGIES = {"OPEN_FULLTEXT", "PUBLIC_SUMMARY", "METADATA_ONLY", "API_ON_DEMAND", "LINK_ONLY", "LICENSE_RESTRICTED", "DO_NOT_INGEST"}
TRUST_TIERS = {"TIER_A", "TIER_B", "TIER_C", "TIER_D"}
SOURCE_STATUSES = {"APPROVED_SOURCE", "CONDITIONAL", "METADATA_ONLY", "DO_NOT_INGEST", "UNAVAILABLE"}
AUDIENCES = {"MEMBER", "HEALTH_MANAGER", "DOCTOR", "ADMIN", "AI_INTERNAL"}
INTENDED_USES = {"EXPLANATION", "NORMALIZATION", "WORKFLOW_GUIDANCE", "DOCTOR_REFERENCE", "MEMBER_EDUCATION", "RULE_REFERENCE_CANDIDATE"}
PROHIBITED_USES = {"NOT_FOR_DIAGNOSIS", "NOT_FOR_PRESCRIPTION", "NOT_FOR_AUTOMATIC_RISK", "NOT_FOR_EMERGENCY_AUTOMATION"}


@dataclass(frozen=True)
class GovernedSource:
    source_id: str
    display_name: str
    organization: str
    country: str
    jurisdiction: str
    source_type: str
    knowledge_domains: tuple[str, ...]
    official_url: str
    api_url: str | None
    language: tuple[str, ...]
    license: str
    commercial_use: str
    redistribution_allowed: str
    attribution_required: bool
    content_strategy: str
    update_frequency: str
    versioning_method: str
    research_date: str
    access_status: str
    trust_tier: str
    status: str
    enabled: bool
    notes: str


@dataclass(frozen=True)
class KnowledgeSourceUpdatePolicy:
    source_id: str
    frequency: str
    method: str
    auto_approve: bool = False


@dataclass(frozen=True)
class CanonicalTerm:
    canonical: str
    aliases: tuple[str, ...]
    coding_system: str | None
    code: str | None
    language: str


CANONICAL_TERMS: tuple[CanonicalTerm, ...] = (
    CanonicalTerm("LDL-C", ("LDL", "低密度脂蛋白", "低密度脂蛋白胆固醇"), "LOINC", None, "zh-CN/en"),
    CanonicalTerm("HbA1c", ("糖化血红蛋白", "A1C", "glycated hemoglobin"), "LOINC", None, "zh-CN/en"),
    CanonicalTerm("Yellow Risk", ("黄风险", "黄色风险", "中风险"), None, None, "zh-CN/en"),
    CanonicalTerm("metformin", ("二甲双胍",), "RxNorm", "6809", "zh-CN/en"),
)


def _s(source_id: str, name: str, org: str, country: str, jurisdiction: str, source_type: str,
       domains: str, url: str, strategy: str, tier: str, status: str, license_note: str,
       *, api: str | None = None, languages: tuple[str, ...] = ("en",), commercial: str = "REVIEW_REQUIRED",
       redistribution: str = "SOURCE_SPECIFIC", update: str = "quarterly metadata check",
       versioning: str = "publisher date/version", enabled: bool = True, notes: str = "") -> GovernedSource:
    return GovernedSource(source_id, name, org, country, jurisdiction, source_type, tuple(domains.split("|")), url, api,
                          languages, license_note, commercial, redistribution, True, strategy, update, versioning,
                          "2026-09-02", "AVAILABLE", tier, status, enabled, notes)


# Verified official entry points.  A source status does not approve individual
# content: each saved document still follows KnowledgeReviewAudit.
FOUNDATION_SOURCES: tuple[GovernedSource, ...] = (
    _s("MEDLINEPLUS", "MedlinePlus", "U.S. National Library of Medicine", "US", "US", "PATIENT_EDUCATION", "report|lab|chronic_disease|lifestyle", "https://medlineplus.gov/about/using/usingcontent/", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "NLM public-domain topic summaries and medical tests; licensed drug/encyclopedia content excluded", api="https://wsearch.nlm.nih.gov/ws/query", commercial="ALLOWED_FOR_PUBLIC_DOMAIN_PORTIONS", redistribution="PUBLIC_DOMAIN_PORTIONS_ONLY", update="monthly"),
    _s("RXNORM", "RxNorm / RxNav", "U.S. National Library of Medicine", "US", "US", "TERMINOLOGY", "medication|terminology", "https://www.nlm.nih.gov/research/umls/rxnorm/index.html", "API_ON_DEMAND", "TIER_A", "APPROVED_SOURCE", "Non-proprietary RxNorm API content; proprietary/UMLS sources excluded", api="https://rxnav.nlm.nih.gov/REST/", commercial="ALLOWED_WITH_TERMS", redistribution="RXNORM_CONTENT_ONLY", update="monthly release"),
    _s("DAILYMED", "DailyMed SPL", "U.S. National Library of Medicine", "US", "US", "MEDICATION", "medication", "https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm", "API_ON_DEMAND", "TIER_A", "APPROVED_SOURCE", "Official SPL access; retain label version and attribution", api="https://dailymed.nlm.nih.gov/dailymed/services/v2/", update="weekly"),
    _s("OPENFDA", "openFDA", "U.S. Food and Drug Administration", "US", "US", "REGULATORY", "medication|device", "https://open.fda.gov/apis/", "API_ON_DEMAND", "TIER_A", "APPROVED_SOURCE", "Public FDA datasets subject to API terms and dataset disclaimer", api="https://api.fda.gov/", commercial="ALLOWED_WITH_TERMS", update="dataset last_updated"),
    _s("LOINC", "LOINC", "Regenstrief Institute", "US", "GLOBAL", "TERMINOLOGY", "lab|report|terminology", "https://loinc.org/kb/license", "METADATA_ONLY", "TIER_B", "CONDITIONAL", "Open commercial/non-commercial license with mandatory notice, identifiers/display names, no competing standard or unauthorized derivatives", redistribution="LICENSE_CONDITIONS", update="each release", versioning="LOINC release version"),
    _s("SNOMED_CT", "SNOMED CT", "SNOMED International", "GLOBAL", "GLOBAL", "TERMINOLOGY", "terminology|classification", "https://www.snomed.org/get-snomed", "LICENSE_RESTRICTED", "TIER_B", "CONDITIONAL", "Affiliate and territory licensing applies; no content imported before licence review", enabled=False, commercial="TERRITORY_SPECIFIC", redistribution="LICENSE_REQUIRED"),
    _s("WHO_ICD11", "WHO ICD-11", "World Health Organization", "GLOBAL", "GLOBAL", "CLASSIFICATION", "classification|terminology", "https://icd.who.int/docs/icd-api/license/", "API_ON_DEMAND", "TIER_A", "CONDITIONAL", "CC BY-ND 3.0 IGO; no adaptation", api="https://id.who.int/", commercial="ALLOWED_NO_DERIVATIVES", redistribution="CC_BY_ND_3_IGO", update="annual release", versioning="ICD release identifier"),
    _s("WHO_TOPICS", "WHO Health Topics", "World Health Organization", "GLOBAL", "GLOBAL", "PUBLIC_HEALTH", "chronic_disease|lifestyle|smoking|alcohol|mental_wellbeing", "https://www.who.int/about/policies/publishing/copyright", "LINK_ONLY", "TIER_A", "CONDITIONAL", "Publication-specific licensing; many works CC BY-NC-SA 3.0 IGO, commercial use requires permission", commercial="NONCOMMERCIAL_UNLESS_PERMISSION", redistribution="PUBLICATION_SPECIFIC", update="monthly metadata check"),
    _s("CDC", "CDC Health Topics", "U.S. Centers for Disease Control and Prevention", "US", "US", "PUBLIC_HEALTH", "chronic_disease|lifestyle|sleep|smoking|device", "https://www.cdc.gov/other/agencymaterials.html", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "Most agency-authored text public domain; third-party items and images excluded", commercial="ALLOWED_WITH_ATTRIBUTION_AND_NO_ENDORSEMENT", redistribution="PUBLIC_DOMAIN_PORTIONS_ONLY", update="monthly"),
    _s("NIH", "NIH Health Information", "U.S. National Institutes of Health", "US", "US", "PATIENT_EDUCATION", "chronic_disease|research", "https://www.nih.gov/", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "U.S. government-authored text generally public domain; page-level rights check required", update="quarterly"),
    _s("NHLBI", "NHLBI Health Topics", "National Heart, Lung, and Blood Institute", "US", "US", "PATIENT_EDUCATION", "blood_pressure|lipids|sleep|lung", "https://www.nhlbi.nih.gov/health", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "NIH government content; exclude credited third-party assets", update="quarterly"),
    _s("NIDDK", "NIDDK Health Information", "National Institute of Diabetes and Digestive and Kidney Diseases", "US", "US", "PATIENT_EDUCATION", "diabetes|obesity|kidney|liver|nutrition", "https://www.niddk.nih.gov/health-information", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "NIH government content; retain page date and review status", update="quarterly"),
    _s("NIMH", "NIMH Health Topics", "National Institute of Mental Health", "US", "US", "PATIENT_EDUCATION", "mental_wellbeing|stress", "https://www.nimh.nih.gov/health/topics", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "Educational information, not diagnosis or personal advice", update="quarterly"),
    _s("NIH_ODS", "NIH Office of Dietary Supplements", "National Institutes of Health", "US", "US", "PATIENT_EDUCATION", "nutrition|supplement|medication_safety", "https://ods.od.nih.gov/factsheets/list-all/", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "Government fact sheets; supplements remain separate from medication and treatment advice", update="quarterly"),
    _s("FDA", "FDA Health and Digital Health", "U.S. Food and Drug Administration", "US", "US", "REGULATORY", "medication|device|ai_safety", "https://www.fda.gov/medical-devices/digital-health-center-excellence/guidances-digital-health-content", "METADATA_ONLY", "TIER_A", "APPROVED_SOURCE", "Official regulatory metadata; guidance-specific version and rights apply", update="monthly metadata check"),
    _s("USPSTF", "USPSTF Recommendations", "U.S. Preventive Services Task Force / AHRQ", "US", "US", "GUIDELINE", "preventive_care|screening", "https://www.uspreventiveservicestaskforce.org/uspstf/recommendation-topics/copyright-notice", "METADATA_ONLY", "TIER_A", "CONDITIONAL", "Unchanged reproduction permitted with attribution; no fee/profit use without written permission", commercial="PERMISSION_REQUIRED_FOR_PROFIT_USE", redistribution="UNCHANGED_ONLY", update="monthly metadata check", versioning="recommendation publication date"),
    _s("NICE", "NICE Guidance", "National Institute for Health and Care Excellence", "UK", "UK", "GUIDELINE", "chronic_disease|preventive_care|medication", "https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence", "METADATA_ONLY", "TIER_B", "CONDITIONAL", "NICE UK Open Content Licence; territory/content restrictions require item review", commercial="LICENSE_SPECIFIC", redistribution="LICENSE_SPECIFIC", update="monthly metadata check"),
    _s("NHS", "NHS Health A to Z", "National Health Service", "UK", "UK", "PATIENT_EDUCATION", "chronic_disease|lifestyle|medication", "https://www.nhs.uk/our-policies/terms-and-conditions/", "LINK_ONLY", "TIER_A", "CONDITIONAL", "NHS site terms and content-specific rights", commercial="REVIEW_REQUIRED", redistribution="LINK_ONLY"),
    _s("AHA", "American Heart Association", "American Heart Association", "US", "US", "PROFESSIONAL_ORGANIZATION", "blood_pressure|lipids|cardiovascular", "https://www.heart.org/en/about-us/statements-and-policies/copyright-permission-guidelines", "METADATA_ONLY", "TIER_B", "METADATA_ONLY", "Copyrighted; reproduction requires permission", commercial="PERMISSION_REQUIRED", redistribution="NO_FULLTEXT"),
    _s("ACC", "American College of Cardiology", "American College of Cardiology", "US", "US", "PROFESSIONAL_ORGANIZATION", "cardiovascular|guideline", "https://www.acc.org/guidelines", "LINK_ONLY", "TIER_B", "METADATA_ONLY", "Copyright/terms are content-specific; link and metadata only", redistribution="LINK_ONLY"),
    _s("ADA", "American Diabetes Association", "American Diabetes Association", "US", "US", "PROFESSIONAL_ORGANIZATION", "diabetes|guideline", "https://diabetes.org/about-us/policies/terms-of-use", "METADATA_ONLY", "TIER_B", "METADATA_ONLY", "Personal use only unless written permission", commercial="PERMISSION_REQUIRED", redistribution="NO_FULLTEXT"),
    _s("USDA_DGA", "Dietary Guidelines for Americans", "USDA / HHS", "US", "US", "GUIDELINE", "nutrition|lifestyle", "https://www.dietaryguidelines.gov/policy-and-links", "OPEN_FULLTEXT", "TIER_A", "APPROVED_SOURCE", "Site information public domain with attribution; exclude protected third-party assets", commercial="ALLOWED_FOR_PUBLIC_DOMAIN_PORTIONS", redistribution="PUBLIC_DOMAIN_PORTIONS_ONLY", update="each edition", versioning="edition year"),
    _s("MHLW_JP", "日本厚生労働省 健康情報", "Ministry of Health, Labour and Welfare", "JP", "JP", "PUBLIC_HEALTH", "lifestyle|physical_activity|workplace_health", "https://www.mhlw.go.jp/chosakuken/", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "Public Data License 1.0 unless otherwise marked; attribution required", languages=("ja", "en"), commercial="ALLOWED_WITH_TERMS", redistribution="PDL_1_0", update="quarterly"),
    _s("NHC_CN", "中华人民共和国国家卫生健康委员会", "国家卫生健康委员会", "CN", "CN", "PUBLIC_HEALTH", "report|preventive_care|privacy|ai_safety", "https://www.nhc.gov.cn/", "LINK_ONLY", "TIER_A", "CONDITIONAL", "版权所有；不得非法镜像，逐项确认授权后方可存储", languages=("zh-CN",), commercial="REVIEW_REQUIRED", redistribution="LINK_ONLY"),
    _s("CHINA_CDC", "中国疾病预防控制中心健康科普", "中国疾病预防控制中心", "CN", "CN", "PUBLIC_HEALTH", "chronic_disease|nutrition|smoking|public_health", "https://www.chinacdc.cn/jkkp/", "LINK_ONLY", "TIER_A", "CONDITIONAL", "网站版权与免责声明适用；默认链接/元数据，不镜像全文", languages=("zh-CN",), redistribution="LINK_ONLY"),
    _s("APPLE_HEALTHKIT", "Apple HealthKit Documentation", "Apple", "GLOBAL", "GLOBAL", "DEVICE_TECHNICAL", "device|health_data", "https://developer.apple.com/documentation/healthkit", "LINK_ONLY", "TIER_D", "METADATA_ONLY", "Apple developer terms apply; technical data definitions only", commercial="DEVELOPER_TERMS", redistribution="LINK_ONLY"),
    _s("NIST_AI_RMF", "NIST AI RMF", "National Institute of Standards and Technology", "US", "GLOBAL", "AI_SAFETY", "ai_safety|governance", "https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-ai-rmf-10", "OPEN_FULLTEXT", "TIER_A", "APPROVED_SOURCE", "U.S. government publication; cite NIST AI 100-1", update="annual metadata check", versioning="publication/version"),
    _s("HHS_HIPAA", "HHS HIPAA Resources", "U.S. Department of Health and Human Services", "US", "US", "PRIVACY", "privacy", "https://www.hhs.gov/hipaa/index.html", "PUBLIC_SUMMARY", "TIER_A", "APPROVED_SOURCE", "Official U.S. legal information; reference only, not a compliance determination", update="quarterly"),
    _s("CN_PIPL", "个人信息保护法官方文本", "中国人大网", "CN", "CN", "PRIVACY", "privacy", "https://www.gov.cn/xinwen/2021-08/20/content_5632486.htm", "LINK_ONLY", "TIER_A", "METADATA_ONLY", "Official legal text; legal-review reference only", languages=("zh-CN",), redistribution="LINK_ONLY"),
    _s("JP_PPC", "Japan PPC / APPI", "Personal Information Protection Commission", "JP", "JP", "PRIVACY", "privacy", "https://www.ppc.go.jp/en/", "LINK_ONLY", "TIER_A", "METADATA_ONLY", "Official legal guidance; legal-review reference only", languages=("ja", "en"), redistribution="LINK_ONLY"),
    _s("EMA", "European Medicines Agency", "European Medicines Agency", "EU", "EU", "REGULATORY", "medication", "https://www.ema.europa.eu/en/about-us/legal-notice", "METADATA_ONLY", "TIER_A", "CONDITIONAL", "EMA legal notice and document-level rights apply", redistribution="SOURCE_SPECIFIC"),
    _s("HEALTHOPS_INTERNAL", "Executive HealthOps Internal Demo Knowledge", "Executive HealthOps Portfolio", "INTERNAL", "GLOBAL", "INTERNAL_SOP", "workflow|service|outcome|communication|ai_safety", "https://github.com/KaedeharaT/executive-healthops", "OPEN_FULLTEXT", "TIER_C", "APPROVED_SOURCE", "Original synthetic Portfolio knowledge; not hospital policy", commercial="PROJECT_LICENSE", redistribution="PROJECT_LICENSE", update="manual version", versioning="semantic document version"),
    _s("UPTODATE", "UpToDate", "Wolters Kluwer", "GLOBAL", "GLOBAL", "COMMERCIAL_DATABASE", "medical", "https://www.uptodate.com/", "DO_NOT_INGEST", "TIER_D", "DO_NOT_INGEST", "Subscription content; no scraping, mirroring or redistribution", enabled=False, commercial="LICENSE_REQUIRED", redistribution="PROHIBITED"),
)


def validate_source_catalog(sources: Sequence[GovernedSource] = FOUNDATION_SOURCES) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if source.source_id in seen:
            errors.append(f"duplicate source_id: {source.source_id}")
        seen.add(source.source_id)
        for field in ("display_name", "organization", "official_url", "license", "research_date", "update_frequency"):
            if not getattr(source, field): errors.append(f"{source.source_id}: missing {field}")
        if not source.official_url.startswith("https://"): errors.append(f"{source.source_id}: official_url must use HTTPS")
        if source.content_strategy not in STRATEGIES: errors.append(f"{source.source_id}: invalid strategy")
        if source.trust_tier not in TRUST_TIERS: errors.append(f"{source.source_id}: invalid trust tier")
        if source.status not in SOURCE_STATUSES: errors.append(f"{source.source_id}: invalid status")
    return errors


def sync_source_registry(session: Session) -> int:
    """Upsert governance metadata; never approves a KnowledgeDocument."""
    if errors := validate_source_catalog():
        raise ValueError("; ".join(errors))
    now = datetime.now(timezone.utc)
    for source in FOUNDATION_SOURCES:
        row = session.get(KnowledgeSourceRegistry, source.source_id)
        if row is None:
            row = KnowledgeSourceRegistry(source_code=source.source_id, display_name=source.display_name,
                provider=source.organization, organization=source.organization, source_type=source.source_type,
                official_url=source.official_url, api_type="HTTPS" if source.api_url else "NONE",
                license_or_terms=source.license, attribution_requirement="Required" if source.attribution_required else "None",
                commercial_use_note=source.commercial_use, cache_policy=source.update_frequency,
                language="/".join(source.language), version=None, retrieved_at=now,
                review_status=source.status, status=source.status, enabled=source.enabled)
            session.add(row)
        row.display_name = source.display_name
        row.provider = source.organization
        row.organization = source.organization
        row.source_type = source.source_type
        row.official_url = source.official_url
        row.api_type = "HTTPS" if source.api_url else "NONE"
        row.license_or_terms = source.license
        row.attribution_requirement = "Required" if source.attribution_required else "None"
        row.commercial_use_note = source.commercial_use
        row.cache_policy = source.update_frequency
        row.language = "/".join(source.language)
        row.retrieved_at = now
        row.review_status = source.status
        row.status = source.status
        row.enabled = source.enabled
        row.governance_metadata = asdict(source)
        row.updated_at = now
    session.flush()
    return len(FOUNDATION_SOURCES)


def update_policies() -> tuple[KnowledgeSourceUpdatePolicy, ...]:
    """Every discovered update requires review; none is auto-approved."""
    return tuple(KnowledgeSourceUpdatePolicy(item.source_id, item.update_frequency, item.versioning_method)
                 for item in FOUNDATION_SOURCES)


class KnowledgeQueryClassifier:
    """Deterministic routing hints; it cannot approve content or make risk decisions."""
    ROUTES = {
        "MEDICATION": ("metformin", "二甲双胍", "药品", "药物", "标签"),
        "LAB": ("ldl", "ldl-c", "低密度脂蛋白", "hba1c", "糖化血红蛋白", "检验"),
        "WORKFLOW": ("yellow risk", "中风险", "医生升级", "任务", "服务", "outcome", "设备异常"),
        "LIFESTYLE": ("运动", "睡眠", "吸烟", "营养", "体重"),
        "DEVICE": ("cgm", "血压计", "apple health", "healthkit", "设备"),
        "PRIVACY": ("隐私", "phi", "hipaa", "个人信息"),
        "AI_SAFETY": ("llm", "ai风险", "模型", "人工智能"),
    }
    def classify(self, query: str) -> str:
        text = query.casefold()
        for route, aliases in self.ROUTES.items():
            if any(alias in text for alias in aliases): return route
        return "GENERAL_HEALTH"


class EmbeddingRetriever(Protocol):
    def search(self, query: str, *, limit: int) -> Sequence[object]: ...


class Reranker(Protocol):
    def rank(self, query: str, hits: Sequence[object]) -> Sequence[object]: ...


@dataclass
class HybridRetrievalAdapter:
    """V2 extension seam. V1 intentionally runs keyword retrieval alone."""
    keyword_retriever: object
    embedding_retriever: EmbeddingRetriever | None = None
    reranker: Reranker | None = None
