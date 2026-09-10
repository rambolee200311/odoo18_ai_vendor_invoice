# CC-09 - Task Parse Lifecycle, Statement Review, and Vendor Bill Link

## Status

```text
AUTHORIZED FOR IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

This document is a complete replacement for the previous CC-09 draft. It
defines the three orthogonal facts that must not be represented by duplicate
states:

```text
Task.state
    = AI invoice import and parsing lifecycle

Statement.state
    = human review lifecycle

vendor_bill_id
    = current effective Vendor Bill relation
```

This Contract is the implementation authority for the CC-09 production changes
described below.

## 1. Responsibility Boundaries

| Fact | Authoritative owner | Meaning |
|---|---|---|
| AI import/parsing stage | `vendor.invoice.import.task.state` | Where the AI import lifecycle is. |
| Human review stage | `vendor.invoice.statement.state` | Whether the current Statement is draft or formally confirmed. |
| Current line review | `vendor.invoice.statement.line.checked` | Whether the current line has been reviewed. |
| Aggregate line review | `vendor.invoice.statement.all_checked` | Computed aggregate of current line checks. |
| Current Vendor Bill | `Statement.vendor_bill_id` | The single currently effective linked bill, when present. |
| Accounting lifecycle | `account.move.state` | Accounting document lifecycle. |
| Historical workflow facts | `vendor.invoice.import.log` | Who, when, and what workflow event occurred. |

Do not add any of these duplicate states:

```text
review_completed
awaiting_bill
bill_generated
bill_cancelled
statement_bill_created
statement_bill_cancelled
auto_checked
auto_confirmed
```

`bill_generated` is specifically not a new workflow state in this Contract.
Vendor Bill existence is represented by the single
`Statement.vendor_bill_id` relation.

If the loaded Task model already has `vendor_bill_id`, it may remain only as a
legacy/read-only compatibility surface after investigation. It must not remain
an independent writable authority and must not be double-written by new
workflow commands.

## 2. Task State Machine

The target Task states are:

```text
to_parse
parsing
parsed
error
cancelled
```

### `to_parse -> parsing`

Run AI may start parsing only when:

- the Task is not `cancelled`;
- a valid source PDF is available;
- provider configuration is available;
- no incompatible active ParseAttempt or queue job exists;
- the caller has the required permission.

### `parsing -> parsed`

Successful parsing ends the Task parsing lifecycle:

```text
Task.state = parsed
Statement.state = draft
```

The transition requires:

- the current ParseAttempt belongs to the Task;
- the attempt completed successfully;
- Canonical/schema validation passes;
- the Statement is created or projected successfully;
- Task, Statement, ParseAttempt, company, and source ownership are consistent;
- all new or rebuilt Statement Lines start with `checked=False`;
- no current Vendor Bill link exists.

`parsed` means:

> AI parsing completed successfully, and the Canonical/Statement result was
> produced. The Task's parsing responsibility is complete.

`parsed` does not mean:

- human review completed;
- Vendor Bill created;
- accounting verification completed;
- business verification completed.

### `parsing -> error`

A failed parse may move the Task to `error`. The ParseAttempt and workflow
audit must remain available.

### `error -> parsing`

Rerun AI may create a new ParseAttempt and return the Task to `parsing` after
the existing retry/permission checks. Prior attempts remain auditable.

### Task cancellation

Task Cancel means:

> The incomplete AI import/parsing operation is abandoned.

It is allowed only before successful parsing completes:

```text
to_parse -> cancelled
parsing  -> cancelled
error    -> cancelled
```

It is not allowed from `parsed`. `parsed` is the successful terminal state of
the Parse Task; subsequent review and Vendor Bill operations belong to the
Statement.

Before cancellation:

- no incompatible active parsing operation may remain;
- the caller must be authorized;
- the Task must not already be terminal;
- no current Vendor Bill relation may exist.

On success:

```text
Task.state = cancelled
```

Task Cancel must not change Statement state. In the new workflow, a successfully
parsed Task owns a Statement and cannot later be cancelled through the normal
Task command. The `cancelled` state represents an abandoned or incomplete
Parse Task only.

`cancelled` is terminal for the Task.

## 3. Statement State Machine

The only effective states in the new workflow are:

```text
draft
confirmed
```

The lifecycle is:

```text
draft
  |  all current lines checked + Confirm
  v
confirmed
  |  no current Vendor Bill + Unconfirm
  v
draft
```

Existing database values may contain:

```text
cancelled
bill_created
```

They are legacy compatibility values only:

- they remain readable if present;
- new commands must never enter them;
- no normal operation may silently rewrite historical records;
- Create Bill must not enter `bill_created`;
- Task Cancel must not enter Statement `cancelled`.

### `draft -> confirmed`

Confirm requires:

- Reviewer authorization;
- `Task.state == parsed`;
- Statement belongs to the Task;
- `Statement.state == draft`;
- `Statement.vendor_bill_id` is empty;
- current Statement Lines exist;
- every current Statement Line has `checked=True`;
- required business fields are valid;
- Statement projection is consistent;
- company and ownership checks pass;
- no conflicting lifecycle command is running.

The server must calculate the source-of-truth expression directly:

```python
bool(statement.line_ids) and all(
    line.checked for line in statement.line_ids
)
```

It must not rely only on client data or stored `all_checked`.

On success:

```text
Statement.state = confirmed
Task.state remains parsed
```

Confirm must preserve existing Statement Lines and must not delete, recreate,
or reorder them.

### `confirmed -> draft`

Unconfirm requires:

- Reviewer authorization;
- `Task.state == parsed`;
- `Statement.state == confirmed`;
- `Statement.vendor_bill_id` is empty;
- no conflicting lifecycle command is running.

On success:

```text
Statement.state = draft
Task.state remains parsed
```

Unconfirm must preserve:

- header values;
- line identity and business values;
- each line's current `checked` value;
- source ParseAttempt;
- source PDF;
- Chatter;
- historical audit.

Unconfirm means that the whole Statement is no longer formally review-complete
and can be corrected. It does not mean that previous line reviews never
happened. It must not delete or recreate lines.

## 4. Review Invariants

```text
line.checked
    = this current Statement Line has been reviewed

all_checked
    = bool(line_ids) and all(current line.checked)

Statement.confirmed
    => line_ids exists
    => every current line.checked is True
```

`all_checked` is an aggregate representation, not a second approval fact.
`confirmed` is the formal workflow decision.

Future Auto Check may become another producer of `line.checked`, but this
Contract covers only Manual Check. No Auto Check state is authorized.

## 5. Review Invalidation

Review invalidation applies only while Statement is `draft`.

Before implementation, inspect the loaded model and actual write paths and
classify fields into:

```text
authoritative review inputs
derived/computed/related outputs
```

Do not classify by field name alone.

### Line input changes

When an authoritative review input has a material business-value change:

```text
affected line.checked = False
```

The condition is:

```text
old business value != new business value
```

The mere presence of a field in `vals`, a related-field refresh, or an ORM
recompute is not enough.

Computed, related, and derived outputs must not independently invalidate a
line. A same-value write must not clear `checked`.

New lines start with:

```text
checked = False
```

If a monetary field is an actual user-editable authoritative input in the
loaded model, it may be classified as an input. If it is derived from another
input, its recomputation alone is not an invalidation trigger.

### Critical header changes

The implementation must verify the actual loaded field names. The initial
semantic candidates are:

```text
supplier
invoice number
invoice date
currency
```

A material change to a critical header invalidates all current lines:

```text
all current line.checked = False
all_checked = False
```

Writing the same business value must not invalidate the Statement.

No generic dependency engine is authorized.

## 6. Candidate Apply

Candidate Apply must invalidate only review facts affected by the candidate:

```text
new/rebuilt line
    -> checked=False

materially changed existing line
    -> checked=False

untouched existing line
    -> may preserve checked=True only with stable verified line identity

materially changed critical header
    -> all lines checked=False
```

If the current implementation rebuilds all lines and has no stable line
identity, all rebuilt lines must be unchecked. It is forbidden to guess old
and new line correspondence to preserve review checks.

## 7. Vendor Bill Contract

Create Bill is a command:

- not a Task state transition;
- not a Statement state transition.

It requires:

```text
Task.state == parsed
Statement.state == confirmed
Statement.vendor_bill_id is empty
current lines exist
every current line.checked == True
projection is consistent
company/ownership checks pass
```

Create Bill must directly recheck current `line_ids.checked`.

On success:

```text
Task.state remains parsed
Statement.state remains confirmed
Statement.vendor_bill_id = created Bill
```

It must not set:

```text
Task.state = bill_generated
Statement.state = bill_created
```

The successful commit boundary must establish all of these facts in one
business transaction:

```text
Vendor Bill exists
Statement.vendor_bill_id == created Bill
Task.state == parsed
Statement.state == confirmed
```

If creation fails, no partial link or state change may remain. Repeated Create
Bill must not create a duplicate.

## 8. Current Vendor Bill and Cancellation

`vendor_bill_id` means:

> The current effective Vendor Bill relation.

It is not a complete historical record of every Bill ever created. Historical
creation and cancellation facts remain in the Audit Log.

When the current linked Vendor Bill is formally cancelled by the Accounting
workflow:

```text
Task.state remains parsed
Statement.state remains confirmed
Statement.vendor_bill_id = False
line.checked remains unchanged
all_checked remains unchanged
```

Bill cancellation must not:

```text
Statement -> draft
Task -> error
Task -> awaiting_review
Task -> bill_cancelled
```

After the current Bill is cancelled, the user may:

1. Create a replacement Bill directly if the confirmed Statement is still
   correct; or
2. Unconfirm, edit, re-check, Confirm, and then Create a replacement Bill.

The system must not automatically Unconfirm.

Bill-cancellation synchronization must be:

- idempotent;
- scoped to the cancelled Bill;
- company-safe;
- protected against stale events.

If Bill A is cancelled after Bill B has become the current link, an event for
Bill A must not clear Bill B:

```text
if statement.vendor_bill_id != cancelled_bill:
    do not clear current link
```

The exact Odoo 18 Accounting cancellation/delete integration path is
`UNKNOWN` until loaded-code investigation. Do not assume a specific
`account.move` state, `unlink()`, `button_cancel()`, or callback path before
inspection.

## 9. Authoritative Combination Matrix

| Task state | Statement state | `vendor_bill_id` | Meaning |
|---|---|---|---|
| `parsed` | `draft` | empty | AI parse complete; human review in progress. |
| `parsed` | `confirmed` | empty | Human review complete; no current Vendor Bill. |
| `parsed` | `confirmed` | populated | Human review complete; current Vendor Bill exists. |
| `to_parse` / `parsing` / `error` | no active Statement | empty | Incomplete Parse Task may be cancelled. |

Invalid for the new workflow:

```text
parsed + draft + populated vendor_bill_id
cancelled + populated vendor_bill_id
parsed + any Statement -> Task Cancel
confirmed with empty line_ids
confirmed with any current line.checked=False
```

Historical legacy combinations are not new workflow invariants.

## 10. Audit Boundary

Continue using `vendor.invoice.import.log` for historical workflow facts. At
minimum, distinguish:

```text
statement_confirm
statement_unconfirm
task_cancel
vendor_bill_created
vendor_bill_cancelled
```

Bill cancellation audit must retain:

```text
which Bill
which Task
which Statement
who
when
event type
```

Clearing the current `vendor_bill_id` must never erase Bill identity history.
Chatter remains collaboration and attachment functionality, not a replacement
for workflow audit.

## 11. Loaded-Code Impact Verification

This section records the current loaded-code facts that must be addressed
before implementation. Actual loaded code takes precedence over older
documents.

### `awaiting_review`

Confirmed current references include:

- Task state selection in `models/import_task.py`;
- parse display mapping in `models/import_task.py`;
- Task review guard in `action_save_review`;
- Task confirmation currently writing `awaiting_review`;
- parse service allowed-state guards and success transition;
- Vendor Bill creator preconditions;
- import task form statusbar and button visibility;
- multiple model, service, observability, and intent tests.

Impact:

```text
UNKNOWN until each reference is migrated or deliberately retained
```

The implementation must not simply delete the selection value. It must first
decide whether to:

- add `parsed`;
- retain `awaiting_review` as legacy-readable;
- update service guards;
- update views and display mappings;
- update tests and audit assumptions.

No automatic migration is authorized by this Contract.

### `bill_generated`

Confirmed current references include:

- Task state selection;
- Task cancel guard;
- parse display mapping;
- Vendor Bill creator success write;
- import task form statusbar and button visibility;
- tests and service expectations.

The Statement-side bill creator also currently writes a legacy
`bill_created` state and `statement_bill_created` audit action.

Impact:

```text
UNKNOWN until bill creation service, view, audit, and tests are reconciled
```

New workflow must not enter `bill_generated`; historical records remain
legacy-compatible unless a separately authorized migration is approved.

### `parsed`

Current loaded-code investigation found no Task selection value or normal
workflow transition using `parsed`.

Impact:

```text
parsed is a new target Task state and requires explicit implementation
analysis.
```

### `vendor_bill_id`

Current loaded code contains `vendor_bill_id` on both Task and Statement.
Existing bill creation and open-bill paths use these relations. The target
Contract requires `Statement.vendor_bill_id` to become the single authoritative
current relation. The Task field must be investigated for conversion to a
related/read-only compatibility surface or another non-authoritative access
path. It must not remain an independent writable authority.
The exact atomic creation and Accounting cancellation synchronization behavior
is `UNKNOWN` and must be investigated before Coding.

### `human_reviewed`

Current loaded code contains Task-level `human_reviewed`, and existing review
and confirmation paths write it. The target Contract treats it as a
legacy/compatibility field only:

```text
new workflow MUST NOT depend on human_reviewed
Confirm/Unconfirm MUST NOT synchronize it
Bill cancellation MUST NOT synchronize it
```

The field may remain readable while all other dependencies are enumerated
before implementation.

### Statement cancellation

Current loaded code still exposes `action_cancel_statement`, permits draft or
confirmed cancellation, writes Statement `cancelled`, and has tests for that
behavior. The target Contract removes this from the new workflow, but does not
authorize silently deleting the legacy method or rewriting historical data.

## 12. Required Tests

### Parse lifecycle

1. `to_parse -> parsing`.
2. Successful parse -> `parsed`.
3. Successful parse creates `Statement=draft`.
4. New/rebuilt lines start unchecked.
5. Parse failure -> `error`.
6. Rerun follows existing retry rules.

### Manual review

7. An unchecked line prevents Confirm.
8. An empty Statement prevents Confirm.
9. All current lines checked allows Confirm.
10. Confirm sets Statement `confirmed`.
11. Confirm leaves Task `parsed`.
12. Confirmed Statement is read-only.

### Unconfirm

14. Confirmed Statement without a current Bill can Unconfirm.
15. Unconfirm sets Statement `draft`.
16. Unconfirm leaves Task `parsed`.
17. Unconfirm preserves existing `checked` values.
18. Unconfirm preserves line identity and business values.
19. A current Bill blocks Unconfirm.

### Invalidation

21. Material review-input change unchecks the affected line.
22. Same-value write does not uncheck.
23. Derived recompute alone does not uncheck.
24. New line starts unchecked.
25. Line deletion recomputes `all_checked`.
26. Material critical-header change unchecks all lines.
27. Candidate-rebuilt lines are unchecked.
28. Stable-identity Candidate Apply preserves only untouched line checks.

### Create Bill

29. Create Bill requires a confirmed Statement.
30. Create Bill directly rechecks current lines.
30. Create Bill stores the single current Bill link on Statement.
31. Create Bill leaves Task `parsed`.
32. Create Bill leaves Statement `confirmed`.
33. Duplicate Create Bill is rejected.
34. Failed Create Bill leaves links and states consistent.

### Bill cancellation

35. Cancelling the current Bill clears the Statement current link.
36. Task remains `parsed`.
37. Statement remains `confirmed`.
38. Line checks remain unchanged.
39. A replacement Bill can be created.
40. A stale cancellation event cannot clear a newer current link.
41. Repeated cancellation synchronization is idempotent.

### Task cancellation

42. Task with a current Statement or current Bill cannot be cancelled after
    successful parsing.
43. An incomplete `to_parse`, `parsing`, or `error` Task can be cancelled.
44. Parsed Task cannot be cancelled through the new workflow.
45. Cancelled Parse Task has no later lifecycle commands.

### Compatibility and security

46. Legacy `awaiting_review` remains readable if retained.
47. Legacy `bill_generated` remains readable if retained.
48. Legacy Statement `cancelled/bill_created` remains readable if retained.
49. New workflow never enters legacy values.
50. Cross-company Task, Statement, and Bill links are rejected.
51. Direct state writes remain forbidden.
52. Audit records preserve Bill creation and cancellation identity.

Tests must not call real AI providers or process real supplier PDFs.

## 13. Non-Goals

This Contract does not authorize:

- Auto Check implementation;
- Transport Order Matching;
- TMS coupling;
- Order Events verification;
- transport invoice reconciliation;
- payment lifecycle or payment reconciliation;
- credit note, refund, or reversal workflow;
- generic accounting lifecycle engine;
- Evidence framework;
- field-level provenance;
- automatic Confirm;
- automatic Create Bill;
- silent production migration;
- changes to SRS, DDD, or TDD.

## 14. Acceptance Criteria

```text
Task owns only AI import/parsing lifecycle
successful parsing ends at Task=parsed
Task does not represent human review completion
Task does not represent Vendor Bill existence
Statement owns draft/confirmed human review lifecycle
line.checked is the authoritative line review fact
all current lines must be checked before Confirm
Confirm leaves Task=parsed
Unconfirm leaves Task=parsed
Create Bill leaves Task=parsed
Create Bill leaves Statement=confirmed
Statement.vendor_bill_id is the single current effective Vendor Bill link
Vendor Bill cancellation clears only the current effective link
Vendor Bill cancellation does not undo Statement confirmation
a confirmed Statement may create a replacement Bill after cancellation
Task Cancel is limited to incomplete Parse Tasks
legacy awaiting_review/bill_generated and Statement cancelled/bill_created are
not entered by the new workflow
Audit preserves historical Bill creation/cancellation after link clearing
```
