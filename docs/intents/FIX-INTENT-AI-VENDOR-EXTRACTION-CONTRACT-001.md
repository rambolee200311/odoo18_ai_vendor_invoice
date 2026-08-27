# FIX-INTENT-AI-VENDOR-EXTRACTION-CONTRACT-001

> Date: 2026-08-26
> Status: IMPLEMENTATION AUTHORIZED
> Scope: DeepSeek Vision page extraction contract only

## 1. Objective

Redefine the DeepSeek Vision page extraction contract so the model acts as a
transport-supplier-invoice page fact extractor, not as an accounting,
mapping, or business decision engine.

The model must extract visible facts from the current PDF page, preserve
uncertain labels and values, and avoid interpreting transport references as an
invoice number without explicit page evidence.

## 2. Scope

### Included

- DeepSeek Vision system prompt;
- DeepSeek Vision user prompt;
- PageExtractionResult JSON Schema;
- `PROMPT_VERSION` constant;
- ParseAttempt prompt-version snapshot;
- ParseAttempt model-name snapshot;
- raw/source metadata for extracted fields.

### Explicitly excluded

- Statement;
- Human Review;
- Mapping;
- Bill Creator;
- Task state machine;
- Canonical Schema;
- PDF renderer;
- DeepSeek HTTP, timeout, and retry behavior;
- existing raw AI response attachment audit mechanism;
- Prompt UI;
- business-user Prompt editing.

## 3. Proposed Prompt Contract

### System Prompt

```text
You are a transport-supplier-invoice page fact extractor.

Your role is limited to extracting facts that are visibly present on the current PDF page. You are not a business decision maker, invoice validator, accounting system, mapping engine, or human reviewer.

Return JSON only and follow the PageExtractionResult contract.

Extract visible facts from the current page when present, including:

- invoice header information;
- invoice number and invoice date;
- supplier or issuer information;
- currency;
- invoice totals and tax amounts;
- fee or charge line items;
- transport references and shipment references;
- dossier, order, opdracht, customer, and other reference numbers;
- sender, receiver, billing, and delivery addresses;
- visible address labels and address values;
- any other visibly printed business field.

Do not infer information that is not visibly present on this page.

Do not guess, autocomplete, calculate, reconcile, or derive missing values.

Missing fields must be omitted or returned as null.

Do not use information from another page. Do not assume that a repeated header, footer, table heading, or column heading is an invoice line.

Do not automatically interpret any of the following as invoice_number unless the page explicitly identifies the value as the invoice number:

- Shipment Number;
- Shipment no.;
- Dossier;
- O.No.;
- Opdracht;
- Uw ref.;
- Your reference;
- customer reference;
- order reference;
- transport reference;
- booking reference;
- consignment reference.

If a field is visible but its business meaning is uncertain, preserve the original printed label and value in raw_facts. For every raw fact, preserve:

- source_label: the original visible field label;
- source_value: the original visible value;
- source_page: the current page number.

Do not silently discard uncertain fields.

For a field that is confidently identified, return its normalized value together with its original source_label, source_value, and source_page.

Use plain scalar values for extracted values. Do not include explanations, markdown, comments, or prose outside the JSON object.
```

### User Prompt

```text
Extract the visible facts from this PDF page and return one PageExtractionResult JSON object.

The result may contain:

- page_number;
- header;
- invoice header fields;
- fee or charge lines;
- transport references;
- dates;
- supplier, sender, receiver, billing, or delivery addresses;
- raw_facts for fields whose business meaning cannot be determined with confidence;
- is_multi_invoice only when multiple invoices are visibly indicated on this page.

For every confidently identified structured field, preserve its original source metadata:

- source_label;
- source_value;
- source_page.

For every visible field with uncertain business meaning, add a raw_facts item with the original label, original value, and current page number.

Do not convert shipment, dossier, order, opdracht, customer, transport, or reference numbers into invoice_number unless the page explicitly labels the value as an invoice number.

Do not guess, calculate, reconcile, autocomplete, or fill missing values.

Return JSON only.
```

The user message also contains one `image_url` item with the current page PNG
encoded as a base64 data URL.

## 4. Proposed PageExtractionResult Schema

This is a page-level schema and does not change the frozen Canonical Schema.

```python
{
    "type": "object",
    "required": ["page_number"],
    "additionalProperties": False,
    "properties": {
        "page_number": {
            "type": "integer",
            "minimum": 1,
        },
        "header": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "invoice_number": {"$ref": "#/$defs/source_field"},
                "invoice_date": {"$ref": "#/$defs/source_field"},
                "supplier": {"$ref": "#/$defs/source_field"},
                "currency": {"$ref": "#/$defs/source_field"},
                "total_amount": {"$ref": "#/$defs/source_field"},
                "total_tax": {"$ref": "#/$defs/source_field"},
                "supplier_address": {"$ref": "#/$defs/source_field"},
                "billing_address": {"$ref": "#/$defs/source_field"},
                "delivery_address": {"$ref": "#/$defs/source_field"},
                "sender_address": {"$ref": "#/$defs/source_field"},
                "receiver_address": {"$ref": "#/$defs/source_field"},
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "description": {"$ref": "#/$defs/source_field"},
                    "quantity": {"$ref": "#/$defs/source_field"},
                    "unit_price": {"$ref": "#/$defs/source_field"},
                    "amount": {"$ref": "#/$defs/source_field"},
                    "tax": {"$ref": "#/$defs/source_field"},
                    "line_total": {"$ref": "#/$defs/source_field"},
                    "raw_fields": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/raw_fact"},
                    },
                },
            },
        },
        "references": {
            "type": "array",
            "items": {"$ref": "#/$defs/raw_fact"},
        },
        "addresses": {
            "type": "array",
            "items": {"$ref": "#/$defs/raw_fact"},
        },
        "raw_facts": {
            "type": "array",
            "items": {"$ref": "#/$defs/raw_fact"},
        },
        "is_multi_invoice": {
            "type": "boolean",
        },
    },
    "$defs": {
        "source_field": {
            "type": "object",
            "required": [
                "value",
                "source_label",
                "source_value",
                "source_page",
            ],
            "additionalProperties": False,
            "properties": {
                "value": {
                    "type": ["string", "number", "null"],
                },
                "source_label": {
                    "type": ["string", "null"],
                },
                "source_value": {
                    "type": ["string", "number", "null"],
                },
                "source_page": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                },
            },
        },
        "raw_fact": {
            "type": "object",
            "required": [
                "source_label",
                "source_value",
                "source_page",
            ],
            "additionalProperties": False,
            "properties": {
                "source_label": {
                    "type": "string",
                },
                "source_value": {
                    "type": ["string", "number", "null"],
                },
                "source_page": {
                    "type": "integer",
                    "minimum": 1,
                },
            },
        },
    },
}
```

## 5. Deterministic Responsibility Boundaries

### Vision AI

- Read visible page content;
- extract explicit page facts;
- preserve uncertain label/value/page information;
- avoid guessing, calculation, and business decisions.

### Python Document Normalizer

- Validate PageExtractionResult;
- order pages;
- merge deterministic duplicate facts;
- normalize confirmed semantic fields;
- construct CanonicalResult;
- report unresolved ambiguity;
- never use carrier-specific hardcode.

### Mapping

Continue to produce supplier, currency, product, and tax candidates from the
existing mapping tables.

### Human Statement Review

Continue to decide the final invoice number, supplier, references, totals,
taxes, lines, addresses, and mapping choices.

## 6. Provenance Changes

Add the following constant:

```python
PROMPT_VERSION = "vision-extraction-v1.0"
```

Add read-only ParseAttempt snapshots:

```text
prompt_version
model_name_snapshot
```

The values must be captured for each attempt and must not change when the
Provider Config is later edited.

Prompt remains hard-coded and is not stored in Provider Config or exposed in
the Odoo UI. The existing private raw-response attachment mechanism remains
unchanged.

## 7. Acceptance Criteria

- Page extraction explicitly describes a fact extractor, not a business
  decision maker;
- invoice headers, fee lines, references, dates, and addresses are covered;
- uncertain facts retain `source_label`, `source_value`, and `source_page`;
- shipment/reference labels cannot be automatically treated as
  `invoice_number`;
- missing values remain empty and are never guessed or calculated;
- normalizer behavior remains carrier-neutral;
- Prompt version and model snapshot are persisted per ParseAttempt;
- no Prompt UI or Prompt editing capability is introduced;
- raw AI response attachments continue to work;
- Statement, Human Review, Mapping, Bill Creator, Task state machine, and
  Canonical Schema remain unchanged.

## 8. Implementation Status

Implementation was authorized after the required review revision and is now
implemented in the current worktree. Targeted source verification passes;
full Odoo runtime regression remains subject to the existing database test
environment.

## 9. Review Revision (2026-08-26)

The following revision supersedes the earlier Prompt and Schema sections.
Implementation is authorized only for this revised contract.

### Contract version

```python
EXTRACTION_CONTRACT_VERSION = "transport-invoice-page-v1"
PROMPT_VERSION = "vision-extraction-v1.1"
```

`extraction_contract_version` binds the system prompt, user prompt,
PageExtractionResult Schema, and normalizer contract. ParseAttempt stores this
contract version and a `model_name_snapshot`. No Prompt is added to Provider
Config or the Odoo UI.

### Revised System Prompt

```text
You are a transport-supplier-invoice page fact extractor, not a business decision maker.
Extract only facts visibly printed on the current PDF page. Return JSON only.
Extract explicit invoice header fields, fee and charge lines, dates, addresses,
and explicitly labelled identifiers or references. Preserve every uncertain or
unclassified printed field in raw_facts using its original source_label and
source_value. Do not determine business meaning unless the printed label
explicitly states it.

Do not guess, autocomplete, calculate, reconcile, or fill missing values.
Omit missing fields or use null. Do not use information from another page.
Do not treat repeated headers, footers, or column headings as invoice lines.
Do not interpret Shipment Number, Dossier, O.No., Opdracht, Uw ref., Your
reference, customer reference, order reference, transport reference, booking
reference, or consignment reference as invoice_number unless the page explicitly
labels the value as an invoice number.
Use plain scalar values and return no explanation outside the JSON object.
```

### Revised User Prompt

```text
Extract visible facts from this PDF page and return one PageExtractionResult JSON object.
Include explicit invoice header fields, fee or charge lines, dates, addresses,
and explicitly labelled identifiers or references. Keep standard fields as plain
scalar values. For every visible field whose business meaning is uncertain, add
a raw_facts item containing the original source_label and source_value.
Do not classify or rename an uncertain reference. Do not convert shipment,
dossier, order, opdracht, customer, transport, or other reference numbers into
invoice_number unless the printed label explicitly says invoice number.
Do not guess, calculate, reconcile, autocomplete, or fill missing values.
Return JSON only.
```

The adapter appends exactly one current-page PNG `image_url` item to the user
message. `source_page` is injected by Python from the local page number and is
not requested from the model.

### Revised PageExtractionResult Schema

```python
{
    "type": "object",
    "required": ["page_number"],
    "additionalProperties": False,
    "properties": {
        "page_number": {"type": "integer", "minimum": 1},
        "header": {
            "type": "object",
            "additionalProperties": {
                "type": ["string", "number", "null"],
            },
        },
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": {
                    "type": ["string", "number", "null"],
                },
                "properties": {
                    "raw_fields": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/raw_fact"},
                    },
                },
            },
        },
        "raw_facts": {
            "type": "array",
            "items": {"$ref": "#/$defs/raw_fact"},
        },
    },
    "$defs": {
        "raw_fact": {
            "type": "object",
            "required": ["source_label", "source_value"],
            "additionalProperties": False,
            "properties": {
                "source_label": {"type": "string"},
                "source_value": {"type": ["string", "number", "null"]},
            },
        },
    },
}
```

Standard fields are plain scalars. Only uncertain facts and line-specific
unclassified fields carry source metadata. Python adds `source_page` to every
raw fact after validating the page response.

### Revised responsibility boundary

The normalizer performs only deterministic structural and lexical operations
defined by this contract: page ordering, duplicate merge, explicit lexical
equivalents such as `Factuurnummer`/`Invoice Number` to
`invoice_number`, and CanonicalResult construction. It must not perform
business semantic mapping such as `Uw ref.` to a carrier reference and must
not use carrier-specific branches. Document-level multi-invoice detection is
performed from cross-page explicit invoice facts; PageExtractionResult has no
`is_multi_invoice` field.
