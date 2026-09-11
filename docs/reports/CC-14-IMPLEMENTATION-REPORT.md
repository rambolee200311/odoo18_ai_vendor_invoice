# CC-14 Implementation Report

## Status

**IMPLEMENTED AND VERIFIED**

CC-14 was frozen and explicitly authorized before implementation. It builds on
CC-10 (Statement business authority), CC-11 (Statement-first, one PDF per
Statement), and CC-13 (Statement-embedded AI/Task workspace) without changing
any of them.

## Implemented scope

- Added a persistent `vendor.invoice.batch` model: batch reference/name,
  company, selected AI Provider, start timestamp, the related Statements
  (`One2many` via `Statement.batch_id`), current aggregate counts (`total`,
  `pending`, `processing`, `success`, `failed`), and a recomputed
  `draft / processing / completed / completed_with_errors` status. Batch owns
  none of supplier/invoice data, human review, Confirm, or Vendor Bill
  creation; those remain exclusively on Statement.
- Added `Statement.batch_id` (`ondelete=restrict`, immutable after it is set:
  rejected by the existing `write()` relation guard exactly like `task_id`/
  `company_id`, and only ever set through `create()` by the Batch
  orchestrator). Historical standalone Statements keep `batch_id = False`.
- Added `Statement.batch_ai_status` — a stored, indexed, searchable
  `pending / processing / success / failed` projection computed only from
  the *current* Task state (`to_parse`→pending, `parsing`→processing,
  `parsed`/`awaiting_review`/`bill_generated`→success, `error`/`cancelled`→
  failed), never from historical ParseAttempts. This backs both Batch's
  aggregate counts and the failed-Statement filter.
- Extracted the CC-14 §13 shared single-Statement launch boundary into
  `services/statement_launch_service.launch_statement_ai(env, statement_id)`:
  lock/recheck the Statement, validate the PDF and Provider, create-or-reuse
  exactly one Task, copy the launch configuration, establish the relation,
  and call `parse_service.start_parse()`. `Statement.action_start_ai()` now
  delegates to this boundary instead of duplicating the logic; its observable
  behavior, return value, and existing test coverage are unchanged.
- Added `services/batch_service.py`:
  - `start_batch(env, company_id, provider_config_id, files)` runs the CC-14
    §6/§10 pre-Statement preflight (empty file, non-PDF content, PDF
    duplicated within the same upload, or a PDF checksum already active in
    another Task — reusing the existing
    `company_source_pdf_checksum_active_unique` predicate) and reports every
    rejection immediately without ever creating a Statement or Batch member
    for the rejected file. Each PDF that passes preflight is created and
    launched (Statement create + shared launch boundary) inside one
    `env.cr.savepoint()` so a single PDF's failure is fully isolated: it
    never rolls back an already-accepted sibling PDF and never blocks the
    remaining PDFs (§15). A summary is posted to the Batch chatter.
  - `retry_selected(env, batch_id, statement_ids)` implements the CC-14 §19
    eligibility matrix — only a Statement that belongs to the given Batch,
    is currently Draft, whose Task is currently `error`, and has no active
    (`queued`/`running`) Attempt is retried. Every other selected Statement
    (wrong Batch, non-Draft, wrong Task state, active Attempt) is reported as
    a per-item rejection and left untouched. Each eligible retry is wrapped
    in its own savepoint and calls the same shared launch boundary, so it
    keeps the same Statement, the same Task, the same Provider, creates
    exactly one new ParseAttempt, and stays asynchronous (the Task's
    `synchronous_parse` was fixed at creation and is immutable). A retry
    failure for one Statement never affects another selected Statement's
    outcome.
- Added the `vendor.invoice.batch.import.wizard` (+ transient line model)
  multi-PDF entry point, Batch list/form/search views and menu, a Statement
  list-view "Retry Selected" `ir.actions.server` (bound to `list` view type,
  calling the new `Statement.action_retry_selected()` multi-record action),
  and `batch_id`/`batch_ai_status` fields plus filters on the existing
  Statement list/search views.
- Added security: `ir.model.access.csv` rows and company-scoped `ir.rule`
  records for `vendor.invoice.batch` and the wizard models, mirroring the
  existing Task/Statement group pattern (AI Invoice User creates/uses;
  Reviewer/Config Manager see all; no group gained new business authority).
- Added `data/system_config_data.xml` sequence `seq_vendor_invoice_batch`
  (`vendor.invoice.batch` code) alongside the existing Task/Statement
  sequences.

## Discovered and fixed

`vendor.invoice.import.log` granted `perm_create` only to the Reviewer and
Config Manager groups, not to the "AI Invoice User" group, even though that
group's own description says it "can create/upload tasks and trigger AI
parse." Any real (non test-mocked) AI launch calls `parse_service.start_parse()`,
which writes an audit log row; a plain AI Invoice User running the existing
CC-13 `Statement.action_start_ai()` end-to-end (not through a test that mocks
`parse_service.start_parse`) would already hit this `AccessError` today. This
directly blocked the CC-14 requirement that Batch creation and Retry Selected
"需要现有 AI Invoice User 权限" (§24), because both go through the same shared
launch boundary. Fixed by granting `perm_create` on `vendor.invoice.import.log`
to the AI Invoice User ACL row. This is a narrow ACL correction; it does not
change any business or Task/Statement authority.

## Boundary and compatibility

- CC-10/CC-11/CC-13 authority is unchanged: Statement remains sole owner of
  Confirm, Unconfirm, and Vendor Bill; Task remains the AI execution
  authority; ParseAttempt remains the execution-attempt history; Statement
  cardinality remains `0..1 <-> 0..1` with a Task.
- Batch is `Batch 1:N Statement` only — no `BatchItem` model was added.
  Rejected files never become persisted Batch members (§6).
- The existing Task/Statement duplicate-PDF and business-duplicate unique
  indexes are reused unchanged; CC-14 adds no new predicates.
- Batch execution is async-only: every Statement/Task the Batch launches
  passes `ai_launch_synchronous_parse=False`; CC-13's own synchronous
  single-Statement capability is untouched.
- Retry Selected is intentionally narrower than the pre-existing CC-13
  single-Statement rerun (which still allows `to_parse`/`error`/
  `awaiting_review`): CC-14 Retry Selected only accepts the current `error`
  + Draft Statement + no active Attempt combination (§19), so Confirmed,
  Bill Created, and Cancelled Statements can never be overwritten by a Batch
  retry.
- No migration was authorized or performed beyond ordinary additive schema
  (`Statement.batch_id`/`batch_ai_status`, the new Batch/wizard models, and
  one ACL correction). Existing Statements, Tasks, and ParseAttempts without
  a Batch relation remain valid and unaffected (`batch_id = NULL`).

## Verification

Targeted CC-14 model/service verification:

```text
python odoo-bin -c odoo.conf -d odoo18e_tms -u ai_vendor_invoice \
  --http-port=8099 --log-level=test --test-enable \
  --test-tags /ai_vendor_invoice:TestBatchInitialLaunch,\
/ai_vendor_invoice:TestBatchPreflight,\
/ai_vendor_invoice:TestBatchLaunchIsolation,\
/ai_vendor_invoice:TestBatchProgressAndFilter,\
/ai_vendor_invoice:TestRetrySelected,\
/ai_vendor_invoice:TestBatchSecurityAndCompany \
  --stop-after-init

0 failed, 0 errors of 19 tests
```

Full module verification:

```text
python odoo-bin -c odoo.conf -d odoo18e_tms -u ai_vendor_invoice \
  --http-port=8099 --log-level=test --test-enable \
  --test-tags /ai_vendor_invoice --stop-after-init

0 failed, 0 errors of 167 tests
```

The full run upgraded `ai_vendor_invoice` and loaded the new Batch/wizard
models, security metadata, views, and the corrected `vendor.invoice.import.log`
ACL alongside all pre-existing CC-10/CC-11/CC-13 coverage, confirming no
regression.

Note: an alternate HTTP port (`--http-port=8099`) was used only because a
long-running development server already held the configured port on the
shared database; that separate long-running server's in-memory registry may
need a restart to see the schema/model changes made by this upgrade.

## Deferred

Consistent with CC-14 §29: Batch human review, Batch Confirm, Batch Create
Vendor Bill, Batch Apply Candidate, Provider fallback, retry with another
Provider, a `BatchItem` model, cross-company Batch, multi-invoice splitting,
advanced queue throttling, and Batch cancellation semantics all remain
deferred and unimplemented.
