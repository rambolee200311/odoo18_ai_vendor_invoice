# FIX-INTENT-AI-VENDOR-PAGE-EXTRACTION-001

> Status: Implemented; real fixture validation pending
> Scope: DeepSeek Vision page extraction and document normalization

## Objective

Separate page recognition from document-level invoice normalization:

```text
PDF page -> PageExtractionResult[] -> document normalization -> CanonicalResult
```

This fix keeps the DeepSeek Vision API and the existing ParseAttempt,
Mapping, Statement, Human Review, Bill Creator, and Task state contracts.
It does not introduce DeepSeek-OCR, a local model, CUDA, or an OCR service.

## Contract

Each page request returns a structured, deliberately incomplete
`PageExtractionResult`. It records only content observed on that page and its
source page number. Missing supplier, invoice number, currency, totals, tax,
or lines are valid at page level.

After all pages succeed, the adapter performs one document normalization pass.
The normalizer fills the existing frozen CanonicalResult shape, accepts headers
from the first non-empty page, combines lines in page order, and rejects
conflicting document identity/totals. Final schema validation remains the
single source of truth for `ParseAttempt.canonical_result`.

Page extraction failures are classified as response/schema failures. Document
normalization failures are classified as `DOCUMENT_NORMALIZATION_INVALID`.
Neither is reported as an HTTP failure when the provider returned HTTP 200.

## Acceptance

The acceptance evidence must distinguish:

```text
Vision page extraction PASS
-> PageExtractionResult[] PASS
-> document normalization PASS/FAIL
-> Canonical Schema PASS/FAIL
```

Bring, Feelogic, and Mainfreight fixtures must be rerun. A fixture may fail,
but the failing layer and persisted diagnostic category must be explicit.
