# INTENT-TEST-AI-VENDOR-EXTRACTION-CONTRACT-001

> Date: 2026-08-26
> Status: TEST IMPLEMENTATION AUTHORIZED
> Scope: Tests for the DeepSeek Vision extraction contract

## 1. Objective

Define the regression coverage for
`FIX-INTENT-AI-VENDOR-EXTRACTION-CONTRACT-001`. The tests must prove that
Vision extraction remains a page-fact contract and does not silently become a
business decision layer.

This Intent defines tests only. It does not change production behavior,
Statement, Human Review, Mapping, Bill Creator, or the Task state machine.

## 2. Test boundaries

### Included

- Prompt constants and version values;
- final OpenAI-compatible `messages` structure;
- model and request options bound to the active frozen extraction contract;
- PageExtractionResult scalar fields;
- `raw_facts` and line `raw_fields`;
- Python injection of `source_page`;
- rejection of model-supplied `source_page` and local provenance injection;
- removal of page-level `is_multi_invoice`;
- document-level multi-invoice detection;
- deterministic lexical normalization;
- non-classification of uncertain references;
- ParseAttempt prompt/contract/model snapshots;
- private raw-response attachment persistence.

### Excluded

- DeepSeek network calls in unit tests;
- real API keys or raw provider payloads;
- carrier-specific branches;
- changes to Statement or Review behavior;
- Mapping master data behavior;
- Bill Creator behavior;
- Task state-machine redesign.

## 3. Required test cases

### Prompt and request contract

1. System Prompt identifies the model as a transport-supplier-invoice page
   fact extractor.
2. System Prompt prohibits guessing, autocomplete, calculation, and
   cross-page inference.
3. System Prompt prohibits interpreting Shipment Number, Dossier, O.No.,
   Opdracht, Uw ref., and Your reference as `invoice_number` without an
   explicit invoice-number label.
4. User Prompt requires explicit headers, fee lines, dates, addresses, and
   raw facts.
5. User Prompt does not request page-level `is_multi_invoice`.
6. The final request contains exactly one system message and one user message,
   with text followed by one page image.
7. `response_format.type` is `json_object`.
8. Request options match the active frozen extraction-contract version.
9. Provider-specific reasoning/thinking options, when required by the frozen
   contract, are included exactly as defined by that contract. For the current
   `vision-extraction-v1.1` fixture this means `reasoning_effort=high` and
   `thinking.type=enabled`.
10. SDK automatic retries remain disabled.

#### Prompt test rule

Prompt tests assert required semantic clauses and contract markers, not
byte-for-byte equality of the complete Prompt text. Full Prompt snapshots are
acceptance gates only when explicitly versioned as immutable fixtures.

### PageExtractionResult

11. Standard header fields accept plain scalar values.
12. Standard line fields accept plain scalar values.
13. Missing fields are accepted.
14. `raw_facts` requires `source_label` and `source_value`.
15. Line `raw_fields` requires `source_label` and `source_value`.
16. Python injects the local `source_page`.
17. PageExtractionResult rejects model-supplied `source_page`. After successful
    schema validation, the Adapter injects `source_page` from the locally known
    PDF page index.
18. Page-level `is_multi_invoice` is rejected.
19. Top-level `references` and `addresses` are rejected.

### Normalizer behavior

- 20. PageExtractionResults are normalized in PDF page order, regardless of
     asynchronous provider completion order.
- 21. Line items from all pages are preserved in stable page/line sequence.
- 22. Duplicate header facts do not accidentally deduplicate legitimate
     invoice lines.
- 23. Empty-header detail pages remain valid and preserve their lines and raw
     facts.
- 24. Identical invoice numbers across pages merge successfully.
- 25. Different explicitly-labelled current-document `invoice_number`
     candidates from independent invoice-header contexts trigger document-level
     multi-invoice detection and do not silently select one as canonical.
- 26. Values appearing only in `raw_facts`, shipment details, references,
     historical text, or free-form descriptions do not trigger multi-invoice
     detection.
- 27. A shipment reference in `raw_facts` does not compete with
    `header.invoice_number`.
- 28. `Uw ref.`, `Your reference`, Dossier, and O.No. remain raw facts and are
    not mapped to a business reference field.
- 29. Only deterministic lexical equivalents such as `Factuurnummer` and
    `Invoice Number` normalize to `invoice_number`.
- 30. Repeated currency and total values merge.
- 31. Conflicting totals do not use last-write-wins.
- 32. Raw facts retain page provenance through page aggregation.
- 33. No carrier name or carrier-specific conditional branch is needed.

### ParseAttempt provenance

- 34. A new ParseAttempt stores `prompt_version`.
- 35. A new ParseAttempt stores `extraction_contract_version`.
- 36. A new ParseAttempt stores `model_name_snapshot`.
- 37. Provider Config edits do not mutate historical snapshots.
- 38. A rerun creates a new attempt with the then-current snapshots.
- 39. Historical attempt provenance remains unchanged after a rerun.
- 40. Successful parsing keeps the existing private raw-response attachment.
- 41. Sensitive Prompt text, API keys, and full response payloads are absent
     from diagnostics and error messages.

### Layer boundaries and error taxonomy

- PageExtractionResult is not required to satisfy Canonical Schema.
- Document Normalizer output must satisfy the frozen Canonical Schema.
- Invalid final Canonical output fails at `CANONICAL_SCHEMA_INVALID`, not at
  PageExtraction.
- PageExtractionResult is never persisted as
  `ParseAttempt.canonical_result`; that field receives only the final
  document-level CanonicalResult.
- Malformed page JSON and valid-but-schema-invalid page JSON remain
  distinguishable as `PAGE_EXTRACTION_RESPONSE_INVALID` and
  `PAGE_EXTRACTION_SCHEMA_INVALID`.
- Page extraction success followed by normalization failure is reported as
  `DOCUMENT_NORMALIZATION_INVALID`, not a generic response-schema error.

## 4. Test data rules

- Use carrier-neutral synthetic page results for unit tests.
- Use no real API key.
- Do not print complete OCR text or raw provider responses.
- Do not assert behavior through a carrier name.
- Real PDF fixture validation remains a separate integration activity.
- PASS for this Test Intent does not equal Extraction Fix Closure PASS; runtime
  validation with Bring, Feelogic, and Mainfreight remains required.

## 5. Acceptance criteria

The Intent passes when all required cases pass and demonstrate:

```text
Vision facts
-> PageExtractionResult
-> deterministic document normalization
-> frozen CanonicalResult
```

No test may require a change to Statement, Human Review, Mapping, Bill Creator,
Canonical Schema, or the Task state machine.

The expected boundary is:

```text
DeepSeek Vision
  -> PageExtractionResult (page facts, scalar fields, raw facts, local page)
  -> Document Normalizer (PDF order, deterministic merge, conflicts,
     multi-invoice detection, provenance preservation)
  -> frozen CanonicalResult
```

## 6. Execution status

Test implementation and execution must be tracked separately from the
extraction-contract production change.
