# CC-03 — Vendor Invoice Statement Form Design

> Document Type: Coding Contract  
> Status: `DRAFT — NOT AUTHORIZED`  
> `IMPLEMENTATION_AUTHORIZED = NO`

## 1. Contract Goal

Turn `vendor.invoice.statement` from a minimal technical form into a clear business
document form inspired by the Odoo 18 Vendor Bill hierarchy, without making it an
`account.move` or adding custom frontend code.

## 2. Current State

The current Statement form has one flat group containing `supplier_id`, `invoice_number`,
`invoice_date`, `currency_id`, `subtotal`, `total_tax`, and `total_amount`, followed by a
basic `line_ids` list. The current list shows invoice number, date, supplier, currency,
and total. There is a separate Statement Line form showing amount, tax rate, tax amount,
reconciliation clue, description, and charge details.

There is no Statement search view, no Statement chatter, and no Statement state field.
The Task form separately exposes AI Attempts, Review, and Audit Log.

Current Statement fields:

| Category | Fields |
| --- | --- |
| Identity / provenance | `task_id`, `company_id`, `source_parse_attempt_id` |
| Invoice identity | `invoice_number`, `invoice_date`, `supplier_id`, `supplier_name`, `currency_id` |
| Totals | `subtotal`, `total_tax`, `total_amount` |
| Notes | `note` |
| Lines | `line_ids` |

Current Statement Line fields include `sequence`, `description`, `product_id`, `quantity`,
`price_unit`, `amount`, `tax_raw_text`, `tax_rate`, `tax_amount`, `reconciliation_clue`,
`charge_details`, `tax_ids`, `reconciliation_clues`, and related `currency_id`.

## 3. In Scope

Use native Odoo form primitives and Vendor Bill-like information hierarchy:

1. `form` / `sheet` / `header`, reserving a status display position for CC-04.
2. Header business identity: supplier, invoice number, invoice date, currency.
3. Main invoice line list with product, description, quantity, unit price, tax information,
   amount, and reconciliation clue where useful.
4. Totals area: subtotal, tax, total.
5. Notebook pages:
   - Additional Information: notes and useful source context.
   - Technical / Provenance: Task, ParseAttempt, source attachment/provider information,
     read-only.
6. Statement Line list plus separate line form for quick review and editing.
7. Optional native relational buttons/links only where existing relationships justify them.

### Field Placement Matrix

| Field | Proposed location | Editability |
| --- | --- | --- |
| `supplier_id`, `invoice_number`, `invoice_date`, `currency_id` | Header identity group | Reviewer in editable lifecycle |
| `subtotal`, `total_tax`, `total_amount` | Totals block | Reviewer through aggregate command |
| `line_ids` | Main invoice-lines section | Reviewer through aggregate command |
| `note` | Additional Information notebook page | Reviewer through aggregate command |
| `task_id`, `source_parse_attempt_id`, `company_id` | Technical / Provenance page | Read-only |
| `supplier_name` | Additional/technical fallback context | Read-only or controlled by aggregate |
| `sequence`, `product_id`, `description`, `quantity`, `price_unit`, `amount` | Line list and line form | Reviewer through aggregate command |
| `tax_raw_text`, `tax_rate`, `tax_amount`, `tax_ids` | Line tax group | Reviewer through aggregate command |
| `charge_details`, `reconciliation_clue`, `reconciliation_clues` | Line details group | Reviewer through aggregate command |

## 4. Out of Scope

- Custom OWL, JS, CSS, dashboard, kanban, or decorative HTML.
- New charge child model or three-level charge structure.
- New persistent fields solely for visual layout.
- Chatter unless separately approved; current model has no chatter foundation.
- State transition implementation; CC-04 owns lifecycle behavior.
- AI pipeline, projection schema, Mapping, reconciliation, or Vendor Bill accounting logic.

## 5. Business Rules

1. Statement remains the human-authoritative review document.
2. The form must not present AI provenance as editable business truth.
3. Statement Lines remain one level below Statement.
4. Current aggregate commands remain the only business mutation path.
5. A status location may be reserved, but its behavior is defined only by CC-04.

## 6. Technical Boundaries

- Native Odoo XML views only.
- Follow Vendor Bill hierarchy, not Vendor Bill inheritance.
- The generated `account.move` remains a linked output, not the Statement model.

## 7. Allowed Changes

- Statement form/list XML layout.
- Statement Line embedded list and form presentation.
- New Statement search view using existing fields, if needed for usability.
- Read-only/invisible/group placement attributes consistent with lifecycle guards.

## 8. Forbidden Changes

- Python model schema changes for layout.
- Removing existing business fields or breaking aggregate commands.
- Generic CRUD exposure through a redesigned form.
- Custom frontend code or unrelated accounting changes.

## 9. Impacted Files / Models / Views

- `addons/ai_vendor_invoice/views/import_task_views.xml`
- `vendor.invoice.statement` and `vendor.invoice.statement.line` view references.
- `models/statement.py`: no required schema change.
- `models/import_task.py`, projection, and bill creator: behavior unchanged.

## 10. Data / Migration Impact

No data migration and no new persistent fields are expected. Existing Statement and Line
records must render in the redesigned views. Existing XML IDs should be retained unless a
new search view is needed.

## 11. Security Impact

No ACL or record-rule change. View editability must not bypass reviewer authorization or
aggregate-command guards.

## 12. Compatibility / Regression Requirements

- Existing review dialog and candidate application remain usable.
- Statement Line quick view and form edit remain available to reviewers.
- Projection output remains semantically unchanged.
- Existing task-to-statement and statement-to-bill traceability remains visible.

## 13. Acceptance Criteria

- Form reads as a business document in Vendor Bill-like order.
- Header, lines, totals, additional information, and technical provenance are distinct.
- Required line fields remain visible in list and line form.
- No custom OWL/JS/CSS is added.
- Existing records open without migration or missing-field errors.
- List view is synchronized with the new identity/status/total hierarchy.
- Search view is added only if it improves finding Statements using existing fields.

## 14. Test Requirements

- XML view load/upgrade test.
- Form/list field presence and model-binding assertions.
- Reviewer editing and non-reviewer access regression tests.
- Existing Statement projection and Bill Creator tests remain green.

## 15. Open Questions

`OPEN_QUESTIONS = NONE`

## 16. Authorization Status

`DRAFT — NOT AUTHORIZED`  
`IMPLEMENTATION_AUTHORIZED = NO`
