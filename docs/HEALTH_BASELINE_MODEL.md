# Health Baseline Model

## Definition

A Health Baseline is the human-confirmed reference state at the start of one annual management cycle. It is a point-in-time snapshot, not a live profile, AI narrative, risk result, or collection of every raw reading.

The product flow is:

`confirmed sources → baseline draft → manager fact review → doctor review when medical judgment is required → confirmed frozen snapshot`

## Baseline and current profile

- **Annual baseline:** keeps the confirmed starting value for later monthly, quarterly, and annual comparison.
- **Current health profile:** projects the latest confirmed observations and records. New data updates this projection, never the confirmed baseline.
- **Risk:** remains a separate deterministic-rule result and is not stored as a baseline fact.

## Annual cycle and versions

Each product baseline records its cycle year, cycle dates, optional annual-account link, collection window, and version. Multiple initial reports inside the open collection window merge into one idempotent draft.

A confirmed snapshot is frozen. A factual error creates a new `AMENDED` version linked to the superseded version, with reason, actor, time, and evidence. A later health change belongs to the current profile, comparison, outcome, and timeline—not an amendment.

The next annual cycle starts with a new draft. Stable historical context may be carried forward as `PENDING_RECONFIRMATION`; it is never silently promoted to a confirmed baseline.

## Evidence and confirmation

Baseline items retain references to report candidates, observations, health problems, medications, procedures, or recorded manual intake. Continuous data is stored only as a bounded 30-day summary with window, coverage, sample count, and freshness.

The UI presents provenance in this operational order without inventing a confidence score: formal medical report, doctor-confirmed record, human-confirmed health record, device summary, then member-reported intake. Source type, confirmer, confirmation time, and evidence reference remain explicit.

Missing data is shown as missing or insufficient; it is never interpreted as normal. Medical conclusions require doctor review. AI and system actors may organize a draft but cannot confirm it.

## Comparisons

- `BASELINE_TO_CURRENT`: annual starting point versus the current confirmed profile.
- `REPORT_TO_REPORT`: one confirmed report versus another comparable report.

Both comparisons describe observed differences. They do not infer diagnosis, causality, improvement, or deterioration without separately governed semantics.

## Visualization

- **Health overview:** groups confirmed baseline facts by health domain. Blue means that a reference point exists, amber is used only when the source report explicitly marks an item for attention, and gray means that data is missing or insufficient. These domain labels are not Risk Engine results.
- **Reference range:** a bullet-style indicator is drawn only when the confirmed report candidate contains an explicit numeric interval or threshold. Without that source field, the UI shows the value, unit, and evidence without inventing a normal range.
- **Baseline trend:** each chart uses one metric and unit (blood pressure may pair systolic and diastolic values in mmHg). The annual-baseline point is labeled, and only later valid observations form the follow-up line. A single point produces an empty state, not a synthetic curve.
- **Coverage:** shows which source groups are covered, partial, stale, missing, or awaiting completion. The interface explicitly states that this is data completeness rather than a health score.
- **Comparison:** presents annual baseline and latest comparable observation side by side. It reports recorded change or missing follow-up without automatically claiming medical improvement or deterioration.
- **Amendment:** charts use the current effective amended baseline while the UI retains the correction reason, confirmer, date, and evidence in a collapsed history.

All visualization objects are read-only projections. They cannot update the baseline, current profile, Risk Engine, or source records.

### Visualization data wiring

`ReportExtractionCandidate (CONFIRMED) → Observation (valid) → Baseline draft → human confirmation → frozen key_metrics → BaselineMetricView → chart`

Later valid observations are matched through the shared canonical terminology registry, not UI string matching. A trend requires the same canonical metric and a compatible unit; only explicit, supported conversions are applied. The latest comparable observation becomes the current value while the original baseline value remains frozen. Report reference metadata and evidence continue to point to the confirmed source candidate.

The isolated Portfolio Demo carries a versioned synthetic fixture with six traceable baseline metrics and later observations. Its launcher checks the fixture contract and rebuilds only the disposable demo database when that data version is stale. Empty non-demo members continue to receive honest compact empty states.
