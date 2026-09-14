# CC-10 Implementation Report

## Scope

CC-10 decouples Statement business authority from the Task aggregate. The
Statement is the user-facing business object; the AI Task remains a
failure-tolerant, repeatable technical execution record. This report covers
implementation of `docs/intents/CC-10-STATEMENT-BUSINESS-AUTHORITY-DECOUPLING.md`.

Per the contract's Authorization Gate (§13) the document's own trailing gate
still reads `DRAFT - NOT AUTHORIZED`, while its header (§Status) reads
`APPROVED FOR FREEZE AND IMPLEMENTATION` / `IMPLEMENTATION_AUTHORIZED = YES`.
This report proceeds on explicit user instruction to implement the frozen
CC-10 contract; the discrepancy between §Status and §13 is noted here for
traceability and was not resolved by editing the contract document itself
(out of scope: "authorizes no ... documentation change outside this new
CC-10 document" refers to other documents, not a rewrite of CC-10 itself).

## Environment note

The `agents/coding-contract-draft-updates` branch in this worktree was found
to be a strict git ancestor of `main` (no local divergence), missing the
already-merged CC-08/CC-09 work that CC-10 depends on (`Statement.state`,
`line.checked`, `all_checked`, `vendor_bill_id`, Confirm/Unconfirm). The
branch was fast-forwarded to `main` (`5930970`) before implementation so that
CC-10 could be implemented against the intended CC-09 baseline. This was a
fast-forward only; no commit was rewritten and no unrelated file was altered.

## Implemented behavior

### Statement-facing Confirm / Unconfirm (2.1.1, 4.1, 4.4)

- Added `vendor.invoice.statement.action_confirm()` and `.action_unconfirm()`.
  Both read only `Statement.state`, `Statement.line_ids.checked`, and
  `Statement.vendor_bill_id`; neither reads `Task.state`,
  `Task.human_reviewed`, or ParseAttempt status.
- `Statement.action_confirm_from_statement()` /
  `.action_unconfirm_from_statement()` (the Statement form button targets)
  now call these Statement-facing methods directly and no longer route
  through `task_id.action_confirm_statement()` /
  `.action_unconfirm_statement()`.
- `Task.action_confirm_statement()` / `.action_unconfirm_statement()` remain
  as legacy Task-facing compatibility entry points (used by the historical
  review dialog widget and the atomic Confirm+Create-Bill combo) and now
  delegate to the Statement-facing commands instead of implementing the
  business rules themselves. The former hard check
  `if self.state != "parsed"` in Unconfirm was removed.

### Statement-facing Create Bill (2.1.2, 4.2)

- `services/bill_creator.py` gained `_create_bill_for_statement(env,
  statement, task=None)`, which takes a Statement as its sole business input,
  requires a confirmed Statement with fully checked lines and no existing
  `vendor_bill_id`, and builds the Vendor Bill purely from
  `statement_to_human_review_result(statement)` (i.e. current Statement/line
  data), never from `Task.human_review_result`.
- Added `create_vendor_bill_for_statement(env, statement_id)`, the new
  Statement-facing entry point used by
  `Statement.action_create_vendor_bill_from_statement()`.
- `_create_locked(env, task)` and `create_vendor_bill(env, task_id)` are kept
  as legacy Task-facing wrappers (existing direct callers/tests) that resolve
  `task.statement_id` and delegate to the same Statement-driven
  implementation. The hard precondition `task.state != "parsed"` was removed
  from the Bill Creator entirely.
- `confirm_review_and_create_bill()` (legacy atomic Task combo) no longer
  gates on `task.state != "parsed"`.
- The Bill Creator still writes `Task.review_warnings` and Task audit/log
  rows as a legacy compatibility side effect only; the only Bill authority
  field written is `Statement.vendor_bill_id`.

### Task failure/cancellation independence (2.1.3, 4.3)

- No production code changes were required here: `action_cancel_task()`
  already restricts Cancel to `to_parse` / `parsing` / `error` (a `parsed`
  Task cannot be cancelled) and only ever writes `Task.state`/attempt fields,
  never touching the Statement. Confirm, Unconfirm, and Create Bill no longer
  reading `Task.state` (above) is what makes an existing Statement remain
  fully usable after the Task enters `error` or `cancelled`. Coverage added
  in `test_cc10_statement_authority.py`.

### Legacy value and field deprecation documentation (2.1.5, 2.1.6, 2.1.7)

- `Task.state`'s selection now documents `parsed` as the current technical
  success value and `awaiting_review` / `bill_generated` as legacy/deprecated
  compatibility values, with `help` text stating they are not Statement
  business preconditions. No selection values were removed or renamed.
- Every retained business-code read of `awaiting_review` / `bill_generated`
  (`_compute_parse_display_status`, the legacy `action_save_review`, and
  `parse_service.start_parse`) now carries an explicit legacy-compatibility
  comment; none of them are in the Confirm/Unconfirm/Create Bill path.
- `Task.human_reviewed` now carries a deprecated `help` text and comment; it
  is not read or written by any Confirm/Unconfirm/Create Bill code path (it
  never was in this codebase — verified by search).
- `Task.vendor_bill_id` was already `related="statement_id.vendor_bill_id",
  readonly=True, store=False` prior to CC-10 (implemented under CC-09); a
  `help` text and comment were added to record the CC-10 authority rule
  explicitly. `Statement.vendor_bill_id` remains the only writable Bill
  authority field; the Bill Creator and `account.move.button_cancel()`
  override write only that field.

### UI boundary (2.1.8, 5.1–5.3)

- No view changes were required: the Statement form (`Confirm`, `Unconfirm`,
  `Create Bill`, current Bill link) and the Task form (Run AI, Cancel, Open
  Statement/PDF, diagnostics) were already split this way under CC-09. The
  Statement form buttons now call into the Statement-facing commands
  described above instead of the Task aggregate.

## Out of scope (unchanged)

Per contract §2.2/§3, this implementation did not touch: Statement 1:N Task,
PDF ownership, Statement creation without a Task, Apply Candidate extraction,
`statement_id` audit anchoring, ParseAttempt/ProviderCall/PageArtifact, or the
CC-09 document.

## Files changed

- `addons/ai_vendor_invoice/models/statement.py` — added
  `action_confirm()`/`action_unconfirm()`; `action_confirm_from_statement()`,
  `action_unconfirm_from_statement()`, and
  `action_create_vendor_bill_from_statement()` now call the Statement-facing
  commands/service instead of the Task aggregate.
- `addons/ai_vendor_invoice/models/import_task.py` — `action_confirm_statement()`
  and `action_unconfirm_statement()` now delegate to the Statement; the
  `Task.state != "parsed"` Unconfirm precondition was removed; deprecation
  `help`/comments added to `state`, `human_reviewed`, `vendor_bill_id`, and
  the retained legacy-value reads in `_compute_parse_display_status` and
  `action_save_review`.
- `addons/ai_vendor_invoice/services/bill_creator.py` — added
  `_create_bill_for_statement()` and `create_vendor_bill_for_statement()`;
  `_create_locked()`, `create_vendor_bill()`, and
  `confirm_review_and_create_bill()` no longer gate on `Task.state` and now
  read Vendor Bill input only from the Statement.
- `addons/ai_vendor_invoice/services/parse_service.py` — added a legacy
  compatibility comment on the retained `awaiting_review` read in
  `start_parse` (no behavior change).
- `addons/ai_vendor_invoice/tests/test_cc10_statement_authority.py` (new) —
  22 tests covering the CC-10 §7 Test Plan scenarios.
- `addons/ai_vendor_invoice/tests/__init__.py` — registers the new test
  module.
- `docs/intents/CC-10-STATEMENT-BUSINESS-AUTHORITY-DECOUPLING.md` — contract
  copied into the worktree for traceability (previously present only outside
  version control in this environment).
- `docs/reports/CC-10-IMPLEMENTATION-REPORT.md` (this file).

No field was deleted or renamed, no selection value was removed, and no
migration script was added, consistent with §8 ("NO BUSINESS DATA MIGRATION
EXPECTED").

## Test Plan (§7) coverage

| Scenario | Test |
|---|---|
| Confirm with legacy/non-`parsed` Task state | `test_confirm_passes_with_legacy_task_state`, `test_confirm_passes_with_bill_generated_legacy_task_state` |
| Confirm does not read Task state | `test_confirm_does_not_read_task_state_after_cancel`, `test_confirm_never_routes_through_task_command` |
| Create Bill with confirmed Statement + legacy Task state | `test_create_bill_passes_with_legacy_task_state` |
| Create Bill reads current Statement data only | `test_create_bill_ignores_stale_task_human_review_result` |
| Task `error` after Statement exists → editable/confirm/bill | `test_statement_editable_after_task_error`, `test_statement_can_confirm_after_task_error`, `test_statement_can_create_bill_after_task_error` |
| Task cancelled after Statement exists → usable | `test_statement_usable_after_task_cancelled` |
| Task Cancel changes no Statement business state | `test_task_cancel_changes_no_statement_business_state` |
| `human_reviewed` old/stale value ignored | `test_human_reviewed_true_does_not_bypass_line_check`, `test_human_reviewed_false_does_not_block_confirm` |
| `Task.vendor_bill_id` read-only related compatibility | `test_task_vendor_bill_id_is_related_and_readonly`, `test_task_vendor_bill_id_mirrors_statement_after_bill_creation` |
| `Statement.vendor_bill_id` sole authority | `test_bill_cancellation_clears_statement_authority_only`, plus the above |
| Duplicate-bill/unconfirmed/unchecked-line guards preserved | `test_create_bill_requires_no_current_link`, `test_create_bill_requires_confirmed_statement`, `test_confirm_still_requires_checked_lines` |
| Manual-only flow without a Task | Not covered — explicitly deferred to CC-11 |

## Validation

Root cause note: this environment's `odoo.conf` sets `log_level = error`, so
the final `odoo.tests.result` / `odoo.tests.stats` summary lines — which are
logged at `INFO` when a run has zero errors — do not appear in the log at the
default level. Process exit code (`0` = `registry._assertion_report.wasSuccessful()`)
is the authoritative pass/fail signal; `--log-level=info` was used to also
capture the human-readable summary line for this report. This is a pre-existing
logging-verbosity property of the environment, not a CC-10 defect.

Command used:

```text
venv/bin/python3 odoo-bin -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,<worktree>/addons \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init \
  --log-level=info
```

Baseline (worktree HEAD after fast-forward to `main`, before CC-10 changes):

```text
0 failed, 0 error(s) of 144 tests when loading database 'odoo18e_tms'
```

After CC-10 implementation (production changes only, before adding new tests):

```text
0 failed, 0 error(s) of 144 tests when loading database 'odoo18e_tms'
```

Full suite including the 22 new CC-10 tests:

```text
0 failed, 0 error(s) of 166 tests when loading database 'odoo18e_tms'
```

The `duplicate key value violates unique constraint
"vendor_invoice_import_parse_attempt_task_sequence_unique"` message is
expected: an existing test deliberately triggers a duplicate `(task_id,
sequence)` write and asserts PostgreSQL rejects it.

## Blockers

None. All targeted CC-10 tests and the full `ai_vendor_invoice` regression
suite pass. The contract's internal §13 gate text ("DRAFT - NOT AUTHORIZED")
versus its §Status header ("APPROVED FOR FREEZE AND IMPLEMENTATION") is
flagged above for the user's awareness; implementation proceeded on the
user's explicit instruction to implement the frozen contract.
