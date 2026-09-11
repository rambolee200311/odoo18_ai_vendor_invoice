# CC-11 - Statement-First Entry and AI Task Launch

## Status

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

This frozen contract authorizes implementation only within the scope and
decisions defined below. It does not authorize unrelated coding, schema,
migration, test, or UI changes.

## 1. Context

CC-10 established the following business boundary:

```text
Statement owns business decisions.
Task records AI execution facts.
```

CC-10 intentionally retained the existing compatibility entry in which a Task
creates the Statement. The user-facing requirement is now more specific:

```text
User creates Statement directly.
User uploads the supplier invoice PDF to Statement.
User starts an AI Task from Statement.
```

The user should not need to understand or create a Task before obtaining a
Statement workbench. AI is an optional assistant launched from that workbench.

This contract extends CC-10 toward a complete Statement-first entry flow. It
does not reopen CC-10's Confirm or Vendor Bill authority decisions.

## 2. Product Intent

The primary user object is one supplier invoice Statement. The intended user
journey is:

```text
Create Statement
    ↓
Upload or replace supplier invoice PDF
    ↓
Start AI parsing from Statement
    ↓
Observe AI execution from Statement
    ↓
Review or edit current Statement data
    ↓
Confirm Statement
    ↓
Create Vendor Bill
```

The AI Task is created as a technical execution context owned by this
Statement-facing flow. It is not the user's primary entry object.

The fixed cardinality for this contract is:

```text
Statement 0..1 ── 0..1 Task
```

Multiple Tasks per Statement, batch upload, and AI execution history redesign
are deferred.

## 3. Scope

### 3.1 In Scope

#### 3.1.1 Direct Statement creation

The system SHALL provide a supported Statement-facing create operation.

The operation MUST:

- create a draft Statement without requiring an existing Task;
- preserve existing Statement business validation;
- preserve company and access checks;
- make the new Statement immediately available as the user workbench;
- avoid creating a fake or placeholder AI result merely to satisfy legacy
  relationships;
- remain compatible with CC-10 Confirm and Create Bill commands.

#### 3.1.2 PDF upload from Statement

The Statement workbench SHALL provide a user-facing operation to upload a
supplier invoice PDF.

The operation MUST:

- accept only a valid supplier invoice PDF;
- preserve filename and attachment metadata;
- make the current PDF visible and downloadable from Statement;
- allow replacement only while the Statement has no Task;
- reject replacement after a Task exists in this contract, rather than silently
  reusing or invalidating Task history;
- reject an invalid file without changing the current valid PDF;
- preserve authorization and company isolation;
- define behavior when a Statement already has an active or completed Task.

#### 3.1.3 Start AI Task from Statement

The Statement workbench SHALL provide a command to start AI parsing for the
current PDF.

The command MUST:

- require a Statement with a valid current PDF;
- create the one allowed technical Task when no Task exists;
- associate the execution with the Statement;
- create the Task only when the user explicitly clicks Start AI;
- never create a Task merely because a Statement or PDF was created or saved;
- preserve queue, retry, stale-worker, transaction, and idempotency safety;
- expose technical progress and failure without changing Statement business
  authority;
- prevent accidental duplicate active executions for the same request;
- preserve the existing supported rerun behavior only for Task states
  explicitly allowed by the frozen Start AI state matrix;
- never create a second Task for a rerun;
- treat `cancelled` and `parsed` Tasks as not restartable in CC-11.

#### 3.1.4 AI result application boundary

AI execution results MUST NOT silently replace user-edited Statement data.

The implementation MUST preserve an explicit result-application boundary:

- an AI result may be presented as a candidate;
- applying a candidate remains subject to the approved Candidate contract;
- user edits and current Statement data remain distinguishable from AI output;
- rerunning AI MUST define whether the result is previewed, merged, or applied;
- no rerun may silently destroy confirmed or user-maintained business data.

The Statement page SHALL expose an apply-candidate command. That command may
delegate to the existing Task/ParseAttempt application logic, but the user
must not be sent to the Task page. No new Candidate aggregate, history model,
merge engine, or confidence-based merge is introduced by this contract.

#### 3.1.5 Statement workbench commands

The Statement page SHALL expose, as applicable:

- Create Statement;
- Upload PDF, and replace it only before Task creation;
- Start AI;
- show AI execution diagnostics;
- edit current Statement data;
- Confirm;
- Unconfirm where valid;
- Create Vendor Bill where valid.

Task remains available as a technical diagnostic record, not as the required
user entry point.

### 3.2 Compatibility requirements

The implementation MUST preserve:

- CC-10 Statement Confirm authority;
- CC-10 Statement Vendor Bill authority;
- existing review completeness and `line.checked` invariants;
- existing Vendor Bill duplicate and transaction protections;
- queue and stale-worker protections;
- historical Task state values and `Task.human_reviewed` field readability;
- existing audit and security constraints unless explicitly superseded here.

The existing groups SHALL be reused without adding a new permission group:

- current AI Invoice User permissions for Statement creation, PDF upload, and
  Start AI;
- current AI Invoice Reviewer permissions for Confirm, Unconfirm, and Create
  Vendor Bill;
- current AI Invoice Config Manager permissions for provider/configuration.

## 4. Out of Scope

The following are not authorized by this draft unless explicitly added during
approval:

1. Rewriting the AI provider pipeline.
2. Replacing ParseAttempt, ProviderCall, PageArtifact, or canonical result
   architecture without a separate decision.
3. Redesigning Vendor Bill accounting behavior.
4. Adding a new `Statement.ai_status` persistence abstraction merely for UI.
5. Changing Confirm or Create Bill back to Task authority.
6. Removing legacy Task fields or historical selection values.
7. Introducing a new generic service framework without repository evidence.
8. Changing queue concurrency or stale-event semantics.
9. Implementing unrelated dashboard or menu redesign.

## 5. Behavioral Changes

### 5.1 Statement creation

Before this contract, Statement creation is effectively gated by a Task
aggregate. After implementation, a user may create an empty draft Statement
as the starting point for the invoice workbench.

The Statement may remain incomplete until the user enters data manually or
starts AI parsing. Incomplete data MUST prevent Confirm and Create Bill using
the existing business validation.

### 5.2 PDF lifecycle

The user may upload a PDF after creating the Statement. A PDF may be replaced
only before a Task exists. Once a Task has been created, PDF replacement is
rejected by this contract so the existing 0..1 Task model cannot silently
associate an execution with a different input document.

Before Task creation, replacement simply replaces the Statement's current PDF.
After Task creation, replacement is rejected. CC-11 therefore introduces no
active-execution cancellation, candidate-staleness, Task reassignment, or
execution-history semantics for PDF replacement.

### 5.3 AI launch lifecycle

Starting AI from Statement is a technical command. It MUST NOT confirm the
Statement, change Statement business state, create a Vendor Bill, or mark the
Statement as reviewed.

AI error or cancellation MUST leave the Statement available for manual editing
and later business commands.

### 5.4 Manual-only path

A Statement with no Task MUST remain a valid draft workbench. The user may
complete it manually, subject to current Statement validation, without being
forced to run AI.

## 6. UI Contract

The primary navigation and form experience SHALL be Statement-first:

```text
Supplier Invoice Statements
    └── New Statement
          ├── Upload PDF
          ├── Start AI
          ├── Review current data
          └── Confirm / Create Bill
```

The UI MUST NOT require users to understand the term “Task” to complete the
normal workflow. Technical Task information may be available through a
diagnostics link or technical tab.

The UI MUST clearly distinguish:

- no PDF uploaded;
- AI not started;
- AI running;
- AI failed or cancelled;
- AI result available;
- current Statement data;
- current Vendor Bill relation.

The exact display mechanism is not frozen as a new persisted `ai_status` field
by this draft.

## 7. Data and Relation Contract

The implementation MUST document and test the selected relation model for:

- Statement to Task;
- Statement to ParseAttempt;
- Statement to current PDF;
- current applied candidate;
- current Vendor Bill.

At minimum:

- a Statement without a Task MUST be representable;
- a Task MUST identify the Statement execution context it serves;
- a Statement MUST NOT accidentally use a result generated for another
  Statement or another current PDF;
- Statement Bill authority remains `Statement.vendor_bill_id`;
- Task Bill data remains compatibility-only.

Existing ParseAttempt diagnostics/history remain available through the current
Task. CC-11 does not introduce Statement-level execution history.

## 8. Frozen Decisions

The following decisions are fixed for CC-11:

1. **PDF authority**

   ```text
   Statement.source_pdf_attachment_id
   ```

   is the authoritative current supplier invoice PDF. At Task creation,
   `Task.source_pdf_attachment_id` MUST reference the same attachment as
   `Statement.source_pdf_attachment_id`. The Task field is an execution-input
   compatibility reference, not the business PDF authority. ParseService may
   continue reading the Task field in CC-11; provider-input ownership is not
   redesigned.

2. **Task cardinality**

   ```text
   Statement 0..1 ── 0..1 Task
   ```

   One Statement has at most one Task in CC-11. Multiple Tasks per Statement,
   batch upload, and execution-history redesign are deferred.

3. **Task creation timing**

   A Task is created only when the user clicks **Start AI**. Creating or
   saving a Statement, or uploading a PDF, MUST NOT create a Task.

4. **PDF replacement**

   A PDF may be uploaded or replaced while the Statement has no Task. Once a
   Task exists, replacement is rejected in CC-11. CC-11 does not reset a Task,
   create Task history, or silently reuse an old result for a new PDF.

5. **Candidate Apply**

   Apply Candidate moves to a Statement-facing command boundary:

   ```text
   Statement.action_apply_ai_candidate(...)
       ↓
   existing Task / ParseAttempt application logic
   ```

   Candidate models, ParseAttempt ownership, and application semantics are not
   redesigned. The user remains on the Statement page.

6. **Manual data and AI merge**

   AI output is never silently merged into Statement data. The only supported
   path is:

   ```text
   AI completed → candidate available → user explicitly applies candidate
   ```

   No fill-empty-only, confidence merge, automatic overwrite, or smart merge is
   introduced.

7. **Permissions**

   Existing groups are reused:

   - AI Invoice User: create Statement, upload PDF, Start AI;
   - AI Invoice Reviewer: Confirm, Unconfirm, Create Vendor Bill;
   - AI Invoice Config Manager: provider/configuration administration.

   No new permission group is introduced by CC-11.

8. **Audit**

   Before Task creation, Statement-facing events use Statement chatter or
   existing message tracking and do not create or require
   `vendor.invoice.import.log`. This applies to manual-only Confirm,
   Unconfirm, and Create Vendor Bill.

   After Task creation, technical AI events continue using the existing
   required `import.log.task_id` relation. CC-11 does not create a fake Task
   for audit compatibility, add `statement_id` to the audit model, or migrate
   historical audit rows.

9. **Statement source ParseAttempt semantics**

   `Statement.source_parse_attempt_id` becomes optional.

   - a new Statement has `NULL`;
   - a manual-only Statement remains `NULL`;
   - starting AI without applying a candidate leaves it `NULL`;
   - a successful ParseAttempt that has not been applied leaves it `NULL`;
   - explicit Apply Candidate sets it to the applied ParseAttempt;
   - rerun/retry MUST NOT silently change it.

   The field means “the ParseAttempt whose candidate was last explicitly
   applied to the current Statement”, not “the latest AI execution”.

10. **Statement company authority**

   `Statement.company_id` becomes Statement-owned and MUST NOT depend on Task
   existence.

   - direct creation takes the current authorized company context;
   - existing company isolation and access rules remain mandatory;
   - a Start AI-created Task MUST inherit the Statement company;
   - cross-company execution is rejected;
   - users cannot choose an independent Task company.

11. **Start AI state matrix**

   CC-11 creates at most one Task:

   | Current Statement/Task state | Start AI behavior |
   |---|---|
   | no Task | create the Task atomically and start its first ParseAttempt |
   | Task `to_parse` | reject as already queued/not yet started; do not enqueue again |
   | Task `error` | use the existing Task rerun command |
   | Task `awaiting_review` | use the existing legacy-compatible rerun command |
   | Task `parsing` | reject duplicate active start |
   | Task `parsed` | reject; no new Task or new execution is introduced |
   | Task `cancelled` | reject; restart/reset is deferred |

   CC-11 does not invent a new Task reset transition. The loaded existing
   rerun command remains the only supported user-triggered rerun path.

12. **Bidirectional relation invariant**

   When a Task exists for a Statement, both relations MUST agree:

   ```text
   statement.task_id == task
   task.statement_id == statement
   ```

   The Statement-facing Start AI transaction MUST establish both relations
   atomically. Normal UI MUST NOT allow users to assign either relation
   independently. Partial or cross-linked relations are invalid.

The following items remain explicitly deferred rather than open decisions:

- batch upload;
- Statement 1:N Task;
- PDF replacement after Task creation;
- AI execution history redesign;
- Candidate aggregate/history redesign;
- full audit-anchor redesign.

No implementation should silently choose among these alternatives.

## 9. Test Plan

The approved implementation SHALL add tests for:

1. AI Invoice User can create a draft Statement without a Task.
2. Unauthorized user cannot create or edit a Statement.
3. Statement can upload a valid PDF.
4. Invalid PDF upload is rejected without replacing the current PDF.
5. Statement can start an AI Task from its current PDF.
6. Starting AI without a PDF is rejected.
7. Duplicate active AI start is rejected; existing `error` and
   `awaiting_review` rerun behavior follows the frozen state matrix.
8. AI error leaves Statement editable.
9. AI cancellation leaves Statement editable and does not change Statement
   business state.
10. Manual-only Statement can be completed, confirmed, and used to create a
    Vendor Bill after valid review.
11. Replacing a PDF before Task creation is allowed, while replacement after
    Task creation is rejected and cannot make stale AI output current.
12. Existing CC-10 Confirm, Bill, cancellation, transaction, and security
    regressions remain green.

## 10. Migration and Rollback

CC-11 necessarily changes the Statement model contract: the current Task
required relation, Task-derived PDF fields, and Task-derived company field must
be made compatible with a Task-less Statement. The existing `unique(task_id)`
constraint MUST first be verified with nullable `task_id`; it MUST NOT be
removed merely because direct Statement creation is introduced.

Schema evolution required by the frozen CC-11 model is authorized by CC-11.
Historical business-data transformation is not implicitly authorized. Before
production implementation:

- inspect actual field storage and existing records;
- determine whether deterministic PDF/company backfill is required;
- report the exact bounded compatibility migration.

A deterministic bounded backfill requires explicit approval before execution.
Semantic reconstruction, destructive migration, or ambiguous historical
mapping is a STOP condition.

Rollback means disabling Statement-first entry and AI-launch behavior while
preserving a CC-11-compatible schema and data. Rollback MUST NOT require:

- deleting Task-less Statements;
- creating fake Tasks;
- deleting Statement-owned PDFs;
- reverting company/PDF fields to Task-required authority.

Rollback MUST preserve:

- existing Statement data;
- current Vendor Bill links;
- ParseAttempt history;
- source PDF attachments;
- active queue executions.

A full database downgrade to the pre-CC-11 schema is not an online rollback
and requires a separately tested downgrade migration or database restore.

## 11. Relationship to CC-10

CC-11 extends CC-10 only at the entry and AI-launch boundary.

CC-10 remains authoritative for:

- Statement Confirm;
- Statement Unconfirm;
- Vendor Bill creation;
- `Statement.vendor_bill_id`;
- Task failure/cancellation independence;
- legacy Task compatibility.

CC-11 MUST NOT weaken those decisions.

## 12. Authorization Gate

The Frozen Decisions in Section 8 and the loaded-code closure in Section 13
have been accepted. This contract is authorized for implementation:

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

## 13. Loaded-Code Decision Closure

This section records a read-only loaded-code inspection completed before CC-11
authorization. It is an implementation-impact map, not an authorization to
change code or data.

### 13.1 Statement `task_id`

`addons/ai_vendor_invoice/models/statement.py` defines:

```python
task_id = fields.Many2one(
    "vendor.invoice.import.task",
    required=True,
    ondelete="cascade",
)
```

`company_id`, `source_pdf_attachment_id`, `source_pdf_filename`, and
`review_warnings` are currently derived from this Task relation.

### 13.2 Task `statement_id`

`addons/ai_vendor_invoice/models/import_task.py` defines:

```python
statement_id = fields.Many2one(
    "vendor.invoice.statement",
    ondelete="restrict",
)
```

It is not currently required at the database field level. The model retains
`statement_required=True` as an application-level compatibility indicator.

### 13.3 Statement unique Task constraint

The constraint is in `models/statement.py`:

```python
_sql_constraints = [
    (
        "task_unique",
        "unique(task_id)",
        "A task can have only one human Statement.",
    ),
]
```

This is the current physical reason the loaded model expresses a one-Task to
one-Statement relationship from the Statement side.

### 13.4 Task-owned PDF dependencies

`Task.source_pdf_attachment_id` is the current PDF field. Strong dependencies
include:

- Task upload/create validation and checksum uniqueness in
  `models/import_task.py`;
- Task source-PDF action and attachment metadata;
- Statement `source_pdf_attachment_id` and filename related fields;
- Statement chatter attachment helper, which reads
  `statement.task_id.source_pdf_attachment_id`;
- ParseAttempt `source_pdf_attachment_id`, related to
  `attempt.task_id.source_pdf_attachment_id`;
- Bill attachment copying in `services/bill_creator.py`;
- task/statement views and source-PDF actions.

Therefore, direct Statement creation cannot be implemented by only relaxing
the Statement `create()` override.

### 13.5 ParseService PDF source

`services/parse_service.py` obtains the provider input through:

```python
prepare_provider_input(
    task.source_pdf_attachment_id,
    mode=input_mode,
)
```

The current ParseService entry remains Task-based. CC-11 must introduce a
Statement-facing launch boundary without silently duplicating PDF authority.

### 13.6 Apply Candidate path

The current candidate path is Task/Attempt-owned:

1. `Task.action_apply_ai_candidate(attempt_id, statement_payload)` loads the
   ParseAttempt and verifies `attempt.task_id == self`.
2. It requires the current attempt to equal
   `Task.current_parse_attempt_id`.
3. It creates or updates the Statement through `Task.statement_id`.
4. `Statement.action_apply_ai_candidate_from_statement()` delegates back to
   `Statement.task_id`.

This confirms that Candidate ownership and application are a separate
decision. CC-11 must explicitly decide whether to preserve this boundary or
move it; it must not happen as an incidental side effect of direct creation.

### 13.7 Audit dependency

`models/import_log.py` defines `task_id` as:

```python
fields.Many2one(
    "vendor.invoice.import.task",
    required=True,
    ondelete="cascade",
)
```

Current Statement review, Bill creation, Task cancellation, timeout, and
observability logging all create audit records with `task_id`. The audit model
has no `statement_id` anchor. CC-11 must choose a compatibility strategy
before allowing a Statement-only operation to emit audit events.

### 13.8 Direct Statement creation blockers

The following loaded-code constraints currently block direct creation:

1. `Statement.task_id` is required.
2. `Statement.source_parse_attempt_id` is required and has
   `ondelete="restrict"`.
3. `Statement.company_id` is related to `task_id.company_id`.
4. Statement `create()` raises `AccessError` and only `_aggregate_create()`
   can persist a record.
5. `_aggregate_create()` and `_statement_values()` currently expect a Task
   relation.
6. Statement source PDF and filename are related to Task.
7. Statement source-PDF chatter attachment reads through Task.
8. The `unique(task_id)` SQL constraint encodes the current one-to-one
   relationship.
9. The current candidate creation path requires a successful ParseAttempt
   belonging to a Task.
10. Audit records require `task_id`.

### 13.9 Decision closure

The loaded-code inspection originally identified the following decisions as
blockers before authorization. Those decisions are now resolved by Section 8
and Section 10:

- PDF authority: Frozen Decision 1;
- Statement/Task relation: Frozen Decisions 2 and 12;
- Statement/ParseAttempt relation: Frozen Decision 9;
- `unique(task_id)`: Section 10 compatibility verification; no automatic
  removal is authorized;
- Task launch/rerun: Frozen Decisions 3 and 11;
- Audit compatibility: Frozen Decision 8;
- Candidate application: Frozen Decision 5.

This loaded-code section records evidence only. It does not introduce
additional open decisions or override the Frozen Contract.

No production code, schema, migration, or database change is authorized beyond
the implementation scope of this frozen contract.
