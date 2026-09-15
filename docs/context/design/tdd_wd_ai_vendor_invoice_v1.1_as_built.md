# AI Vendor Invoice TDD v1.1 — As-Built Baseline

**版本**：TDD v1.1
**状态**：FROZEN — RELEASE 1.1 AS-BUILT BASELINE
**冻结日期**：2026-09-15
**方法**：AS-BUILT DOCUMENTATION
**范围**：已实现并验证的 Statement、AI Task、Extraction Profile 与 Batch 流程

## 1. Release 1.1 Boundary

Release 1.1 retains the Statement-first architecture:

```text
Statement -> source PDF -> Task -> ParseAttempt
          -> Provider/Input Mode -> Canonical
          -> automatic Statement projection -> review
          -> Confirm -> Vendor Bill
```

Statement remains the human business workspace and authority. Task and
ParseAttempt remain technical execution and audit records.

## 2. Entry Points

### 2.1 Single Statement

The normal single-document flow is:

```text
Statements -> New -> upload PDF -> Save
           -> AI / Task -> Provider / Execution Mode -> Run AI
           -> automatic result projection -> review -> Confirm
```

Run AI is available for a Draft Statement with a Task in `to_parse`, `error`,
`awaiting_review`, or `parsed`. A rerun keeps the same Task and creates a new
ParseAttempt.

### 2.2 Batch Import

The Batch Import Wizard contains:

- Company;
- optional trusted Supplier;
- AI Provider;
- one or more PDF files.

When Supplier is selected, the batch persists that supplier on the Batch and
each created Statement. The mapped Profile is passed as an explicit
`extraction_profile_key` to every Statement launch and ParseAttempt.

When Supplier is empty, the batch uses the Generic Profile. A batch is
expected to contain invoices from one supplier; mixed suppliers should be
split into separate batches.

## 3. Provider and Input Mode

Provider and Input Mode remain separate concerns:

- Native PDF uses the native PDF Prompt;
- Markdown uses the Markdown Prompt;
- rendered-image paths use the vision Prompt;
- the selected Extraction Profile Extension is composed onto the active
  Input-Mode Prompt.

Profile selection never changes Provider or Input Mode.

## 4. Extraction Profiles

The code-managed registry contains:

- `generic`;
- `ups_transport`, version `ups-transport-v5`.

Generic is used when no explicit or trusted supplier mapping selects a
Specialized Profile. An explicit Profile assignment is not silently replaced
by Generic when the requested Profile is invalid.

UPS Profile semantics include:

- `BTW` means Dutch VAT (`Belasting over de toegevoegde waarde`);
- `21% BTW` is a VAT rate, not a charge or discount;
- a BTW row below Total Charges applies to the consolidated transport line;
- Charge, Discount, and Net Charge remain nested charge facts;
- line `tax_rate` and `tax_amount` are populated when the document provides
  applicable line tax facts.

Native extraction supports nullable line `tax_rate` and `tax_amount` fields,
which project to the shared Canonical and Statement Line contract.

## 5. Audit and Rerun

Every ParseAttempt records the actual Profile key, Profile version, extension
version, and extension checksum. On rerun, a previously resolved Specialized
Profile is retained rather than being replaced by Generic because the
Statement now has an AI-derived source Attempt.

## 6. Frozen Non-Goals

This baseline does not introduce:

- new Providers;
- new Canonical versions;
- supplier-specific Statement models;
- mixed-supplier batch inference;
- configurable user-managed Profiles;
- changes to Statement authority or Vendor Bill workflow.

## 7. Verification Record

The Release 1.1 implementation was checked against:

- UPS Native PDF and Markdown comparisons;
- UPS Statement line VAT projection (`21%`, `2.69`);
- DHL Generic Compatibility UAT for Statements 1809 and 1810;
- Batch Supplier selection and explicit Profile propagation;
- targeted extraction, native projection, task, and batch regression tests;
- 8091 runtime health check.
