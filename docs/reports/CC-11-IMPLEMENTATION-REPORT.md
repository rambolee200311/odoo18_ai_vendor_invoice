# CC-11 Implementation Report

## Status

**IMPLEMENTED AND VERIFIED**

CC-11 was approved for implementation before coding. The implementation keeps the
existing Task/ParseAttempt provider pipeline while moving the user-facing entry
point and current PDF authority to `vendor.invoice.statement`.

## Implemented scope

- A user with the existing AI Invoice User role can create a draft Statement
  without a Task.
- A Statement owns its current source PDF, filename, and company.
- A PDF can be uploaded or replaced before AI starts. Once a Task exists, PDF
  replacement is rejected.
- `Start AI` creates exactly one Task, copies the Statement PDF as the Task
  execution-input reference, inherits the Statement company, establishes both
  sides of the Statement/Task relation, and starts the existing parse service.
- A Statement supports at most one Task in this contract.
- Duplicate Start AI requests are rejected for queued/running/completed or
  cancelled Task states according to the frozen state matrix.
- Existing Task-first Statement creation remains compatible and now populates
  the Statement-owned company and PDF fields.
- Statement-facing review, unconfirm, candidate application, and bill creation
  remain the business command boundaries. Task-less audit uses Statement chatter;
  technical Task audit remains unchanged.
- Task-less bill creation locks the Statement row to preserve duplicate protection.
- Statement and Statement Line access rules permit current-company Task-less
  records while retaining own-Task visibility restrictions for AI Invoice Users.

## Compatibility and migration

The loaded-code verification confirmed that `Task.vendor_bill_id` is already a
read-only related compatibility field, so no business-data migration was
required. Existing Task-created Statements remain readable and retain their
legacy Task/Attempt provenance. No database business records were deleted or
reset during CC-11 implementation.

The security rule update also refreshes the existing Task-less Statement rule on
module upgrade so an already-installed database receives the company-aware
domain.

No semantic backfill was performed. Historical records whose meaning cannot be
deterministically reconstructed remain unchanged.

## Rollback

Rollback means disabling the Statement-first entry behavior while preserving the
CC-11-compatible schema and data. Task-less Statements, PDFs, and relations must
not be deleted as part of an online rollback. A full pre-CC-11 schema downgrade
requires a separately approved migration or database restore.

## Verification

Focused model verification:

```text
0 failed, 0 errors of 35 tests
```

Full module verification:

```text
0 failed, 0 errors of 146 tests
```

The full run also upgraded `ai_vendor_invoice`, loading Python models, security
data, views, and access metadata.

The focused CC-11 regression coverage verifies:

- direct Statement creation by an AI Invoice User;
- Statement-owned PDF upload;
- one Task created on Start AI;
- bidirectional Statement/Task linkage;
- shared Statement/Task execution PDF reference;
- inherited provider/company behavior;
- legacy Task-created Statement PDF and Attempt provenance;
- parsed Task cancellation protection and legacy states.

## Deferred by contract

Batch upload, Statement 1:N Task execution history, PDF replacement after Task
creation, candidate history, audit-anchor redesign, provider/queue redesign,
and a new persisted AI summary state remain outside CC-11.

## Final acceptance

CC-11 acceptance criteria are satisfied by the implementation and the test
results above. No known blocker remains within the authorized scope.
