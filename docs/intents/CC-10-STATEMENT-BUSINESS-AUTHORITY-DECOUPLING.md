# CC-10 - Statement Business Authority Decoupling

## Status

```text
APPROVED FOR FREEZE AND IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

This document is a coding contract draft. It authorizes no production coding,
schema change, migration, test change, or documentation change outside this
new CC-10 document.

## 1. Context

The preceding **Statement-first Architecture Spike** completed the required
loaded-code investigation and selected:

```text
C. PARTIAL DECOUPLING
```

The Spike established that the current implementation still makes the
Statement dependent on the Task for creation, PDF access, command routing,
and Vendor Bill creation. The Spike also established that the user-facing
business object is the Statement, while the Task is an AI execution record.
This contract uses that conclusion as a decision baseline and does not
re-argue the Spike findings.

The business interpretation fixed by this contract is:

```text
The user operates on a Statement.
An AI Task is a failure-tolerant, repeatable technical assistance job.
```

The answer to the core product question is:

```text
Business semantics: YES.
This implementation: PARTIAL DECOUPLING.
Full Statement-first architecture: deferred to a later contract.
```

### 1.1 CC-09 disposition

CC-09 originally addressed Task and Statement state-machine optimization. The
Spike showed that the business values in `Task.state`, especially
`awaiting_review` and `bill_generated`, are symptoms of the architectural
coupling rather than states that should receive further workflow optimization.
The technical success value `parsed` remains useful as the current successful
AI execution state.

CC-09 is therefore:

```text
SUPERSEDED BY CC-10
```

This does not mean CC-09 is void or that its historical implementation is
deleted. CC-10 supersedes CC-09 as the implementation authority for Statement
review and Vendor Bill business authority. Where CC-09 conflicts with CC-10
on business authority, CC-10 prevails. Non-conflicting review-integrity,
transaction, idempotency, and security constraints remain applicable unless
explicitly superseded. CC-09 itself must not be modified by this contract.

### 1.2 CC-10 positioning

CC-10 is not a user-entry rewrite. It is a **Statement business authority
decoupling** contract.

The user-entry simplification is a result of the behavioral decoupling:

```text
Statement owns business decisions.
Task records AI execution facts.
```

## 2. Scope

### 2.1 In Scope

#### 2.1.1 Confirm no longer routes through Task

Confirm SHALL use a Statement-facing command or service.

The preferred shape is:

```text
StatementService.confirm(statement)
```

or an equivalent Statement-owned command boundary.

The Confirm implementation:

- MUST NOT route through `task.action_confirm_statement()`;
- MUST NOT read `Task.state` as a business precondition;
- MUST validate the current Statement business data;
- MUST validate the current Statement line review completeness;
- MUST preserve the existing Statement `draft -> confirmed` behavior;
- MUST keep the current `line.checked` and `all_checked` review invariant;
- MUST keep existing authorization and transactional behavior.

The existence of a Task may remain as a compatibility relationship in this
contract, but it must not determine whether a valid Statement can be
confirmed.

#### 2.1.2 Create Vendor Bill no longer routes through Task

Vendor Bill creation SHALL use a Statement-facing command or service.

The preferred shape is:

```text
StatementService.create_bill(statement)
```

or an equivalent Statement-owned service boundary.

The Bill Creator:

- MUST accept a Statement as its business input;
- MUST NOT require a Task as its business input;
- MUST remove the hard precondition `task.state != "parsed"`;
- MUST read Vendor Bill data only from the current Statement data;
- MUST require a confirmed Statement;
- MUST require valid current Statement lines and review completeness;
- MUST require no current `Statement.vendor_bill_id`;
- MUST write only the Statement Bill link;
- MUST preserve the existing transactional and duplicate-protection behavior.

The Bill Creator MUST NOT use `Task.human_reviewed`, legacy Task state values,
or a Task-owned writable Vendor Bill relation as business preconditions.

#### 2.1.3 AI Task failure and cancellation independence

When a Statement already exists, an AI Task entering `error` or `cancelled`
MUST NOT make that Statement unusable.

After an AI error or cancellation, the Statement MUST remain able to:

- continue draft editing;
- complete line checks;
- be confirmed;
- create a Vendor Bill after confirmation.

Task cancellation SHALL not change `Statement.state`, clear Statement data,
or create a Statement cancellation transition.

#### 2.1.4 Narrow the Statement command boundary

Confirm and Create Bill MUST no longer be implemented as Task aggregate
commands.

Apply Candidate remains routed through the existing Task command boundary in
this contract. Its extraction is explicitly deferred to CC-11 and MUST NOT be
expanded into CC-10.

#### 2.1.5 Deprecate legacy Task business values

The following selection values remain for historical compatibility and are
deprecated:

```text
awaiting_review
bill_generated
```

The current technical success value remains active:

```text
parsed = the AI execution completed successfully and produced parse results.
```

`parsed` MUST NOT mean that a user reviewed the Statement, that the Statement
is confirmed, or that a Vendor Bill exists.

`awaiting_review` and `bill_generated` MUST be documented in the field
definition as legacy or deprecated compatibility values, including help text
that explains that they are not current Statement business preconditions.

Implementation rules:

- all selection values MUST remain readable;
- historical records MUST remain loadable;
- new business code MUST NOT read these values as Confirm or Create Bill
  preconditions;
- every retained read of `awaiting_review` or `bill_generated` MUST carry a
  legacy compatibility comment;
- new technical execution code MAY use `parsed` to represent successful
  execution, but MUST NOT use it as a Statement business precondition;
- this contract does not remove or rename the field or selection values.

#### 2.1.6 Deprecate `Task.human_reviewed`

`Task.human_reviewed` is a legacy compatibility field.

New Confirm, Unconfirm, and Create Bill logic:

- MUST NOT read it;
- MUST NOT write it;
- MUST NOT use it to derive Statement business authority.

The field remains available for historical data reading. Its field definition
MUST include a deprecated comment and help text describing its compatibility
role.

#### 2.1.7 Converge Vendor Bill authority

The Bill relationship MUST have one business authority:

```text
Statement.vendor_bill_id
```

`Task.vendor_bill_id` MUST remain only a related, read-only compatibility
surface. It MUST NOT become an independent writable authority.

The Bill Creator MUST write the Statement relation only.

#### 2.1.8 Adjust the UI boundary

The Statement page SHALL be the primary business workspace for:

- current invoice data;
- line review;
- Confirm;
- Create Bill;
- current Bill traceability.

The Task page SHALL be treated as a technical diagnostic entry point for
authorized users. The Statement page command flow MUST NOT require a user to
understand or navigate the Task lifecycle.

The existing Task technical entry may remain for compatibility and diagnostics.

### 2.2 Out of Scope

The following are explicitly out of scope for CC-10:

1. Statement 1:N Task.
2. PDF ownership migration; Statement continues to access the PDF through the
   existing Task relationship in this contract.
3. Creating a Statement without a Task or implementing the manual-only flow.
4. Extracting Apply Candidate from the Task command boundary.
5. Adding `statement_id` as an audit anchor.
6. Deleting any field.
7. Rewriting the AI pipeline.
8. Modifying ParseAttempt, ProviderCall, or PageArtifact.
9. Modifying the CC-09 document itself.

All of these items are deferred to CC-11 or a later architecture decision.
They MUST NOT be implemented as incidental parts of CC-10.

## 3. Non-Goals

CC-10 does not make Statement creation fully independent from Task.

CC-10 does not solve PDF ownership. The existing Task-owned PDF relationship
remains in place.

CC-10 does not implement the manual-only flow.

CC-10 does not change Task/Statement cardinality. The current compatibility
relationship remains in this contract.

CC-10 does not redesign ParseAttempt, ProviderCall, PageArtifact, queue
execution, or the AI provider pipeline.

CC-10 does not delete legacy state values or compatibility fields.

## 4. Behavioral Changes

### 4.1 Confirm decoupling

Before:

```text
Statement form
    -> Task aggregate command
    -> Statement confirmation
```

After:

```text
Statement form
    -> Statement-facing confirm command/service
    -> Statement confirmation
```

Confirm MUST use the current Statement as the authority for:

- draft status;
- required business data;
- current lines;
- current line checks;
- projection consistency;
- review completeness.

Confirm MUST NOT use:

- `Task.state`;
- `Task.human_reviewed`;
- ParseAttempt success as a business prerequisite;
- current Task parsing display status.

### 4.2 Create Bill decoupling

Before:

```text
Statement
    -> Task
    -> Bill Creator
```

After:

```text
Statement
    -> Statement-facing Bill Creator
```

Create Bill MUST preserve the existing successful business outcome:

```text
Statement.confirmed
Statement.vendor_bill_id = created bill
```

It MUST NOT introduce a new Statement state and MUST NOT update the Task into
a Bill lifecycle state.

### 4.3 Narrow Task Cancel semantics

Task Cancel SHALL mean:

```text
Cancel this AI execution context.
```

It SHALL NOT mean:

```text
Cancel the supplier invoice business document.
```

Task Cancel:

- MUST only affect the AI execution record and its in-flight execution facts;
- MUST apply only to a cancellable, incomplete execution;
- MUST NOT cancel an execution already in the successful `parsed` state;
- MUST NOT rewrite a completed AI result as if it had not occurred;
- MUST NOT change `Statement.state`;
- MUST NOT clear Statement fields or lines;
- MUST NOT prevent Statement editing;
- MUST NOT prevent Statement Confirm;
- MUST NOT prevent Statement Create Bill.

### 4.4 Statement command boundary

The following commands are Statement-owned for CC-10:

```text
Confirm
Create Bill
Unconfirm, where applicable to the existing review lifecycle
```

The following remains Task-owned for compatibility in CC-10:

```text
Apply Candidate
Run AI
Parse execution controls
```

This split is intentional. CC-10 removes business authority from Task without
expanding into the deferred Candidate Apply redesign.

### 4.5 Task state value deprecation

`awaiting_review` and `bill_generated` remain readable legacy values only.
`parsed` remains the current technical success state for an AI execution.

They MUST NOT be used to decide:

- whether Statement can be confirmed;
- whether Statement can be unconfirmed;
- whether a Vendor Bill can be created;
- whether Statement data is editable after an AI error or cancellation;
- whether the current Bill link exists.

The legacy values MAY remain visible in technical diagnostics for historical
records, but they are not current business lifecycle authority. The `parsed`
technical success state MAY remain visible for current execution diagnostics,
but it is not current Statement business authority.

### 4.6 `human_reviewed` deprecation

The authoritative review facts are:

```text
Statement.state
Statement.line_ids.checked
Statement.all_checked
```

`Task.human_reviewed` is retained only for compatibility and historical
inspection. New business commands MUST neither read nor write it.

### 4.7 Vendor Bill link convergence

The authoritative relation is:

```text
Statement.vendor_bill_id
```

The Task relation is compatibility-only and read-only:

```text
Task.vendor_bill_id = related(Statement.vendor_bill_id)
```

Bill creation, current Bill display, and Bill cancellation handling MUST use
the Statement authority.

## 5. UI Changes

### 5.1 Statement as primary entry

The Statement list and form remain the primary business workspace. The form
MUST make the following available without requiring Task navigation:

- current Statement data;
- line review and `all_checked`;
- Confirm;
- Unconfirm where valid;
- Create Bill;
- Vendor Bill link.

### 5.2 Task as technical diagnostic entry

The Task list and form MAY remain available to authorized technical or
reviewer users for:

- provider diagnostics;
- ParseAttempt history;
- queue status;
- error details;
- technical audit data.

Task state labels MUST not be presented as the business approval status of the
Statement.

### 5.3 Compatibility entries

Existing Task menu/action and technical Task form remain available for
compatibility. They are not removed or renamed by CC-10.

## 6. Compatibility

### 6.1 `human_reviewed`

Historical values remain readable. No new Confirm, Unconfirm, or Create Bill
logic may depend on or synchronize this field.

### 6.2 Vendor Bill relation

`Statement.vendor_bill_id` remains the authority. The Task related field
continues to provide a read-only compatibility surface for existing technical
views and callers.

### 6.3 Legacy Task state values

Historical `awaiting_review` and `bill_generated` values remain loadable and
readable as deprecated compatibility values. `parsed` remains loadable and
usable as the technical success state of an AI execution. None of these
values is a Statement business precondition.

### 6.4 Historical data

Historical records are not migrated by CC-10. Existing relationships and
legacy values must remain readable after the implementation.

## 7. Test Plan

The implementation must add or update tests for the following behavior.

| Scenario | Expected result |
|---|---|
| Confirm with a valid Statement while Task has a legacy/non-`parsed` state | Passes |
| Confirm command does not read Task state | Passes |
| Create Bill with a confirmed valid Statement while Task has a legacy/non-`parsed` state | Passes |
| Create Bill reads current Statement data only | Passes |
| AI Task enters `error` after a Statement exists | Statement remains editable |
| AI Task enters `error` after review is complete | Statement can Confirm |
| AI Task enters `error` after confirmation | Statement can Create Bill |
| AI Task is cancelled after a Statement exists | Statement remains usable |
| Task Cancel changes no Statement business state | Passes |
| `human_reviewed` contains an old value | New workflow ignores it |
| Task `vendor_bill_id` is read-only related compatibility data | Passes |
| Statement `vendor_bill_id` is the only Bill authority | Passes |
| Manual-only flow without a Task | Not covered by CC-10; deferred to CC-11 |

Tests MUST verify that invalid business data, incomplete line checks, access
rules, duplicate Bill protection, and transaction rollback remain enforced.

## 8. Migration

Expected business-data migration classification:

```text
NO BUSINESS DATA MIGRATION EXPECTED
```

CC-10 retains existing fields, legacy selection values, historical
relationships, Task-owned PDF access, and the current compatibility Bill
field. However, changing an existing independent Task Bill field to a
related/read-only compatibility field requires loaded-code and existing-data
verification before implementation.

Migration impact for that field conversion is therefore:

```text
UNKNOWN - EXPECTED LIGHT OR NONE
```

Implementation preparation MUST verify historical consistency between Task and
Statement Bill links, including historical `bill_generated` records whose
Statement link is empty. If a **LIGHT MIGRATION** is unavoidable, it must be
documented separately before implementation continues. It must not be
silently introduced as part of coding.

No migration script is authorized by this draft.

## 9. Rollback Plan

If CC-10 must be rolled back:

1. Restore the previous Statement-facing command routing.
2. Restore the previous Task-based Bill Creator entry point.
3. Restore the previous Task state precondition behavior.
4. Keep legacy field values and historical records unchanged.
5. Keep `Statement.vendor_bill_id` and the Task related compatibility field
   consistent.
6. Do not delete or rewrite historical Task, Statement, Attempt, or Bill data.

Rollback must be performed as a controlled code rollback. It must not use a
destructive database reset or discard unrelated workspace changes.

## 10. Open Questions

The following questions remain open and are intentionally not hidden:

1. Which existing Statement-facing service naming and module location best
   matches repository conventions?
2. Can the existing Bill attachment-copy behavior be invoked from a
   Statement-facing service without changing PDF ownership in this contract?
3. What is the exact compatibility behavior for historical records whose Task
   state is `bill_generated` but whose Statement Bill link is empty?

These questions must be resolved during implementation design or a follow-up
contract. They do not authorize scope expansion into the out-of-scope items.

## 11. Relationship to CC-11

CC-11 or a later contract must handle the remaining P1 architecture work:

1. Statement independent creation and the manual-only flow.
2. Candidate Apply extraction from Task commands.
3. Statement-owned PDF/source document authority.
4. Any future Task/Statement cardinality change.
5. Business audit anchoring with `statement_id`.
6. A complete AI history and candidate selection UX.
7. Any required migration analysis for the above changes.

CC-11 must not be used to reopen or silently alter the CC-10 authority
boundary without a new documented decision.

## 12. Acceptance Criteria

CC-10 is complete only when all of the following are true:

1. Confirm is a Statement-facing operation and does not read `Task.state`.
2. Create Bill is a Statement-facing operation and does not require
   `Task.state == "parsed"`.
3. A Task error or cancellation does not block an existing Statement's
   editing, confirmation, or Bill creation.
4. `Task.human_reviewed` is compatibility-only and is not read or written by
   new review/Bill commands.
5. `Statement.vendor_bill_id` is the sole writable Bill authority.
6. Legacy `awaiting_review` and `bill_generated` values remain readable and
   deprecated; `parsed` remains the technical success state.
7. The Task technical entry remains available for compatibility.
8. The required regression tests pass.
9. No existing CC-09, DDD, SRS, TDD, migration, or unrelated source file is
    modified as part of drafting this contract.

## 13. Authorization Gate

```text
DRAFT - NOT AUTHORIZED
IMPLEMENTATION_AUTHORIZED = NO
```

Implementation requires explicit approval after review of this contract.
