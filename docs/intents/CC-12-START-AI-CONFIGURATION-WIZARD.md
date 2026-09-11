# CC-12 - Start AI Configuration Wizard

## 1. Status

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

The Open Questions in Section 9 (OQ-12.1 through OQ-12.7) have been frozen by
the user. This contract authorizes implementation only within the scope and
decisions defined below. It does not authorize unrelated coding, schema,
migration, test, or UI changes.

## 2. Context

CC-10 established the business authority boundary:

```text
Statement owns business decisions.
Task records AI execution facts.
```

CC-11 established the Statement-first entry flow:

```text
User creates Statement
    ->
User uploads supplier invoice PDF
    ->
User starts AI Task from Statement
```

Manual verification identified an execution-configuration gap in the current
entry flow:

- `Start AI` automatically selects the first active provider;
- `synchronous_parse` currently comes from the Task default, which is `True`;
- the user has no opportunity to choose the provider or execution mode before
  the Task is created and started;
- opening the Task after Start AI is too late for initial configuration;
- the existing Task form already exposes provider, execution mode, state,
  ParseAttempt history, diagnostics, audit, and source PDF, but is a technical
  detail page rather than a suitable first-launch configuration surface.

CC-12 closes only this configuration boundary. It does not reopen the
Statement/Task authority decisions frozen by CC-10 and CC-11.

## 3. Product Intent

The user continues to work from the Statement. Before the technical execution
context is created, the user may choose the provider and execution mode for the
current AI run.

The intended journey is:

```text
Open Statement
    ->
Click Start AI
    ->
Choose Provider and Sync/Async in wizard
    ->
Click Start
    ->
Create and start exactly one Task atomically
    ->
Observe technical execution from Statement or Task detail
```

The Task remains a technical execution context and MUST NOT become the primary
user entry object.

## 4. Scope

### 4.1 Start AI configuration wizard

The Statement-facing `Start AI` command SHALL open a small configuration wizard
instead of immediately creating or starting a Task.

The wizard MUST provide at least:

- Provider selection;
- Execution mode selection: synchronous or asynchronous;
- `Cancel` action;
- `Start` action.

The wizard MUST validate the Statement, current PDF, company, permissions,
provider availability, and execution configuration before `Start` proceeds.

### 4.2 Atomic Task launch

Only after the user clicks the wizard's `Start` action SHALL the system perform
the CC-11 launch operation:

1. create the one allowed Task;
2. write `selected_provider_config_id`;
3. write `synchronous_parse`;
4. establish both sides of the Statement/Task relation;
5. create the first ParseAttempt;
6. start the existing ParseService.

The execution-mode mapping MUST be explicit:

```text
Synchronous selection  -> synchronous_parse = True
Asynchronous selection -> synchronous_parse = False
```

The operation MUST remain one transactional launch boundary. It MUST NOT create
a partially configured Task merely because the wizard was opened.

The wizard `Start` action MUST be idempotent against double submission within
the same user session. A second `Start` against an already-launched Task MUST
NOT create a second Task, relation write, or ParseAttempt.

### 4.3 Task detail form

The existing Task form SHALL remain available as a technical detail and
diagnostic surface. It SHALL expose, as applicable:

- selected Provider;
- synchronous/asynchronous execution mode;
- Task state;
- ParseAttempt history;
- parse errors;
- queue diagnostics;
- Audit Log;
- source PDF;
- a command to return to the owning Statement.

The Task form MUST NOT be the first-launch creation flow.

### 4.4 Configuration immutability and rerun boundary

After a Task has been created, its selected provider and execution mode MUST be
read-only for that Task.

A normal rerun MUST reuse the original Task configuration. It MUST NOT silently
switch provider or execution mode.

If a future workflow needs another provider, it MUST be an explicit
`Retry with another provider` operation with separately defined history,
permissions, and transaction semantics. That operation is deferred to a future
contract and is not part of this implementation.

## 5. Out of Scope

CC-12 MUST NOT authorize:

1. rewriting the AI provider or ParseService pipeline;
2. redesigning ParseAttempt, ProviderCall, PageArtifact, or canonical result
   architecture;
3. redesigning Vendor Bill accounting behavior;
4. adding a persisted `Statement.ai_status` abstraction;
5. moving Confirm or Create Bill authority back to Task;
6. deleting legacy Task fields or historical provider/selection values;
7. introducing a new generic service framework;
8. changing queue concurrency, retry, stale-event, or worker semantics;
9. adding batch upload or Statement 1:N Task history;
10. redesigning unrelated dashboards, menus, or navigation;
11. implementing `Retry with another provider`.

The wizard MAY be implemented with the repository's existing transient-model
patterns, but CC-12 does not authorize a generic wizard framework.

## 6. Behavioral Changes

### 6.1 Opening Start AI

When an authorized user clicks `Start AI` on a valid Statement:

- the wizard SHALL open;
- no Task SHALL be created;
- no ParseAttempt SHALL be created;
- no provider execution SHALL start;
- no Statement business data SHALL be changed merely by opening the wizard.

The wizard MUST refuse to open and MUST surface a visible validation error when:

- the Statement has no valid current PDF;
- the Statement already has a Task that is not in a re-runnable state; or
- the Statement is otherwise not eligible under the CC-11 lifecycle.

The behavior for a Statement with an existing re-runnable Task is governed by
OQ-12.3 and OQ-12.7. It MUST NOT silently create a second Task.

### 6.2 Cancelling the wizard

`Cancel` SHALL close the wizard without starting AI.

Cancellation MUST create:

- no Task;
- no ParseAttempt;
- no ProviderCall;
- no queue job;
- no new audit event representing an AI launch.

It MUST preserve the Statement and its current PDF unchanged.

### 6.3 Starting from the wizard

After valid Provider and execution mode selection, `Start` SHALL create and
launch the Task using the selected values.

The created Task MUST:

- reference the current Statement PDF as its execution-input compatibility
  reference;
- inherit the Statement company;
- contain the selected provider;
- contain the selected synchronous/asynchronous mode;
- satisfy the bidirectional Statement/Task relation invariant;
- enter the existing parse lifecycle through ParseService.

The wizard MUST NOT create a second Task for a Statement that already has one.

### 6.4 Task detail behavior

The Task detail form SHALL display technical execution facts without becoming a
second business workbench.

Task provider and execution mode fields MUST be read-only after creation.
Statement Confirm, Unconfirm, Vendor Bill creation, and business data editing
remain Statement-facing and MUST NOT be moved to Task authority by this
contract.

### 6.5 Rerun behavior

An existing supported rerun MUST use the original Task provider and execution
mode. A rerun MUST NOT silently overwrite those fields or create a second Task.

`Retry with another provider` remains deferred and MUST raise an explicit
deferred or unavailable outcome if referenced by a future surface before its
own contract is approved.

## 7. UI Contract

### 7.1 Statement entry

The Statement page SHALL retain the `Start AI` command defined by CC-11. Its
behavior changes only from immediate launch to opening the configuration wizard.

The wizard SHALL provide:

```text
Provider          [selection]
Execution mode    [Synchronous / Asynchronous]

[Cancel] [Start]
```

The final labels and widget implementation MUST follow repository conventions,
but the two choices and two actions are mandatory.

### 7.2 Provider presentation

The provider field SHALL present only the provider records authorized by the
frozen decision in Section 9. The wizard MUST communicate unavailable or
invalid configuration rather than silently falling back to another provider.
If no provider in the wizard selection is currently usable, the `Start` action
MUST be disabled and the wizard MUST explain why.

### 7.3 Task form

The Task form SHALL remain a read-only-after-creation technical detail page
covering:

- provider;
- sync/async mode;
- state;
- ParseAttempt history;
- errors;
- queue diagnostics;
- Audit Log;
- source PDF;
- owning Statement navigation.

The Task page MUST NOT provide a normal first-time Task creation route.
The owning-Statement navigation SHALL be disabled or hidden when the Task has
no Statement, preserving readability of historical Task records.

## 8. Data and Relation Contract

### 8.1 Task ownership of execution configuration

The selected provider and execution mode are execution facts belonging to the
Task:

```text
Task.selected_provider_config_id
Task.synchronous_parse
```

The wizard is a pre-creation input surface. It MUST NOT persist its own provider
or execution-mode fields and MUST NOT become a second persistent authority for
execution configuration.

### 8.2 Statement/Task relation

CC-11's cardinality and invariant remain unchanged:

```text
Statement 0..1 <-> 0..1 Task
statement.task_id == task
task.statement_id == statement
```

The wizard MUST NOT create a placeholder Task to hold selected options.

### 8.3 ParseAttempt and provider pipeline

The first ParseAttempt MUST be created only after the wizard `Start` action and
within the same launch transaction as Task creation and relation establishment.

CC-12 MUST reuse the existing ParseService, queue, ProviderCall, PageArtifact,
canonical result, retry, stale-event, and transaction semantics.

### 8.4 Statement and business authority

CC-12 MUST preserve:

- Statement Confirm authority;
- Statement Unconfirm authority;
- Statement Vendor Bill creation authority;
- `Statement.vendor_bill_id` as Vendor Bill authority;
- Task failure or cancellation not changing Statement business state.

## 9. Decisions Required Before Authorization

The following Open Questions MUST be explicitly frozen before implementation
authorization.

### OQ-12.1 Provider list policy

Which records SHALL appear in the wizard Provider field?

Options:

1. Active and currently usable providers only;
2. All providers, with unavailable providers visibly disabled and explained;
3. Another explicitly defined policy.

A provider config is "currently usable" only when it is active, its required
credentials and configuration are present, and its configured service is not
disabled.

The implementation MUST NOT silently fall back to the first active provider
when the user has been given a provider-selection surface.

### OQ-12.2 Execution mode default

What default SHALL the wizard use?

Options:

1. Follow the existing Task default (`synchronous_parse = True`);
2. Define a separate wizard default;
3. Require an explicit user choice with no preselected mode.

The default MUST be explicit and testable.
The contract MUST also state whether the default is merely preselected and
user-overridable, or whether the user must make an explicit choice.
Recommended answer: the wizard preselects the existing Task default
(`synchronous_parse = True`) and the user may override it before `Start`.

### OQ-12.3 Rerun configuration policy

When rerunning an existing Task, may the user change provider or execution mode?

Options:

1. Normal rerun always reuses the original Task configuration; changing it
   requires a separately approved `Retry with another provider` flow;
2. Rerun opens the same wizard but still reuses the original configuration;
3. Rerun opens the same wizard and permits changing the configuration;
4. Another explicitly defined policy.

No silent configuration change is permitted.
Recommended answer: normal rerun reuses the original Task configuration;
changing provider or execution mode requires a separately approved `Retry with
another provider` flow. The contract MUST also freeze whether normal rerun
opens the wizard or launches directly with the original configuration.

### OQ-12.4 Wizard cancellation

Shall cancellation simply close the wizard and create no Task, ParseAttempt, or
launch audit event?

The recommended answer is **YES**, consistent with the CC-11 atomic launch
boundary. Cancellation records no audit event because no AI launch occurred.
Whether a non-launch "wizard opened/cancelled" audit event is recorded is a
separate decision; the recommended answer is no audit event for either open or
cancel, keeping the audit stream limited to actual execution facts.

### OQ-12.5 Permission policy

Who may open the wizard and select a provider?

The recommended answer is to align with CC-11 Section 8:

- AI Invoice User may create a Statement, upload PDF, open the wizard, and
  start AI using only provider records they are authorized to select;
- AI Invoice Config Manager owns provider/configuration administration;
- AI Invoice Reviewer retains Confirm, Unconfirm, and Create Vendor Bill.

Provider selection authorization SHALL use the existing provider-config access
rules. CC-12 does not introduce a new provider-level authorization model.

No new permission group is authorized by this draft.

### OQ-12.6 Start atomicity

If wizard `Start` fails at any point, shall Task creation, relation writes,
ParseAttempt creation, and launch-side effects roll back together?

The required contract direction is **YES**:

```text
Start failure -> no partially created Task, relation, or ParseAttempt
```

Any external provider or queue side effect MUST continue to follow existing
repository transaction and stale-event protections, including the existing
ParseService transaction boundary and queue stale-worker handling defined by
CC-10/CC-11. CC-12 does not invent a new external-rollback mechanism.

### OQ-12.7 Statement already has a Task

When a Statement already has a Task, what shall `Start AI` do?

Options:

1. Refuse to open the wizard because the existing Task is the only execution;
2. Reopen the wizard for a rerun using the original Task configuration;
3. Open another explicitly defined rerun surface.

Recommended answer: when a Statement already has a Task, `Start AI` SHALL NOT
reopen the configuration wizard. The command SHALL be hidden or disabled with
an explanation, and any supported rerun SHALL launch directly with the
original Task configuration. A different provider or execution mode requires
the separately approved `Retry with another provider` contract.

## 10. Test Plan

The implementation test plan MUST include, at minimum:

1. Clicking Start AI opens the wizard and creates no Task.
2. Cancelling the wizard creates no Task and no ParseAttempt.
3. Selecting a provider and asynchronous mode, then clicking Start, writes the
   selected provider and `synchronous_parse = False` to the Task.
4. Selecting synchronous mode writes `synchronous_parse = True`.
5. The first launch establishes both sides of the Statement/Task relation.
6. Task provider and execution mode are read-only after Task creation.
7. A normal rerun reuses the original provider and execution mode.
8. A normal rerun does not silently switch provider and does not create a
   second Task.
9. A wizard Start failure rolls back Task, relation, and ParseAttempt creation.
10. Provider visibility and selection enforce the approved permission and
    availability policy.
11. Invalid or unavailable provider configuration is surfaced explicitly and
    never replaced by an implicit fallback.
12. A user without provider-selection permission cannot see or select
    restricted provider records in the wizard.
13. A user without Statement-create permission cannot open the wizard.
14. Task detail exposes provider, mode, state, attempts, errors, queue
    diagnostics, audit, PDF, and Statement navigation.
15. CC-10 and CC-11 Confirm, Unconfirm, Create Bill, cancellation, transaction,
    idempotency, company isolation, and security regressions remain green.
16. Existing legacy Task states, provider selection values, and Task-first
    compatibility records remain readable.
17. Double-clicking wizard Start creates exactly one Task and one ParseAttempt.
18. A Task created before CC-12 remains readable and its Task detail form
    renders without requiring wizard-created provider or mode metadata.
19. After a rolled-back wizard Start, the Statement remains eligible to start
    AI again without manual cleanup.

## 11. Migration and Rollback

### 11.1 Migration

The preferred implementation is a transient wizard that writes the selected
values to the existing Task fields at launch. No new persistent wizard
configuration data is authorized by this draft.

Existing Tasks and historical selection values MUST remain readable. No
semantic reconstruction or destructive migration is permitted.

Any schema change discovered during implementation preparation MUST be reported
as a separate migration decision before coding. It MUST NOT be inferred from
the existence of this wizard contract.

### 11.2 Rollback

An online rollback SHALL disable the wizard-based configurable launch behavior
while preserving existing CC-10/CC-11-compatible Task, Statement,
ParseAttempt, and audit data.

Rollback MUST NOT:

- create fake Tasks;
- delete Task-less Statements;
- delete source PDFs;
- rewrite historical provider or execution-mode facts;
- silently convert a started Task into an unstarted placeholder.

A full downgrade requiring schema removal or historical data transformation
requires a separately approved migration or database restore.

## 12. Relationship to CC-10 / CC-11

CC-12 extends CC-11 only at the pre-launch configuration boundary:

```text
CC-11: Statement -> Start AI -> create and start Task
CC-12: Statement -> Start AI wizard -> choose config -> create and start Task
```

CC-12 MUST NOT weaken or supersede the following:

- Statement owns Confirm and Unconfirm decisions;
- Statement owns Vendor Bill creation decisions;
- `Statement.vendor_bill_id` is the Vendor Bill authority;
- Task records technical AI execution facts;
- Task failure or cancellation is not Statement business failure;
- Statement 0..1 <-> 0..1 Task cardinality;
- Task/Statement bidirectional relation invariant;
- no Task before the user explicitly starts AI;
- no second Task for a rerun;
- existing queue, retry, transaction, idempotency, stale-event, security, and
  company-isolation constraints.

The existing Task form remains a technical detail page. It does not replace the
Statement workbench and does not become the first-launch entry point.

## 13. Authorization Gate

### 13.1 Current gate

Before the explicit approval recorded in this contract:

```text
IMPLEMENTATION_AUTHORIZED = NO
```

No implementation, schema modification, migration, test addition, or UI
change is authorized by this draft.

### 13.2 Required authorization state

The approved authorization state is:

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

That change MUST be explicit. It MUST NOT be inferred from discussion,
manual-verification results, or a partial decision.
