# Release 1.2 Closure Report

> Release: `1.2`
> Status: `CLOSED / RELEASED`
> Closure Date: `2026-09-16`
> Module: `ai_vendor_invoice`

## Release Outcome

Release 1.2 delivers the frozen CC-17 contract:

```text
Human-confirmed Statement -> Draft Vendor Bill
```

The Statement remains the only business authority. AI Provider output,
Canonical data and Mapping data do not bypass the confirmed Statement when a
Vendor Bill is created.

## Delivered Scope

- Confirmed Statement to Draft Vendor Bill creation;
- Statement/Bill bidirectional traceability;
- active-Bill idempotency;
- cancelled-Bill link release and recreation;
- per-line tax-fact resolution;
- controlled percentage Purchase Tax reuse/creation;
- explicit failure for unresolved special tax treatments;
- historical untaxed and percentage-tax compatibility;
- actionable Provider error messages;
- GPT Native PDF Structured Output Schema correction;
- user-facing workflow documentation.

## Verification Evidence

| Area | Result |
|---|---|
| CC-17 ORM transaction verification | PASS |
| Statement 1815 Draft Vendor Bill creation | PASS |
| Statement 1816 historical percentage-tax compatibility | PASS |
| GPT Native PDF test with production PDF | PASS, 5 lines |
| DeepSeek Markdown regression | PASS |
| Odoo service health check | PASS, HTTP 200 |

## Tax Boundary

AI Parse extracts tax facts such as rate, amount and printed treatment. It does
not create or select an Odoo tax code. Purchase Tax resolution belongs to the
Bill Creator after human confirmation.

## Deferred Items

- Standardized AI parse error-code taxonomy remains deferred;
- automatic posting, payment and reconciliation remain out of scope;
- Provider fallback remains out of scope;
- automatic Statement confirmation remains out of scope.

## Release Decision

Release 1.2 is approved for closure and release. The TDD as-built baseline is
[TDD v1.2](/docs/context/design/tdd_wd_ai_vendor_invoice_v1.2_as_built.md),
and the operator workflow is documented in the
[AI Invoice User Guide](/docs/user-guide/AI-INVOICE-USER-GUIDE.md).
