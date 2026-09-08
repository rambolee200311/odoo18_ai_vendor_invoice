# CC-04 — Vendor Invoice Statement State Machine

> Document Type: Coding Contract  
> Status: `DRAFT — NOT AUTHORIZED`  
> `IMPLEMENTATION_AUTHORIZED = NO`

## 1. Contract Goal

Define a minimal business lifecycle for `vendor.invoice.statement`, separate from Task,
ParseAttempt, Vendor Bill, payment, and reconciliation lifecycles.

## 2. Current State

- `vendor.invoice.statement` currently has no `state` field.
- `vendor.invoice.import.task` owns the existing AI/import state:
  `to_parse`, `parsing`, `awaiting_review`, `bill_generated`, and error states.
- Successful parsing may create a prefilled Statement; Task aggregate commands support
  create, edit, apply candidate, and confirm operations.
- Statement `write` currently permits reviewer writes, while business paths are intended
  to use Task aggregate commands.
- Bill Creator currently requires Task `awaiting_review`, `human_reviewed`, a non-empty
  projection, a Statement when required, and projection consistency. It then sets Task
  to `bill_generated` and links the draft bill.
- No Statement confirmed/locked/cancelled semantics currently exist.

## 3. In Scope

Introduce the smallest lifecycle that expresses document readiness:

| State | Meaning |
| --- | --- |
| `draft` | AI-prefilled or manually edited Statement awaiting reviewer confirmation. |
| `confirmed` | Reviewer confirmed the Statement and its projection is valid; it is ready for bill creation. |
| `cancelled` | Reviewer intentionally abandoned the Statement; it cannot produce a bill. |
| `bill_created` | A draft Vendor Bill is linked; the Statement is terminal and read-only. |

`bill_created` is a Statement document state, not a copy of the Vendor Bill posting or
payment state.

## 4. Out of Scope

- Task, ParseAttempt, queue, provider, AI runtime, payment, posting, reconciliation, or
  Vendor Bill state redesign.
- `submitted`, `approved`, `rejected`, `posted`, `paid`, or `reconciled` states.
- Automatic reopen or a second workflow engine.

## 5. Business Rules

1. New Statements start in `draft`.
2. Drafts are editable by reviewers through aggregate commands.
3. Apply AI Candidate is allowed only for a valid current successful attempt and keeps the
   Statement in `draft`.
4. `confirmed` means human review is complete and projection consistency has passed.
5. Confirmed Statements are not normally editable; confirmation must not create a bill by
   itself.
6. `cancelled` is terminal for normal operations and preserves audit history.
7. A Statement with a linked bill is `bill_created` and cannot be cancelled or edited.
8. Task state remains Task-owned. Bill creation must update Task and Statement in one
   transaction, with the existing one-task/one-bill idempotency guard.

## 6. Technical Boundaries

- Only explicit aggregate transition commands may change Statement state.
- Suggested command names:
  - `action_confirm_statement`
  - `action_cancel_statement`
  - internal Bill Creator transition `action_mark_bill_created`
- Direct `write({"state": ...})`, generic form persistence, context flags, or `sudo()` must
  not bypass transition guards.
- Transition audit must record actor, timestamp, prior state, next state, Task, and
  ParseAttempt where available.

## 7. Allowed Changes

- Add Statement `state` selection and transition guards.
- Add explicit transition commands and native form buttons/statusbar.
- Extend audit action vocabulary for confirm/cancel/bill-created transitions.
- Add tests for transition, permission, projection, idempotency, and rollback behavior.
- Update Bill Creator only to enforce and atomically set the Statement lifecycle state.

## 8. Forbidden Changes

- Copying Task or `account.move` state machines.
- Allowing Statement state to represent AI runtime, queue, payment, posting, or
  reconciliation.
- Bypassing projection consistency or Bill Creator locking.
- Making direct Statement CRUD the business workflow.

## 9. Impacted Files / Models / Views

- `addons/ai_vendor_invoice/models/statement.py`
- `addons/ai_vendor_invoice/models/import_task.py`
- `addons/ai_vendor_invoice/services/bill_creator.py`
- `addons/ai_vendor_invoice/views/import_task_views.xml`
- Existing audit log model/action vocabulary if required
- Focused Statement, Task, Bill Creator, permission, and transaction tests

## 10. Data / Migration Impact

Existing Statements require a deterministic migration/default to `draft`; no historical
business data may be discarded. Existing Tasks retain their current state values. A
Statement-to-bill link must be preserved and must determine/validate `bill_created`.

## 11. Security Impact

Only the existing reviewer group may confirm or cancel. AI Invoice Users may view only
according to current rules and may not transition. Config Managers gain no Statement
workflow rights unless already granted independently.

## 12. Transition Matrix

| From | Action | To | Preconditions | Side Effects | Editable? |
| --- | --- | --- | --- | --- | --- |
| new | aggregate create | `draft` | Valid Task, source attempt, invoice number | Create Statement/Lines; audit creation | Yes, reviewer |
| `draft` | apply AI candidate | `draft` | Reviewer; current successful attempt; payload valid | Replace candidate data, preserve provenance/audit | Yes |
| `draft` | `action_confirm_statement` | `confirmed` | Reviewer; valid data; projection generated and consistent | Set human review/projection; audit transition | No normal edit |
| `draft` | `action_cancel_statement` | `cancelled` | Reviewer; no linked Vendor Bill | Audit cancellation; no bill creation | No |
| `confirmed` | create Vendor Bill | `bill_created` | Reviewer flow; Task awaiting review; projection valid; lock/idempotency pass | Create draft bill; link Statement/Lines; set Task bill-generated; audit | No |
| `confirmed` | cancel | `cancelled` | Reviewer; no linked Vendor Bill; cancellation policy permits | Audit cancellation | No |
| `cancelled` | any normal transition | unchanged | None | Raise validation error | No |
| `bill_created` | any normal transition | unchanged | None | Raise validation error | No |

## 13. Compatibility / Regression Requirements

- Existing Task state meanings remain unchanged.
- Existing `action_confirm_statement` remains the review/projection command; it must not
  silently invoke Vendor Bill creation.
- Bill Creator remains the only bill creation entry point and still consumes only
  `human_review_result`.
- Duplicate bill attempts remain rejected.
- Stale AI candidates remain rejected.
- Failure during bill creation leaves Task and Statement in their prior states.

## 14. Acceptance Criteria

- State defaults to `draft` and appears in Statement list/form.
- Every valid transition is explicit, permission-checked, audited, and idempotent.
- Invalid transitions raise visible Odoo validation/access errors.
- Confirmed and bill-created documents are protected from normal editing.
- Bill creation requires `confirmed` and projection consistency, then atomically sets
  Statement `bill_created`, Task `bill_generated`, and the linked bill relation.
- Cancelled Statements never create a bill and retain audit history.
- No runtime, payment, posting, or reconciliation state is introduced.

## 15. Test Requirements

- Default state and existing-record migration/default tests.
- Full transition-matrix tests, including invalid transitions.
- Reviewer/user/config-manager permission tests.
- Candidate application and stale-attempt tests.
- Projection consistency and Bill Creator precondition tests.
- Duplicate/concurrent bill and rollback atomicity tests.

## 16. Open Questions

`OPEN_QUESTIONS = NONE`

## 17. Authorization Status

`DRAFT — NOT AUTHORIZED`  
`IMPLEMENTATION_AUTHORIZED = NO`
