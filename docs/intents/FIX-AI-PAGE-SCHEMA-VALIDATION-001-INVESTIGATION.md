# FIX-AI-PAGE-SCHEMA-VALIDATION-001 — Investigation

## 1. Incident Summary

Task 1689 / ParseAttempt 1156 / ProviderCall 1 sent the persisted effective
prompt to `deepseek-v4-flash-vision-exp`. The provider returned HTTP 200 and a
valid JSON response envelope, but the model content was rejected when the
adapter added `page_number` and validated it as `transport-invoice-page-v1`.

This is an AI extraction contract-alignment issue, not an Observability issue.
The raw response, prompt snapshot, image evidence, validation failure, and
failure stage are already persisted.

## 2. Real Sample

```text
Task                  = 1689
ParseAttempt          = 1156
Attempt sequence      = 4
ProviderCall          = 1
Page                  = 1
Provider              = deepseek API
Model                 = deepseek-v4-flash-vision-exp
Request               = 2026-08-28 11:00:06
Response              = 2026-08-28 11:00:37
HTTP status           = 200
Outcome               = response_invalid
Failure stage         = PAGE_SCHEMA_VALIDATION
Raw attachment        = attempt-1156-call-1-response.json
```

## 3. Actual Effective Prompt

The persisted prompt has the following relevant contract language:

```text
Return one PageExtractionResult JSON object.
Extract explicit invoice header fields, fee or charge lines, dates, addresses,
and explicitly labelled identifiers or references.
Keep standard fields as plain scalar values.
For every visible field whose business meaning is uncertain, add a raw_facts
item containing the original source_label and source_value.
Return JSON only.
```

The system prompt also says to preserve uncertain fields in `raw_facts`, avoid
guessing, and not interpret references as `invoice_number` unless explicitly
labelled that way.

The prompt does not provide an exact JSON skeleton or explicitly map the words
“header”, “lines”, and “page number” to the required JSON property names.

## 4. Actual Provider Raw Response

The persisted provider response is a valid JSON envelope with the normal
OpenAI-compatible shape:

```text
{
  "id": "...",
  "choices": [
    {
      "message": {
        "content": "<JSON text>",
        "role": "assistant",
        "reasoning_content": "<JSON-like reasoning text>"
      },
      "finish_reason": "stop"
    }
  ]
}
```

Secrets, authorization headers, image base64, and unrelated envelope metadata
are omitted here.

## 5. Extracted Model Content

The adapter reads `choices[0].message.content`, JSON-decodes it, adds
`page_number = 1`, and then validates it. The decoded model content has this
top-level structure:

```json
{
  "sender": { "...": "..." },
  "receiver": { "...": "..." },
  "invoice_header": { "...": "..." },
  "invoice_lines": [],
  "totals": { "...": "..." },
  "raw_facts": [
    {"source_label": "...", "source_value": "..."}
  ],
  "page_number": 1
}
```

The returned content is therefore valid JSON:

```text
VALID_JSON = YES
MODEL_CONTENT_EXTRACTED = YES
```

Its semantic fields contain plausible transport-invoice facts, including sender
and receiver objects, invoice header values, totals, and many raw facts. The
content is not in the PageExtractionResult property vocabulary enforced by the
production validator.

## 6. Expected PageExtractionResult Contract

The production schema is defined in
`addons/ai_vendor_invoice/schemas/page_extraction.py`.

Top level:

```json
{
  "page_number": "integer >= 1, required",
  "header": "object, optional; each value string, number, or null",
  "lines": "array, optional",
  "raw_facts": "array, optional"
}
```

The schema has `additionalProperties: false` at the top level.

`lines` items are objects whose additional properties must be string, number,
or null. A line may include `raw_fields`, an array of raw facts.

Each raw fact must be exactly:

```json
{
  "source_label": "string, required",
  "source_value": "string, number, or null, required"
}
```

There are no enum restrictions, date-format restrictions, numeric-format
restrictions, or required fields beyond `page_number` and the raw-fact
properties above. Missing optional values may be omitted or represented as
null. Additional properties are rejected.

## 7. Validation Diff

The validator rejects the model content at the top-level additional-property
check. The first validation location is the object being validated after the
adapter adds `page_number`.

```text
VALIDATION_FAILURE_PATH = $
```

Representative jsonschema failure:

```text
Expected:
  top-level properties limited to:
  page_number, header, lines, raw_facts

Actual:
  sender, receiver, invoice_header, invoice_lines, totals,
  raw_facts, page_number

Unexpected:
  sender
  receiver
  invoice_header
  invoice_lines
  totals

Result:
  MISMATCH
```

The existing `raw_facts` entries use the expected `source_label` and
`source_value` shape. The decisive failure occurs before any useful conversion
of the alternate invoice structure can happen.

## 8. Prompt vs Schema Analysis

| Concern | Prompt | Schema | Result |
|---|---|---|---|
| JSON-only output | Explicit | Required by decode/validation path | Aligned |
| PageExtractionResult | Named, but not structurally defined | Exact property names required | Under-specified |
| Header facts | Says invoice header fields | Requires `header` object | Semantic intent, not lexical contract |
| Charge/fee lines | Mentioned | Requires `lines` array | Semantic intent, not lexical contract |
| Uncertain facts | Explicit `raw_facts` instruction | Exact raw-fact object required | Mostly aligned |
| Page number | Not explicitly required in model output | Required, adapter adds it | Adapter supplies it |
| Additional properties | Not discussed | Rejected | Contract gap |

The phrase “keep standard fields as plain scalar values” applies naturally to
values inside a header or line structure, but the prompt does not state the
required nesting or property names. It is therefore possible for the model to
interpret “invoice header” and “invoice lines” as descriptive names rather than
the exact schema keys.

## 9. Adapter Transformation Analysis

The adapter:

1. extracts `choices[0].message.content`;
2. decodes the content with `json.loads`;
3. adds the current page number;
4. calls `jsonschema.validate`;
5. records the raw response and validation failure.

It does not rename `sender`, `receiver`, `invoice_header`, `invoice_lines`, or
`totals`, and it does not create the mismatch. Therefore:

```text
ADAPTER_TRANSFORMATION_DEFECT = NOT_PROVEN
```

The adapter correctly rejects a structure that is not the frozen
PageExtractionResult contract.

## 10. Root Cause

The provider returned a valid and semantically plausible invoice JSON object,
but the effective prompt did not make the exact PageExtractionResult property
contract sufficiently explicit. The model selected an alternate
document-level invoice vocabulary instead of the required page-fact vocabulary.
Strict `additionalProperties: false` then correctly rejected the result.

```text
PROMPT_SCHEMA_ALIGNED = PARTIAL
ROOT_CAUSE_CATEGORY = PROMPT_CONTRACT_MISMATCH
```

This is not proven to be pure provider noncompliance because the prompt names
PageExtractionResult but does not show its exact required JSON structure.
It is also not validator-too-strict: rejecting unknown top-level properties is
necessary for deterministic downstream normalization.

## 11. Recommended Minimal Fix

```text
RECOMMENDED_MINIMAL_FIX = OPTION A — Prompt correction
```

Make the prompt provide an exact minimal JSON skeleton and explicitly state:

- only `page_number`, `header`, `lines`, and `raw_facts` are allowed;
- sender/receiver/totals facts belong inside the permitted `header` or
  `raw_facts` representation;
- `lines` is an array and line values are scalar;
- `raw_facts` entries must contain exactly `source_label` and `source_value`;
- no `sender`, `receiver`, `invoice_header`, `invoice_lines`, or `totals`
  top-level keys may be emitted;
- the adapter supplies the current `page_number`.

Do not loosen `additionalProperties: false` and do not silently normalize an
alternate document-level contract in this fix.

### Alternative

```text
ALTERNATIVE = OPTION D — Provider structured-output request correction
```

Send a provider-enforced structured-output schema matching
`PAGE_EXTRACTION_RESULT_SCHEMA`, if the configured DeepSeek endpoint reliably
supports that mode. This should be evaluated after the prompt-only minimal
change and must preserve the same contract.

## 12. Regression Impact

Potentially affected tests:

- DeepSeek page parsing success and schema-failure tests;
- prompt/version contract tests;
- document normalizer page-result tests;
- real single-page and multi-page extraction acceptance tests.

No change is authorized in this investigation, so no current test behavior is
changed.

If the recommended prompt correction is implemented:

- extraction contract semantics remain unchanged;
- CanonicalResult and MappingResult semantics remain unchanged;
- historical Attempts remain immutable and continue to show their original
  failed response;
- a prompt version bump is required because the effective prompt changes;
- a contract version bump is not required if only wording and an explicit
  example are added without changing accepted schema;
- TDD/SRS/DDD updates are only needed if the prompt contract is formally
  documented there.

## 13. Required Tests

Before implementation approval:

1. Assert the exact prompt skeleton contains only the allowed top-level keys.
2. Assert a canonical valid PageExtractionResult still passes unchanged.
3. Assert the captured alternate top-level structure remains rejected.
4. Add a mocked provider response using the explicit skeleton and assert
   PageExtractionResult generation succeeds.
5. Assert historical failed Attempt 1156 remains unchanged.
6. Run the existing extraction, normalizer, observability, and repository
   verification suites.

## 14. Implementation Scope

```text
Allowed only after separate approval:
  Prompt text/version update
  Provider structured-output request update, if selected
  Focused extraction tests

Not authorized in this investigation:
  Schema relaxation
  Adapter alternate-shape normalization
  Canonical or Mapping changes
  Observability changes
  Queue/runtime changes
  Database repair
  New real AI Task
```

## 15. Explicit Non-Changes

```text
PRODUCTION_CODE_CHANGED = NO
DATABASE_CHANGED = NO
CONFIG_CHANGED = NO
OBSERVABILITY_CHANGED = NO
QUEUE_JOB_CHANGED = NO
NEW_AI_TASK_STARTED = NO
FIX_IMPLEMENTATION_AUTHORIZED = NO
```

## Final Conclusion

```text
RAW_RESPONSE_READ = YES
MODEL_CONTENT_EXTRACTED = YES
VALID_JSON = YES
VALIDATION_FAILURE_PATH = $

EXPECTED = page_number + optional header/lines/raw_facts only;
           no additional top-level properties
ACTUAL = sender + receiver + invoice_header + invoice_lines + totals
         + raw_facts; adapter-added page_number

PROMPT_SCHEMA_ALIGNED = PARTIAL
ROOT_CAUSE_CATEGORY = PROMPT_CONTRACT_MISMATCH
ROOT_CAUSE = The model returned a valid alternate invoice JSON vocabulary because
             the prompt did not explicitly provide the required PageExtractionResult
             property contract; strict validation then rejected unknown top-level keys.
RECOMMENDED_MINIMAL_FIX = Explicit PageExtractionResult JSON skeleton in the prompt
PROMPT_VERSION_BUMP_REQUIRED = YES
CONTRACT_VERSION_BUMP_REQUIRED = NO

FIX_IMPLEMENTATION_AUTHORIZED = NO
PRODUCTION_CODE_CHANGED = NO
DATABASE_CHANGED = NO
CONFIG_CHANGED = NO
```
