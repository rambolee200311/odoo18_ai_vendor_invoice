# Sprint Implementation Log

## 2026-08-21 - Intent-1 Foundation

### Scope

- Completed the foundation models for vendor invoice import tasks, parse attempts,
  audit logs, provider configuration, mapping configuration, confidence
  thresholds, system configuration, and row-lock utilities.
- Added model access groups, ACLs, record rules, cron data, JSON schemas, and
  model-layer tests.
- Preserved the frozen contract:
  - `queue_job` remains a manifest dependency.
  - `account_invoice_import` is not a runtime dependency.
  - `company_id` is immutable after task creation.
  - `(task_id, sequence)` is unique for parse attempts.

### Compatibility corrections found during installation

- Corrected security XML IDs from the stale `wd_ai_vendor_invoice.*` namespace
  to the actual module namespace `ai_vendor_invoice.*`.
- Removed the obsolete Odoo 17 cron fields `numbercall` and `doall`; they are
  not valid fields on Odoo 18 `ir.cron`.

## 2026-08-21 - Intent-2 AI + Review

### Scope

- Implemented `BaseAIProviderAdapter`, DeepSeek and Claude adapters.
- Added temporary/permanent provider exceptions and bounded provider retries.
- Persisted raw provider responses as private `ir.attachment` records.
- Implemented parse orchestration and worker execution:
  - `queued -> running -> success / failed / superseded`
  - stale-worker guards before and after external AI work
  - company context restoration with `task.with_company(task.company_id)`
  - no database commit inside the worker
- Implemented mapping candidate recommendations for suppliers, products, taxes,
  and currencies without modifying mapping master data.
- Added AI rerun action, parse enqueue model entry point, review persistence,
  and audit logging.
- Added task list/form views and an Owl review dialog. The review UI does not
  create bills.

### Verification

Command used:

```text
venv/bin/python3 odoo-bin -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,<worktree>/addons \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init
```

Result:

```text
34 tests, 0 failures, 0 errors
```

The duplicate-key message emitted by the parse-attempt uniqueness test is
expected: the test deliberately attempts a duplicate `(task_id, sequence)` and
asserts that PostgreSQL rejects it.

### Environment notes

- OCA `queue_job` was made available from the Odoo 18 branch under
  `addons/queue`; the addons path must point to that repository root.
- `jsonschema` was installed into the active Odoo virtual environment because
  the existing model tests import it.
- Existing unrelated database warnings for `wd_tlms` and `worlddepot` remain;
  they do not affect this module's targeted test result.

## 2026-08-21 - Intent-3 Bill Closure

### Scope

- Added `validation_service` for human-review integrity and amount-balance
  checks.
- Added `bill_creator` with the required preconditions, task/attempt row
  locking, explicit task-company context, explicit `account.move.create()`,
  independent source-PDF attachment copying, idempotency guard, and audit log.
- Added the atomic model entry point
  `action_confirm_review_and_create_bill`, which saves the review and creates
  the draft bill in one transaction.
- Added timeout inspection using `enter_parsing_datetime` for tasks in the
  parsing business state, covering queued and running attempts.
  `last_activity_at` is not used for timeout decisions.
- Added Intent-3 validation, idempotency, timeout, permission, rollback, and
  bill-creation test coverage.

### Verification

Command used:

```text
venv/bin/python3 odoo-bin -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,<worktree>/addons \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init
```

Result:

```text
Intent-1 through Intent-3 tests: 0 failures, 0 errors
```

The duplicate-key message from the parse-attempt uniqueness test is expected
and is caught by that test. Existing unrelated `wd_tlms` and `worlddepot`
module warnings remain in the database.

### Contract boundary

- No `cr.commit()` was added to queue workers.
- The stale-worker guard and provider-secret handling remain unchanged.
- `task.company_id` remains immutable.
- Intent-3 does not add or change the frozen state collections.

## 2026-08-21 - FIX-INTENT-AI-VENDOR-001

### Scope

- Preserved `human_review_result` during AI reruns while resetting only the
  current `human_reviewed` flag.
- A-002 was paused after rechecking the final TDD: timeout is defined by the
  task parsing window and queued/running state, without a retry-count gate.
- Added canonical result normalization and JSON Schema validation in the
  provider adapter boundary.
- Added the in-memory PDF preprocessor and `ProviderInput` pages contract;
  adapters now consume ordered PNG page images rather than Odoo attachments.
- Added distinguishable invalid, empty, encrypted, and render-failure PDF
  preprocessing errors without adding task states.
- Replaced the review JSON-only display with structured editable header/line
  fields, candidate application for untouched fields, and confidence classes
  driven by threshold configuration.
- Recomputed `review_warnings` when an independent review save is performed.

### Verification

```text
Python/XML validation: PASS
Owl JS syntax: PASS
Odoo module tests: 53 tests, 0 failures, 0 errors
```

## 2026-08-21 - TEST-INTENT-AI-VENDOR-002

### Scope

- Added formal tests for concurrent bill creation, stale-worker protection,
  multi-company behavior, ACL/record-rule coverage, provider secret exposure,
  adapter retry/error behavior, the PDF-to-ProviderInput pipeline, and PDF
  preprocessing failures.
- No business implementation, frozen baseline document, or `verify.py` was
  modified.

### Verification

- The normal module suite executed 62 tests.
- The Config Manager `api_key` RPC visibility assertion failed, exposing an
  implementation/security defect; it was not fixed in this Test Intent.
- The multi-company test was skipped because the selected task company has no
  purchase journal in the configured database.
- The dedicated real multi-transaction concurrency test executed separately
  but could not start its first transaction within the test timeout; this is
  recorded as a test-environment/concurrency-runner blocker.
- Existing unrelated `wd_tlms` and `worlddepot` module warnings remain.

The separate Closure findings for concurrency, multi-company, secret,
verification-script, and documentation-drift work remain outside this Fix
Intent. A-002 remains a `BASELINE_CONFLICT` pending a separate baseline
decision.

## 2026-08-24 - DOC-INTENT-AI-VENDOR-003

- Chose documentation correction方案 A after comparing the frozen SRS with
  TDD v1.4.2, DDD v1.2, and Coding Contract T-016/GATE-01.
- Added frozen SRS v1.3.4:
  `docs/context/requirements/spec_wd_ai_vendor_invoice_1.3.4.md`.
- Clarified that the module uses Odoo `account`, `contacts`, `ir.attachment`,
  `account.move`, and OCA/queue `queue_job`; it does not use
  `account_invoice_import` at runtime.
- Kept SRS v1.3.3 as an unchanged historical baseline.
- Updated active Intent SRS references and the Closure report matrix for
  SRS-4.5.1, SRS-9.19, T-016, and GATE-01.
- No source code or formal test code was modified.

## 2026-08-24 - SCRIPT-INTENT-AI-VENDOR-004

- Generalized `execution/scripts/verify.py` with a `--module` argument.
- Set `ai_vendor_invoice` as the default verification target; `wd_tlms` is not
  part of this repository's implementation scope.
- Added module-specific static checks for `ai_vendor_invoice` GATE-01 through
  GATE-15, with one structured result per gate and a non-zero failure status.
- Added `execution/scripts/README.md` with verifier usage examples.
- The AI module verifier runs without requiring a `wd_tlms` checkout.
- No business source or formal test code was modified.

## 2026-08-24 - INTENT-HUMAN-REVIEW-01 Readiness Check

- Executed the non-sensitive automatic environment checks against
  `odoo18e_tms`.
- Confirmed Odoo 18, PostgreSQL connectivity, `account`, `contacts`,
  `queue_job`, and `ai_vendor_invoice` installation, model registry, one
  purchase journal, configured fallback product, four active Provider records,
  and required security groups.
- Confirmed `account_invoice_import` is absent from the module runtime
  dependency set.
- Recorded four readiness blockers: GATE-08 provider field metadata failure,
  empty mapping master data, stopped Odoo Web endpoint, and a dirty Git
  baseline while preparing the readiness documents.
- Did not read or record any Provider API key.
- Did not create a UAT instance because the overall result is
  `UAT_BLOCKED`; browser, account, real-key, sample, and visual checks remain
  manual prerequisites.

## 2026-08-24 - INTENT-HUMAN-REVIEW-01 Follow-up

- Applied the authorized GATE-08 provider field XML ID fix and confirmed
  `verify.py --module ai_vendor_invoice` reports GATE-01 through GATE-15 all
  PASS.
- Started Odoo Web on port 8091 and confirmed `/web/login` returns HTTP 200.
- Inspected the supplied five-page
  `docs/carrier_invoice/bring_26022366.pdf` without reading or recording any
  Provider API key.
- Identified mapping source text: Bring Cargo B.V., Transportkosten ex Douane,
  Dieselolietoeslag, ADR toeslag, ETS toeslag, IMO toeslag, 21%, and EUR.
- Confirmed the database lacks the corresponding supplier, freight products,
  21% tax, EUR currency, and mapping rows; no guessed business data was
  created.
- Readiness remains `UAT_BLOCKED` only for missing invoice mapping data and the
  dirty Git baseline; account/API-key/PDF/browser checks are owner actions and
  are not recorded as automatic environment blockers.

### FIX-INTENT continuation: ProviderInput boundary

- Rechecked the final TDD §5.3 and T-026 directly; A-002 remains paused as
  `BASELINE_CONFLICT`, with no retry-count condition retained in timeout code.
- Added `services/pdf_preprocessor.py` to render attachment PDF pages into an
  in-memory ordered `ProviderInput` pages structure.
- Changed DeepSeek and Claude adapters to consume ProviderInput images rather
  than `ir.attachment`.
- Added explicit invalid, empty, encrypted, and render-failure PDF exceptions.
- Added PyMuPDF as the technical rendering dependency.
- Added regression coverage for ProviderInput boundaries, one-page/multi-page
  conversion, page ordering, PDF failures, and canonical schema behavior.

Verification for this continuation:

```text
Python/XML validation: PASS
Owl JS syntax: PASS
Odoo module tests: 53 tests, 0 failures, 0 errors
```

## 2026-08-25 - INTENT-IMPLEMENT-INVOICE-STATEMENT-001 Sprint 1

### Scope

- Added the `vendor.invoice.statement` and
  `vendor.invoice.statement.line` models.
- Added Task aggregate commands for first creation, human edits, AI candidate
  application, and Statement confirmation.
- Enforced ParseAttempt provenance rules and blocked direct Statement/Line ORM
  CRUD as an external business entry point.
- Added Statement/Line ACLs, company and ownership record rules, audit action
  coverage, and model-level tests.
- Corrected the provider API-key field group XML ID to the actual module
  namespace.

### Sprint 1 acceptance status

- `PASS`: Python compilation, XML parsing, ACL CSV structure, and
  `git diff --check`.
- `PASS`: Existing `GATE-01` through `GATE-15` static verifier.
- `NOT_APPLICABLE_YET`: Statement review/projection gates owned by Sprint 2.
- `NOT_APPLICABLE_YET`: Bill consistency, closure, concurrency, and final
  Statement gates owned by Sprint 3.
- `PASS`: Odoo TransactionCase suite completed in the configured test
  environment; the new Statement tests were executed successfully.

### Verification commands

```text
python3 -m compileall -q addons/ai_vendor_invoice
python3 execution/scripts/verify.py
git diff --check
cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && source venv/bin/activate
python3 odoo-bin -c odoo.conf --addons-path=<odoo>,<queue>,<statement-worktree>/addons \
  -d odoo18e_tms -u ai_vendor_invoice --test-enable \
  --test-tags /ai_vendor_invoice --stop-after-init
```

Result:

```text
verify.py: 19 pass, 0 fail
Odoo module tests: 102 tests, 0 failed, 0 errors
```

Sprint 1 implementation and acceptance are complete. Sprint 2 may start after
the Sprint 1 evidence is reviewed.

## 2026-08-25 - INTENT-IMPLEMENT-INVOICE-STATEMENT-001 Sprint 2

### Scope

- Added `services/statement_projection.py` to build and semantically validate
  the `task.human_review_result` compatibility projection from Statement.
- Extended Statement fields for supplier, product, and tax relations required
  by the review payload.
- Changed `action_confirm_statement(...)` to persist the review payload through
  Task aggregate commands, generate the projection, mark the task
  `awaiting_review`, and reject inconsistent Statement/projection content.
- Changed the Owl review confirmation to call `action_confirm_statement(...)`
  rather than directly invoking the Bill Creator.
- Added database coverage for Statement confirmation and projection output.

### Sprint 2 verification

```text
python3 -m compileall -q addons/ai_vendor_invoice: PASS
git diff --check: PASS
Odoo module tests: 65 tests, 0 failed, 0 errors
verify.py: 19 pass, 0 fail
```

The existing Sprint 1 gates remained passing. Sprint 3 bill-closure and final
Statement gates remain `NOT_APPLICABLE_YET` and were not claimed as complete.

## 2026-08-25 - INTENT-IMPLEMENT-INVOICE-STATEMENT-001 Sprint 3

### Scope

- Added the Statement-to-`human_review_result` consistency gate immediately
  before Bill Creator.
- Updated the unified review-and-bill entry point to confirm through the Task
  Statement aggregate when a Statement exists.
- Preserved the existing bill transaction, company context, idempotency,
  attachment-copy, and `account.move.create()` behavior.
- Added a database test proving an inconsistent projection is rejected.

### Verification

```text
python3 -m compileall -q addons/ai_vendor_invoice: PASS
git diff --check: PASS
Odoo module tests: 66 tests, 0 failed, 0 errors
verify.py: 19 pass, 0 fail
```

The test suite includes the existing concurrency, stale-worker, permission,
rollback, attachment, and company-context coverage. The new consistency test
was executed as `test_statement_projection_rejects_inconsistent_result`.

### New versus historical task policy

- New Tasks default to `statement_required=True`; Bill Creator rejects a new
  Task without a Statement.
- Existing Tasks upgraded from the historical schema retain the compatibility
  value `False` and may continue using the legacy `human_review_result` path.
- The flag is immutable after Task creation. Historical compatibility is
  explicit in legacy test fixtures and is not available as a UI bypass for
  newly created Tasks.

### Closure status

- `PASS`: Statement projection is checked before Bill Creator when a Statement
  exists.
- `PASS`: Existing `GATE-01` through `GATE-15` regression suite.
- `PASS`: Sprint 1 and Sprint 2 database tests remain green.
- Final `STATEMENT-GATE-01..25` evidence mapping and any production-scale
  multi-transaction concurrency run remain pending; this Sprint 3 entry does
  not claim those final closure gates without that evidence.

### Policy verification

```text
Odoo module tests: 67 tests, 0 failed, 0 errors
verify.py: 19 pass, 0 fail
```

## 2026-08-26 - FIX-INTENT-AI-VENDOR-PROVIDER-STABILITY-001

### Scope

- Added non-sensitive page/batch diagnostics persisted on each ParseAttempt.
- Kept DeepSeek Vision requests at one PDF page per batch and retained the
  configured timeout and retry ceiling.
- Disabled OpenAI SDK automatic retries so only the configured adapter retry
  ceiling controls transport attempts.
- Classified timeout, connection, rate-limit, 5xx, authentication,
  unsupported-input, bad-request, invalid JSON, schema, merge, and unknown
  provider failures without exposing secrets or raw responses in logs.
- Made multi-page merge deterministic: conflicting header values and
  `is_multi_invoice` flags fail explicitly; line order is preserved and exact
  duplicate line records are removed.

### Verification

```text
python3 -m py_compile: PASS
git diff --check: PASS
verify.py: 19 pass, 0 fail
Odoo module tests: 72 tests, 0 failed, 0 errors
```

The real Bring, Feelogic, and Mainfreight fixture matrix remains pending. No
`PROVIDER_STABILITY_PASS` claim is made until every page succeeds, the merged
canonical result validates, and the ParseAttempt reaches its expected state.

### Real fixture matrix

The current worktree was run against the configured `deepseek API` record in
`odoo18e_tms`. All three requests returned HTTP 200 and produced persisted
diagnostics, but each first page failed canonical validation:

```text
bring_26022366.pdf       task 904 / attempt 610  5 pages  RESPONSE_SCHEMA_INVALID
feelogic_35318.pdf       task 905 / attempt 611  1 page   RESPONSE_SCHEMA_INVALID
mainfreight_1727001370.pdf task 906 / attempt 612 3 pages  RESPONSE_SCHEMA_INVALID
```

The resulting status is `PROVIDER_STABILITY_BLOCKED`, not a provider pass.
The failure is now isolated to the provider response/schema contract; no
additional timeout, batch-size, or retry changes were made.

## 2026-08-26 - FIX-INTENT-AI-VENDOR-PAGE-EXTRACTION-001

### Scope

- Introduced a deliberately incomplete `PageExtractionResult` schema for each
  Vision page response.
- Added document-level normalization that converts ordered page results into
  the existing frozen `CanonicalResult`.
- Kept ParseAttempt, Mapping, Statement, Human Review, Bill Creator, and Task
  state semantics unchanged.
- Reclassified document-level conversion failures as
  `DOCUMENT_NORMALIZATION_INVALID`, distinct from HTTP and page response
  failures.

### Verification

```text
Python compile: PASS
git diff --check: PASS
verify.py: 19 pass, 0 fail
```

Final real-fixture matrix:

```text
bring_26022366.pdf          5 pages  extraction PASS  normalization FAIL
feelogic_35318.pdf          1 page   extraction PASS  normalization PASS  canonical PASS
mainfreight_1727001370.pdf 3 pages  extraction PASS  normalization PASS  canonical PASS
```

Bring is blocked only by a cross-page `factuurnummer` conflict during document
normalization. Mainfreight recovered two temporary timeout retries and
completed successfully. The final status is `PAGE_EXTRACTION_FIX_BLOCKED`, not
a full pass.

The verifier remains green (`19 pass, 0 fail`), Python compilation and
`git diff --check` pass. A subsequent full Odoo test rerun was not accepted as
a regression result because fixture execution had left a duplicate ParseAttempt
sequence in the shared validation database; no source failure was inferred
from that contaminated run.

## 2026-08-26 - DeepSeek Vision Runtime Audit

### Actual call chain

The current runtime path is:

```text
PDF upload
-> ir.attachment
-> vendor.invoice.import.task
-> ParseAttempt
-> pdf_preprocessor.prepare_provider_input()
-> PDF pages rendered as in-memory PNG images
-> DeepSeekAIProviderAdapter.parse_pdf()
-> one OpenAI-compatible Vision request per page
-> PageExtractionResult validation
-> document_normalizer.normalize_page_results()
-> frozen CanonicalResult validation
-> mapping_service.do_mapping()
-> ParseAttempt persistence
-> human Statement Review
```

The PDF renderer is `fitz`; rendered pages are not persisted. The adapter uses
`page_batch_size = 1`, so each request contains one page image.

### Prompt and request contract

The system prompt is hard-coded in
`addons/ai_vendor_invoice/adapters/deepseek.py`, inside
`DeepSeekAIProviderAdapter._parse_page_batch()`:

```text
Extract only what is visibly present on this page into PageExtractionResult JSON. Return JSON only. Missing fields are allowed. Do not treat repeated page headers or column headings as invoice lines.
```

The user text prompt is:

```text
Return an object with page_number, optional header values, optional lines, and optional is_multi_invoice. Use plain scalar values.
```

The final `messages` value contains one system message and one user message.
The user message content is an array containing the text item followed by one
`image_url` item with a base64 PNG data URL.

The request uses:

```text
model = Provider Config.model_name
stream = False
reasoning_effort = high
extra_body.thinking.type = enabled
response_format.type = json_object
OpenAI timeout = Provider Config.http_timeout
OpenAI max_retries = 0
```

### PageExtractionResult

The schema is defined in
`addons/ai_vendor_invoice/schemas/page_extraction.py`. Only `page_number` is
required. Optional fields are `header`, `header_values`, `lines`, and
`is_multi_invoice`; additional properties are allowed. The adapter overwrites
the model-provided page number with the actual local page number.

The AI is asked to extract visible page facts only, allow missing fields, and
avoid turning repeated page headers or column headings into lines. It is not
currently asked to return `source_label`, `source_value`, confidence values, or
evidence regions. Shipment references, Dossier, O.No., and Uw ref. are not
explicitly prohibited in the Prompt from competing with invoice fields.

### Responsibility boundaries

AI performs visual reading and page-level JSON organization. Python performs
PageExtraction schema validation, page ordering, semantic aliases, cross-page
header candidate scoring, duplicate merging, conflict detection, line
aggregation, `is_multi_invoice` consistency, and final Canonical Schema
validation. Mapping performs supplier, currency, product, and tax candidate
matching using configured mapping records. Human Statement Review decides
whether to accept or correct supplier, invoice fields, totals, taxes, lines,
and mapping candidates. Bill Creator reads the human review result.

### Prompt and response traceability

Prompt text is not exposed in the Odoo UI, is not editable, and is not stored
in Provider Config. ParseAttempt stores no actual system prompt, user prompt,
prompt version, model snapshot, or request payload hash. Successful attempts
store the raw provider response in a private `ir.attachment` linked through
`raw_response_attachment_id`; failures before persistence may have no raw
response attachment. `canonical_result`, `mapping_result`, provider
diagnostics, the source PDF attachment, and the Provider Config reference are
stored, but a historical attempt cannot fully reconstruct:

```text
PDF + Provider + historical Model snapshot + Prompt Version + actual Prompt
+ Raw Response + CanonicalResult
```

The audit conclusion is therefore: the runtime has raw-response and
CanonicalResult provenance, but not Prompt or Model-version provenance.

## 2026-08-26 - FIX-INTENT-AI-VENDOR-EXTRACTION-CONTRACT-001

### Status

`Implemented` — revised contract implementation is recorded in the
implementation section below.

### Proposed scope

The proposed FIX Intent changes only the DeepSeek Vision page extraction
contract. It introduces a fact-extractor role, explicit extraction coverage
for invoice headers, fee lines, transport references, dates, and addresses,
and requires uncertain facts to retain `source_label`, `source_value`, and
`source_page`.

The proposed PageExtractionResult adds `source_field`, `raw_facts`,
`references`, and `addresses` structures. It does not modify the frozen
Canonical Schema or downstream Statement, Human Review, Mapping, Bill Creator,
or Task state machine contracts.

The proposed audit additions are:

```text
PROMPT_VERSION = vision-extraction-v1.0
ParseAttempt.prompt_version
ParseAttempt.model_name_snapshot
```

Prompt remains hard-coded, absent from Provider Config and Odoo UI, and not
editable by business users. The existing private raw AI response attachment
mechanism remains unchanged.

The complete proposed system prompt, user prompt, schema, responsibility
boundaries, and acceptance criteria are saved in:

```text
docs/intents/FIX-INTENT-AI-VENDOR-EXTRACTION-CONTRACT-001.md
```

The initial design was saved for review without code changes. Following the
required review revision, implementation was explicitly authorized.

### Review revision

The review identified six required contract corrections: standard fields are
plain scalars, `source_page` is injected locally, page-level
`is_multi_invoice` is removed, references and addresses are unified into
`raw_facts`/line `raw_fields`, reference extraction is mechanical rather than
business classification, and lexical normalization is separated from semantic
mapping. The Intent was revised accordingly, its status is now
`IMPLEMENTATION AUTHORIZED`, and the implementation is complete in the current
worktree. Targeted verification passes; full Odoo runtime regression remains
subject to the existing database test environment.

## 2026-08-26 - PAGE_EXTRACTION_FIX_PASS

The document normalizer now ranks header candidates using source-container
evidence and cross-page repetition. Exact duplicates merge; equal-strength
conflicts raise a safe `HEADER_CONFLICT` diagnostic with field and page
metadata, never candidate values. Bring rerun attempt 680 completed with
5/5 page extraction, document normalization, Canonical validation, and
`awaiting_review` task state (22 lines). Feelogic and Mainfreight remained
green. The fixture records were cleaned before the full addon regression, which
exited successfully. Final status is `PAGE_EXTRACTION_FIX_PASS`.

## 2026-08-26 - FIX-INTENT-AI-VENDOR-EXTRACTION-CONTRACT-001 Implementation

### Status

`IMPLEMENTED` — revised extraction contract applied in the current worktree.

### Scope completed

- Replaced the DeepSeek Vision prompts with the hard-coded v1.1 fact-extraction
  prompts and added the `PROMPT_VERSION` and
  `EXTRACTION_CONTRACT_VERSION` constants.
- Tightened `PageExtractionResult` to plain scalar header/line fields with
  `raw_facts` and line `raw_fields`; source pages are injected locally.
- Kept document-level multi-invoice detection deterministic from explicit
  cross-page invoice numbers while retaining the frozen Canonical Schema and
  existing Task transition.
- Added immutable-at-source ParseAttempt prompt, extraction-contract, and model
  snapshots; private raw-response attachments remain unchanged.
- Added focused contract, provenance, normalization, and snapshot regression
  tests.

### Verification

- `python3 -m compileall -q addons/ai_vendor_invoice`: PASS
- `git diff --check`: PASS
- `python3 execution/scripts/verify.py --module ai_vendor_invoice`: 19 pass,
  0 fail

## 2026-08-26 - EXTRACTION_CONTRACT_TDD_AND_TEST_INTENT

Updated `docs/context/design/tdd_wd_ai_vendor_invoice_v1.4.md` with the
page-extraction contract, versioned Prompt and contract provenance, raw fact
handling, local `source_page` injection, document-level multi-invoice
normalization, and the extraction test boundary. No downstream Statement,
Review, Mapping, Bill Creator, Canonical Schema, or Task state-machine design
was changed.

Created the testing Intent:

```text
docs/intents/INTENT-TEST-AI-VENDOR-EXTRACTION-CONTRACT-001.md
```

The Intent is `Draft for Review`; it defines regression coverage and
acceptance criteria without adding or executing new test implementation.

## 2026-08-26 - TEST_INTENT_REVIEW_REVISION

Applied the review corrections to
`INTENT-TEST-AI-VENDOR-EXTRACTION-CONTRACT-001`:

- provider reasoning/thinking options are tested against the active versioned
  contract rather than treated as permanent global invariants;
- model-supplied `source_page` is rejected and local page provenance is
  injected by the adapter;
- Prompt tests assert semantic markers instead of byte-for-byte text;
- page ordering, complete line aggregation, empty-header detail pages, and
  reference-only multi-invoice exclusions are explicit;
- ParseAttempt tests cover immutable historical snapshots and rerun snapshots;
- PageExtraction, Normalizer, and Canonical boundaries plus error taxonomy are
  explicit;
- runtime fixture validation remains separate from Test Intent PASS.

The Intent status is now `TEST IMPLEMENTATION AUTHORIZED`. This revision still
does not implement or execute the tests.

## 2026-08-26 - EXTRACTION_CONTRACT_TEST_IMPLEMENTATION

Implemented the authorized extraction-contract regression coverage in the
existing test suite. Coverage includes request structure and Prompt semantics,
PageExtraction schema boundaries and local provenance, deterministic
cross-page normalization, reference and multi-invoice handling, and raw
response attachment persistence.

The normalizer was adjusted so independently labelled, differing invoice
numbers produce the document-level multi-invoice result instead of being
reported as an ordinary header conflict. It does not select a canonical
invoice number in that case.

### Verification

- `python3 -m compileall -q addons/ai_vendor_invoice`: PASS
- `git diff --check`: PASS
- `python3 execution/scripts/verify.py --module ai_vendor_invoice`: 19 pass,
  0 fail
- Odoo runtime tests: NOT RUN; the environment does not have the `odoo`
  Python module installed.
