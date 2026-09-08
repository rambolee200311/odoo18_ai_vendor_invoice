# CC-01 — AI Invoice Independent Application

> Document Type: Coding Contract  
> Status: `DRAFT — NOT AUTHORIZED`  
> `IMPLEMENTATION_AUTHORIZED = NO`  
> Target: Odoo 18.0

## 1. Contract Goal

Present the existing `ai_vendor_invoice` addon as an independent Odoo application with
its own application entry point and navigation root. This is a product/navigation
boundary, not permission to create a second addon or redesign the AI pipeline.

## 2. Current State

- `addons/ai_vendor_invoice/__manifest__.py` currently has `"application": False`.
- The technical addon is already one bounded module: models, services, security, views,
  assets, scheduled data, and tests live under `addons/ai_vendor_invoice`.
- Manifest dependencies are `account`, `contacts`, and `queue_job`; `account` remains
  valid because the module creates and traces vendor bills.
- The two current menus are declared in `views/import_task_views.xml` and both use
  `parent="account.menu_finance"`.
- Existing actions/models are:
  - `action_vendor_invoice_import_task` → `vendor.invoice.import.task`
  - `action_vendor_invoice_statement` → `vendor.invoice.statement`
- Task, Statement, Statement Line, Provider Config, ParseAttempt, and Bill Creator
  boundaries are already implemented and are not to be redesigned.

## 3. In Scope

- Set the addon application flag and application-facing metadata.
- Add one addon-owned root application menu.
- Place existing AI Invoice navigation below that root.
- Preserve existing technical addon, model, action, and XML identifiers.
- Verify clean install/upgrade and visibility under existing security groups.

## 4. Out of Scope

- Creating a second addon.
- Removing `account` or `queue_job` dependencies.
- Renaming models, database tables, or technical addon directory.
- Moving data or changing AI extraction, Mapping, Task, ParseAttempt, queue, or Bill
  Creator behavior.
- Copying or replacing `account.move`.

## 5. Business Rules

1. AI Invoice is entered as a standalone Odoo application.
2. Vendor Bill integration remains a business relationship, not a navigation ownership
   relationship.
3. Existing reviewer, user, and configuration-manager permission semantics remain intact.

## 6. Technical Boundaries

- Ownership is defined by the addon manifest and addon-owned root menu.
- `account` remains a technical dependency.
- Existing actions continue to target their current models.
- Existing aggregate-command mutation boundaries remain unchanged.

## 7. Allowed Changes

- `__manifest__.py` application metadata.
- Addon-owned root menu and parent references.
- Menu/action sequence or presentation metadata required for the new root.
- Installation/navigation documentation and focused tests.

## 8. Forbidden Changes

- New addon or model namespace.
- Database migration or model/table rename.
- Security broadening.
- AI pipeline or vendor-bill logic changes.

## 9. Impacted Files / Models / Views

- `addons/ai_vendor_invoice/__manifest__.py`
- `addons/ai_vendor_invoice/views/import_task_views.xml`
- Existing models `vendor.invoice.import.task`, `vendor.invoice.statement`,
  `vendor.invoice.statement.line`, and `wd.ai.provider.config`: no schema change.

## 10. Data / Migration Impact

No data migration is expected. Existing XML IDs, actions, model records, and menu records
must survive module upgrade. If a parent menu change requires an XML update, it must be
idempotent and must not create duplicate legacy navigation.

## 11. Security Impact

No ACL, record rule, or group change is authorized. Menu visibility must continue to
follow the existing access model.

## 12. Compatibility / Regression Requirements

- Existing action URLs and bookmarks remain valid.
- Existing action XML IDs and model bindings remain valid.
- Clean install and upgrade work with declared dependencies only.
- No deprecated synchronous invoice-import dependency is introduced.

## 13. Acceptance Criteria

- Manifest reports the addon as an Odoo application.
- A root application entry owned by this addon is visible.
- Existing Import and Statement actions open the same models as before.
- No duplicate Accounting-owned legacy menus remain visible.
- Existing security groups retain their current access behavior.
- No Task, Statement, Provider Config, ParseAttempt, or Bill Creator behavior changes.

## 14. Test Requirements

- Manifest/application metadata check.
- Clean install and module upgrade check.
- Menu parent, action, model, and XML ID assertions.
- Existing model/service/security tests remain green.

## 15. Open Questions

`OPEN_QUESTIONS = NONE`

## 16. Authorization Status

`DRAFT — NOT AUTHORIZED`  
`IMPLEMENTATION_AUTHORIZED = NO`
