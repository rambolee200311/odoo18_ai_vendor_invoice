# INTENT-IMPLEMENT-INVOICE-STATEMENT-001

> Document Type: Coding Contract / Implementation Intent
> Status: Frozen
> Scope: Vendor invoice Statement implementation for Odoo 18.0
> Purpose: Define the implementation boundary, sprint acceptance, closure gates, and required evidence. This document does not authorize new business rules or architecture.

## 1. Implementation boundary

This intent implements the frozen Statement domain design only. The implementation must preserve the existing Task aggregate, ParseAttempt lifecycle, mapping services, HumanReviewResult compatibility projection, and Bill Creator contract.

The implementation must not:

- add a new business workflow, state, model, or carrier-specific rule without a separate Intent;
- allow the UI, a scheduled job, or an external service to perform business-level direct CRUD on Statement or Statement Line;
- change the Bill Creator data source: Bill Creator continues to read only `task.human_review_result`;
- modify Odoo core or the `queue_job` implementation;
- introduce a runtime dependency on `account_invoice_import`;
- add browser E2E automation to this scope.

The implementation must use the repository's frozen SRS, DDD, and TDD documents as its source of truth. Their canonical references must use final, versioned names:

```text
spec_wd_ai_vendor_invoice_1.3.4.md
ddd_wd_ai_vendor_invoice_v1.3.md
tdd_wd_ai_vendor_invoice_v1.5.md
INT-WD-AI-VENDOR-INVOICE-STATEMENT-CODING-CONTRACT.md
```

If a repository file still has a historical version or path, that file must be explicitly mapped to the approved frozen baseline before implementation starts. Do not leave a temporary draft name beside a frozen name in the same implementation contract.

## 2. Statement domain contract

### 2.1 Statement as human-authoritative data

Statement and Statement Line are the human-authoritative representation used after review. AI output, canonical parse output, and mapping recommendations are candidates or inputs only; none of them may silently overwrite the human Statement.

The compatibility projection is written to `task.human_review_result`. It is a derived representation of the current Statement and must not become a second editable source of truth.

### 2.2 Canonical candidate and source attempt lifecycle

The following rules are mandatory:

- When a Statement is first created from a ParseAttempt candidate, `source_parse_attempt_id` must point to that ParseAttempt.
- An AI rerun alone must not modify `source_parse_attempt_id`.
- For an existing Statement, only the human `Apply AI Candidate` command may update `source_parse_attempt_id` to a new ParseAttempt.
- Applying a candidate must preserve the audit trail and identify the source ParseAttempt.
- Manual edits must not change `source_parse_attempt_id`.
- A stale or superseded ParseAttempt must not be applied as a current candidate.

### 2.3 Statement mutation boundary

“UI/job/external service must not directly CRUD Statement/Line” means that business-level mutation must be authorized by a Task aggregate command.

- The UI must not call generic `create`, `write`, or `unlink` as a business edit path.
- Review operations must call Task aggregate commands. The frozen command names are:
  - `action_apply_statement_changes(...)`
  - `action_apply_ai_candidate(...)`
  - `action_confirm_statement(...)`
- Statement/Line ORM `create` and `write` may be called internally by the Task aggregate service.
- Statement/Line ORM methods must not be independent RPC business entry points.
- Context flags, `sudo()`, direct model RPC, or another bypass must not be used to evade the Task aggregate boundary.
- Every accepted mutation must validate the resulting aggregate before saving it.

The review UI may display and edit fields, but its save action must invoke the appropriate aggregate command rather than ordinary form persistence.

### 2.4 Projection consistency before bill creation

Before invoking the existing Bill Creator, the Task aggregate service must guarantee:

```text
Statement == semantic content of task.human_review_result
```

The consistency check must compare business meaning, not merely an incidental serialization or record identity.

If the projection is missing, stale, or semantically inconsistent:

- Vendor Bill creation must be rejected.
- Bill Creator must not repair or regenerate the projection.
- The Task aggregate service must rebuild the projection in the same business transaction, or raise the consistency error defined by the TDD.
- Bill creation must never continue while Statement and the compatibility projection disagree.

Bill Creator itself must continue to read only `task.human_review_result`; it must never read Statement, `canonical_result`, or `mapping_result`.

### 2.5 Carrier-neutral candidate processing

Named carriers in required tests are acceptance fixtures only. They are not implementation contracts and must not receive dedicated business logic.

Implementation must not contain carrier-specific branching such as:

```python
if vendor == "Bring Cargo":
if vendor == "Feelogic":
if vendor == "Mainfreight":
```

Unless authorized by a future Intent, the same canonical normalization, field mapping, and candidate mechanism must process all carriers. Bring Cargo summary/detail PDFs, Feelogic `Uw ref.`/Dossier/Opdracht samples, and Mainfreight Shipment number/O.No. samples are fixtures for exercising generic behavior.

## 3. Required implementation surfaces

The implementation must cover all relevant surfaces consistently:

- Statement and Statement Line ORM models, constraints, relations, and indexes;
- Task aggregate commands and their authorization boundary;
- canonical candidate application and ParseAttempt provenance;
- HumanReviewResult projection and semantic consistency validation;
- review views and Owl actions;
- audit logging for candidate application and manual changes;
- access control and record rules for review and configuration users;
- Bill Creator preconditions, idempotency, attachment traceability, and company context;
- unit, integration, concurrency, stale-worker, and permission tests;
- machine-checkable gates and a sprint report containing evidence.

## 4. Closure gates

`STATEMENT-GATE-01` through `STATEMENT-GATE-25` are final closure gates. Their numbering does not imply sprint ownership.

| Gate | Required evidence |
| --- | --- |
| `STATEMENT-GATE-01` | Statement aggregate model exists with the frozen technical name and required identity fields. |
| `STATEMENT-GATE-02` | Statement Line model exists and is related to its owning Statement with the frozen delete behavior. |
| `STATEMENT-GATE-03` | Statement and Line constraints reject invalid mandatory, numeric, tax, currency, and relation values. |
| `STATEMENT-GATE-04` | Statement creation from a ParseAttempt stores that attempt in `source_parse_attempt_id`. |
| `STATEMENT-GATE-05` | AI rerun does not mutate an existing Statement or its `source_parse_attempt_id`. |
| `STATEMENT-GATE-06` | Only `action_apply_ai_candidate(...)` can replace provenance on an existing Statement. |
| `STATEMENT-GATE-07` | Candidate application rejects stale or superseded ParseAttempts. |
| `STATEMENT-GATE-08` | Manual Statement edits do not change ParseAttempt provenance. |
| `STATEMENT-GATE-09` | Every candidate or manual mutation is authorized by a Task aggregate command. |
| `STATEMENT-GATE-10` | Generic Statement/Line CRUD is not exposed as a UI or external business edit path. |
| `STATEMENT-GATE-11` | Context flags, `sudo()`, and direct model RPC cannot bypass the mutation boundary. |
| `STATEMENT-GATE-12` | `action_confirm_statement(...)` validates and persists the complete human Statement atomically. |
| `STATEMENT-GATE-13` | The projection is generated from the current human Statement, not directly from AI or mapping output. |
| `STATEMENT-GATE-14` | Statement save and projection update use one business transaction. |
| `STATEMENT-GATE-15` | Projection content has a semantic consistency check against Statement. |
| `STATEMENT-GATE-16` | Bill creation rejects a missing, stale, or inconsistent `human_review_result` projection. |
| `STATEMENT-GATE-17` | The consistency gate runs before the existing Bill Creator is called. |
| `STATEMENT-GATE-18` | Bill Creator reads only `task.human_review_result`, never Statement or candidate fields. |
| `STATEMENT-GATE-19` | Review confirmation and Bill creation preserve the existing single-entry and transaction boundary. |
| `STATEMENT-GATE-20` | Concurrent review/candidate operations do not lose human edits or provenance. |
| `STATEMENT-GATE-21` | Audit records identify the actor, operation, source ParseAttempt, and resulting Statement change. |
| `STATEMENT-GATE-22` | Company context and permissions are enforced for Statement, Line, Task, and projection operations. |
| `STATEMENT-GATE-23` | Source PDF and resulting Vendor Bill attachment traceability remains intact. |
| `STATEMENT-GATE-24` | Required carrier samples pass through generic normalization and candidate logic without carrier branches. |
| `STATEMENT-GATE-25` | Full Statement closure, including bill traceability and regression of existing `GATE-01` through `GATE-15`, passes. |

A gate result must be one of `PASS`, `FAIL`, or `NOT_APPLICABLE_YET`. `NOT_APPLICABLE_YET` is allowed only during an intermediate Sprint acceptance as defined below; it is forbidden at final closure.

## 5. Sprint implementation order and acceptance

### Sprint 1 — Statement Foundation

Implement:

- Statement and Statement Line models and constraints;
- canonical Statement identity and provenance fields;
- first creation from a ParseAttempt candidate;
- Task aggregate command boundary for Statement mutation;
- review permissions, audit foundations, and model-level tests.

Acceptance:

- Execute every Statement Gate whose implementation preconditions exist in this Sprint.
- Mark gates that depend on Sprint 2 or Sprint 3 as `NOT_APPLICABLE_YET`; never mark them `FAIL` merely because their implementation has not started, and never fabricate a `PASS`.
- The Sprint 1 report must list:
  - every applicable gate;
  - `PASS` or `FAIL`;
  - code evidence;
  - test evidence;
  - every deferred gate marked `NOT_APPLICABLE_YET` with its owning Sprint.

### Sprint 2 — Review and Projection

Implement:

- human review commands and review UI actions;
- `Apply AI Candidate` provenance behavior;
- candidate rejection and stale-attempt protection;
- HumanReviewResult projection;
- atomic Statement save plus projection update;
- projection semantic consistency validation and related tests.

Acceptance:

- All Sprint 1 `PASS` gates remain passing; regressions are `FAIL`.
- Execute all gates related to Review, Candidate Application, and Projection.
- Gates that require Sprint 3 bill closure are `NOT_APPLICABLE_YET`.
- The report must include code and test evidence for every applicable gate and explicitly identify deferred Sprint 3 gates.

### Sprint 3 — Bill Traceability and Closure

Implement:

- the projection consistency gate immediately before Bill Creator;
- bill traceability and attachment behavior;
- final idempotency and transaction checks;
- concurrent review/bill tests, stale-worker tests, permission tests, and carrier-neutral fixture tests.

Acceptance:

- Execute all `STATEMENT-GATE-01` through `STATEMENT-GATE-25` for final closure.
- No gate may remain `NOT_APPLICABLE_YET`.
- Run the existing `GATE-01` through `GATE-15` regression suite at the same closure point.
- Any failure blocks completion; a report must include the failing gate, observed behavior, and reproducible test evidence.

Sprints must be executed in order. Do not authorize one implementation run to silently continue through all three Sprints without an acceptance report at each boundary.

## 6. Required tests and evidence

Tests must prove behavior rather than only inspect method names. At minimum they must cover:

- first Statement creation from ParseAttempt A and provenance A;
- AI rerun leaving an existing Statement and provenance unchanged;
- applying candidate B through the aggregate command updating provenance to B;
- manual edits preserving provenance;
- stale/superseded candidate rejection;
- UI or RPC attempts to bypass the aggregate boundary;
- atomic Statement and projection updates, including rollback;
- bill rejection and repair behavior when projection content is stale or inconsistent;
- Bill Creator receiving only the compatibility projection;
- concurrent review and bill creation with no lost update or duplicate bill;
- company isolation and review/configuration permissions;
- source attachment copying and traceability;
- generic processing of Bring Cargo, Feelogic, and Mainfreight fixtures without vendor-name branching.

Each Sprint report must include the command used, test result, applicable gate list, and links or paths to code and test evidence. A green test run without gate-to-evidence mapping is insufficient for acceptance.

## 7. Definition of done

The Statement implementation is complete only when:

- all three Sprints have been accepted in order;
- all `STATEMENT-GATE-01` through `STATEMENT-GATE-25` are `PASS`;
- existing `GATE-01` through `GATE-15` regression checks are `PASS`;
- no temporary implementation-contract filename remains as an alternative frozen baseline;
- no carrier-specific branch has been introduced;
- the human Statement and `task.human_review_result` projection are consistent at the Bill Creator boundary;
- required code, tests, permissions, audit evidence, and sprint reports are present.
