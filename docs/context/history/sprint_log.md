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

The separate Closure findings for concurrency, multi-company, secret,
verification-script, and documentation-drift work remain outside this Fix
Intent. A-002 remains a `BASELINE_CONFLICT` pending a separate baseline
decision.

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
