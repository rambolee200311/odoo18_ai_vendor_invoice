# CC-08 Implementation Report

## 1. Contract

`CC-08 — Statement Form Totals, Check Selection, and Transport Order Fields`

Status: `IMPLEMENTED`

The contract was authorized before coding:

```text
AUTHORIZED FOR IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

## 2. Implementation Summary

Implemented the requested Statement form and list-view improvements:

- Statement header exposes untaxed amount, tax amount, total amount, and
  overall tax rate.
- Statement line list uses native Odoo aggregate footers for untaxed amount,
  tax amount, and total amount.
- Statement lines have persisted `checked`, `order_no`, and `order_id` fields.
- Statement header has persisted `all_checked` behavior that checks or unchecks
  all current lines.
- Individual line changes recompute `all_checked`.
- Product selection is restricted to service products with the Odoo 18
  `detailed_type = service` domain.
- Statement list exposes supplier, totals, overall tax rate, and all checked.
- Existing Statement lifecycle, Chatter, aggregate commands, and human
  confirmation boundary remain unchanged.

## 3. Files Changed

- `addons/ai_vendor_invoice/models/statement.py`
  - Added `all_checked` computed/inverse field.
  - Added Statement Line `checked`, `order_no`, and `order_id` fields.
  - Added service-product domain to `product_id`.
- `addons/ai_vendor_invoice/models/import_task.py`
  - Preserved the new line fields through Statement creation and projection
    payloads.
- `addons/ai_vendor_invoice/views/import_task_views.xml`
  - Added header totals and all-checked control.
  - Added line fields and native list aggregate footers.
  - Added Statement list columns.
- `addons/ai_vendor_invoice/tests/test_models.py`
  - Added focused totals, check synchronization, transport-field, and view
    coverage.
- `docs/intents/CC-08-STATEMENT-FORM-TOTALS-AND-TRANSPORT-FIELDS.md`
  - Marked the authorized contract as implemented.
- `docs/reports/CC-08-IMPLEMENTATION-REPORT.md`
  - Recorded this implementation history.

## 4. Transport Order Field Decision

The loaded codebase has no authoritative transport-order model or Canonical
`order_id` / `order_no` source. To avoid inventing a relationship or silently
mapping incorrect business data:

- `order_no` is implemented as an optional `Char`;
- `order_id` is implemented as an optional `Char`;
- current extraction paths preserve these values when supplied by a payload;
- no fake Many2one relationship, transport-order synchronization, or new
  transport-order model was introduced.

This is the smallest implementation consistent with the approved contract.
If a real transport-order model becomes available, the field type and source
mapping should be revisited in a separate contract.

## 5. Behavioral Details

### Totals

Header totals continue to use the existing `_compute_totals` implementation and
currency rounding. The change does not create a second totals calculation
path.

### Check synchronization

- Empty Statements report `all_checked = False`.
- `all_checked = True` writes `checked = True` to all current lines.
- `all_checked = False` writes `checked = False` to all current lines.
- A line-level check change recomputes the header value.
- The inverse is restricted to draft Statements.

### Product domain

The loaded Odoo product model exposes the service classification as `type`, so
the form and embedded line list use:

```python
[("type", "=", "service")]
```

Existing stored product values are not rewritten by this view-only domain.

## 6. Tests

Added and ran focused coverage for:

- Statement totals after multiple lines;
- overall tax-rate calculation;
- `checked` and `all_checked` synchronization;
- transport-order value preservation;
- service-product domain presence;
- Statement form and list view field presence;
- existing Statement creation and lifecycle behavior.

The test does not call a real AI provider, process a real supplier PDF, or
create a Vendor Bill.

Validation results:

- Focused `TestImportTaskModel`: passed after correcting the floating-point
  assertion to use tolerance-aware comparison.
- Full `/ai_vendor_invoice` addon test run: process exit code `0`.
- The full run emitted existing warnings about unrelated unavailable modules
  (`wd_tlms`, `worlddepot`, and related modules), but no CC-08 test failure or
  error was reported.

## 7. Regression Boundary

The implementation does not modify:

- Provider or ParseAttempt behavior;
- Canonical schema;
- Mapping or retry behavior;
- Statement state transitions;
- Chatter attachment behavior;
- workflow audit logging;
- Vendor Bill creation;
- automatic confirmation or business approval.

## 8. Deviations

The requested transport-order fields were not backed by an existing source
model. They are therefore optional text fields rather than a guessed relational
field. This deviation is explicit and recorded above; no unrelated transport
integration was added.

## 9. Completion

CC-08 implementation is complete within the authorized scope.
