# INTENT-AI-PARSE-PIPELINE-VERIFICATION-OBSERVABILITY-001
## Sprint 1 — Pipeline Evidence Foundation Report

**Date:** 2026-08-28  
**Status:** IMPLEMENTED — CLOSURE PASS  
**Next Sprint authorized:** Sprint 2 Verification UI

## Implemented

- Added ParseAttempt diagnostic children:
  - `vendor.invoice.import.page.artifact`
  - `vendor.invoice.import.provider.call`
- Added ParseAttempt `failure_stage` and `observability_status`.
- Persisted ordered PNG bytes actually supplied to DeepSeek, including page number, MIME type, SHA-256 checksum,
  byte size, render timestamp, private attachment, and company ownership.
- Persisted one ProviderCall for every actual provider request/retry, including Provider/Model snapshots,
  `effective_prompt_snapshot`, timestamps, HTTP outcome, per-call private raw response, PageExtractionResult,
  validation status, failure stage, and safe error.
- Preserved ProviderCall history across technical retries and ParseAttempt history across reruns.
- Kept Pipeline Stage as derived presentation; no PipelineStageEvent or PageExtractionResult model was added.
- Isolated diagnostic persistence failures from the business parse result.
- Moved PageArtifact/ProviderCall writes to short independent diagnostic transactions so queue transaction rollback or
  dead-job recovery does not erase already captured facts.
- Added company rules, read-only ACLs, sensitive field groups, and attachment `res_field` protection.
- Added a minimal read-only Backend Attempt form for development verification.

## Automated Validation

Final affected suite:

```text
TestPageArtifactEvidence
TestProviderCallEvidence
TestObservabilityFailureIsolation
TestObservabilitySecurity
TestDurableEvidenceTransaction
TestClosureStaleWorker
TestParseLifecycleConvergence
TestClosurePipeline

16 tests passed
```

The suite includes production-branch validation proving that PageArtifact, ProviderCall, and per-call raw response
remain committed after the caller queue transaction is explicitly rolled back. It also verifies that a duplicate
worker cannot overwrite a terminal Attempt as `superseded`.

An earlier combined run including `TestParseAttemptModel` completed with:

```text
24 tests
0 failures
0 errors
```

Repository verification:

```text
19 pass
0 fail
```

The separate historical `TestFixIntentAdapter` group still has its pre-existing missing `Mock` import and Prompt
case-sensitive assertion failure. Neither failure was introduced or changed by Sprint 1.

## Real Five-Page UAT

Task:

```text
Task ID = 1689
Attempt ID = 1156
Attempt Sequence = 4
Source PDF = bring_26022366.pdf
PDF Pages = 5
```

Terminal result:

```text
Attempt = failed
Observability = partial
ProviderCall outcome = response_invalid
ProviderCall validation = fail
ProviderCall failure_stage = PAGE_SCHEMA_VALIDATION
Raw response persisted = YES
PageExtractionResult generated = NO
```

Persisted page evidence:

```text
PAGE_ARTIFACT_COUNT = 5
PAGE_IMAGE_COUNT = 5
PAGE_ORDER = 1..5
TOTAL_PNG_BYTES = 923721
PAGE_PREVIEW_OPENED_IN_BACKEND = YES
PAGE_IMAGES_MATCH_SOURCE = PASS
HUMAN_PAGE_ARTIFACT_VERIFICATION = PASS
```

Persisted ProviderCall evidence:

```text
PROVIDER_CALL_COUNT = 1
ACTUAL_PROVIDER = deepseek API
ACTUAL_MODEL = deepseek-v4-flash-vision-exp
EFFECTIVE_PROMPT_SNAPSHOT = PERSISTED
PER_CALL_RAW_RESPONSE = PERSISTED
PAGE_SCHEMA_VALIDATION = FAIL
PAGE_EXTRACTION_RESULT = NOT_GENERATED
```

The failure occurred on the first page, so pages 2–5 correctly have no fabricated ProviderCall or extraction result.

## UAT Finding and Correction

The ProviderCall correctly persisted `PAGE_SCHEMA_VALIDATION`, but the Attempt initially stored `OTHER` because the
current queue transaction could not see a ProviderCall committed by the independent diagnostic transaction. The code
was corrected to propagate sanitized `failure_stage` metadata directly on the raised exception instead of querying
an invisible transaction snapshot. The affected automated tests pass. Per the one-task UAT authorization, no second
real AI task was started to revalidate this correction.

## Sprint 1 Gates

```text
EVIDENCE_PERSISTENCE = PASS
HISTORICAL_IMMUTABILITY = PASS
SECURITY = PASS
RERUN_ISOLATION = PASS
EXTRACTION_REGRESSION = PASS
STATE_CONVERGENCE_REGRESSION = PASS
HUMAN_REAL_PDF_VERIFICATION = PASS
```

The real Provider response failed PageExtractionResult schema validation. This is an extraction compatibility fact,
not an observability closure blocker: raw response and validation failure were persisted truthfully, and no
PageExtractionResult was fabricated for later pages.

## Final Status

```text
SPRINT_1_IMPLEMENTATION = COMPLETE
SPRINT_1_CLOSURE = PASS
SPRINT_2_IMPLEMENTATION_AUTHORIZED = YES
SPRINT_3_AUTHORIZED = NO

PDF_PAGE_COUNT = PASS
PAGE_IMAGE_COUNT = PASS
PAGE_ORDER = PASS
PAGE_IMAGES_MATCH_SOURCE = PASS

PROVIDER_CALL_COUNT = PASS
ACTUAL_PROVIDER = PASS
ACTUAL_MODEL = PASS
ACTUAL_PROMPT_CAPTURED = PASS
RAW_RESPONSE_CAPTURED = PASS
PAGE_EXTRACTION_RESULT_CAPTURED = NOT_GENERATED_EXPECTED
PAGE_SCHEMA_VALIDATION_FAILURE_CAPTURED = PASS

PRODUCTION_CODE_CHANGED = YES
QUEUE_JOB_SOURCE_CHANGED = NO
CONFIG_CHANGED = NO
DATABASE_ROWS_MANUALLY_REPAIRED = NO
```

All five PageArtifacts were opened and manually compared with the source PDF. The schema validation failure remains
an independent extraction defect and is not changed by this observability closure.
