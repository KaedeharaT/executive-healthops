# AI Grounding and Citation Policy

Executive HealthOps separates two evidence types:

- **Fact Evidence** answers “what happened to this member?” and points to a report page or excerpt, an Observation/device record, a doctor record, medication, service, problem, or outcome.
- **Knowledge Evidence** answers “what does this mean or what workflow applies?” and points to the exact `KnowledgeChunk` retrieved from an active, approved, in-review-date `KnowledgeDocument`.

## AI answer contract

Every user-visible generated explanation returns content, fact citations, knowledge citations, model information, grounding status, and limitations through `GroundedAnswerService`. Citation display data is assembled by application code from retrieval results; the model cannot invent titles, URLs, or chunk identifiers. Only markers returned from the current retrieval set are accepted, and only actually cited chunks are written to `KnowledgeUseRecord`.

An answer is **GROUNDED**, **PARTIALLY_GROUNDED**, or **INSUFFICIENT_EVIDENCE**. If no eligible knowledge is found, the model is not called and the UI states that approved support is insufficient. Archived, expired, inactive, pending, rejected, or review-overdue sources are excluded from new answers. Historical answers retain immutable citation snapshots and show the source's current governance state.

## Special cases

- Report semantic extraction is structured fact extraction, not a knowledge answer. Its evidence is the original report page and preserved excerpt. Any later interpretation requires Knowledge Evidence.
- Risk is produced by deterministic rules from Observations and `RiskRule`; it is not an AI answer.
- A doctor's conclusion is a human medical decision. An AI-generated doctor brief must cite member facts and must cite approved knowledge if it adds interpretation.
- SOP and workflow answers use approved internal knowledge chunks. The cancelled Training Copilot product is not part of this contract; generic grounding, refusal, citation validation and usage auditing remain platform infrastructure.

The LLM never diagnoses, prescribes, changes medication, decides risk, or overrides clinicians.
