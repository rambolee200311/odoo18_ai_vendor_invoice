# CC-13 - Statement AI Task Workspace

## 1. Status

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

CC-13 replaces the cancelled CC-12 Wizard interaction model. The Frozen
Decisions in Section 9 authorize implementation only within the scope defined
below. They do not authorize unrelated coding, schema, migration, test, or UI
changes.

## 2. Context

CC-10 established:

```text
Statement owns business decisions.
Task records AI execution facts.
```

CC-11 established Statement-first entry:

```text
Create Statement
    ->
Upload supplier invoice PDF
    ->
Save Statement
    ->
Run AI from the Statement
```

Manual UAT rejected the CC-12 flow:

- a Wizard separated configuration from the Statement workbench;
- successful launch redirected to the standalone Task form;
- the user needs execution configuration and progress visible in the Statement;
- a new unsaved Statement is not expected to run AI before it has a database
  identity;
- uploaded PDF filename presentation also exposed a separate CC-11 defect.

CC-13 therefore defines a Statement-embedded AI/Task workspace that is
permanently available as a page inside the Statement form. The standalone Task
form remains a technical diagnostics surface, not the normal user entry point.

## 3. Product Intent

The user journey SHALL remain within the Statement workbench:

```text
New Statement
    ->
Upload PDF
    ->
Save Statement
    ->
Open AI / Task page
    ->
Choose Provider and Sync/Async
    ->
Run AI
    ->
Observe execution on the same Statement
    ->
Apply Candidate
    ->
Review / Confirm / Create Bill
```

The user MUST NOT be required to understand or navigate to a standalone Task
form to configure or launch the first AI execution.

## 4. Scope

### 4.1 Statement AI/Task page

The Statement form SHALL contain an AI/Task page or tab exposing, as applicable:

- current Source PDF and filename;
- Provider configuration;
- Execution Mode: synchronous or asynchronous;
- Run AI command;
- Task state;
- current or latest ParseAttempt information;
- parse error information;
- Apply Candidate command;
- technical Task navigation/details command.

Queue job identifiers, ProviderCall/PageArtifact details, retry and
stale-worker diagnostics, and full technical audit remain behind Technical
Details.

The exact page label MAY follow repository conventions, but it MUST be clearly
owned by the Statement form and MUST NOT require a separate standalone Task
form for normal use.

### 4.2 Run AI

The user SHALL save the Statement before running AI. CC-13 MUST NOT create a
Task, attachment relation, or ParseAttempt for an unsaved Statement.

When the user clicks `Run AI` from the Statement AI/Task page, the system SHALL:

1. validate the saved Statement, current PDF, company, permissions, and launch
   configuration;
2. create the one allowed Task if no Task exists;
3. copy the selected launch configuration into Task execution fields;
4. establish the CC-11 bidirectional Statement/Task relation;
5. create the first ParseAttempt;
6. start the existing ParseService;
7. remain on the Statement form and refresh the AI/Task page.

The operation MUST NOT automatically open the standalone Task form.

### 4.3 Task detail role

The standalone Task form SHALL remain available through an explicit technical
details action. It MAY expose full technical diagnostics, but it MUST NOT
replace the Statement AI/Task page as the normal launch or review surface.

## 5. Out of Scope

CC-13 MUST NOT authorize:

1. changing CC-10 Confirm, Unconfirm, or Vendor Bill authority;
2. redesigning the provider, ParseAttempt, ProviderCall, PageArtifact, queue,
   retry, or stale-event architecture;
3. adding Statement 1:N Task history;
4. adding a persisted `Statement.ai_status` abstraction merely for display;
5. implementing batch upload;
6. implementing `Retry with another provider` as a new workflow;
7. redesigning Candidate history, merge, or confidence semantics;
8. redesigning unrelated menus, dashboards, or navigation;
9. allowing AI execution from an unsaved Statement.

## 6. Behavioral Changes

### 6.1 Saved Statement lifecycle

An unsaved Statement MAY accept draft field edits and PDF upload according to
CC-11, but `Run AI` MUST remain unavailable until the Statement is saved.

The UI SHOULD explain that saving is required before AI execution. It MUST NOT
silently create a business record or Task merely to enable the button.

### 6.2 Launch configuration

Before a Task exists, the Statement AI/Task page SHALL expose launch
configuration for:

- Provider;
- Execution Mode.

These values represent the next Task launch configuration, not historical AI
execution facts.

At first launch:

```text
Statement launch configuration
    ->
Task.selected_provider_config_id
Task.synchronous_parse
```

After Task creation, the actual Task execution fields remain authoritative and
MUST be treated as read-only for that Task. The Statement AI/Task page SHALL
display `Task.selected_provider_config_id` and `Task.synchronous_parse` in the
same location as read-only execution facts. Statement launch-preference fields
MUST NOT remain a second editable authority.

### 6.3 Run AI result

For synchronous success, asynchronous queueing, running, error, parsed, or
cancelled outcomes, the user SHALL remain on the Statement form. The AI/Task
page MUST reflect the technical outcome without changing Statement business
authority.

### 6.4 Candidate application

Apply Candidate SHALL remain an explicit Statement-facing command. AI output
MUST NOT silently overwrite current Statement data.

## 7. UI Contract

The Statement form SHALL provide an AI/Task page with a layout equivalent to:

```text
Source PDF       invoice_123.pdf
Provider         [provider selection]
Execution Mode   [Synchronous / Asynchronous]

                 [Run AI]

Task State       Parsing / Parsed / Error / ...
Latest Attempt   ...
Error            ...

                 [Apply Candidate]
                 [Technical Details]
```

Required behavior:

- `Run AI` is visible/enabled only for a saved, eligible Statement;
- no Task exists before Run AI;
- the page does not redirect to standalone Task form after launch;
- `Technical Details` is an explicit optional navigation;
- Apply Candidate is available only when an applicable candidate exists;
- provider and execution mode controls follow the frozen pre/post-Task authority
  decision.

## 8. Data and Relation Contract

### 8.1 Existing Task execution facts

Task remains the authority for actual execution facts:

```text
Task.selected_provider_config_id
Task.synchronous_parse
Task.state
Task.current_parse_attempt_id
```

CC-13 MUST reuse these existing fields and MUST NOT reinterpret them as
Statement business decisions.

### 8.2 Statement launch configuration

Because Task does not exist before Run AI, the pre-launch Provider and Execution
Mode values SHALL persist in these Statement launch-preference fields:

```text
Statement.ai_launch_provider_config_id
Statement.ai_launch_synchronous_parse
```

Their semantics MUST be limited to the next Task launch configuration. They MUST
NOT be treated as completed execution facts, AI summary state, or a replacement
for Task authority.

### 8.3 Relation and atomicity

CC-11 cardinality and invariant remain unchanged:

```text
Statement 0..1 <-> 0..1 Task
statement.task_id == task
task.statement_id == statement
```

Run AI MUST establish both relations and the first ParseAttempt atomically
according to existing transaction and queue/stale-worker protections.

## 9. Frozen Decisions

### 9.1 Launch configuration authority

Before Task creation, these Statement fields are the editable next-launch
configuration:

```text
Statement.ai_launch_provider_config_id
Statement.ai_launch_synchronous_parse
```

They are launch preferences only. They MUST NOT represent completed execution
facts, AI summary state, or Task history.

At Run AI:

```text
Statement launch configuration
    ->
Task.selected_provider_config_id
Task.synchronous_parse
```

After Task creation, Task execution fields are authoritative. The Statement
workspace displays those Task fields read-only in the same configuration
location. The Statement launch fields MUST NOT remain a second editable
authority.

### 9.2 Provider policy

The Statement workspace SHALL show only providers accepted by the existing
provider availability, access, and company rules. No new provider permission
model is introduced.

The user MUST explicitly select a provider before the first Run AI. There MUST
be no implicit "first active provider" fallback and no silent substitution.

### 9.3 Execution mode

The default execution mode SHALL be Asynchronous:

```text
Asynchronous -> synchronous_parse = False
Synchronous  -> synchronous_parse = True
```

The user MAY switch to Synchronous before the first Run AI.

### 9.4 Run AI lifecycle

CC-13 changes the interaction surface, not the Task lifecycle:

```text
Unsaved Statement
    -> Run AI unavailable
Saved Statement with no Task
    -> first launch, create one Task
Existing supported rerunnable Task
    -> invoke existing CC-11 rerun behavior
Parsing / active execution
    -> reject duplicate Run AI
Parsed
    -> reject
Cancelled
    -> reject
Other unsupported state
    -> reject
```

An existing supported rerun MUST reuse the original Task, provider, and
execution mode. It MUST NOT create a second Task. The CC-11 state matrix
remains the lifecycle authority.

### 9.5 Concurrency

Run AI MUST be concurrency-safe at the server/database transaction boundary.
Concurrent or repeated Run AI requests for one Statement MUST result in at most:

- one Task;
- one Statement/Task relation pair;
- one first execution launch.

This guarantee MUST NOT rely only on disabling the UI button. The loaded-code
implementation MAY use row locks, unique constraints, transaction rechecks, or
the repository's equivalent safeguards.

### 9.6 Failure semantics

Before entering the existing ParseService execution lifecycle, configuration
validation, Task creation, launch-configuration copy, relation establishment,
and initial launch preparation form one atomic launch boundary.

Failure during this preparation MUST leave no partial Task or relation.

After entering ParseService, queue, or provider execution, timeout, HTTP error,
provider error, retry exhaustion, and worker failure MUST follow existing Task
and ParseAttempt technical failure semantics. These failures MUST preserve
genuine execution diagnostics and MUST NOT roll back the Task/Attempt as though
execution never occurred.

This uses the existing ParseService transaction boundary and queue
stale-worker handling; CC-13 introduces no new external rollback mechanism.

### 9.7 Workspace boundary

The inline Statement AI/Task page SHALL contain:

- current PDF and filename;
- Provider;
- Execution Mode;
- Run AI;
- Task state;
- latest/current Attempt summary;
- user-readable error summary;
- Apply Candidate;
- Technical Details navigation.

The standalone Task technical details surface SHALL contain, as applicable:

- full ParseAttempt history;
- ProviderCall and PageArtifact details;
- queue diagnostics;
- retry and stale-worker diagnostics;
- full technical audit;
- raw technical error details.

Run AI MUST never redirect automatically to the standalone Task form.

## 10. Test Plan

The eventual implementation MUST test at least:

1. New unsaved Statement cannot Run AI.
2. Saved Statement with PDF exposes the AI/Task page and Run AI.
3. Provider and execution mode are visible before first launch.
4. Run AI creates exactly one Task and one first ParseAttempt.
5. Statement/Task bidirectional relation is established.
6. Synchronous and asynchronous values map correctly.
7. Run AI remains on the Statement form for queued, running, success, error,
   parsed, and cancelled outcomes.
8. No second Task is created by duplicate Run AI or supported rerun.
9. Provider and execution mode follow the frozen post-launch authority rule.
10. Launch-preparation failure rolls back Task and relations and allows retry
    without manual cleanup; ParseService/provider/queue execution failures
    preserve the resulting Task and Attempt diagnostics.
11. Apply Candidate remains explicit and Statement-facing.
12. Technical Details navigation is optional and historical Task records remain
    readable.
13. The CC-11 UAT filename defect is corrected independently, and the CC-13
    workspace renders the corrected uploaded filename exactly.
14. CC-10 and CC-11 Confirm, Unconfirm, Create Bill, cancellation, transaction,
    security, company isolation, and idempotency regressions remain green.

## 11. Migration and Rollback

Any new Statement launch-preference fields require ordinary schema upgrade
handling. Existing Statements and Tasks MUST remain readable.

No semantic reconstruction or destructive backfill is authorized. Existing Task
execution fields remain the historical authority.

Online rollback means disabling the AI/Task page launch behavior while
preserving CC-10/CC-11-compatible Statements, Tasks, PDFs, ParseAttempts, and
audit data. It MUST NOT delete Task-less Statements, create fake Tasks, or
rewrite execution facts.

## 12. Relationship to CC-10 / CC-11

CC-13 supersedes CC-12 as the authorized product direction for AI launch
interaction. CC-12's Wizard and automatic Task-form redirect MUST NOT be used
as the target UX.

CC-13 preserves all non-conflicting CC-10/CC-11 constraints:

- Statement owns Confirm, Unconfirm, and Vendor Bill decisions;
- `Statement.vendor_bill_id` is Vendor Bill authority;
- Task records technical execution facts;
- Task failure/cancellation is not Statement business failure;
- Statement-first entry and saved-record lifecycle;
- `Statement 0..1 <-> 0..1 Task`;
- existing transaction, queue, retry, stale-worker, security, and
  company-isolation protections.

## 13. Authorization Gate

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```
