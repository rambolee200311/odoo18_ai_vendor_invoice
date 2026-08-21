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
