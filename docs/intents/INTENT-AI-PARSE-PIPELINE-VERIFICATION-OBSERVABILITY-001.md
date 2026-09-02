# INTENT-AI-PARSE-PIPELINE-VERIFICATION-OBSERVABILITY-001

> **Document Type:** Development Intent / Verification & Observability Design  
> **Status:** Sprint 1 closure PASS; Sprint 2 implementation authorized  
> **Implementation:** Sprint 1 complete; Sprint 2 authorized; Sprint 3 not authorized  
> **Scope:** `ai_vendor_invoice` development/admin verification only

## 1. Intent Metadata

| Item | Value |
|---|---|
| Intent ID | INTENT-AI-PARSE-PIPELINE-VERIFICATION-OBSERVABILITY-001 |
| Owner | AI Vendor Invoice development team |
| Audience | Authorized developer, administrator, reviewer |
| Priority | P1 development verification capability |
| Depends on | Existing frozen AI Parse pipeline and ParseAttempt lifecycle |
| Related runtime risk | Queue lock/dead-job risk remains deferred to `FIX-INTENT-AI-QUEUE-RUNTIME-002` |
| Status | Sprint 1 closure PASS; Sprint 2 implementation authorized |

Sprint 1 implementation and human closure were completed on 2026-08-28. Sprint 2 is authorized; Sprint 3 remains unauthorized.

## 2. Background

The frozen pipeline is:

```text
PDF
  → PDF preprocessing
  → ordered PDF pages/images
  → per-page DeepSeek Vision request
  → PageExtractionResult
  → document normalization
  → CanonicalResult
  → MappingResult
  → Apply AI Candidate
  → Statement
  → Human Review
  → human_review_result
  → existing Bill Creator
  → account.move
```

Real asynchronous enqueue, queue consumption, two-job execution overlap, and Attempt terminal convergence have
already been verified. Historical queue lock loss is a known deferred runtime risk and is not reopened here.

## 3. Problem Statement

The current Backend UI can show that an Attempt was queued, started, or failed, but cannot answer the questions
needed for reliable human verification:

- Was the source PDF readable and how many pages did it contain?
- Which rendered image was sent for each page?
- What provider, model, contract, and actual prompt were used?
- Did the HTTP request succeed and what was returned?
- Was the response converted into a PageExtractionResult?
- Which page and pipeline stage failed?
- What inputs produced the document CanonicalResult and MappingResult?
- Did a provider retry occur, and how many real calls were made?

The solution must expose historical facts without changing extraction semantics, business states, or the queue runtime.

## 4. Goals

1. Provide an authorized Odoo Backend Verification UI for a Task and each ParseAttempt.
2. Make the actual pipeline traceable from source PDF through final mapping or failure.
3. Preserve immutable historical provenance for provider, model, prompt, contract, images, calls, and results.
4. Make page ordering and page-image content directly verifiable.
5. Represent provider retries as separate historical calls rather than overwriting one record.
6. Keep raw provider data restricted, company-isolated, and free of API secrets.
7. Persist objective stage facts only; never fabricate percentage progress or “AI thinking” progress.
8. Reuse existing fields, attachments, JSON results, and diagnostics before adding storage.

## 5. Non-Goals

This Intent does not authorize:

- changing PDF preprocessing, page batching, prompts, extraction schemas, normalization, canonical semantics, mapping,
  Statement, Human Review, or Bill Creator;
- adding Task business states or ParseAttempt statuses;
- changing queue channels, workers, dispatch, retry policy, timeout, or queue_job source;
- redesigning the provider API or adding OCR/DeepSeek-OCR;
- creating a customer Portal UI or a prompt editor;
- exposing raw responses or prompts to ordinary business users;
- changing existing raw-response security contracts;
- building a general object-storage or log-search platform;
- reopening the deferred queue lock investigation.

## 6. Frozen Baseline

The following contracts remain unchanged:

```text
Task states:
to_parse, parsing, awaiting_review, bill_generated,
error_split_required, error_ai_unavailable, error_timeout

ParseAttempt statuses:
queued, running, success, failed, superseded
```

`QUEUE_JOB__NO_DELAY` remains unset in real runtime. AI runs remain asynchronous. Bill Creator continues to read only
`task.human_review_result`.

## 7. Current Pipeline

The current implementation has these boundaries:

1. `start_parse()` creates a queued ParseAttempt, snapshots provider model/prompt/contract identifiers, sets Task to
   `parsing`, and enqueues only `job_run_parse()`.
2. `job_run_parse()` calls `run_parse_attempt()`.
3. `prepare_provider_input()` reads the source attachment and renders ordered PNG bytes in memory.
4. The DeepSeek adapter makes one-page calls, validates the response, normalizes page results, and returns a combined
   canonical result plus a base64-encoded raw response payload.
5. Provider diagnostics currently store non-sensitive transport/page metadata on `provider_diagnostics`.
6. Success currently persists `canonical_result`, `mapping_result`, and one private raw-response attachment.
7. Failure currently persists a safe summary and terminal Attempt/Task state.

## 8. Current Implementation Gap Analysis

| Information | Current source | Persisted? | Historical? | Visible in UI? | Gap | Proposed minimal change |
|---|---|---:|---:|---:|---|---|
| Source PDF | `source_pdf_attachment_id` | Yes | Yes | Yes | No page-level verification view | Link from Attempt Overview |
| PDF page count | In-memory `fitz` document | No | No | No | Count disappears after run | Persist Attempt preprocessing summary |
| Rendered page PNGs | `prepare_provider_input()` memory only | No | No | No | Actual sent image cannot be inspected | Restricted page artifact attachments |
| Page ordering | In-memory list order | No | No | No | No durable order evidence | Page artifact sequence |
| Provider/model | Attempt snapshot/provider config | Partly | Model yes; provider indirect | Provider shown | Provider call history absent | Immutable call snapshot |
| Actual prompt | Adapter constants at execution time | No | No | No | Current config could be mistaken for historical prompt | Prompt snapshot per call |
| Contract version | Attempt field | Yes | Yes | Not currently | Not prominent in UI | Show in Overview and call trace |
| Request timing/status | `provider_diagnostics` metadata | Partly | Partly | No | No call entity or attempt/retry grouping | ProviderCall trace records |
| Raw provider response | Private combined attachment | Yes on success | Yes | No | Not linked per page/call; failure may lack response | Private per-ProviderCall attachment |
| PageExtractionResult | Returned/merged in memory | No per page | No | No | Cannot identify page result or schema failure | Persist immutable per-page result |
| Normalization outcome | In-memory adapter result | No explicit stage | No | No | Stage boundary invisible | Derive stage display from persisted results/failure |
| CanonicalResult | `ParseAttempt.canonical_result` | Yes | Yes | Review-oriented only | Verification placement unclear | Read-only diagnostic panel |
| MappingResult | `ParseAttempt.mapping_result` | Yes | Yes | Review-oriented only | Verification placement unclear | Read-only diagnostic panel |
| Failure stage | Exception class/log/summary | Safe summary only | No structured stage | Summary only | Page/stage cannot be determined | Attempt/ProviderCall failure metadata |
| Internal provider retry count | `attempt_internal_retry_count` | Yes | Aggregate only | No | Individual calls overwritten | Separate immutable ProviderCall rows |
| Queue timestamps | Attempt and queue job fields | Yes | Yes | Attempt summary | Runtime details out of scope | Display existing timestamps only |

The gap analysis proves that the existing Attempt-level JSON and combined attachment cannot represent ordered page
artifacts or every real provider call/retry. The MVP therefore freezes exactly two new diagnostic child models:
`PageArtifact` and `ProviderCall`. No third event or PageExtractionResult model is authorized.

## 9. Domain / Ownership Boundaries

The ownership graph is:

```text
Task
└── ParseAttempt (immutable run identity)
    ├── PageArtifact 1:N (one ordered rendered page)
    └── ProviderCall 1:N (one actual provider request/response attempt)
        ├── page_extraction_result JSON (if generated)
        └── raw_response_attachment_id (per call, if received)
```

Every diagnostic record must be owned by exactly one ParseAttempt and indirectly by its Task and Company. A rerun
creates a new ParseAttempt; it never updates or replaces historical artifacts from an earlier Attempt.

Diagnostic data is evidence, not a second candidate or business workflow. Existing canonical and mapping fields remain
the pipeline's result data and are not duplicated into a competing source of truth. `PageArtifact` and `ProviderCall`
are the two frozen MVP diagnostic child entities; neither is a domain aggregate root.

## 10. Observability Data Contract

The implementation proposal should expose immutable, read-only facts with these minimum fields:

### Attempt overview

- attempt ID and sequence;
- status, submitted/started/completed/finished timestamps;
- provider name, model snapshot, prompt version, extraction contract version;
- source PDF attachment and page count;
- generated image count;
- safe error summary and structured failure stage;
- linked queue job and existing queue timestamps.

### Page artifact

- Attempt ID, company ID, page sequence, and source page number;
- MIME type, byte size, checksum;
- restricted attachment reference;
- render status and render timestamp;
- no prompt, response, or secret embedded in the image record.

### Provider call

- Attempt ID, company ID, page sequence, call sequence, retry index;
- provider and model snapshot;
- immutable `effective_prompt_snapshot` containing the actual textual system/user prompt components and checksum;
- page artifact references actually sent;
- request started/ended timestamps;
- HTTP status/category without credentials;
- response received status;
- per-call `raw_response_attachment_id` when a response was received;
- `page_extraction_result` JSON snapshot when generated;
- validation outcome and failure stage;
- safe error summary.

### Derived stage presentation

Pipeline stage is a derived presentation concept based on persisted Attempt, PageArtifact, ProviderCall, and result
facts. The MVP introduces **no standalone `PipelineStageEvent` model** and no event store.

The UI may derive and display the following bounded labels:

```text
PDF_RECEIVED
PDF_SPLIT
PAGE_REQUEST
PAGE_RESPONSE
PAGE_EXTRACTION
DOCUMENT_NORMALIZATION
CANONICAL_READY
MAPPING_READY
FAILED
```

Derived stages are facts about available evidence. They are not Task states, progress percentages, or authorization
to mutate business data.

## 11. Page Artifact Design

The current rendered images exist only in memory. The frozen MVP adds a `PageArtifact` diagnostic child for each
rendered page and one private `ir.attachment` per artifact.

Requirements:

- `image/png` MIME type;
- stable page sequence and checksum;
- `res_model`/`res_id` ownership that enforces Task/Company access;
- immutable after creation;
- not public and not posted to chatter;
- actual bytes passed to the provider, not a later re-render;
- source PDF remains the original input and is not replaced by page artifacts.

Storage must be bounded by retention policy. A complex object store is out of scope.

Frozen MVP fields:

```text
PageArtifact
  parse_attempt_id
  company_id
  page_no
  image_attachment_id
  mime_type
  checksum
  byte_size
  rendered_at
```

## 12. Provider Call Traceability

Each actual HTTP provider call must have one historical `ProviderCall` diagnostic child. A technical retry creates another
ProviderCall with an incremented retry index. The UI must show all calls, including failed calls, rather than
collapsing them into one “page succeeded” row.

The record must reference the exact page artifacts and the immutable provider/model/prompt snapshot used for that
call. Provider response payloads must be stored or linked without API keys, request authorization headers, or full
secret-bearing configuration.

Frozen MVP fields:

```text
ProviderCall
  parse_attempt_id
  company_id
  page_artifact_id
  call_sequence
  retry_index
  provider_snapshot
  model_snapshot
  effective_prompt_snapshot
  request_started_at
  response_received_at
  http_status
  outcome
  raw_response_attachment_id
  page_extraction_result
  validation_status
  failure_stage
  safe_error_summary
```

Existing `provider_diagnostics` may remain as a compact compatibility summary, but it must not be presented as a
complete call history if it omits calls.

## 13. Prompt Snapshot Design

Three concepts must remain visibly distinct:

1. default prompt;
2. current Provider Config prompt;
3. historical actual prompt sent by this Attempt/ProviderCall.

The Verification UI shows only the third when proving a historical run. The frozen field is
`effective_prompt_snapshot`, a structured JSON value containing the effective textual system and user prompt
components, prompt version, and checksum. It does not contain image base64, authorization headers, API keys, or a
full HTTP request dump. Images are proven by `page_artifact_id`.

Prompt snapshots are restricted diagnostic data and must not contain API keys or unrelated provider configuration.

## 14. Raw Response Design

The frozen MVP stores one private `raw_response_attachment_id` on each ProviderCall when a response is received.
The existing Attempt-level combined `raw_response_attachment_id` may remain for compatibility, but it is not the
source of page/call traceability.

Raw response access must:

- require explicit developer/admin or equivalent diagnostic permission;
- enforce company isolation;
- remain private and absent from chatter;
- avoid exposing request headers, API keys, or unrelated secrets;
- distinguish response-not-received from response-received-but-invalid.

Ordinary invoice users should see only safe status and error summary.

## 15. PageExtractionResult Traceability

The existing adapter creates and validates page results in memory before merging them. The frozen MVP persists an
immutable `page_extraction_result` JSON snapshot directly on each ProviderCall.

It must record whether the result was:

```text
GENERATED
NOT_GENERATED
FAILED_VALIDATION
```

The persisted result is diagnostic evidence of the existing extraction contract; it must not change that contract or
become an editable candidate.

## 16. Canonical / Mapping Result Traceability

The existing `canonical_result` and `mapping_result` fields should be reused and displayed read-only in a Document
Result panel. The panel must clearly distinguish:

- generated;
- not generated;
- failed before this stage.

No duplicate result source should be introduced. Statement, Human Review, and Bill Creator remain outside this
verification design.

The MVP adds `observability_status` to ParseAttempt (or an equivalent derived diagnostic value):

```text
complete
partial
unavailable
```

Observability is auxiliary evidence and is never a prerequisite for the business result. A diagnostic persistence
failure MUST NOT convert an otherwise successful ParseAttempt into a business failure. The failure must not be
silently swallowed: it must be recorded as partial/unavailable evidence, logged through the existing safe logging
path, and shown in the Verification UI. This preserves the separation:

```text
BUSINESS PIPELINE RESULT != OBSERVABILITY COMPLETENESS
```

## 17. Failure Stage Design

Persist a diagnostic failure stage independently from Task state and ParseAttempt status:

```text
PDF_PREPROCESS
PAGE_PROVIDER_REQUEST
PAGE_PROVIDER_RESPONSE
PAGE_SCHEMA_VALIDATION
DOCUMENT_NORMALIZATION
CANONICAL_VALIDATION
MAPPING
PERSISTENCE
OTHER
```

The UI displays safe user-facing error text separately from authorized diagnostic detail. Stack traces and raw
exception objects must not be shown to ordinary users. A failure before a stage must be represented as
`NOT_GENERATED`, not as an empty or fabricated result.

The frozen MVP adds `failure_stage` to ParseAttempt for document-level failure and to ProviderCall for page/call
failure. No standalone stage-event entity is introduced.

## 18. Verification UI Design

Extend the existing Task form with an authorized, read-only Verification view. The minimum information architecture:

```text
Task
└── Parse Attempts
    └── Attempt #N
        ├── Overview
        ├── PDF Pages
        ├── Provider Calls / Page Extraction
        ├── Document Result
        └── Failure / Diagnostics
```

### Attempt Overview

Show sequence, lifecycle timestamps, status, provider/model, prompt snapshot reference, contract version, source PDF,
page/image counts, safe error, failure stage, and existing queue timestamps.

### PDF Pages

Show every ordered page with an actual image preview, page number, checksum/size, and render status.

### Provider Calls / Page Extraction

Show page, call/retry sequence, image reference, provider/model, actual prompt snapshot, request/response timestamps,
outcome, raw response link (permission-gated), PageExtractionResult, validation result, and failure reason.

### Document Result

Show page extraction summary, CanonicalResult, and MappingResult, with explicit generated/not-generated markers.

### Failure / Diagnostics

Show stage, safe error summary, authorized diagnostic detail, retry history, and relevant artifact links. Never show
secrets or pretend that missing evidence is success.

## 19. Security & Access Control

| Role | Source PDF | Page images | Prompt | Parsed results | Failure detail | Raw response |
|---|---:|---:|---:|---:|---:|---:|
| AI Invoice User | Existing access | Existing company access | No | Safe/read-only | Safe summary | No |
| Reviewer | Existing review access | Company-scoped read | No by default | Existing review access | Safe/limited | No by default |
| Config Manager / Administrator | Company-scoped read | Yes | Yes | Yes | Yes, sanitized | Yes |

The MVP freezes the existing group mapping:

- `group_ai_invoice_user`: safe status/error only; no Prompt or Raw Response;
- `group_reviewer`: company-scoped page images and parsed business results; no Prompt or Raw Response by default;
- `group_config_manager`: company-scoped Page Images, Effective Prompt, Raw Response, PageExtractionResult, and
  sanitized diagnostics.

PageArtifact and ProviderCall record rules must follow their immutable `company_id` and owning Attempt/Task.
Diagnostic attachments must remain private, link to the owning diagnostic child, and be read only when the caller can
read that child and has the corresponding sensitive-data group. Do not create a broad global sudo endpoint.

## 20. Retention

MVP rule:

```text
retain diagnostic artifacts with the ParseAttempt
```

This preserves evidence for development acceptance and rerun comparison. This Intent does not implement a cleanup
cron, object storage, archival engine, or automatic retention platform. Sprint 3 records actual filestore impact for
multi-page PDFs, PNGs, repeated Attempts, provider calls, and retries. Any future cleanup requires a separate Intent.

## 21. Retry / Re-run Semantics

- A Task rerun creates a new ParseAttempt.
- Attempt N artifacts are never overwritten by Attempt N+1.
- A technical provider retry creates a new ProviderCall under the same Attempt.
- Call sequence and retry index remain visible.
- Current retry limits and behavior are unchanged by this Intent.
- The Verification UI must distinguish queue retry, provider retry, and Task rerun.

## 22. Automated Test Plan

Prefer model/data-contract, ownership, immutability, security, and traceability tests over brittle XML text matching:

1. Attempt owns all diagnostic artifacts and company scope is preserved.
2. Page sequence and image linkage are stable and ordered.
3. ProviderCall links to the exact page artifact.
4. Prompt snapshot is immutable and differs from later Provider Config changes.
5. Raw response linkage is private and permission-gated.
6. Per-page PageExtractionResult persistence is correct.
7. CanonicalResult and MappingResult remain the existing result source.
8. Failure stage is persisted without expanding business states.
9. Provider retries do not overwrite earlier calls.
10. Reruns isolate all evidence from prior Attempts.
11. Cross-company access is denied.
12. No Task state or ParseAttempt status is added.
13. Existing extraction contract and pipeline semantics are unchanged.
14. Existing success, failure, stale-worker, and convergence tests remain valid.

## 23. Human UAT Plan

### UAT-OBS-01 — Multi-page PDF

Upload a multi-page PDF. Verify page count, image count, previews, and page order.

### UAT-OBS-02 — Actual request

Run DeepSeek. For every page, verify the actual image, provider/model, contract, and actual prompt snapshot.

### UAT-OBS-03 — Successful provider response

Verify raw provider response access for an authorized administrator and the corresponding PageExtractionResult.

### UAT-OBS-04 — Complete document result

Verify CanonicalResult and MappingResult are visible and marked generated.

### UAT-OBS-05 — Known extraction failure

Use a fixture that causes extraction failure. Verify the failed page, provider response outcome, raw response (if
received), failure stage, safe error, and explicit absence of a generated PageExtractionResult.

### UAT-OBS-06 — Rerun isolation

Run a rerun and verify Attempt N and N+1 images, prompts, calls, responses, extraction results, and final results do
not overwrite each other.

### UAT-OBS-07 — Provider configuration change

Change Provider Config after an Attempt and reopen the old Attempt. Verify historical provider/model/prompt snapshots
remain unchanged.

## 24. Migration / Existing Data

Existing Attempts retain their current fields and attachments. Historical Attempts cannot display evidence that was
never persisted; the UI must show `NOT_AVAILABLE_FOR_HISTORICAL_ATTEMPT` rather than reconstructing or guessing.

The frozen diagnostic models/fields are additive and nullable. No historical raw response,
prompt, page image, or extraction result should be fabricated.

## 25. Risks

- Per-page PNGs and provider-call responses may materially increase filestore usage.
- Raw response and prompt visibility creates a data-disclosure risk.
- Persisting evidence inside the provider transaction must not reintroduce queue transaction/cursor coupling.
- A diagnostic write failure must not change extraction semantics or turn a successful parse into a different business
  state; it must degrade `observability_status` and emit a sanitized diagnostic warning.
- UI simplification may accidentally hide retries or confuse current config with historical snapshots.
- Adding diagnostic records may require careful company record rules and attachment access controls.

## 26. Explicit Non-Changes

```text
No Prompt change
No Extraction contract change
No Normalizer/Canonical/Mapping semantic change
No Statement/Human Review/Bill Creator change
No Task state expansion
No ParseAttempt status expansion
No queue_job source/channel/capacity/worker/retry change
No timeout or synchronous fallback
No QUEUE_JOB__NO_DELAY
No queue lock investigation in this Intent
```

## 27. Acceptance Gates

```text
OBS-01 PDF_TO_PAGES_VISIBLE
OBS-02 PAGE_IMAGE_PREVIEWABLE
OBS-03 ACTUAL_PROMPT_TRACEABLE
OBS-04 PROVIDER_MODEL_TRACEABLE
OBS-05 RAW_RESPONSE_TRACEABLE
OBS-06 PAGE_EXTRACTION_RESULT_TRACEABLE
OBS-07 FAILURE_STAGE_TRACEABLE
OBS-08 CANONICAL_RESULT_TRACEABLE
OBS-09 MAPPING_RESULT_TRACEABLE
OBS-10 RERUN_HISTORY_ISOLATED
OBS-11 RAW_RESPONSE_ACCESS_RESTRICTED
OBS-12 COMPANY_ISOLATION
OBS-13 NO_BUSINESS_STATE_CHANGE
OBS-14 NO_EXTRACTION_CONTRACT_CHANGE
OBS-15 NO_QUEUE_RUNTIME_CHANGE
OBS-16 OBSERVABILITY_FAILURE_ISOLATED
OBS-17 PROVIDER_RETRY_HISTORY_PRESERVED
OBS-18 REAL_PDF_UAT_PASS
OBS-19 STORAGE_IMPACT_ASSESSED
```

All gates require evidence from automated tests and the applicable UAT. A missing historical artifact must be reported
as unavailable, not inferred.

## 28. Open Questions

1. Confirm the exact attachment record-rule implementation that links access to the owning diagnostic child without
   broad `sudo()`.
2. Confirm whether the existing Attempt-level combined raw response remains populated for compatibility or becomes
   optional after per-call responses are authoritative.
3. Confirm the final UI wording for historical Attempts whose evidence was never captured. The required semantic value
   remains `NOT_AVAILABLE_FOR_HISTORICAL_ATTEMPT`.

## P0/P1 Human Decisions Required

The four reviewed P1 architecture decisions are closed. The remaining Open Questions are implementation details and
must not reopen the frozen ownership, failure semantics, effective prompt boundary, or stage derivation.

## 29. Reviewed P1 Closure

| P1 | Resolution |
|---|---|
| P1-01 Pipeline stage model | Closed. Stage is derived presentation. No `PipelineStageEvent` or event store. |
| P1-02 Diagnostic children | Closed. MVP adds exactly `PageArtifact` and `ProviderCall` as 1:N ParseAttempt children. |
| P1-03 Failure semantics | Closed. Evidence failure marks `observability_status` but never changes an otherwise successful business result. |
| P1-04 Prompt boundary | Closed. `effective_prompt_snapshot` contains actual effective text components only; image bytes remain in PageArtifact. |

## 30. Implementation Sprint Plan

The implementation is strictly divided into three Sprints:

```text
Sprint 1 = Persist the truth.
Sprint 2 = Show the truth.
Sprint 3 = Prove the truth.
```

Do not subdivide these Sprints into Phase A/B/C. Each Sprint follows:

```text
Authorized Sprint
→ Implementation
→ Automated Tests
→ Human Verification
→ Sprint Closure
```

A focused FIX Intent is required only when a concrete defect is identified. A normal implementation bug does not
automatically reopen a broad investigation.

### 30.1 Sprint 1 — Pipeline Evidence Foundation

#### Goal

Make the real pipeline evidence persistent. After Sprint 1, an authorized developer must be able to prove:

- how the PDF was split and what bytes were sent for each page;
- how many real Provider calls occurred;
- the effective text instructions, Provider, and Model used for every call;
- what each call returned and whether PageExtractionResult validation succeeded;
- which page/stage failed;
- that retries and reruns did not overwrite history.

#### Scope

1. Add PageArtifact and ProviderCall diagnostic child models.
2. Add ParseAttempt `failure_stage` and `observability_status`.
3. Persist the ordered PNG bytes actually passed to the Provider.
4. Persist page number, MIME type, checksum, byte size, and render timestamp.
5. Create one ProviderCall for every actual HTTP call, including technical retries.
6. Persist Provider/Model snapshots and the structured `effective_prompt_snapshot`.
7. Persist request/response timestamps, HTTP status/outcome, validation status, failure stage, and safe error.
8. Store one private raw-response attachment per ProviderCall when a response exists.
9. Store immutable `page_extraction_result` JSON directly on ProviderCall when generated.
10. Preserve existing Attempt combined raw response as compatibility data according to the approved implementation
    detail; it is not the per-call source of truth.
11. Enforce company isolation and private attachment access.
12. Isolate evidence-persistence failure from the business pipeline result and mark evidence complete/partial/unavailable.
13. Preserve provider retry history and Task rerun isolation.
14. Provide only the minimum Backend tree/form required to verify that evidence exists.

#### Non-Scope

- complete Verification UI, Owl components, polling, Processing Activity, Prompt Editor, or Portal;
- PipelineStageEvent or PageExtractionResult models;
- queue runtime, retry policy, timeout, channel, or worker changes;
- Prompt, extraction contract, normalization, canonical, mapping, Statement, Review, or Bill Creator changes;
- new Task states or ParseAttempt lifecycle statuses.

#### Models / Fields

```text
ParseAttempt
  failure_stage
  observability_status = complete | partial | unavailable
  page_artifact_ids
  provider_call_ids

PageArtifact
  parse_attempt_id
  company_id
  page_no
  image_attachment_id
  mime_type
  checksum
  byte_size
  rendered_at

ProviderCall
  parse_attempt_id
  company_id
  page_artifact_id
  call_sequence
  retry_index
  provider_snapshot
  model_snapshot
  effective_prompt_snapshot
  request_started_at
  response_received_at
  http_status
  outcome
  raw_response_attachment_id
  page_extraction_result
  validation_status
  failure_stage
  safe_error_summary
```

All diagnostic records and snapshots are read-only after creation/finalization and are not aggregate roots.

#### Touched Components

- ParseAttempt model and model registration;
- new PageArtifact and ProviderCall model files;
- PDF preprocessing/provider-input boundary;
- DeepSeek per-page request/retry boundary;
- parse orchestration and observability error isolation;
- security groups, ACLs, record rules, and diagnostic attachment ownership;
- minimum diagnostic Backend views;
- model/service/security tests.

Queue job source and Odoo configuration are excluded.

#### Automated Tests

```text
S1-TEST-01 PAGE_ARTIFACT_ORDER
S1-TEST-02 ACTUAL_IMAGE_BYTES_PERSISTED
S1-TEST-03 PROVIDER_CALL_CREATED_PER_REAL_CALL
S1-TEST-04 PROVIDER_RETRY_HISTORY_NOT_OVERWRITTEN
S1-TEST-05 EFFECTIVE_PROMPT_SNAPSHOT_IMMUTABLE
S1-TEST-06 RAW_RESPONSE_LINKED_TO_CALL
S1-TEST-07 PAGE_EXTRACTION_RESULT_PERSISTED
S1-TEST-08 FAILURE_STAGE_PERSISTED
S1-TEST-09 RERUN_ATTEMPT_ISOLATION
S1-TEST-10 COMPANY_ISOLATION
S1-TEST-11 ATTACHMENT_ACCESS_RESTRICTED
S1-TEST-12 OBSERVABILITY_FAILURE_DOES_NOT_CHANGE_BUSINESS_RESULT
S1-TEST-13 NO_EXTRACTION_SEMANTIC_CHANGE
S1-TEST-14 EXISTING_STATE_CONVERGENCE_REGRESSION_PASS
```

#### Human Verification

Use at least one real multi-page PDF and the minimum diagnostic Backend form. Verify:

```text
PDF_PAGE_COUNT = PASS
PAGE_IMAGE_COUNT = PASS
PAGE_ORDER = PASS
PAGE_IMAGES_MATCH_SOURCE = PASS
PROVIDER_CALL_COUNT = PASS
ACTUAL_PROVIDER = PASS
ACTUAL_MODEL = PASS
ACTUAL_PROMPT_CAPTURED = PASS
RAW_RESPONSE_CAPTURED = PASS
PAGE_EXTRACTION_RESULT_CAPTURED = PASS
```

Human verification must not depend entirely on SQL.

#### Exit Gates

```text
EVIDENCE_PERSISTENCE = PASS
HISTORICAL_IMMUTABILITY = PASS
SECURITY = PASS
RERUN_ISOLATION = PASS
EXTRACTION_REGRESSION = PASS
STATE_CONVERGENCE_REGRESSION = PASS
HUMAN_REAL_PDF_VERIFICATION = PASS
```

All Sprint 1 exit gates have passed; Sprint 2 implementation is authorized.

#### Dependencies

- frozen pipeline and state-convergence behavior;
- existing private attachment mechanism and security groups;
- approved field/model contract in this Intent;
- real multi-page PDF available for authorized UAT.

#### Risks

- diagnostic writes accidentally becoming business-critical;
- image/response attachment leakage;
- snapshots being taken before the actual request is finalized;
- per-call records changing provider retry behavior;
- storage growth and transaction contention.

### 30.2 Sprint 2 — Verification UI

#### Goal

Make persisted evidence directly human-verifiable in the authorized Odoo Backend without SQL, server logs, or source
tracing. Sprint 2 consumes the frozen Sprint 1 contract and does not redesign it.

#### Scope

Provide a read-only ParseAttempt Verification UI:

```text
Attempt
├── Overview
├── PDF Pages
├── Provider Calls / Page Extraction
├── Document Result
└── Failure / Diagnostics
```

- **Overview:** sequence, status, lifecycle timestamps, Provider, Model, contract, source PDF, page/image counts,
  observability status, safe error, and failure stage.
- **PDF Pages:** true page order, actual image preview, page number, checksum/size, and explicit missing evidence.
- **Provider Calls:** page/call/retry sequence, image, Provider/Model, Effective Prompt, request/response timestamps,
  outcome, permission-gated Raw Response, PageExtractionResult, validation, failure stage, and safe error.
- **Document Result:** reuse and read-only display existing CanonicalResult and MappingResult.
- **Failure/Diagnostics:** failed page/call/stage, safe error, authorized sanitized detail, and evidence availability.
- Derive stage labels exclusively from persisted facts.
- Enforce the frozen role matrix in view visibility and server-side access.

The UI must distinguish:

```text
GENERATED
NOT_GENERATED
FAILED_BEFORE_STAGE
NOT_AVAILABLE_FOR_HISTORICAL_ATTEMPT
```

#### Non-Scope

- changes to evidence models/contracts established in Sprint 1;
- editable diagnostic data;
- final Prompt Editor, Restore Default, Processing Activity, polling, or customer Portal;
- fake percentage/thinking progress;
- queue runtime or pipeline semantic changes.

#### Models / Fields

No new business model or state. Use:

- ParseAttempt lifecycle/result/observability fields;
- PageArtifact and ProviderCall;
- existing source PDF, CanonicalResult, MappingResult, and compatibility raw response;
- optional non-stored/read-only presentation fields only when necessary to derive UI labels.

#### Touched Components

- Task and ParseAttempt Backend actions/forms;
- PageArtifact and ProviderCall read-only views;
- security-driven field/view visibility;
- private attachment preview/download actions;
- minimal client code only where standard Odoo widgets cannot safely preview structured evidence;
- UI/security tests.

#### Automated Tests

```text
S2-TEST-01 PAGE_ORDER_UI_SOURCE
S2-TEST-02 HISTORICAL_ATTEMPT_DISPLAY
S2-TEST-03 CURRENT_CONFIG_DOES_NOT_REPLACE_HISTORICAL_PROMPT
S2-TEST-04 RAW_RESPONSE_PERMISSION
S2-TEST-05 PROMPT_PERMISSION
S2-TEST-06 CROSS_COMPANY_DENIED
S2-TEST-07 MISSING_EVIDENCE_EXPLICIT
S2-TEST-08 CANONICAL_MAPPING_REUSE_EXISTING_FIELDS
S2-TEST-09 NO_EDITABLE_DIAGNOSTIC_SOURCE
S2-TEST-10 NO_BUSINESS_STATE_CHANGE
```

Avoid brittle exact XML-text assertions. Test data sources, permissions, ownership, and read-only behavior.

#### Human Verification

From the browser, an authorized administrator must:

1. open one ParseAttempt;
2. open its source PDF and every actual page image;
3. verify page order;
4. inspect each ProviderCall and retry;
5. inspect Effective Prompt and per-call Raw Response;
6. inspect PageExtractionResult, CanonicalResult, and MappingResult;
7. identify a failed page/stage;
8. inspect an old Attempt without current configuration replacing historical evidence;
9. complete the verification without SQL/server logs/source tracing.

Repeat permission checks as AI Invoice User, Reviewer, and Config Manager.

#### Exit Gates

```text
HUMAN_PIPELINE_TRACEABLE = PASS
PDF_TO_PAGE_VISIBLE = PASS
ACTUAL_PROVIDER_INPUT_VISIBLE = PASS
ACTUAL_PROVIDER_OUTPUT_VISIBLE = PASS
PAGE_RESULT_VISIBLE = PASS
DOCUMENT_RESULT_VISIBLE = PASS
FAILURE_STAGE_VISIBLE = PASS
SECURITY_UI = PASS
```

Sprint 3 cannot start until every Sprint 2 gate passes.

#### Dependencies

- Sprint 1 closed;
- evidence records available for success, failure, retry, rerun, and partial observability;
- final attachment ACL implementation validated.

#### Risks

- view visibility mistaken for server-side security;
- image/raw-response preview bypassing record rules;
- historical missing evidence displayed as empty success;
- current Provider Config accidentally presented as historical provenance;
- UI creating an editable second source of truth.

### 30.3 Sprint 3 — Integration & UAT Closure

#### Goal

Test, harden, and close this Intent by proving Observability across the real frozen pipeline. Sprint 3 is not a new
feature Sprint.

#### Scope

- run targeted and complete relevant automated regressions;
- perform integration and security testing;
- execute real PDF UAT for single-page/multi-page success and failure;
- verify provider HTTP failure, schema failure, page failure, retry, rerun, changed Provider Config, cross-company
  access, Raw Response/Prompt permissions, partial observability, and historical Attempts without evidence;
- verify CanonicalResult/MappingResult display and existing extraction/state-convergence regressions;
- measure storage impact;
- produce a closure report for all OBS gates.

#### Non-Scope

- new diagnostic or UX features;
- cleanup cron, object storage, archival engine, or automatic retention;
- Extraction, Statement, Human Review, Bill Creator, or queue runtime changes;
- resolving unrelated defects without a focused FIX Intent.

#### Models / Fields

No planned new models or fields. Sprint 3 validates and, only for confirmed defects, hardens the approved Sprint 1/2
implementation without expanding the contract.

#### Touched Components

- automated test fixtures and integration/security tests;
- UAT evidence and closure documentation;
- approved Sprint 1/2 files only when a concrete defect is fixed within scope;
- no queue_job source or Odoo configuration.

#### Automated Tests

Run the smallest existing targeted suites covering:

- PageArtifact/ProviderCall lifecycle and immutability;
- provider success/failure/retry;
- rerun and historical provenance;
- attachment and Prompt/Raw Response permissions;
- company isolation;
- partial/unavailable observability;
- existing extraction, success/failure, stale-worker, and state-convergence behavior.

Escalate to the relevant full module suite only after targeted tests pass.

#### Human Verification

Use authorized real supplier PDFs covering:

```text
single-page
multi-page
successful extraction
failed extraction
```

The Backend UI must directly answer:

- how many pages were rendered and what each page image contains;
- what image, Provider, Model, and Effective Prompt each call used;
- whether the Provider responded, what it returned, and its HTTP outcome;
- which PageExtractionResult was generated and where/why a page failed;
- what CanonicalResult and MappingResult were produced.

The UAT must not require SQL or server logs to determine pipeline results.

#### Storage Assessment

Measure and report:

```text
average PDF pages
average rendered PNG size
average ProviderCall raw response size
estimated storage per Attempt
estimated storage under repeated reruns
MVP_STORAGE_ACCEPTABLE = YES/NO
```

If storage is unacceptable, propose a future retention Intent; do not add cleanup in Sprint 3.

#### Exit Gates

Close all gates `OBS-01` through `OBS-19`, including:

```text
OBS-16 OBSERVABILITY_FAILURE_ISOLATED
OBS-17 PROVIDER_RETRY_HISTORY_PRESERVED
OBS-18 REAL_PDF_UAT_PASS
OBS-19 STORAGE_IMPACT_ASSESSED
```

The closure report must include automated-test results, role/security evidence, real-PDF UAT evidence, storage
measurements, known limitations, and deferred enhancements.

#### Dependencies

- Sprint 1 and Sprint 2 closed;
- stable test/UAT environment;
- authorized representative PDFs;
- users for all three permission roles.

#### Risks

- production-like PDF evidence containing sensitive data;
- provider variability affecting repeatability;
- unrelated historical test failures obscuring regression results;
- Sprint 3 expanding into storage architecture or final AI Parse UX.

## 31. Boundary with Subsequent AI Parse UX

After this Intent closes, a separate AI Parse UX scope may implement Prompt Editing, Restore Default, Processing
Activity, Waiting/Running presentation, Owl polling, and final user-facing parsing experience.

This Intent provides persisted facts for those features but does not implement them. Any future display such as
`Processing page 2 / 5` must derive from real persisted evidence and must never claim fabricated AI reasoning progress.

## Final Status

```text
ARCHITECTURE_ALIGNMENT = PASS
SCOPE_CONTROL = PASS
OBSERVABILITY_DIRECTION = PASS
SECURITY_DIRECTION = PASS
P0 = 0
P1 = 0

INTENT_STATUS = SPRINT_1_CLOSED_SPRINT_2_IMPLEMENTED
SPRINT_1_IMPLEMENTATION_AUTHORIZED = YES
SPRINT_2_IMPLEMENTATION_AUTHORIZED = YES
SPRINT_3_IMPLEMENTATION_AUTHORIZED = NO
PRODUCTION_CODE_CHANGED = YES
DATABASE_CHANGED = YES
CONFIG_CHANGED = NO
```
