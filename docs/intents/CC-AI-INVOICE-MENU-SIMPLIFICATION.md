# CC-02 — AI Invoice Menu Simplification

> Document Type: Coding Contract  
> Status: `DRAFT — NOT AUTHORIZED`  
> `IMPLEMENTATION_AUTHORIZED = NO`  
> Depends on: CC-01 navigation root

## 1. Contract Goal

Shorten AI Vendor Invoice navigation labels without changing business behavior, actions,
security, workflow, or schemas.

## 2. Current State

| Current Menu Name | XML ID | Parent Menu | Action |
| --- | --- | --- | --- |
| `AI Vendor Invoice Imports` | `menu_vendor_invoice_import_task` | `account.menu_finance` | `action_vendor_invoice_import_task` |
| `Vendor Invoice Statements` | `menu_vendor_invoice_statement` | `account.menu_finance` | `action_vendor_invoice_statement` |

The action display names are currently `Vendor Invoice AI Imports` and
`Vendor Invoice Statements`. There is no addon-owned root menu.

## 3. In Scope

Recommended navigation:

| Current | Proposed | Technical object |
| --- | --- | --- |
| — | `AI Invoice` | new addon-owned root menu |
| `AI Vendor Invoice Imports` | `Imports` | `menu_vendor_invoice_import_task` |
| `Vendor Invoice Statements` | `Statements` | `menu_vendor_invoice_statement` |

Only menu display names, necessary sequence values, and the parent relationship required
by CC-01 may change.

## 4. Out of Scope

- Action business behavior, domains, views, models, security, workflow, and AI pipeline.
- Technical XML ID, model name, action ID, or database table renames.
- Renaming fields or changing Statement state behavior.

## 5. Business Rules

1. The user should see one concise `AI Invoice` application entry.
2. `Imports` means AI import tasks; `Statements` means reviewed invoice statements.
3. Labels must not repeat the full module name when the parent already supplies context.

## 6. Technical Boundaries

- Existing action IDs and model bindings remain authoritative.
- Existing menus remain the same records where possible.
- The new root is addon-owned; it must not be an alias or duplicate legacy menu.

## 7. Allowed Changes

- Menu `name`.
- Menu `sequence`.
- Menu `parent` as required by CC-01.
- Root menu declaration.
- Action display labels only if needed for coherent navigation; action behavior is frozen.

## 8. Forbidden Changes

- `res_model`, `view_mode`, action domain, security groups, ACLs, and record rules.
- Any Task, Statement, Provider Config, ParseAttempt, or Bill Creator code.

## 9. Impacted Files / Models / Views

- `addons/ai_vendor_invoice/views/import_task_views.xml`
- Menu/action records only; no model or view schema change.

## 10. Data / Migration Impact

No business data migration. XML IDs must remain stable so existing bookmarks and external
references continue to resolve. Upgrade must not leave duplicate old-label menus.

## 11. Security Impact

No security change. Existing menu visibility and model access remain unchanged.

## 12. Compatibility / Regression Requirements

- `Imports` opens `vendor.invoice.import.task`.
- `Statements` opens `vendor.invoice.statement`.
- Existing action URLs remain valid.
- No menu is visible twice through Accounting and AI Invoice navigation.

## 13. Acceptance Criteria

- The application shows `AI Invoice` as the root.
- The child labels are exactly `Imports` and `Statements`, unless product review approves
  an explicit alternative.
- Existing XML IDs and actions remain intact.
- No functional behavior changes.

## 14. Test Requirements

- Read menu records and assert name, parent, sequence, action, and XML IDs.
- Upgrade check for duplicate menus.
- Access checks for AI Invoice User, Reviewer, and Config Manager.

## 15. Open Questions

`OPEN_QUESTIONS = NONE`

## 16. Authorization Status

`DRAFT — NOT AUTHORIZED`  
`IMPLEMENTATION_AUTHORIZED = NO`
