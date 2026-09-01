# HealthOps Knowledge Architecture V1

```text
Official source / internal SOP
  → fetch or upload
  → raw reference (never overwritten)
  → parse and remove navigation/boilerplate
  → semantic sections
  → one-complete-idea chunks
  → metadata + provenance
  → human review
  → APPROVED index
  → filtered retrieval
  → grounded AI answer
  → actual-chunk citation + KnowledgeUseRecord
```

The database is the source of truth. Download folders are staging/cache only. `KnowledgeDocument` owns version, licence, review and validity; `KnowledgeChunk` owns exact source-located excerpts; `KnowledgeReviewAudit` is append-only governance; `KnowledgeUseRecord` records chunks actually used, not every retrieved chunk.

## Safety boundary

- External medical knowledge explains concepts. Internal SOP describes HealthOps actions.
- Member facts remain separate Fact Evidence from reports, observations, devices and clinician records.
- Retrieval defaults to active, `APPROVED`, non-archived, non-expired content and filters audience, jurisdiction and intended use.
- Knowledge never becomes a `RiskRule` directly: `Knowledge → Rule candidate → human author → medical reviewer → approved clinical rule`.
- Conflicting sources remain separate by jurisdiction, version and date. The answer must disclose the difference.
- V1 is deterministic keyword/BM25-ready retrieval. V2 may add embeddings through `HybridRetrievalAdapter`; V3 may add a reranker. Governance filters run before every retrieval generation.

## Update policy

API sources such as RxNorm, DailyMed and openFDA are on demand. WHO/NICE/USPSTF metadata is checked periodically. Internal SOP updates are manual. A discovered update enters `PENDING_REVIEW`; it never replaces an approved version automatically. Superseded historical citations remain auditable.
