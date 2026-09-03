# Product Direction Correction

Executive HealthOps is an enterprise executive-health operations platform. It is not a new-health-manager training platform.

The previously introduced Training Copilot navigation, case practice, assessment, progress and scoring surfaces have been withdrawn. Historical migration `0021_add_grounded_ai_training` and its tables remain for backward compatibility; current product code does not depend on them.

The reusable foundation remains part of the platform:

- `GroundedAnswerService` and the shared AI answer contract;
- separate Fact Evidence and Knowledge Evidence;
- approved-only knowledge retrieval and no-source refusal;
- citation-marker validation and fabricated-source blocking;
- `KnowledgeUseRecord` and actual used-chunk auditing;
- the shared citation inspector.

Approved internal SOP, communication, service and AI-safety knowledge can support grounded HealthOps workflow questions. It does not create a training product, diagnose, prescribe, determine risk or replace a clinician.
