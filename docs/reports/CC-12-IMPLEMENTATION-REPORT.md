# CC-12 Implementation Report

## Status

**IMPLEMENTED AND VERIFIED**

CC-12 was frozen and explicitly authorized before implementation. The change
adds only the pre-launch AI execution configuration boundary and preserves the
CC-10/CC-11 business authority model.

## Implemented scope

- Statement `Start AI` now opens a transient configuration wizard without
  creating a Task or ParseAttempt.
- The wizard lets an authorized AI Invoice User select:
  - an active provider with complete required configuration;
  - synchronous or asynchronous execution.
- The execution mapping is explicit:

```text
Synchronous  -> Task.synchronous_parse = True
Asynchronous -> Task.synchronous_parse = False
```

- Wizard cancellation creates no Task, ParseAttempt, ProviderCall, queue job,
  or AI-launch audit event.
- Wizard `Start` creates one Task, copies the Statement PDF execution reference,
  stores the selected provider and execution mode, establishes both sides of
  the Statement/Task relation, and starts the existing ParseService.
- The Statement row is locked before launch, preventing duplicate Task creation
  from repeated submission.
- Task provider and execution mode are immutable after Task creation.
- Normal reruns continue to reuse the original Task configuration.
- The Task detail form remains a technical diagnostics page and is not the
  first-time Task creation entry point.
- Task provider, execution mode, source PDF, ParseAttempt history, errors,
  queue diagnostics, audit log, and Statement navigation remain available.
- Historical Tasks without wizard-created metadata remain readable.

## Compatibility and boundaries

CC-10 and CC-11 boundaries remain unchanged:

- Statement Confirm and Unconfirm remain Statement-facing;
- Vendor Bill creation remains Statement-facing;
- `Statement.vendor_bill_id` remains the Vendor Bill authority;
- Task failure or cancellation does not change Statement business state;
- Statement/Task cardinality remains `0..1 <-> 0..1`;
- existing ParseService, queue, retry, stale-worker, and transaction behavior is
  reused.

No new provider-level authorization model was introduced. Provider selection
uses existing provider configuration access rules. No persistent wizard
configuration fields were added.

## Migration and rollback

No business-data migration or semantic backfill was required. Existing Task
provider and execution-mode facts remain readable and are not rewritten.

Online rollback means disabling the wizard launch behavior while preserving
CC-10/CC-11-compatible Tasks, Statements, ParseAttempts, and audit data. It
does not create placeholder Tasks, delete Task-less Statements, delete PDFs, or
rewrite historical execution facts.

## Verification

Focused CC-12/model verification:

```text
0 failed, 0 errors of 48 tests
```

Full module verification:

```text
0 failed, 0 errors of 147 tests
```

The full run upgraded `ai_vendor_invoice` and loaded the model, transient
wizard, access control, security rules, and views.

Coverage includes:

- opening Start AI without creating a Task;
- provider and async selection;
- Task/Statement relation creation;
- immutable provider and execution mode;
- rerun configuration reuse;
- legacy Task compatibility;
- Task form and security regression coverage.

## Deferred

`Retry with another provider`, provider pipeline redesign, Task history
redesign, candidate history, queue semantics changes, and unrelated dashboard or
menu redesign remain deferred to future contracts.

## Final acceptance

CC-12 is implemented and verified within the authorized scope.
