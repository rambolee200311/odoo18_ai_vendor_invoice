# AI Vendor Invoice - TDD v1.5 Implementation Alignment Matrix

> Status: `DRAFT - NOT AUTHORIZED FOR IMPLEMENTATION`
>
> Scope: documentation alignment only. This matrix does not authorize
> production-code, test-suite, or frozen-baseline changes.

## 1. Baseline and evidence

| Item | Reference |
|---|---|
| Historical TDD | [TDD v1.5 draft](./tdd_wd_ai_vendor_invoice_v1.5_draft.md) |
| Implemented source | `addons/ai_vendor_invoice/models/statement.py`, `import_task.py`, `import_task_views.xml` |
| CC-08 evidence | [CC-08 history](../history/cc08-task-cancellation.md) |
| CC-09 evidence | [CC-09 amounts](../history/cc09-statement-line-amounts.md), [realtime onchange](../history/cc09-realtime-onchange.md) |
| Browser evidence | AI Invoice Imports and Statements pages verified on 2026-09-08 |
| Module/runtime evidence | `ai_vendor_invoice` module upgrade completed; XML/Python validation passed |

## 2. Classification rules

- `DOC_OUTDATED`: the implemented behavior is authorized and the document is stale.
- `IMPLEMENTATION_DEVIATION`: code conflicts with the frozen design or contract.
- `PENDING_CONTRACT`: implementation exists, but the related contract is not a
  formally frozen baseline for this revision.
- `VERIFICATION_MISSING`: the code/design relationship lacks sufficient
  acceptance evidence.

This revision uses the confirmed implementation as the primary baseline.
Implemented behavior that has passed focused tests or manual browser
verification may be synchronized into R1. Only genuine business conflicts,
data risks, or undecided rules remain open. Historical mismatches that no
longer represent required behavior are recorded as retired requirements,
not as implementation work.

## 3. Difference matrix

### A. Statement fields and relationships

| Area | TDD v1.5 current | Code current | Frozen contract | Resolution |
|---|---|---|---|---|
| Statement number | `statement_number`, nullable | `name`, required, sequence-backed, readonly | CC-03/CC-04 use a business Statement number | `DOC_OUTDATED` |
| Supplier | `vendor_partner_id` | `supplier_id` plus `supplier_name` | Supplier identity is part of the Statement business key | `DOC_OUTDATED` |
| Source PDF | `source_attachment_id` | related `source_pdf_attachment_id` | Source PDF belongs to the Task aggregate | `DOC_OUTDATED` |
| Source filename | Not specified | related `source_pdf_filename`, readonly | Not specified in v1.5 | `DOC_OUTDATED` |
| Parse attempt | nullable; updated only by candidate application | required Many2one; set by Task aggregate creation/application | Candidate provenance must be explicit | `DOC_OUTDATED` |
| Invoice date | `invoice_date` | `invoice_date` | Same business field | `DOC_OUTDATED` |
| Totals | `total_amount`, `total_tax` | computed stored `subtotal`, `total_tax`, `total_amount`, `overall_tax_rate` | CC-09 reuses existing header totals | `DOC_OUTDATED` |
| Raw fields | `raw_fields` required by TDD | field is absent from current Statement/Line models | No current business need was identified | `DOC_OUTDATED` (retired) |
| Human review flag | `human_reviewed` | field is absent; state and Task commands govern review | State and aggregate commands are the current review control | `DOC_OUTDATED` (retired) |
| Task relationship | required Task relation, cascade | required `task_id`, cascade, unique per Task | Task is aggregate root | `DOC_OUTDATED` |
| Vendor bill relation | reverse computed relation described | readonly `vendor_bill_id` on Statement; invoice-side relation exists | Bill traceability is required | `VERIFICATION_MISSING` |

### B. Statement lines and amounts

| Area | TDD v1.5 current | Code current | Frozen contract | Resolution |
|---|---|---|---|---|
| Untaxed amount | `subtotal` | `amount` | CC-09 defines `amount` as untaxed amount | `DOC_OUTDATED` |
| Unit price | `unit_price` | `price_unit` | No conflicting approved behavior found | `DOC_OUTDATED` |
| Tax fields | `tax_amount`, `line_total_amount` | `tax_rate`, `tax_amount`, `total_amount`, `tax_ids`, `tax_raw_text` | CC-09 four-field linkage | `DOC_OUTDATED` |
| References/raw metadata | transport/reference/raw fields listed | only `reconciliation_clue`, `charge_details`, `reconciliation_clues` | No current business need was identified for the retired fields | `DOC_OUTDATED` (retired) |
| Multiple monetary writes | Not specified | deterministic precedence: `amount > tax_rate > tax_amount > total_amount` | CC-09 requires deterministic precedence | `DOC_OUTDATED` |
| Zero untaxed boundary | Not specified | non-zero tax with zero untaxed amount raises `ValidationError` | CC-09 requires this boundary | `DOC_OUTDATED` |
| Realtime editing | Not specified | four independent onchange handlers plus ORM normalization | CC-09 realtime verification accepted | `DOC_OUTDATED` |
| Draft editing | not fully specified | reviewer-only Draft create/write/unlink; non-Draft blocked in ORM and view | CC-09 requires two-layer control | `DOC_OUTDATED` |
| Header aggregation | no `overall_tax_rate` | computed stored subtotal/tax/total/overall rate | CC-09 requires header aggregation | `DOC_OUTDATED` |

### C. Statement state machine

| Area | TDD v1.5 current | Code current | Frozen contract | Resolution |
|---|---|---|---|---|
| State set | computed UI state derived from Task/review/invoice | stored Selection: `draft`, `confirmed`, `cancelled`, `bill_created` | CC-04 state set is authoritative; stored state is accepted for R1 | `DOC_OUTDATED` |
| Direct state write | readonly computed | ORM rejects direct `state` writes | Business transitions must use commands | `DOC_OUTDATED` |
| Draft edits | implied by review flow | only Draft editable; reviewer and aggregate paths are controlled | CC-04/CC-09 behavior | `DOC_OUTDATED` |
| Bill transition | invoice-side relation listed | Task confirmation/bill flow controls `bill_created` | Must be verified with runtime bill creation | `VERIFICATION_MISSING` |

### D. AI Candidate

| Area | TDD v1.5 current | Code current | Frozen contract | Resolution |
|---|---|---|---|---|
| Reparse | new Attempt only | `Run AI` creates/runs a new ParseAttempt | AI rerun must not silently overwrite Statement | `DOC_OUTDATED` |
| Candidate application | apply untouched fields and preserve edits | backend validates current successful Attempt, rewrites Statement values, deletes/rebuilds Lines | Current behavior is recorded; it is not the human review entry point | `DOC_OUTDATED` |
| UI action | candidate action described as review operation | `Apply AI Candidate` button removed from Statement form | Candidate application is not exposed as the human review workflow | `DOC_OUTDATED` |
| Backend entry | Task aggregate command | Statement façade delegates to Task aggregate | Aggregate boundary preserved | `DOC_OUTDATED` |

### E. CC-08, CC-09, menus, and filenames

| Area | Evidence | Current behavior | Resolution |
|---|---|---|---|
| Task cancellation | CC-08 focused tests passed; browser button verified | `Cancel`, `cancelled`, checksum release, stale synchronous-result guard | `DOC_OUTDATED` |
| Unified error | CC-08 focused tests passed; Error Badge visible | Task uses one `error` state and parse error summary/badge | `DOC_OUTDATED` |
| Synchronous parse | runtime/manual verification | `synchronous_parse` defaults to synchronous path | `DOC_OUTDATED` |
| Async queue | history explicitly says not accepted end-to-end | no async UAT claim | `VERIFICATION_MISSING` |
| Task PDF uniqueness | automated tests/history | active Task uniqueness by company/checksum; cancelled Task releases checksum | `DOC_OUTDATED` |
| Statement uniqueness | automated tests/history | active business key by company/supplier identity/invoice number; cancelled excluded | `DOC_OUTDATED` |
| Statement/Line forms | browser verification | dedicated Statement Line form and read-only non-Draft behavior | `DOC_OUTDATED` |
| Configuration menu | browser verification | AI Invoice root menu contains Configuration and seven children | `DOC_OUTDATED` |
| PDF filenames | code fix plus five-row development backfill | Task stores filename; Statement exposes related filename; both lists display it | `DOC_OUTDATED` |
| Historical backfill scope | one development database was updated | no production-wide migration was executed | `DOC_OUTDATED` |

## 4. Pending contract and verification register

### Pending contracts

- None for the synchronous R1 baseline. Candidate application is documented as
  a technical compatibility operation and is not an entry point for human
  review.

### Verification missing

- End-to-end asynchronous queue execution and interruption. This is an async
  special study and does not block the synchronous R1 baseline.
- Runtime confirmation of concurrent Statement confirmation and concurrent Bill
  generation against the current database.
- Complete verification of raw-field schema behavior because the current model
  does not expose the TDD-required `raw_fields` fields.

## 5. Matrix conclusion

The historical TDD v1.5 must not be overwritten. R1 may synchronize the
implemented, tested, and manually confirmed synchronous behavior, while
retiring obsolete fields and keeping asynchronous verification outside the
baseline. No genuine implementation deviation or pending synchronous
business contract remains in this matrix.
