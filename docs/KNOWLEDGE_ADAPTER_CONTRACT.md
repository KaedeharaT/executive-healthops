# Knowledge Adapter Contract

HealthOps consumes governed knowledge through one result contract while retaining grounding, citation validation, no-source refusal and usage auditing.

```python
search(query, category=None, audience=None, jurisdiction=None, top_k=5)
```

Each result must contain an external chunk identifier, title, content, section, source name, organization, source URL, version, timezone-aware retrieval time and licence note. Incomplete source metadata is rejected; an adapter may not return answer text without traceable source material.

## Routing

- Internal SOP, communication, service and AI-safety queries prefer `LocalKnowledgeAdapter`.
- External medical explanations may prefer `ExternalPartnerKnowledgeAdapter`.
- Portfolio/offline operation falls back to approved local demo knowledge.
- If neither provider returns valid source material, `GroundedAnswerService` refuses; the LLM is not allowed to answer from model memory.

Partner configuration uses `KNOWLEDGE_PROVIDER`, `KNOWLEDGE_API_BASE` and `KNOWLEDGE_API_KEY`. Only a de-identified query plus category, audience, jurisdiction and bounded `top_k` are sent. Member names, member IDs, full reports, prompts and health records are not part of the adapter request.

Partner chunks are not mirrored into `KnowledgeDocument`. Only the actually cited external chunk identifiers and immutable display snapshots are stored in `KnowledgeUseRecord` for audit.
