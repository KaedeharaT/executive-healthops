# Unified Health Data Gateway V0.3

All included payloads and files are **SYNTHETIC DEMO DATA**, never real health data.

## Data flow

```text
Provider / CSV / Excel / JSON / PDF
→ Adapter
→ Member matching
→ RawIngestionRecord + immutable RawData
→ Canonical code + unit normalization + data quality
→ deduplication
→ Observation
→ existing Signals, HealthOps, Program reviews and outcomes
```

External sources cannot create a diagnosis, prescription, medical conclusion,
or HealthProgram decision. They only supply provenance-preserving data.

## Canonical model and quality

The registry centrally maps aliases such as `SYS`, `收缩压`, and `高压` to
`systolic_bp`. It currently covers blood pressure, glucose, body measures,
sleep, activity, selected metabolic/liver values, and explicit unit conversion
for glucose, weight, height, and temperature.

`valid` records may enter signals. `suspect`, `invalid`, `duplicate`, and
`manually_corrected` are traceable data-quality outcomes. A correction creates
a new standardized observation and audit row; it never overwrites `RawData`.

## Provider adapter contract

Each adapter implements `parse(payload, mapping)` and emits provider-neutral
records with a source record id, metric, value, unit, observed time, raw
payload, and optional device id. `IngestionService` owns matching,
normalization, deduplication, persistence, and job status.

## Adding a new device (example: Omron)

1. Add an adapter that only maps its payload into `IncomingRecord`.
2. Register it in `PROVIDERS`.
3. Use the central canonical-code and unit registry; do not duplicate aliases.
4. Create an `ExternalIdentity` mapping for the provider's member id.
5. Add adapter, conversion, quality, idempotency, and API tests.
6. Do not modify Alert, Program, DoctorReview, or other HealthOps logic.

The canonical model can later map to FHIR resources such as Observation,
Medication, DocumentReference and Patient/Member; V0.3 is not a FHIR server.

## Retention and security

Raw and standardized layers are intentionally separate. Production policy will
need consent, retention, deletion, export, authentication, and signed-webhook
controls. V0.3 includes only structural placeholders and no real credentials.
