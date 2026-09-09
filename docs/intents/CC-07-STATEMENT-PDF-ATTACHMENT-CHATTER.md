# CC-07 — Statement PDF Attachment and Native Chatter

> Document Type: Coding Contract
> Status: `AUTHORIZED FOR IMPLEMENTATION`
> `IMPLEMENTATION_AUTHORIZED = YES`
> Target: Odoo 18.0

## 1. Contract Goal

Make the original supplier invoice PDF available from the `vendor.invoice.statement`
record and add the native Odoo Chatter to the Statement form. Users must be able to use
Odoo's standard attachment behavior to open/preview the PDF without introducing a custom
PDF viewer or field-level evidence feature.

## 2. Current State

- `vendor.invoice.import.task` stores the original PDF in
  `source_pdf_attachment_id`.
- `vendor.invoice.statement` already links to its source Task through `task_id` and to
  the source ParseAttempt through `source_parse_attempt_id`.
- The current Statement model has no PDF attachment field and does not inherit
  `mail.thread` or `mail.activity.mixin`.
- The current Statement form has no `<chatter/>` area.
- The current Task form exposes the source PDF attachment and an Audit Log notebook.
- Existing aggregate commands create and modify Statements; this contract must not bypass
  those command boundaries.

## 3. In Scope

1. Make the original supplier invoice PDF available as an attachment of the Statement.
2. Preserve the relationship to the source Task and source ParseAttempt.
3. Add native Odoo Chatter support to `vendor.invoice.statement`.
4. Add the native Chatter component to the Statement form view.
5. Allow users with existing Statement access to use standard attachment open/preview
   behavior from the Statement record.
6. Keep the existing Statement business values, lifecycle, aggregate commands, and
   human-confirmation boundary unchanged.

### Attachment behavior

- The Statement must expose a PDF attachment associated with the Statement record.
- The implementation should reuse the existing source PDF attachment where Odoo
  attachment ownership and security permit it, avoiding unnecessary duplicate binary
  storage.
- If association to both Task and Statement cannot safely reuse one attachment, a
  controlled attachment copy is permitted, but it must preserve the original PDF bytes,
  access rules, and source Task traceability.
- The Statement attachment must be available to the native Chatter attachment UI; no
  custom preview component is authorized.
- Non-PDF or missing source attachments must not be silently presented as a valid PDF.
  Existing validation/error conventions must be used.

### Chatter behavior

- Statement inherits the standard Odoo mail threading capability required by native
  Chatter.
- The form includes the native `<chatter/>` component.
- Users can use standard Odoo functions such as viewing/download/previewing an attached
  PDF, subject to existing ACLs and record rules.
- Chatter messages and attachments are scoped to the Statement record and do not expose
  another company's invoice.

## 4. Out of Scope

- Custom OWL, JavaScript, CSS, iframe, or PDF viewer.
- Side-by-side PDF and Statement layout.
- Field-level raw text, page number, coordinates, or provenance.
- Canonical schema, ProviderCall, ParseAttempt, Mapping, or extraction changes.
- New Statement workflow states or transition rules.
- Vendor Bill Creator, `account.move`, posting, payment, or reconciliation behavior.
- Automatic fallback, automatic confirmation, Risk Score, or dynamic Mapping.
- Replacing the existing Task Audit Log with Chatter.
- Introducing a generic Evidence or audit platform.

Chatter is an additional native collaboration surface; the existing structured audit
log remains responsible for the current workflow event records.

## 5. Business Rules

1. The PDF shown from a Statement must be the original supplier invoice PDF belonging to
   that Statement's source Task.
2. Attaching the PDF to Statement must not alter Canonical values, Statement values, or
   the source ParseAttempt.
3. Existing Task-to-Statement traceability must remain valid.
4. Statement creation through the existing Task aggregate commands must populate or
   establish the Statement PDF attachment.
5. Existing reviewers, users, company boundaries, and attachment access rules remain
   authoritative.
6. Chatter messages do not constitute field-level human-change audit records.
7. A missing or invalid source PDF must produce a visible, convention-consistent error;
   it must not create a misleading success-shaped attachment state.

## 6. Technical Boundaries

- Use the standard Odoo mail thread/chatter mechanism.
- Use existing `ir.attachment` records and access rules; do not store PDF bytes in a
  new custom binary field.
- Keep `source_pdf_attachment_id` on Task as the source-of-truth relationship unless a
  narrowly scoped Statement attachment relation is required for native record access.
- Any new Statement attachment relation must be read-only to ordinary users and must be
  populated through the existing Statement creation/aggregate path.
- Do not expose generic Statement CRUD or bypass reviewer/aggregate-command guards.
- Do not use `sudo()` to broaden user access to another company’s attachment.

## 7. Allowed Changes

- `vendor.invoice.statement` inheritance from the required native mail mixin(s).
- A narrowly scoped Statement-to-PDF attachment relation or attachment association
  required to make the existing source PDF available from Statement.
- Statement creation/projection wiring needed to associate the existing source PDF.
- `views/import_task_views.xml` Statement form update with native `<chatter/>`.
- Manifest dependency metadata only if the existing addon does not already declare the
  native mail dependency required by the chosen Odoo mixin.
- Focused model, view, attachment-access, and regression tests.

## 8. Forbidden Changes

- New custom PDF preview implementation.
- New binary storage that duplicates the PDF without a demonstrated Odoo requirement.
- Changes to Canonical, Structured Output, Provider, Mapping, or ParseAttempt semantics.
- Changes to Statement field values, line structure, state machine, or confirmation rules.
- Changes to Vendor Bill creation or accounting behavior.
- Security broadening, cross-company attachment access, or public attachment exposure.
- Replacing or weakening the existing Audit Log.
- Automatic creation of Chatter messages for every field write unless separately
  authorized.

## 9. Impacted Files / Models / Views

- `addons/ai_vendor_invoice/models/statement.py`
- `addons/ai_vendor_invoice/models/import_task.py` (only Statement attachment wiring,
  if required)
- `addons/ai_vendor_invoice/views/import_task_views.xml`
- `addons/ai_vendor_invoice/__manifest__.py` (only if a native mail dependency is absent)
- Focused Statement, attachment-security, and view tests

Existing Task, ParseAttempt, Canonical, ProviderCall, Mapping, and Vendor Bill behavior
must remain unchanged.

## 10. Data / Migration Impact

- Existing Statements must remain readable after upgrade.
- Existing Statements created before this change must either resolve their source PDF
  through the existing Task relationship or receive a deterministic attachment
  association during upgrade.
- No PDF bytes may be lost or silently replaced.
- No migration may change the original PDF content.
- If a new stored relation is introduced, its backfill must be limited to
  `Statement -> task -> source_pdf_attachment_id` and must be safe for missing/deleted
  attachments.

## 11. Security Impact

- Existing Statement ACLs and record rules remain unchanged unless the native mail
  inheritance requires the smallest explicit access metadata.
- The source PDF must remain private and company-scoped according to existing rules.
- A reviewer may preview the PDF only when the reviewer can access the Statement and its
  source Task/attachment.
- Ordinary users must not gain arbitrary attachment create/write/unlink rights through
  the Statement form.
- Chatter must not expose raw AI responses, provider secrets, or unrelated attachments.

## 12. Compatibility / Regression Requirements

- Existing Statement list/form fields and aggregate mutation paths remain usable.
- Existing Task source PDF access remains valid.
- Existing Statement provenance through `source_parse_attempt_id` remains intact.
- Existing Audit Log remains visible and unchanged in meaning.
- Existing Review widget and candidate application remain functional.
- Existing multi-company access tests continue to pass.
- Native Chatter must render without requiring custom frontend assets.

## 13. Acceptance Criteria

- A newly created Statement is associated with the original supplier invoice PDF.
- The Statement form renders native Odoo Chatter.
- A permitted user can use native attachment behavior from the Statement record to
  open/preview or download the PDF.
- The PDF bytes match the source Task attachment.
- Existing Task and Statement source relationships remain traceable.
- Missing or invalid source PDFs are surfaced visibly and are not treated as valid
  attachments.
- Existing Statement and Task values are unchanged by attachment association.
- No custom PDF viewer, OWL component, field-level provenance, or evidence platform is
  added.
- Existing company isolation and attachment permissions remain effective.

## 14. Test Requirements

- Statement form XML loads with native Chatter.
- Statement creation associates the source PDF with the Statement.
- The associated PDF has the same bytes/content as the Task source attachment.
- Existing Statement records without a resolvable attachment remain readable and show a
  controlled missing-source condition.
- Reviewer/user/config-manager attachment access follows existing security rules.
- Cross-company users cannot preview another company’s Statement PDF.
- Existing Statement projection, review, audit-log, and Task source-attachment tests
  remain green.

## 15. Open Questions

`OPEN_QUESTIONS = NONE`

The implementation may choose attachment reuse or a controlled copy according to Odoo
attachment ownership constraints, but must satisfy the same source-traceability,
security, and byte-preservation criteria.

## 16. Authorization Status

`AUTHORIZED FOR IMPLEMENTATION`
`IMPLEMENTATION_AUTHORIZED = YES`
