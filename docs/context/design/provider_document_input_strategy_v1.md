# Provider Document Input Strategy v1

**Intent:** `INTENT-DESIGN-PROVIDER-DOCUMENT-INPUT-STRATEGY-001`
**Status:** Conditional pass; design only; no implementation authorization
**Date:** 2026-09-02

## 1. Current State

The current production path accepts the source PDF through
`pdf_preprocessor.prepare_provider_input()`. That function renders every PDF
page to ordered PNG bytes, and the Provider adapter receives an `images`
collection. The current OpenAI diagnostic adapter also sends PNG data URLs; it
does not use the Direct PDF Files API / Responses API path.

```text
Source PDF
  -> prepare_provider_input()
  -> ordered PNG[]
  -> Provider adapter
  -> {"pages": [...]}
  -> PageExtractionResult[]
  -> Document Normalizer
  -> CanonicalResult
```

The source PDF remains the authoritative input. Rendered images are a derived
transport representation, not a replacement source document.

## 2. Confirmed Evidence

The same `bring_26022366.pdf` has five pages. The standalone GPT-5.6 Luna
Direct PDF experiment used OpenAI Files API plus Responses API and `input_file`,
without PNG rendering:

```text
HTTP_STATUS = 200
ELAPSED_SECONDS = 20
SUPPLIER = Bring Cargo B.V.
INVOICE_NUMBER = 26022366
INVOICE_DATE = 06/07/26
CURRENCY = EUR
SUBTOTAL = 4221.24
TAX_TOTAL = 886.46
GRAND_TOTAL = 5107.70
BUSINESS_LINE_COUNT = 12
BUSINESS_LINE_COUNT_VALIDATED = YES
```

The evidence is recorded in
[gpt56-luna-direct-pdf-experiment-20260902.md](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice.worktrees/docsintentsinvoice-statement-review/docs/evidence/gpt56-luna-direct-pdf-experiment-20260902.md).

This was a standalone extraction contract, not a production Gate 1 result.
It did not run the production PageExtractionResult validator or Document
Normalizer.

The earlier DeepSeek production path used five rendered PNG images, returned
five valid pages, and produced 49 CanonicalResult lines. The manually validated
business granularity for this PDF is 12 independent transport records. These
are different contracts and must not be compared as if `49 == expected Luna
lines`.

## 3. Design Goals

1. Keep the original PDF as source ownership and provenance.
2. Support a minimal set of explicit input modes:
   - `rendered_images`
   - `native_pdf`
3. Keep Provider-specific file upload and request packaging out of Parse
   Service.
4. Preserve one unified downstream business validation boundary without
   prematurely forcing every input mode into a page-level transport shape.
5. Preserve one transport business record as one Statement business line.
6. Make the actual input mode and payload type truthful in observability.
7. Reject incompatible configuration before a Provider request is sent.
8. Avoid coupling one Provider adapter to another Provider adapter.

## 4. Non-Goals

This design does not authorize changes to:

- PageExtractionResult schema;
- Canonical schema;
- Document Normalizer;
- Mapping;
- Statement or Statement Line model;
- Human Review projection;
- Bill Creator;
- Task / ParseAttempt states;
- queue_job or worker behavior;
- production default Provider;
- Prompt business semantics;
- automatic conversion of 49 existing lines into 12 lines.

It also does not choose a final production Provider. The Direct PDF experiment
is capability evidence only.

## 5. Provider Input Mode Model

### Recommendation

Add a Provider configuration field named `document_input_mode`, with the
minimal selection:

```text
rendered_images
native_pdf
```

This field belongs on `wd.ai.provider.config` because it is an operational
choice for a configured Provider/model/endpoint. It must not be inferred only
from the Provider name.

The adapter must also declare its supported modes:

```python
supported_input_modes = frozenset({"rendered_images"})
```

or:

```python
supported_input_modes = frozenset({"native_pdf"})
```

The two declarations have different responsibilities:

```text
Provider Config:
  selected/preferred mode for this configured endpoint and model

Adapter capability:
  modes this adapter can actually transport
```

Before making a request, a dispatcher validates:

```text
configured document_input_mode in adapter.supported_input_modes
```

An unsupported combination is a deterministic configuration failure at
`INPUT_STRATEGY`, before PDF rendering, file upload, or Provider HTTP.

The design intentionally does not add a general capability registry,
negotiation protocol, or per-model feature matrix in this phase. Two explicit
modes and an adapter capability set are sufficient.

### Initial assignments

```text
DeepSeek / deepseek-v4-flash-vision-exp:
  document_input_mode = rendered_images

OpenAI / gpt-5.6-luna:
  candidate document_input_mode = native_pdf
```

The OpenAI assignment is a candidate for a future authorized implementation,
based on the Direct PDF evidence. It is not a current production change.

## 6. ProviderInput Contract

Use one small immutable-like transport value object. Keep source provenance
separate from the Provider transport payload, and require exactly one active
payload:

```text
ProviderInput
  mode: "rendered_images" | "native_pdf"
  source:
    source_attachment / source metadata
    page_count
    mime_type
    checksum
  payload:
    images: tuple[bytes, ...] | None
    document_bytes: bytes | None
```

Invariants:

```text
mode = rendered_images:
  images is present and ordered
  document_bytes is None
  source metadata is present
  source.page_count = len(images)

mode = native_pdf:
  images is None
  document_bytes is present
  source metadata is present
  source.page_count is read from the source PDF
```

The original PDF remains the authoritative source for provenance, but it is
not automatically a second Provider payload. In particular, a rendered-image
input should not unnecessarily retain PDF bytes alongside all rendered image
bytes merely because the source document is recorded.

The implementation may use a dataclass or a small validated dictionary; it
should not introduce a broad generic document framework. A `mode` value is
required so the adapter never guesses from whether an incidental field happens
to be non-empty.

The Provider adapter receives this `ProviderInput`; it does not look up Task,
ParseAttempt, or `ir.attachment` itself.

## 7. Adapter Capability Contract

The shared Vision adapter contract should expose:

```text
supported_input_modes
parse(provider_input, provider_config, ...)
```

The common extraction layer owns response extraction, JSON decoding, envelope
validation, page validation, and failure classification. Each Provider adapter
owns only its transport:

```text
DeepSeek:
  rendered_images
  image_url data URLs
  DeepSeek-specific request options

OpenAI Luna:
  native_pdf
  Files API upload
  Responses API input_file
  OpenAI-specific request options
```

There must be no Provider-name conditional in Parse Service such as
`if provider == "openai"`. Parse Service asks the adapter/dispatcher to prepare
the configured input mode and then invokes the common Provider contract.

## 8. Production Flow

Recommended flow:

```text
Task source attachment
  -> input strategy dispatcher
  -> validate configured mode against adapter capability
  -> ProviderInput
  -> adapter-specific transport
  -> raw Provider response
  -> model content extraction
  -> JSON decoding
  -> unified extraction output validation
  -> Document Normalizer
  -> CanonicalResult
```

For `rendered_images`:

```text
source PDF
  -> PDF renderer
  -> ordered PNG[]
  -> one multi-image request
```

For `native_pdf`:

```text
source PDF
  -> Provider-specific file upload/document input
  -> one request referencing the original PDF
```

`pdf_preprocessor` remains the owner of PDF-to-PNG rendering. It must not
upload files to OpenAI. The OpenAI adapter or a narrowly scoped Provider
transport helper owns Files API upload and Responses API packaging. The
dispatcher owns selection and input invariants, not HTTP.

`prepare_provider_input()` can remain as the compatibility entry point during
migration, but its responsibility should become strategy dispatch rather than
always rendering PNG. A future split into `prepare_rendered_images()` and
`prepare_native_pdf()` is clearer internally; both remain behind one Parse
Service-facing strategy boundary.

## 9. Output Contract Options

### Option A: Native PDF still returns pages envelope

Require a native PDF Provider to return the existing pages envelope only if the
compatibility gate below proves that this preserves business granularity:

```json
{
  "pages": [
    {
      "page_number": 1,
      "header": {},
      "lines": [],
      "raw_facts": []
    }
  ]
}
```

If proven compatible, reuse the existing page validator and Document Normalizer.
This keeps Provider input differences separate from business output differences.
The output contract must still explicitly preserve business-line granularity.
A page result may contain one transport record with nested charge components,
but a Provider must not flatten every component into an independent business
line merely to satisfy a page envelope.

### Option B: Native PDF returns document-level extraction

Allow native PDF to return a document-level result such as the Direct PDF
experiment's `invoice_lines`. This reflects the model's natural result, but it
requires a new validated document-level contract and a deterministic conversion
to CanonicalResult. It would create a second extraction validation path and
would need explicit provenance for each business line.

This may be required if the pages envelope cannot represent the 12-record
result without loss or false page ownership. It is not authorized by this
design.

### Option C: Provider-specific conversion inside adapter

The adapter could convert a native document result into PageExtractionResult
objects. This hides the difference but risks silently inventing page ownership
and makes it easy to flatten or duplicate business lines. It is not recommended
unless the Provider returns reliable page references for every fact.

### Decision Gate

The native PDF output strategy is intentionally **to be validated**, not
preselected:

```text
A. If the existing PageExtractionResult can represent the native PDF result
   without changing its schema, losing the 12-record business granularity, or
   inventing page ownership:
   -> reuse the pages envelope.

B. If pages-envelope compatibility would split transport records, flatten
   charge components into 49 component lines, or invent page ownership:
   -> stop.
   -> design a versioned document-level extraction contract.
```

The unified boundary is the downstream business meaning and validation, not a
premature requirement that every Provider expose identical page-level
transport structure.

## 10. 12-line Business Granularity Analysis

The target is:

```text
1 independent transport business record = 1 Statement business line
```

A transport record may contain multiple charge components:

```text
Transportkosten
Dieselolietoeslag
ADR toeslag
ETS toeslag
IMO toeslag
```

For example, four components can total one business amount of `381.01`.
Those components are not four Statement lines.

Carrier-specific identifiers such as `ref`, `reference`, `our_reference`,
`load_ref`, and `shipping_ref` are reconciliation clues between invoice
business lines and transport orders. Their relationship is not assumed to be
one-to-one: one invoice line may point to one order, or multiple invoice lines
may share one order reference. For a document with 12 transport business
lines, these clues may identify 12 orders, fewer orders, or an unresolved
combination; they do not create additional invoice, Canonical, Statement, or
Bill lines. The system must not automatically merge, split, group, match, or
reconcile business lines based on these clues.

The extraction layer must preserve each clue's original label and value when
available. It must not infer that an unlabeled `Reference` means
`load_ref`, `transport_order_no`, or another carrier-specific field. If the
provider can only establish `label = "Reference"` and its value, that pair is
retained as-is. The minimum generic representation is a line-level
`reconciliation_clues` collection of `{label, value}` objects. A readable
copy may also be included in the corresponding business-line `description`;
if several invoice lines share the same clue, the clue may appear in each of
those line descriptions. No carrier-specific Canonical, Statement, or Bill
field is introduced by this rule.

The future transport reconciliation business context is:

```text
one settlement period
  -> many transport orders
  -> one carrier summary invoice
  -> invoice business lines with reconciliation clues and amounts
  -> locate the related transport order(s)
  -> Invoice Line(s) <-> Transport Order
  -> compare billed carrier charges with agreed/expected order charges
  -> matched / discrepant / unmatched
  -> human review and discrepancy handling
```

This is a reconciliation workflow, not an invoice-line normalization rule.
The current generic invoice module preserves the line amount and clue text so
that a future transport module can perform the lookup and comparison. It does
not search transport orders, determine the relationship cardinality, compare
charges, classify discrepancies, or resolve them.

The current path likely permits over-splitting because
`normalize_page_results()` currently extends all page `lines` directly into
Canonical `lines`. It then maps each extracted line to one Canonical line.
This is structurally faithful to page rows, but it does not by itself prove
that a page row equals a transport business record.

The likely impact points are:

```text
PageExtractionResult.lines
  -> Document Normalizer line assembly
  -> CanonicalResult.lines
  -> Statement line creation
```

The Statement model and Bill Creator should not be used to repair this
granularity. Statement remains the human-editable structured authority, and
Bill Creator must continue reading the review projection.

Before implementation, inspect representative first/middle/last records and
charge components from the persisted DeepSeek evidence. Establish whether 49
means physical charge rows, charge components, or an already-business-level
result. The Direct PDF experiment establishes the 12-record reference but does
not prove how to transform the current PageExtractionResult safely.

## 11. Observability Impact

### Rendered images

Existing PageArtifact records are truthful for this mode:

```text
source PDF -> rendered PNG page artifacts -> ProviderCall
```

They should record ordered page number, MIME type, checksum, and byte size as
currently designed.

### Native PDF

Do not create fake PageArtifact records for PNGs that were never sent. The
minimal truthful design is:

```text
PageArtifact count = 0
source_pdf_attachment_id = original source
ProviderCall.input_mode = native_pdf
ProviderCall.input_document_type = application/pdf
ProviderCall.input_page_count = source PDF page count
ProviderCall.rendered_image_count = 0
```

The existing source attachment is sufficient provenance for the native PDF.
A new `DocumentArtifact` model is not needed in this phase. A ProviderCall
field or a small structured input metadata snapshot can record the native
document type and checksum without storing duplicate PDF bytes.

For both modes, persist:

```text
provider/model snapshot
input mode
input counts and sizes
effective prompt snapshot
request start / response timestamps
HTTP status
raw response attachment subject to existing access controls
failure stage and safe error
```

Never persist API keys, Authorization headers, or image/PDF base64 in ordinary
diagnostic fields.

## 12. Prompt Contract Impact

Business extraction instructions should remain semantically shared:

```text
extract visible invoice facts
preserve uncertainty
do not guess
preserve business-line boundaries
return the agreed output envelope
```

Transport-specific instructions may vary only where required by the input
representation:

```text
rendered_images:
  process ordered supplied images

native_pdf:
  process all pages in the supplied PDF
```

The business extraction requirements, including transport-record granularity,
must remain equivalent. The exact native PDF output envelope remains subject to
the decision gate in Section 9. A native PDF prompt may not reduce fields or
silently switch to a different business-line meaning. Prompt snapshots must
record the effective prompt without credentials or HTTP headers.

## 13. Failure Semantics

Reuse the existing diagnostic failure-stage vocabulary where possible. The
minimal mapping is:

```text
input mode/capability mismatch -> INPUT_STRATEGY
PDF read/render failure        -> PDF_PREPROCESSING
native file upload failure     -> FILE_UPLOAD
Provider HTTP/API failure      -> PROVIDER_REQUEST
response content extraction    -> RESPONSE_EXTRACTION
JSON decoding failure          -> JSON_DECODE
pages envelope/page schema     -> SCHEMA_VALIDATION
Document Normalizer failure    -> NORMALIZATION
```

These are diagnostic stages, not new Task or ParseAttempt business states.
Failures must retain safe summaries and truthful transport metadata. An
unsupported input mode must fail before any Provider request.

## 14. Compatibility Impact

DeepSeek remains unchanged operationally:

```text
rendered_images
five ordered PNGs
one multi-image request
existing v1.3 output validation
```

OpenAI Luna native PDF would be a new transport path:

```text
native_pdf
Files API
Responses API
input_file
```

The Direct PDF experiment's `invoice_lines` response cannot be passed directly
to the existing PageExtractionResult validator. It must either be changed at
the Provider prompt/output boundary to the unified pages envelope or be
validated by a separately designed document contract. No silent fallback
conversion should be added.

No database migration is required for existing Tasks or Attempts merely to
document this design. A future `document_input_mode` field would require a
normal Odoo module upgrade and a default value of `rendered_images` for
existing configurations.

## 15. Recommended Minimal Implementation

Implementation must be split into two separately authorized gates.

### Implementation A: Provider Input Strategy Foundation

This phase should contain only:

1. Extend the existing adapter boundary with `supported_input_modes`.
2. Introduce the small validated `ProviderInput` contract.
3. Add `document_input_mode` to Provider Config with the two explicit values.
4. Add dispatcher/configuration validation before any Provider request.
5. Add truthful ProviderCall input-mode metadata.
6. Keep DeepSeek on `rendered_images`.
7. Keep OpenAI's existing production behavior unchanged.

This phase does not require a real Luna request and must not change
PageExtractionResult, Document Normalizer, or business-line semantics. Its
success criterion is that adding another Provider does not require
Provider-name conditionals in Parse Service.

### Implementation B: OpenAI Native PDF Integration

Only after Implementation A is reviewed and accepted:

1. Add OpenAI Files API plus Responses API native PDF transport.
2. Run SYNC FIRST with one explicitly authorized request.
3. Validate the 12 transport records, totals, provenance, and business
   granularity against the source PDF.
4. Apply the Section 9 decision gate to choose pages-envelope reuse or a
   separately designed versioned document-level contract.
5. Add only the observability and contract changes proven necessary.

Do not make adapter hierarchy/shared-vision refactoring a prerequisite. Perform
that refactor only if the current structure makes the input boundary
impossible or creates actual duplicated production logic.

Do not add automatic mode fallback. If `native_pdf` fails, do not silently
render PNG and retry; that would invalidate evidence and obscure capability
failures.

## 16. Files Likely Affected

Likely implementation surface, subject to detailed design review:

```text
addons/ai_vendor_invoice/models/ai_provider_config.py
addons/ai_vendor_invoice/models/import_parse_attempt.py
addons/ai_vendor_invoice/models/provider_call.py
addons/ai_vendor_invoice/services/parse_service.py
addons/ai_vendor_invoice/services/pdf_preprocessor.py
addons/ai_vendor_invoice/services/observability_service.py
addons/ai_vendor_invoice/adapters/aibase.py
addons/ai_vendor_invoice/adapters/deepseek.py
addons/ai_vendor_invoice/adapters/openai.py
addons/ai_vendor_invoice/adapters/base.py
addons/ai_vendor_invoice/views/config_views.xml
addons/ai_vendor_invoice/views/diagnostic_views.xml
addons/ai_vendor_invoice/tests/
```

The exact files must be confirmed before implementation. Statement, Mapping,
and Bill Creator should remain unchanged unless the separately approved
granularity analysis proves a direct contract defect.

## 17. Test Strategy

### Static and contract tests

- Config accepts only the two supported input modes.
- Existing configurations default to `rendered_images`.
- Unsupported mode/adapter combinations fail before HTTP.
- DeepSeek does not receive native PDF input.
- OpenAI native PDF does not receive DeepSeek `thinking` parameters.
- ProviderInput rejects ambiguous simultaneous payloads.

### Rendered-image regression

- `bring_26022366.pdf` renders five ordered images.
- DeepSeek sends five images in one request.
- Existing page envelope and page schema checks remain unchanged.
- Existing Gate 1/2/3 behavior is not regressed.

### Native-PDF diagnostic

- Source PDF is uploaded once and referenced once.
- No PageArtifact is created for nonexistent PNGs.
- ProviderCall records `native_pdf`, PDF MIME type, page count, and zero
  rendered images.
- Raw response, model content, parsed JSON, and validation failures remain
  distinguishable.
- Exactly one authorized synchronous request is used for a first run.

### Granularity

- Compare first, middle, and last transport records with the source PDF.
- Verify charge components remain nested within their transport record.
- Verify the reference document's expected business granularity is 12.
- Do not accept equal counts as proof without field/provenance checks.

## 18. Migration Impact

Existing Provider configurations should remain behaviorally unchanged by a
future migration:

```text
missing document_input_mode -> rendered_images
```

OpenAI Luna should be explicitly configured as `native_pdf` only after its
native adapter, output contract, observability, and granularity tests pass.
There should be no automatic migration of the current OpenAI PNG behavior.

Existing PageArtifact rows remain valid evidence for historical rendered-image
runs. Native PDF runs should use the source PDF attachment and ProviderCall
metadata rather than fabricated page artifacts.

## 19. Open Questions

1. Can GPT-5.6 Luna native PDF reliably return a usable output for the
   existing downstream contract, or does it naturally return a document-level
   result?
2. If native PDF output is document-level, where should page provenance be
   represented without inventing page ownership?
3. What exact current DeepSeek 49 lines represent: physical charge rows,
   charge components, or business lines?
4. Can the existing PageExtractionResult represent one transport record with
   nested charge components without changing its schema?
5. Does the OpenAI Files API file upload need a durable remote-file lifecycle,
   or should the diagnostic/production request delete temporary files?
6. What usage and cost metadata does the Responses API expose reliably?
7. Should native PDF raw responses be retained under the same ProviderCall
   attachment policy as rendered-image responses?
8. Which carrier-specific reconciliation clues are present in each document?
   They should be preserved as generic line-level `{label, value}` data, with
   an optional readable description copy; no future transport meaning is
   inferred.

## 20. Final Recommendation

Adopt a Provider-configured `document_input_mode` plus adapter-declared
`supported_input_modes`. Keep the original PDF as source, put rendering in the
PDF preprocessing strategy, and put native file upload in the Provider
transport adapter.

Do not preselect a native PDF output envelope. First run the Section 9 decision
gate: reuse the pages envelope only if it preserves the 12-record business
granularity without schema changes or invented page ownership; otherwise stop
and design a versioned document-level extraction contract. Before changing any
business pipeline, resolve the line-granularity mismatch:

```text
1 transport record = 1 Statement line
```

The Direct PDF evidence proves that GPT-5.6 Luna can read this PDF directly and
extract 12 validated transport records with correct totals. It does not by
itself authorize a production adapter or prove compatibility with the current
PageExtractionResult/Normalizer path.

```text
DESIGN_STATUS = CONDITIONAL_PASS
P1_REQUIRED_CHANGES = 1. Defer native PDF output strategy until granularity compatibility is proven; 2. Separate ProviderInput source/provenance from its active payload; 3. Make adapter hierarchy refactoring conditional; 4. Split Foundation from native PDF integration
RECOMMENDED_PROVIDER_CONFIG_FIELD = document_input_mode
RECOMMENDED_INPUT_MODES = rendered_images, native_pdf
DEEPSEEK_MODE = rendered_images
OPENAI_LUNA_MODE = native_pdf (candidate)
PARSE_SERVICE_DEPENDS_ON_PROVIDER_NAME = NO
ADAPTER_CAPABILITY_REQUIRED = YES
RECOMMENDED_NATIVE_PDF_OUTPUT_STRATEGY = TO_BE_VALIDATED
PAGE_EXTRACTION_RESULT_CHANGE_REQUIRED = UNKNOWN
NORMALIZER_CHANGE_REQUIRED = UNKNOWN
CANONICAL_CHANGE_REQUIRED = NO (minimum generic line-level clue collection)
STATEMENT_CHANGE_REQUIRED = NO
OBSERVABILITY_CHANGE_REQUIRED = YES
BUSINESS_LINE_GRANULARITY = 1 transport record = 1 Statement line
MIGRATION_REQUIRED = future default rendered_images for existing configs
IMPLEMENTATION_AUTHORIZED = NO
NEXT_STEP = STOP_FOR_REVIEW
```

Implementation B Phase 2 adds the minimum generic `reconciliation_clues`
collection and native document projection without introducing transport-order
relations or automatic reconciliation. A recognized clue is retained as its
original `{label, value}` pair and may also have a readable description copy.
An unclassified fact remains raw evidence/description text. The line
cardinality remains unchanged: one native document business line produces one
Canonical line.
