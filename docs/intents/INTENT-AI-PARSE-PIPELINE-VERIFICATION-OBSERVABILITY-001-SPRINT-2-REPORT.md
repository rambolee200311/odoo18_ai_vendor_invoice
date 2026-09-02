# INTENT-AI-PARSE-PIPELINE-VERIFICATION-OBSERVABILITY-001
## Sprint 2 — Verification UI Implementation Report

**Status:** IMPLEMENTATION COMPLETE — HUMAN VERIFICATION PENDING  
**Sprint 1 closure:** PASS  
**Sprint 3:** NOT AUTHORIZED

## Implemented UI

The existing read-only ParseAttempt Backend form now presents persisted evidence as
human-verifiable facts:

- Attempt overview with lifecycle, provider/model, contract and prompt versions,
  source PDF, observability status, and derived evidence status.
- PDF Pages tab with ordered page number, checksum, byte size, render time, preview
  status, and the actual private image preview.
- Provider Calls tab with call/retry sequence, page, provider/model, request and
  response timestamps, HTTP outcome, validation status, failure stage, and derived
  PageExtraction status.
- Restricted effective prompt snapshot and per-call raw response attachment.
- Per-call PageExtractionResult when it was actually generated.
- Document Result tab with CanonicalResult and MappingResult plus explicit derived
  availability status.
- Failure page, provider call, failure stage, and safe explanation on the Attempt
  overview.

The UI does not infer progress or fabricate missing records. For example, the real
Task 1689 / Attempt 1156 failure displays the Page 1 schema-validation failure,
`NOT_GENERATED` PageExtractionResult, and no ProviderCall for pages 2–5.

## Security

- Evidence tabs remain restricted to Reviewer and Config Manager roles.
- Effective prompt and raw response remain restricted to Config Manager.
- Existing company record rules and private attachment access are unchanged.
- All views are read-only (`create="0"`, `edit="0"`, `delete="0"`).

## Changed Files

- `addons/ai_vendor_invoice/models/import_parse_attempt.py`
- `addons/ai_vendor_invoice/models/page_artifact.py`
- `addons/ai_vendor_invoice/models/provider_call.py`
- `addons/ai_vendor_invoice/views/diagnostic_views.xml`
- `addons/ai_vendor_invoice/tests/test_observability.py`
- Sprint 1 and master observability reports/status documentation.

No extraction contract, prompt semantics, provider adapter behavior, canonical/mapping
semantics, queue runtime, retry policy, timeout policy, or business state was changed.

## Automated Validation

```text
Python compile                         PASS
XML structure                          PASS
Repository verification                19 pass, 0 fail
Targeted Odoo model tests              PASS (exit code 0)
git diff --check                       PASS
```

The new automated coverage verifies derived statuses, page failure location, and
that missing PageExtractionResult remains represented as a failed-before-stage fact.

The complete module test invocation still reports the repository's pre-existing
`wd_tlms`/`worlddepot` dependency notices and unrelated historical test failures
(2 failures, 2 errors out of 111). No Sprint 2 test failure was reported by the
targeted run.

## Human Verification Steps

1. Sign in as a Reviewer and open AI Vendor Invoice Imports.
2. Open Task 1689 and Attempt 1156.
3. Confirm the overview shows five PDF artifacts, partial evidence, failed status,
   `PAGE_SCHEMA_VALIDATION`, and failure page 1.
4. Open PDF Pages and inspect pages 1–5 in order; compare each preview with the
   source PDF.
5. Open Provider Calls and confirm exactly one call for page 1, its provider/model,
   response-invalid outcome, validation failure, and `FAILED_BEFORE_STAGE` status.
6. As Config Manager, inspect the effective prompt snapshot and raw response
   attachment; confirm no credentials or base64 image is shown in the prompt.
7. Confirm PageExtractionResult is explicitly absent/not generated and that
   CanonicalResult/MappingResult show their persisted availability status.
8. Confirm pages 2–5 have no fabricated ProviderCall rows.

## Known Issues

The real sample's `PAGE_SCHEMA_VALIDATION` failure is an independent extraction
compatibility issue. Sprint 2 intentionally does not modify the extraction contract,
prompt, adapter semantics, or schema to change that result.

## Gate Status

```text
SPRINT_1_CLOSURE = PASS
SPRINT_2_IMPLEMENTATION = COMPLETE
SPRINT_2_HUMAN_VERIFICATION = PENDING
SPRINT_2_GATE = READY_FOR_HUMAN_VERIFICATION
SPRINT_3_AUTHORIZED = NO
```
