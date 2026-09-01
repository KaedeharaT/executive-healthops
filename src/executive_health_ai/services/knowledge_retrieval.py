"""Auditable first-pass keyword retrieval for approved knowledge chunks only.

This intentionally avoids a vector database and never sends an entire library
to a model.  A future hybrid/embedding layer can implement the same result
contract without changing governance rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from executive_health_ai.models import KnowledgeChunk, KnowledgeDocument
from executive_health_ai.services.knowledge import KnowledgeService


QUERY_SYNONYMS = (
    (("yellow risk", "黄风险", "黄色风险", "中风险"), ("yellow risk", "yellow", "risk", "中风险", "黄色风险")),
    (("接手", "领取", "接受任务"), ("接手", "负责人", "active worklist")),
    (("内部医生", "医学复核", "医生复核", "提交医生"), ("内部医生", "doctor review", "医学判断")),
    (("体检报告", "上传报告", "报告上传"), ("体检报告", "报告审核", "candidate", "evidence")),
    (("健康计划", "调整计划", "暂缓计划"), ("健康计划", "成员确认", "调整", "暂缓")),
    (("任务没完成", "任务没有完成", "未完成任务"), ("任务未完成", "成员任务", "提醒")),
    (("服务申请", "服务通过", "安排服务"), ("服务申请", "审核", "安排", "结果回流")),
    (("outcome", "阶段结果", "阶段复盘"), ("outcome", "阶段复盘", "下一步")),
    (("很久没有更新", "陈旧数据", "数据过期", "缺少数据"), ("陈旧数据", "数据缺失", "新鲜度", "补测")),
)


def normalize_query_terms(phrase: str) -> list[str]:
    """Expand a small, auditable HealthOps synonym set without inventing answers."""
    normalized = phrase.strip().lower()
    terms = [normalized]
    for aliases, expansions in QUERY_SYNONYMS:
        if any(alias in normalized for alias in aliases):
            terms.extend(expansions)
    return list(dict.fromkeys(term for term in terms if term))


@dataclass(frozen=True)
class KnowledgeRetrievalHit:
    document: KnowledgeDocument
    chunk: KnowledgeChunk
    score: int

    def citation(self) -> dict[str, str | None]:
        """A UI-safe citation based only on the exact retrieved chunk."""
        return {
            "title": self.document.title,
            "source": self.document.source_name,
            "source_url": self.document.source_url,
            "version": self.document.source_version or self.document.version,
            "retrieved_at": self.document.retrieved_at.isoformat() if self.document.retrieved_at else None,
            "location": self.chunk.source_location or self.chunk.heading,
            "excerpt": self.chunk.content[:500],
        }


class KnowledgeRetrievalService:
    """Stable keyword/BM25-ready boundary for formal AI knowledge use."""

    def search(
        self, session: Session, query: str, *, category: str | None = None,
        source_provider: str | None = None, language: str | None = None, limit: int = 6,
        categories: tuple[str, ...] = (), source_types: tuple[str, ...] = (),
        audience: str | None = None, jurisdiction: str | None = None,
        intended_use: str | None = None, feature: str | None = None,
    ) -> list[KnowledgeRetrievalHit]:
        phrase = query.strip().lower()
        if not phrase:
            return []
        # Safe one-time backfill for previously approved, text-bearing assets.
        KnowledgeService().ensure_approved_chunks(session)
        statement = select(KnowledgeChunk, KnowledgeDocument).join(
            KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.knowledge_document_id
        ).where(
            KnowledgeDocument.is_active.is_(True),
            KnowledgeDocument.review_status == "APPROVED",
        )
        if category:
            statement = statement.where(KnowledgeDocument.category == category)
        if source_provider:
            statement = statement.where(KnowledgeDocument.source_provider == source_provider)
        if language:
            statement = statement.where(KnowledgeDocument.language == language)
        if categories:
            statement = statement.where(KnowledgeDocument.category.in_(categories))
        if source_types:
            statement = statement.where(KnowledgeDocument.source_type.in_(source_types))

        normalized_terms = normalize_query_terms(phrase)
        tokens = [
            token
            for term in normalized_terms
            for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", term)
            if token
        ]
        # Chinese questions often contain no whitespace.  Bigrams make the
        # deterministic first-pass retrieval useful without inventing semantic
        # similarity or adding a vector-store dependency.
        expanded: list[str] = []
        for token in tokens or [phrase]:
            expanded.append(token)
            if any("\u4e00" <= char <= "\u9fff" for char in token) and len(token) > 2:
                expanded.extend(token[index:index + 2] for index in range(len(token) - 1))
        # Common question scaffolding must not make an unrelated query look
        # grounded merely because an SOP also contains words such as “流程”.
        stop_tokens = {
            "一个", "一些", "什么", "怎么", "如何", "应该", "当前", "以后",
            "知识", "知识库", "没有", "完全", "覆盖", "问题", "流程", "告诉",
        }
        tokens = [token for token in dict.fromkeys(expanded) if token not in stop_tokens]
        if not tokens:
            return []
        hits: list[KnowledgeRetrievalHit] = []
        for chunk, document in session.execute(statement).all():
            if not KnowledgeService._eligible_for_formal_ai(document):
                continue
            metadata = document.metadata_json or {}
            audiences = {str(item).casefold() for item in metadata.get("audience", [])}
            if audience and audience.casefold() not in audiences and "all" not in audiences:
                continue
            jurisdictions = {str(item).upper() for item in metadata.get("jurisdiction", ["GLOBAL"])}
            if jurisdiction and jurisdiction.upper() not in jurisdictions and "GLOBAL" not in jurisdictions:
                continue
            intended_uses = {str(item).upper() for item in metadata.get("intended_use", [])}
            if intended_use and intended_use.upper() not in intended_uses:
                continue
            features = {str(item).casefold() for item in metadata.get("features", [])}
            if feature and feature.casefold() not in features:
                continue
            title = document.title.lower()
            body = f"{chunk.heading or ''}\n{chunk.content}".lower()
            lexical_score = sum(8 for token in tokens if token == title) + sum(4 for token in tokens if token in title)
            lexical_score += sum(body.count(token) for token in tokens)
            if lexical_score:
                category_priority = {"INTERNAL_SOP": 12, "TRAINING_MATERIAL": 10, "CLINICAL_GUIDELINE": 3, "PATIENT_EDUCATION": 1}
                title_intent_bonus = sum(20 for term in normalized_terms if len(term) >= 4 and term in title)
                score = lexical_score + title_intent_bonus + category_priority.get(document.category, 0)
                hits.append(KnowledgeRetrievalHit(document=document, chunk=chunk, score=score))
        return sorted(hits, key=lambda item: (-item.score, item.document.title, item.chunk.chunk_index))[:limit]

    def search_routed(self, session: Session, query: str, *, audience: str | None = None,
                      jurisdiction: str | None = None, intended_use: str | None = None,
                      limit: int = 6) -> list[KnowledgeRetrievalHit]:
        """Apply a deterministic domain route before lexical scoring."""
        from executive_health_ai.services.knowledge_foundation import KnowledgeQueryClassifier
        route = KnowledgeQueryClassifier().classify(query)
        categories = {
            "MEDICATION": ("MEDICATION", "TERMINOLOGY", "REGULATORY"),
            "LAB": ("MEDICAL_TEST", "TERMINOLOGY"),
            "WORKFLOW": ("INTERNAL_SOP", "TRAINING_MATERIAL"),
            "LIFESTYLE": ("LIFESTYLE", "PATIENT_EDUCATION"),
            "DEVICE": ("DEVICE_GUIDANCE",),
            "PRIVACY": ("PRIVACY", "AI_SAFETY"),
            "AI_SAFETY": ("AI_SAFETY", "INTERNAL_SOP", "TRAINING_MATERIAL"),
        }.get(route, ())
        return self.search(session, query, categories=categories, audience=audience,
                           jurisdiction=jurisdiction, intended_use=intended_use, limit=limit)
