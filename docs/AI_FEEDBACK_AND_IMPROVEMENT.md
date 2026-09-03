# Governed AI Feedback and Improvement

Executive HealthOps captures human corrections as governance records; it does not learn online and does not deploy models automatically.

## Feedback classes

| Type | Purpose | Dataset eligibility |
|---|---|---|
| `AI_CONTENT_FEEDBACK` | Report extraction, semantic mapping, summaries, grounded answers and citations | Review required; only de-identified records may be accepted |
| `WORKFLOW_FEEDBACK` | The action a health manager selected and whether workflow assistance was useful | Not a medical/risk label; explicit review required |
| `RISK_RULE_FEEDBACK` | False-positive/negative, scope, unit, window or threshold-review concern | Never model-training eligible; creates a Rule Review Candidate |

Doctor conclusions default to ineligible. Outcomes are observational references and never causal labels. Full prompts, reports, names, contact details, local paths and member identifiers are excluded from dataset snapshots.

## Offline lifecycle

```text
Human correction
  → CAPTURED
  → human REVIEWED
  → explicit ACCEPTED_FOR_DATASET
  → immutable de-identified JSONL snapshot
  → versioned prompt/model candidate
  → fixed evaluation suite and active-version comparison
  → human approval
  → explicit activation
```

The evaluation gate covers semantic mapping, citation validity, no-source refusal, hallucination, prompt injection, medical boundaries and separation from deterministic risk. A safety regression blocks approval. The V1 training adapter is deliberately `NOT_CONFIGURED`; no GPU job, fine-tune or deployment is started.

Activation and rollback are explicit, human-operated registry transitions with audit records. They are never triggered by feedback capture or dataset creation.

## Risk separation

`Observation + unit + context + time window + population + approved RiskRule` produces a `RiskEvent`. Human disagreement creates a `RiskRuleReviewCandidate`; it cannot change a threshold, activate a rule, or teach an LLM to assign RED/YELLOW/GREEN. Any future Clinical Rule change remains a separately reviewed, versioned medical-governance action.
