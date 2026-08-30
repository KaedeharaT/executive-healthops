"""Governance and on-demand provider contracts for public medical sources."""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from executive_health_ai.models import Base, KnowledgeDocument, KnowledgeSourceRegistry
from executive_health_ai.services.knowledge import KnowledgeService
from executive_health_ai.services.knowledge_sources import (
    MedlinePlusProvider, OpenFDAProvider, RxNormProvider, SOURCE_DEFINITIONS,
)


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()


class _Response:
    def __init__(self, *, text: str = "", payload: dict | None = None, status_code: int = 200) -> None:
        self.text, self._payload, self.status_code = text, payload or {}, status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP failure")

    def json(self) -> dict:
        return self._payload


class _HTTP:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_registry_records_terms_license_attribution_cache_and_review_state() -> None:
    with _session() as session:
        rows = KnowledgeService().ensure_source_registry(session)
        assert {row.source_code for row in rows} >= {"MEDLINEPLUS", "RXNORM", "OPENFDA", "WHO_ICD11"}
        medline = session.get(KnowledgeSourceRegistry, "MEDLINEPLUS")
        who = session.get(KnowledgeSourceRegistry, "WHO_ICD11")
        assert medline and medline.review_status == "APPROVED_SOURCE" and medline.enabled
        assert medline.attribution_requirement and medline.cache_policy
        assert who and who.review_status == "RESTRICTED" and not who.enabled


def test_medlineplus_provider_returns_linked_snippets_not_a_full_site_mirror() -> None:
    xml = """<searchResults><list><document rank='1'><content name='title'>Asthma</content><content name='url'>https://medlineplus.gov/asthma.html</content><content name='snippet'>Short topic snippet</content></document></list></searchResults>"""
    http = _HTTP(_Response(text=xml))
    rows = MedlinePlusProvider(http=http).search("asthma")
    assert rows[0].title == "Asthma" and rows[0].summary == "Short topic snippet"
    assert rows[0].source_url == "https://medlineplus.gov/asthma.html"
    assert "retmax" in http.calls[0][1]["params"] and http.calls[0][1]["params"]["retmax"] <= 10


def test_rxnorm_provider_returns_canonical_drug_concepts() -> None:
    http = _HTTP(_Response(payload={"drugGroup": {"conceptGroup": [{"conceptProperties": [{"rxcui": "1191", "name": "Aspirin"}]}]}}))
    rows = RxNormProvider(http=http).search("aspirin")
    assert rows[0].source_code == "RXNORM" and rows[0].external_id == "1191"
    assert "标准化" in (rows[0].summary or "")
    assert rows[0].provider_code == "RXNORM" and rows[0].structured_metadata["rxcui"] == "1191"
    assert "/REST/" not in rows[0].official_url


def test_openfda_provider_returns_regulatory_label_reference_without_medical_decision() -> None:
    http = _HTTP(_Response(payload={"results": [{"id": "label-1", "spl_id": "spl-1", "openfda": {"generic_name": ["aspirin"]}, "warnings": ["Regulatory warning"]}]}))
    rows = OpenFDAProvider(http=http).search("aspirin")
    assert rows[0].source_code == "OPENFDA" and "FDA 药品标签" in rows[0].title
    assert rows[0].summary == "Regulatory warning"
    assert "api.fda.gov" not in rows[0].official_url
    assert rows[0].subtitle == "药品标签资料"


def test_source_results_cache_selectively_as_pending_review_with_attribution() -> None:
    with _session() as session:
        service = KnowledgeService(); service.ensure_source_registry(session)
        result = RxNormProvider(http=_HTTP(_Response(payload={"drugGroup": {"conceptGroup": [{"conceptProperties": [{"rxcui": "1191", "name": "Aspirin"}]}]}}))).search("aspirin")[0]
        document = service.cache_source_result(session, result)
        assert document.review_status == "PENDING_REVIEW"
        assert document.attribution and document.source_url and document.content_hash
        assert service.cache_source_result(session, result).id == document.id


def test_only_approved_documents_can_be_recorded_as_actual_ai_sources() -> None:
    with _session() as session:
        service = KnowledgeService()
        draft = service.create_document(session, title="Draft", category="MEDICATION", source_type="公开医学来源", source_name="RXNORM")
        try:
            service.record_ai_usage(session, output_type="health_explanation", output_reference="example", documents=[draft])
        except ValueError:
            pass
        else:
            raise AssertionError("draft knowledge was accepted for AI use")
        service.approve_document(session, draft, "健康管理师")
        records = service.record_ai_usage(session, output_type="health_explanation", output_reference="example", documents=[draft])
        assert records[0].source_title == "Draft"


def test_registry_does_not_promote_public_sources_to_clinical_rules() -> None:
    assert all(item.source_type != "RISK_RULE" for item in SOURCE_DEFINITIONS)
    assert all("风险规则" not in item.display_name for item in SOURCE_DEFINITIONS)
