# CC-17 — Confirmed Statement to Draft Vendor Bill

> Document Type: Coding Contract
> Release: `1.2`
> Status: `FROZEN — IMPLEMENTATION AUTHORIZED`
> `IMPLEMENTATION_AUTHORIZED = YES`
> Target: Odoo 18.0

## 1. Contract Goal

Enable a human-confirmed `vendor.invoice.statement` to create one correct,
auditable, idempotent Odoo Draft Vendor Bill (`account.move`).

The Statement is the only business authority. The Vendor Bill must not read
Provider response, Canonical data, or AI mapping data as a side channel.

## 2. Current State

- Release 1.1 establishes Statement as the business authority.
- `vendor.invoice.statement.vendor_bill_id` is the writable Statement-side
  Bill authority.
- `account.move.vendor_invoice_statement_id` links a generated Vendor Bill
  back to its Statement.
- Bill creation already requires a confirmed Statement and checked Statement
  lines.
- Current Statement tax facts contain `tax_rate`, `tax_amount`, `tax_raw_text`,
  `tax_ids`, and reconciliation data, but no explicit field that distinguishes
  `0%`, Exempt, Non-taxable, and Outside-Scope treatment.
- Cancelling a linked Vendor Bill clears the active Statement-side Bill link
  and writes an audit record.
- The current Bill Creator remains the implementation baseline; CC-17 freezes
  the Release 1.2 accounting contract and may extend it only within the
  boundaries below.

## 3. In Scope

1. Explicit user-triggered creation from a confirmed Statement.
2. Statement-to-`account.move` header and line mapping.
3. Partner, currency, journal, account, and tax validation.
4. Per-line tax-fact resolution and controlled percentage Purchase Tax creation.
5. Amount and tax recalculation with configured tolerances.
6. One-active-Bill-per-Statement idempotency.
7. Cancellation, link release, and recreation from the same Statement.
8. Transactional audit and source traceability.
9. Permission and concurrency protection.

## 4. Out of Scope

- Automatic Bill creation during Statement confirmation.
- Posting, payment, reconciliation, or Vendor Bill approval workflows.
- Replacing the Statement, Task, ParseAttempt, Canonical, or Profile models.
- Reading Provider response or Canonical data outside the confirmed Statement.
- Automatic Partner or Currency creation.
- Fuzzy Partner matching.
- Multiple active Vendor Bills for one Statement.
- Deleting historical cancelled Vendor Bills as part of recreation.

## 5. Business Rules

1. Only a `confirmed` Statement can start Bill creation.
2. The user starts creation with the Statement `Create Vendor Bill` action.
3. All current Statement Lines must be checked and pass validation.
4. One Statement may have at most one active Vendor Bill link.
5. A repeated request while an active Bill exists returns or opens that existing
   Bill; it must never create a second active Bill.
6. A cancelled Bill remains historical. Its cancellation releases the active
   Statement link and permits a new Draft Bill from the same confirmed
   Statement.
7. Statement state remains `confirmed` after its linked Bill is cancelled.
8. A cancelled old Bill can never become the current Statement Bill again.
9. A Draft Bill created by this contract must remain unposted.
10. `checked=True` means that the business line was manually reviewed; it does
    not mean that accounting, journal, or tax mapping has been validated.
11. Any unsafe or incomplete accounting mapping must fail visibly before a
    successful Bill link is recorded.

## 6. Technical Boundaries

### 6.1 Authority and traceability

The input chain is:

```text
Confirmed Statement
        ↓
Validated Statement business fields
        ↓
Draft account.move
```

The generated move stores:

```text
account.move.vendor_invoice_statement_id = Statement.id
Statement.vendor_bill_id = account.move.id
```

The `account.move` link uses `ondelete="restrict"`. Historical cancelled Bills
are retained and are not silently removed during recreation.

### 6.2 Required source fields

| Vendor Bill field | Statement source | Rule |
| --- | --- | --- |
| `move_type` | Contract | Always `in_invoice` |
| `partner_id` | `supplier_id` | Must resolve uniquely to `res.partner` |
| `invoice_date` | `invoice_date` | Required valid date |
| `currency_id` | `currency_id` | Must be valid for the company |
| `ref` | `invoice_number` | Preserve the confirmed invoice number |
| `journal_id` | Existing Odoo/Bill Creator resolution | Do not choose arbitrarily among multiple candidates |
| `invoice_line_ids` | `line_ids` | Include every current checked line |
| `vendor_invoice_statement_id` | Statement identity | Required source link |

Missing or ambiguous Partner, Currency, or Purchase Journal is a controlled
validation error. The system must not silently substitute a value. CC-17 does
not introduce a new Journal master-data or fallback algorithm.

### 6.3 Line mapping

| Vendor Bill line | Statement Line source | Rule |
| --- | --- | --- |
| `name` | `description` | Preserve confirmed description |
| `product_id` | `product_id` | Use when present |
| `quantity` | Contract | Always `1.0`; accounting representation only, never shipment/package/weight quantity |
| `price_unit` | `amount` | Always the confirmed Statement Line net amount |
| `account_id` | Existing Odoo/Bill Creator account resolution | Reuse the current Expense Account resolution; CC-17 does not create a new account authority |
| `tax_ids` | Confirmed Statement Line tax facts | Resolve independently for this line by the rules below |
| source trace | Statement Line id | Preserve line-level traceability |

The account source is the existing Odoo/current Bill Creator behavior, not a
new company/category fallback invented by CC-17. If no valid Expense Account
can be resolved, Bill creation must fail before creating a usable Draft Bill.

## 7. Amount and Tax Contract

### 7.1 Amount validation

`Statement Line.amount` is the confirmed accounting net amount authority.
Transportation lines may consolidate freight, surcharge, discount, and other
charge facts, so Bill Creator must not reject a valid transport line merely
because its amount cannot be reconstructed from `quantity × price_unit`.

The generated accounting line must use:

```text
quantity = 1.0
price_unit = confirmed Statement Line.amount
```

`account.move.line.quantity` is an accounting representation only. It does not
represent shipment, package, pallet, weight, distance, or any other transport
quantity. Transport quantities remain Statement business facts and must not
change the Vendor Bill amount representation.

The generated Odoo line and totals must be recalculated by Odoo. The system
must not create a successful Bill whose recalculated values contradict the
confirmed Statement beyond the configured tolerance.

### 7.2 Per-line tax-fact resolution

Tax resolution is performed independently for every confirmed Statement Line.
A single Vendor Bill may contain multiple tax rates and tax treatments. No
invoice-level tax rate may be applied to all lines.

The Statement stores confirmed supplier tax facts:

```text
tax_rate
tax_amount
tax_treatment
tax_raw_text
charge_details
```

These are business facts confirmed by a reviewer. `account.tax` is an Odoo
accounting configuration object. Bill Creator maps the confirmed facts to Odoo
taxes but never re-reads PDF, Canonical, or Provider data.

For an explicit ordinary percentage VAT (`tax_treatment = percentage`), the
reuse key is:

```text
company + Purchase Tax + percentage + tax_rate
```

Rules for ordinary percentage VAT:

1. Reuse the unique existing percentage Purchase Tax when present.
2. If no matching tax exists, create one automatically.
3. The created tax is a percentage Purchase Tax with the Statement rate.
4. Use a stable name such as `BTW 21% Purchase`.
5. Concurrent requests must not create duplicate taxes.
6. Tax creation must be permission-checked and transactional.
7. Recalculate tax using Odoo and compare it with the confirmed Statement tax
   amount using the configured tolerance.

Special treatments are not interchangeable:

```text
0% / Exempt / Non-taxable / Outside Scope / other explicit treatment
        ↓
confirmed Statement tax facts
        ↓
deterministic Tax Resolution
        ↓
unique mapping required
```

`tax_rate = 0` alone must not be treated as proof that a line is exempt,
non-taxable, or outside scope. If the confirmed facts are insufficient to
uniquely determine the Odoo tax treatment, Bill creation must report a
Statement Tax Contract Gap and fail visibly. The system must not invent a
special tax meaning.

The minimum Statement Tax Contract extension is a confirmed
`tax_treatment` value with the following controlled values:

```text
percentage
zero_rated
exempt
non_taxable
outside_scope
other
```

`percentage` requires a valid `tax_rate`. The other values must be mapped to a
unique configured Odoo treatment; unsupported `other` values fail visibly.
The value must be preserved through Canonical/Statement projection when the
source document expresses a special treatment.

If the tax calculation differs beyond tolerance, the operation must fail
without leaving a successful Statement/Bill association.

### 7.3 Charge facts are not reinterpreted

`charge_details` preserves transport-invoice facts such as:

```text
Charge / Discount / Net Charge
```

These facts are already interpreted into the confirmed top-level Statement
Line. Bill Creator must not expand, recompute, or reinterpret them. Accounting
creation consumes the confirmed Statement Line `amount` and tax facts only.

## 8. Idempotency and Concurrency

The Bill creation command must lock the Statement before checking and creating
the Bill.

```text
lock Statement
  → reload current vendor_bill_id
  → if active Bill exists, return/open existing Bill
  → validate confirmed Statement
  → resolve mapping and tax
  → create Draft Bill
  → write Statement.vendor_bill_id
  → audit success
commit
```

Required behavior:

- Duplicate button clicks cannot create two active Bills.
- Concurrent requests cannot create two active Bills.
- A failed transaction leaves no active Statement/Bill link.
- Repeating after a successful transaction returns or opens the existing
  active Bill.
- Repeating after Bill cancellation is allowed and creates a new Draft Bill.

## 9. Cancellation and Recreation

```text
Confirmed Statement
        ↓ Create
Active Draft Vendor Bill #1
        ↓ Cancel
Confirmed Statement + no active Bill
        ↓ Create again
Active Draft Vendor Bill #2
```

When the linked Bill is cancelled:

1. Keep the cancelled `account.move` for audit history.
2. Clear `Statement.vendor_bill_id`.
3. Keep Statement state as `confirmed`.
4. Keep the cancelled Bill's source link for historical traceability.
5. Write a `vendor_bill_cancelled` audit event.
6. Permit a later Create Vendor Bill action from the same Statement.

Direct deletion is not a supported relationship-release mechanism. Existing
restrict semantics must prevent deletion that would violate source traceability,
or the delete must fail with a visible Odoo error.

## 10. Audit Requirements

At minimum, record:

| Event | Required facts |
| --- | --- |
| `bill_create` | Statement, new Bill, actor, timestamp, accounting mapping outcome |
| `vendor_bill_cancelled` | Statement, cancelled Bill, actor, timestamp |
| tax creation | Company, tax rate, created tax, actor, timestamp, reuse key |

The audit trail must distinguish the current active Bill from historical
cancelled Bills. Release 1.2 requires persistent audit for successful creation,
tax creation, and cancellation. A failed creation must return a clear error and
roll back; it does not require a separate persistent `bill_create_failed`
business event.

## 11. Permissions and Error Handling

- Only an authorized Invoice Reviewer may create or cancel through the
  Statement workflow.
- Config Manager permissions do not automatically grant Bill creation.
- Validation, access, mapping, tax, and concurrency failures must surface as
  visible Odoo errors.
- No broad catch or success-shaped fallback is allowed.
- A failed Bill creation must not silently alter the confirmed Statement data.

## 12. Allowed Changes

- `account.move` Statement link and cancellation synchronization.
- Bill Creator mapping and validation logic.
- Controlled automatic Purchase Tax creation and reuse.
- Statement Bill action, audit vocabulary, and focused view changes.
- Concurrency/idempotency guards and focused tests.
- Documentation directly describing the Release 1.2 contract.

## 13. Forbidden Changes

- Creating a Bill from an unconfirmed Statement.
- Directly using AI/Canonical/Provider data as Bill input.
- Posting or paying the generated Bill.
- Creating duplicate active Bills or duplicate automatic taxes.
- Automatically creating Partners or Currencies.
- Clearing audit history during cancellation or recreation.
- Changing Task/ParseAttempt runtime semantics.
- Bypassing ACLs with `sudo()` or context flags.

## 14. Acceptance Criteria

- A confirmed, valid Statement creates exactly one correct Draft Vendor Bill.
- The Bill contains the correct Partner, date, currency, journal, reference,
  accounts, per-line taxes, confirmed net amounts, lines, and source link.
- Every generated Vendor Bill line uses `quantity=1.0` and
  `price_unit=confirmed Statement Line.amount`; these fields do not represent
  transport quantities.
- Odoo recalculated amounts and taxes match the confirmed Statement within the
  configured tolerance.
- Invalid or ambiguous mapping fails before successful Bill creation.
- Repeated and concurrent creation requests are idempotent.
- Cancelling the active Bill clears the active Statement link and preserves the
  confirmed Statement.
- The same confirmed Statement can create a new Draft Bill after cancellation.
- Historical cancelled Bills and all audit events remain traceable.
- No posting, payment, or reconciliation behavior is introduced.

## 15. Test Requirements

- Confirmed/unconfirmed Statement precondition tests.
- Partner, currency, journal, account, and line validation tests.
- Existing Product/account resolution regression tests.
- Existing account and Purchase Journal resolution regression tests.
- Existing-tax reuse and automatic-tax creation tests.
- Tax uniqueness and concurrent tax creation tests.
- Per-line mixed-tax, special-treatment, amount/tax tolerance, and rounding tests.
- Statement Tax Contract tests for `percentage`, `zero_rated`, `exempt`,
  `non_taxable`, `outside_scope`, and unsupported `other` treatments.
- Transport charge/discount/net-charge non-reinterpretation tests.
- Duplicate-click and concurrent Bill creation tests.
- Bill cancellation link-release tests.
- Recreate-after-cancellation tests.
- Failed-transaction rollback tests.
- Permission and audit event tests.
- Existing Statement, Task, ParseAttempt, and Bill Creator regressions.

## 16. Open Questions

`OPEN_QUESTIONS = NONE`

The existing fields were verified as insufficient to distinguish special tax
treatments by themselves. CC-17 therefore closes the gap with the minimum
confirmed `tax_treatment` field and controlled values defined in §7.2. No
additional SRS, DDD, or Spike is required.

## 17. Authorization Status

`FROZEN — IMPLEMENTATION AUTHORIZED`
`IMPLEMENTATION_AUTHORIZED = YES`
Authorization recorded: 2026-09-15. Release 1.2 implementation may begin
within this contract; no SRS, DDD, or new Spike is required.
