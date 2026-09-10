# CC-08 — Statement Form Totals, Check Selection, and Transport Order Fields

> Document Type: Coding Contract
> Status: `AUTHORIZED FOR IMPLEMENTATION`
> `IMPLEMENTATION_AUTHORIZED = YES`
> Target: Odoo 18.0

## 1. Contract Goal

Improve the `vendor.invoice.statement` review views for invoice totals, line
selection, and transport-order traceability while preserving the existing
Statement aggregate, lifecycle, human-review, and Chatter behavior.

This contract authorizes design and implementation only after explicit approval.
It does not authorize coding by itself.

## 2. Current Scope Boundary

The existing production chain remains:

```text
Task
-> ParseAttempt
-> Canonical
-> Vendor Invoice Statement
-> Human Review
```

This contract is limited to:

- Statement header totals and aggregate tax rate;
- Statement line checked and transport-order information;
- Statement header `all checked` selection behavior;
- Statement line product filtering;
- Statement list columns and native aggregate totals.

No Vendor Bill, automatic confirmation, risk score, provenance, or custom review
widget is included.

## 3. In Scope

### 3.1 Statement form header totals

The Statement form must expose the following read-only header values:

| Business value | Existing canonical field | Display meaning |
|---|---|---|
| Untaxed Amount | `subtotal` | Sum of Statement line untaxed amounts |
| Tax Amount | `total_tax` | Sum of Statement line tax amounts |
| Total Amount | `total_amount` | Sum of Statement line totals including tax |
| Overall Tax Rate | `overall_tax_rate` | `total_tax / subtotal * 100`, with a safe zero-subtotal result |

The values must remain consistent with the current currency rounding and
`_compute_totals` semantics. The implementation must not introduce a second,
conflicting total-calculation path.

When a Statement line changes in the editable draft form, the header totals and
overall tax rate must refresh through the existing ORM dependency/onchange
behavior. The implementation must not depend on a browser-only calculation to
persist correct values.

### 3.2 Statement line list totals

The Statement Lines list in the Statement form must display native Odoo
aggregate footers for:

- Untaxed Amount (`amount`);
- Tax Amount (`tax_amount`);
- Total Amount (`total_amount`).

The footer must aggregate the currently displayed Statement lines using Odoo's
native list-view aggregation behavior. It must not create a second summary line
record and must not change `line_ids` persistence.

### 3.3 Statement line checked field

Each `vendor.invoice.statement.line` must expose a Boolean field:

```text
checked
```

The field is used for human review selection. Its intended behavior is:

- editable while the parent Statement is in draft/reviewable state;
- read-only when the parent Statement is not editable under existing lifecycle
  rules;
- persisted on the Statement line;
- included in the Statement line list and line form where appropriate.

The implementation must preserve existing line creation, update, deletion,
candidate application, and Statement lifecycle semantics.

### 3.4 Transport order fields

Each Statement line must expose:

| Field | Meaning | Required implementation decision |
|---|---|---|
| `order_no` | Transport order number | Preserve the source value as a user-visible traceability field |
| `order_id` | Transport order identifier | Confirm the actual source type and target model before coding; do not infer a Many2one relationship solely from the label |

The final field types and source mapping must follow the currently loaded
Canonical/Statement data model. If no authoritative transport-order source
exists in current production data, the fields must not be populated with
invented values; the implementation must report the gap before coding.

### 3.5 Statement header `all checked`

The Statement header must expose a Boolean field:

```text
all_checked
```

Its behavior must be:

- checking `all_checked` checks all current `line_ids`;
- unchecking `all_checked` unchecks all current `line_ids`;
- changing an individual line must refresh `all_checked` to reflect whether all
  current lines are checked;
- an empty Statement has an explicitly defined result, preferably `False`;
- the behavior applies only to the current Statement's lines;
- the operation must respect existing draft/review editability and access rules.

The implementation may use a computed field with inverse and/or a narrowly
scoped onchange, but it must keep persisted line state authoritative and avoid
duplicating line records.

### 3.6 Product service domain

The Statement line Product field must default to the Odoo service-product
domain used by the loaded Odoo 18 model. In the currently loaded product model,
the service classification is:

```python
[("type", "=", "service")]
```

The actual field and model definition must be checked before implementation.
The domain must not silently prevent existing stored products from being
displayed or edited when they are already present on a Statement.

### 3.7 Statement list view

The Statement list view must add the following columns:

- Supplier;
- Untaxed Amount;
- Tax Amount;
- Total Amount;
- Overall Tax Rate;
- All Checked.

Existing useful columns, ordering, access rules, and search behavior must remain
intact unless a specific conflict is found.

## 4. Onchange and Persistence Rules

1. Existing stored totals remain the source of truth for persisted Statement
   totals.
2. Line edits must invalidate/recompute Statement totals through declared ORM
   dependencies.
3. `all_checked` must not become stale after line creation, deletion, candidate
   application, or manual line edits.
4. UI onchange behavior must not be the only protection for server-side
   commands.
5. No automatic confirmation or business approval may be triggered by checking
   one line or all lines.
6. The current Statement state machine and human confirmation boundary remain
   unchanged.

## 5. Security and Access

- Existing Statement and Statement Line ACLs remain authoritative.
- Users may only change `checked`, `all_checked`, and editable line values when
  the current Statement lifecycle permits editing.
- The new fields must not expose another company's transport-order data.
- No `sudo()`, new broad record rule, or new arbitrary CRUD permission is
  allowed.
- The product domain must not bypass existing company or product access rules.

## 6. Out of Scope

- Vendor Bill creation or modification;
- `account.move` behavior;
- automatic confirmation, risk scoring, or approval rules;
- field-level provenance or Evidence;
- custom OWL/JavaScript review widgets;
- side-by-side PDF review;
- transport-order synchronization or a new transport-order model;
- dynamic Mapping;
- changes to Provider, ParseAttempt, Canonical, retry, or fallback behavior;
- replacing Chatter or workflow audit logs;
- new generic selection or aggregate frameworks.

## 7. Required Pre-Coding Verification

Before implementation, confirm against the loaded code:

1. Existing `subtotal`, `total_tax`, `total_amount`, and
   `overall_tax_rate` computation and dependency behavior.
2. Existing Statement Line fields and aggregate creation values.
3. Whether `checked`, `order_no`, and `order_id` already exist under another
   name or on the Canonical source.
4. The authoritative type and source of `order_id`.
5. The actual Odoo 18 service-product field/domain.
6. Existing lifecycle restrictions for Statement and Statement Line writes.
7. Whether the current list view supports the requested native sum footers for
   each monetary field.
8. Existing tests for totals, line editing, candidate application, and
   Statement list/form views.

If the actual loaded code differs from this contract, actual code takes
precedence and the deviation must be recorded before implementation.

## 8. Required Tests

At minimum, add focused tests for:

1. Header totals remain correct after line creation and line edits.
2. Overall tax rate handles a zero untaxed subtotal without an error.
3. Native Statement line list footers expose the three requested sums.
4. `checked` is persisted and respects Statement editability.
5. Checking `all_checked` checks all lines.
6. Unchecking `all_checked` unchecks all lines.
7. Individual line changes refresh `all_checked`.
8. Empty-line `all_checked` behavior is deterministic.
9. `order_no` and `order_id` preserve the verified source values and types.
10. Product selection is restricted to service products without breaking
    existing stored lines.
11. Statement list view includes supplier, totals, tax rate, and all-checked
    columns.
12. Existing Statement creation, candidate application, confirmation, Chatter,
    and audit behavior remains unchanged.

Tests must not call a real AI provider, process real supplier PDFs, or create
Vendor Bills.

## 9. Acceptance Criteria

CC-08 is complete only when:

- header totals and overall tax rate are visible and remain accurate;
- Statement line list has native untaxed/tax/total aggregate footers;
- line checked, order number, and order identifier are available with verified
  semantics;
- header all-checked behavior is bidirectionally consistent with line values;
- Product selection is limited to service products according to the loaded
  Odoo model;
- Statement list exposes supplier, totals, tax rate, and all-checked;
- existing lifecycle, security, Chatter, audit, and human-confirmation behavior
  remains unchanged;
- focused tests and relevant regression tests pass.

## 10. Authorization Status

```text
AUTHORIZED FOR IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

Implementation requires explicit user authorization after review of the
verified field types, transport-order source mapping, and proposed onchange
semantics.
