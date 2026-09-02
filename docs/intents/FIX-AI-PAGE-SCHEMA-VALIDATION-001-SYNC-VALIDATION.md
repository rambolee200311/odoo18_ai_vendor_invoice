# FIX-AI-PAGE-SCHEMA-VALIDATION-001 — Synchronous Validation

## 1. Validation Purpose

This validation isolates the Prompt v1.2 contract from queue, worker, retry,
and Attempt lifecycle behavior. It performs sequential real extraction calls
for `bring_26022366.pdf`, stopping at the first failed page.

The harness does not create a Task, ParseAttempt, queue job, attachment, or
other business record.

## 2. Why Queue Was Excluded

The asynchronous runs for Tasks 1689 and 2062 were affected by provider
timeouts and queue/job lifecycle behavior. This run intentionally calls the
production adapter synchronously with in-memory rendered page bytes. Task
2062, Attempt 1310, and Queue Job 66 were not read or modified.

## 3. Production Functions Reused

The diagnostic harness is
[`scripts/validate_deepseek_extraction_sync.py`](../../scripts/validate_deepseek_extraction_sync.py).
It reuses:

- `services.pdf_preprocessor.prepare_provider_input`
- `adapters.deepseek.DeepSeekAIProviderAdapter.parse_pdf`
- `adapters.deepseek.DeepSeekAIProviderAdapter._page_extraction`
- `schemas.page_extraction.PAGE_EXTRACTION_RESULT_SCHEMA`
- `adapters.document_normalizer.normalize_page_results` (called by the
  production adapter after page extraction)

No request, JSON decoder, or schema validator was reimplemented in the
harness. The harness temporarily captures the adapter's in-memory diagnostic
response without supplying an Attempt, so no observability records are
written.

## 4. Input PDF

```text
FILE = bring_26022366.pdf
PAGES_REQUESTED = 1-5 sequential
IMAGE_RENDERED = YES for Pages 1-3
IMAGE_BYTES = Page 1: 281111; Page 2: 159135; Page 3: 158084
```

## 5. Page 1 Request

```text
PROMPT_VERSION = vision-extraction-v1.2
PROVIDER = deepseek API
MODEL = deepseek-v4-flash-vision-exp
REQUEST_STARTED_AT = 2026-08-28T08:03:59.989889+00:00
```

The actual production prompt components were printed by the harness and are
included in its output. They contain no API key, Authorization header, or
image base64.

Production request options:

```json
{
  "stream": false,
  "reasoning_effort": "high",
  "extra_body": {"thinking": {"type": "enabled"}},
  "response_format": {"type": "json_object"},
  "max_retries": 0,
  "http_timeout": 60
}
```

## 6. Page 1–3 Raw Responses

Each of the first three requests received an HTTP 200 response. The raw
responses were decoded from the production adapter's response envelope.
It contained `choices[0].message.content` with a JSON object and no API key,
Authorization header, or image base64 was included in the report.

```text
PAGE_1 = HTTP 200, raw response received
PAGE_2 = HTTP 200, raw response received
PAGE_3 = HTTP 200, raw response received
```

Pages 1–3 returned JSON objects with `page_number`, `header`, `lines`, and
`raw_facts`. The full sanitized diagnostic output is emitted by the retained
harness; the report records the relevant validation facts rather than
duplicating the provider payload.

## 7. Page 1–3 Schema Results

```text
PAGE_1 = PASS; HTTP_STATUS = 200; ELAPSED_SECONDS = 144.326
PAGE_1_SCHEMA_VALIDATION = PASS
PAGE_1_EXTRACTION_RESULT = GENERATED

PAGE_2 = PASS; HTTP_STATUS = 200; ELAPSED_SECONDS = 130.122
PAGE_2_SCHEMA_VALIDATION = PASS
PAGE_2_EXTRACTION_RESULT = GENERATED

PAGE_3 = FAIL; HTTP_STATUS = 200; ELAPSED_SECONDS = 124.048
PAGE_3_SCHEMA_VALIDATION = FAIL
PAGE_3_EXTRACTION_RESULT = NOT_GENERATED
```

Page 3 exact validation failure:

```text
VALIDATION_FAILURE_PATH = raw_facts[48].source_label
EXPECTED = string
ACTUAL = null
VALIDATION_ERROR = None is not of type 'string'
```

The production adapter added the page number and validated each result against
`transport-invoice-page-v1`. No alternate-shape normalization or schema
relaxation was used. Page 3 failed before a PageExtractionResult could be
generated, so the harness stopped immediately.

## 8. Page 2–5 Results

Not executed because Page 3 failed and the Gate 1 failure rule requires an
immediate stop:

```text
PAGE_2 = PASS
PAGE_3 = FAIL
PAGE_4 = NOT_RUN
PAGE_5 = NOT_RUN

```text
GATE_1_AI_EXTRACTION_CONTRACT = FAIL
```
```

## 9. Document Normalizer Result

Not executed. The production adapter only normalizes after all requested page
extractions return successfully.

```text
CANONICAL_RESULT = NOT_RUN
```

## 10. Mapping Result

Not executed because no canonical result was generated.

```text
MAPPING_RESULT = NOT_RUN
```

## 11. Prompt Fix Conclusion

The run loaded Prompt v1.2 and passed the frozen schema on Pages 1 and 2.
Page 3 returned valid JSON but violated the frozen schema because one
`raw_facts.source_label` was `null`. Therefore the multi-page Prompt/schema
fix is not proven and this Gate 1 run is failed. No Prompt or schema change was
made.

```text
PROMPT_SCHEMA_FIX = FAIL
```

## 12. Provider Stability Observation

The three executed provider calls returned HTTP 200 within the 180-second
diagnostic window. Latency remained high, but no provider timeout or retry
occurred before the schema failure.

```text
PROVIDER_STABILITY = STABLE
```

## 13. Async Pipeline Status

```text
ASYNC_PIPELINE_VALIDATION = NOT_PART_OF_THIS_TEST
```

The asynchronous Task 2062 flow was not inspected, waited on, or changed.

## 14. Explicit Non-Changes

```text
SYNC_VALIDATION_IMPLEMENTED = YES
QUEUE_USED = NO
TASK_CREATED = NO
PARSE_ATTEMPT_CREATED = NO
DATABASE_BUSINESS_STATE_CHANGED = NO
PRODUCTION_EXTRACTION_CODE_REUSED = YES
PROMPT_VERSION = vision-extraction-v1.2

PAGE_1 = PASS
PAGE_1_HTTP_STATUS = 200
PAGE_1_SCHEMA_VALIDATION = PASS
PAGE_1_EXTRACTION_RESULT = GENERATED

PAGE_2 = PASS
PAGE_2_HTTP_STATUS = 200
PAGE_2_SCHEMA_VALIDATION = PASS
PAGE_2_EXTRACTION_RESULT = GENERATED

PAGE_3 = FAIL
PAGE_3_HTTP_STATUS = 200
PAGE_3_SCHEMA_VALIDATION = FAIL
PAGE_3_EXTRACTION_RESULT = NOT_GENERATED

PAGE_4 = NOT_RUN
PAGE_5 = NOT_RUN

GATE_1_AI_EXTRACTION_CONTRACT = FAIL

CANONICAL_RESULT = NOT_RUN
MAPPING_RESULT = NOT_RUN

PROMPT_SCHEMA_FIX = FAIL
PROVIDER_STABILITY = STABLE
ASYNC_PIPELINE_VALIDATION = NOT_PART_OF_THIS_TEST
```

No production Task workflow, queue_job source, channel, retry policy,
timeout policy, schema, adapter semantics, canonical normalizer, mapping, or
observability behavior was changed.

## 15. Multi-Page Single-Call Experiment

The retained harness was extended with
`--mode multi-page-single-call`. It rendered all five pages with the
production preprocessor and sent all five images in one production adapter
request. A process-local diagnostic prompt wrapper was used; the production
Prompt v1.2 constants were not changed.

```text
VALIDATION_MODE = SYNC_MULTI_PAGE_SINGLE_CALL
QUEUE_USED = NO
PDF = bring_26022366.pdf
PAGE_COUNT = 5
IMAGE_COUNT_SENT = 5
IMAGE_BYTES = [281111, 158582, 159135, 158084, 166809]
TOTAL_IMAGE_BYTES = 923721
PROMPT_BASE_VERSION = vision-extraction-v1.2
DIAGNOSTIC_PROMPT_MODE = MULTI_PAGE_SINGLE_CALL
MODEL = deepseek-v4-flash-vision-exp
PRODUCTION_TIMEOUT = 60
DIAGNOSTIC_TIMEOUT = 300
HTTP_CALL_COUNT = 1
REQUEST_STARTED_AT = 2026-08-28T09:20:18.703732+00:00
RESPONSE_RECEIVED_AT = 2026-08-28T09:23:03.419219+00:00
ELAPSED_SECONDS = 164.716
HTTP_STATUS = 200
RAW_RESPONSE_RECEIVED = YES
RAW_RESPONSE_BYTE_SIZE = 69189
VALID_JSON = YES
RETURNED_PAGE_COUNT = 5
```

The model returned a diagnostic object with a `pages` array containing page
numbers 1 through 5. Each page was then validated using the production
`document_normalizer._validate_page_result()` function:

```text
PAGE_1_SCHEMA = PASS
PAGE_2_SCHEMA = PASS
PAGE_3_SCHEMA = PASS
PAGE_4_SCHEMA = PASS
PAGE_5_SCHEMA = PASS
ALL_PAGE_SCHEMA_PASS = YES
MULTI_PAGE_SINGLE_CALL_EXTRACTION = PASS
```

Compared with the one-page baseline:

```text
SINGLE_PAGE_ELAPSED = 174.834
MULTI_PAGE_ELAPSED = 164.716
LATENCY_MULTIPLIER = 0.942
```

This experiment proves that this real five-page PDF can be returned as a
diagnostic multi-page envelope in one successful provider call, with every
page satisfying the frozen page-level extraction schema. It does not authorize
multi-page production mode and does not validate the document normalizer,
mapping, business pipeline, or asynchronous runtime.

```text
PRODUCTION_CODE_CHANGED = NO
TASK_CREATED = NO
PARSE_ATTEMPT_CREATED = NO
QUEUE_JOB_CREATED = NO
```

## 16. Gate 1 — Real Production Multi-Page Sync Validation

The new production multi-page extraction path was invoked synchronously once
with all five rendered pages. The harness did not replace the v1.3 prompt,
adapter parser, timeout, or schema. It stopped before document normalization,
mapping, and any business or queue lifecycle.

```text
VALIDATION_MODE = SYNC_PRODUCTION_MULTI_PAGE
QUEUE_USED = NO
PROMPT_VERSION = vision-extraction-v1.3
MODEL = deepseek-v4-flash-vision-exp
PDF = bring_26022366.pdf
PAGE_COUNT = 5
IMAGE_COUNT_SENT = 5
IMAGE_BYTES = [281111, 158582, 159135, 158084, 166809]
TOTAL_IMAGE_BYTES = 923721
PRODUCTION_TIMEOUT = 60
DIAGNOSTIC_TIMEOUT = 60
HTTP_CALL_COUNT = 1
REQUEST_STARTED_AT = 2026-08-28T10:09:53.354203+00:00
RESPONSE_RECEIVED_AT = UNKNOWN
ELAPSED_SECONDS = 120.793
HTTP_STATUS = UNKNOWN
RAW_RESPONSE_RECEIVED = NO
VALID_JSON = NO
RETURNED_PAGE_COUNT = UNKNOWN
PAGE_NUMBERS = UNKNOWN
PAGE_1_SCHEMA = NOT_REACHED
PAGE_2_SCHEMA = NOT_REACHED
PAGE_3_SCHEMA = NOT_REACHED
PAGE_4_SCHEMA = NOT_REACHED
PAGE_5_SCHEMA = NOT_REACHED
ALL_PAGE_SCHEMA_PASS = NO
MULTI_PAGE_SINGLE_CALL_EXTRACTION = TIMEOUT
VALIDATION_ERROR = AI provider request temporarily unavailable.
```

The production path did not receive a provider response, so JSON decoding and
all five page schema validations were not reached. This is a provider
availability/latency failure, not evidence that Prompt v1.3 or the page schema
failed. The request used one HTTP call with `max_retries = 0`; no Task,
ParseAttempt, queue job, or business state was created.

```text
GATE_1_AI_EXTRACTION_CONTRACT = FAIL
NEXT_GATE = STOP_FOR_REVIEW
```

## 17. Gate 1 — Production Timeout 180 Seconds

The DeepSeek provider configuration record was updated from a 60-second
production HTTP timeout to 180 seconds. No retry, queue, Task, ParseAttempt, or
business workflow was used. The real production multi-page extraction path was
then invoked once with all five rendered pages.

```text
VALIDATION_MODE = SYNC_PRODUCTION_MULTI_PAGE
QUEUE_USED = NO
PROMPT_VERSION = vision-extraction-v1.3
MODEL = deepseek-v4-flash-vision-exp
PAGE_COUNT = 5
IMAGE_COUNT_SENT = 5
TOTAL_IMAGE_BYTES = 923721
PRODUCTION_TIMEOUT = 180
DIAGNOSTIC_TIMEOUT = 180
HTTP_CALL_COUNT = 1
REQUEST_STARTED_AT = 2026-08-28T11:31:41.887180+00:00
RESPONSE_RECEIVED_AT = 2026-08-28T11:35:58.836192+00:00
ELAPSED_SECONDS = 256.952
HTTP_STATUS = 200
RAW_RESPONSE_RECEIVED = YES
RAW_RESPONSE_BYTE_SIZE = 110639
VALID_JSON = YES
RETURNED_PAGE_COUNT = 5
PAGE_NUMBERS = [1, 2, 3, 4, 5]
NO_DUPLICATE_PAGE_NUMBER = YES
NO_MISSING_PAGE_NUMBER = YES
NO_UNEXPECTED_PAGE_NUMBER = YES
PAGE_1_SCHEMA = PASS
PAGE_2_SCHEMA = PASS
PAGE_3_SCHEMA = PASS
PAGE_4_SCHEMA = PASS
PAGE_5_SCHEMA = PASS
ALL_PAGE_SCHEMA_PASS = YES
GATE_1_AI_EXTRACTION_CONTRACT = PASS
NEXT_GATE = STOP_FOR_REVIEW
```

The provider returned a valid multi-page JSON envelope. The production
multi-page extraction validator accepted all five page results and their
ordered page numbers. Normalizer, mapping, statement, bill, and async runtime
were not executed.

## 18. Gate 2 — Document Pipeline Real Sync Validation

Gate 2 reused the successful Gate 1 `MODEL_CONTENT` locally. No Provider call
was made. The five page results were passed, in order, to the production
Document Normalizer and then to the production candidate Mapping service.

```text
VALIDATION_MODE = SYNC_GATE_2_DOCUMENT_PIPELINE
QUEUE_USED = NO
PROVIDER_CALLS = 0
SOURCE_PDF = bring_26022366.pdf
INPUT_PAGE_COUNT = 5
INPUT_PAGE_NUMBERS = [1, 2, 3, 4, 5]
INPUT_PAGE_SCHEMA_STATUS = ALL_PASS
NORMALIZER_USED = PRODUCTION
NORMALIZER_STATUS = PASS
CANONICAL_RESULT_GENERATED = YES
CANONICAL_VALIDATION = PASS
CANONICAL_INVOICE_NUMBER = 26022366
CANONICAL_INVOICE_DATE = 6-7-26
CANONICAL_CURRENCY = null
CANONICAL_LINE_COUNT = 49
CANONICAL_SUBTOTAL = null
CANONICAL_TAX_TOTAL = null
CANONICAL_GRAND_TOTAL = empty
MULTI_INVOICE_DETECTION = false
MAPPING_ENGINE_USED = PRODUCTION
MAPPING_RESULT_GENERATED = YES
SUPPLIER_MAPPING_STATUS = NO_MATCH
SUPPLIER_CANDIDATE_COUNT = 0
PRODUCT_MAPPING_STATUS = 49 lines, 0 matched
PRODUCT_MAPPING_LINE_COUNT = 49
PRODUCT_CANDIDATE_COUNT = 0
TAX_MAPPING_STATUS = 49 lines, 0 matched
TAX_MAPPING_LINE_COUNT = 49
TAX_CANDIDATE_COUNT = 0
CURRENCY_MAPPING_STATUS = NO_MATCH
CURRENCY_CANDIDATE_COUNT = 0
GATE_2_DOCUMENT_PIPELINE = PASS
NEXT_GATE = STOP_FOR_REVIEW
```

The empty supplier, product, tax, and currency candidate results were returned
by the existing mapping rules and did not cause Gate 2 failure. No mapping
configuration or master data was changed. Statement, human review, bill
creation, and queue processing were not entered.

## 19. Gate 3 — Business Pipeline Validation Attempt

Gate 3 did not reach Statement creation. The validation fixture reused the Gate
1 and Gate 2 results locally and made no Provider call, but creation of the
required successful ParseAttempt was rejected before the aggregate workflow
could begin.

```text
VALIDATION_MODE = GATE_3_BUSINESS_PIPELINE
QUEUE_USED = NO
PROVIDER_CALLS = 0
SOURCE_PDF = bring_26022366.pdf
GATE_1_SOURCE = PASS
GATE_2_SOURCE = PASS
STATEMENT_CREATED = NO
HUMAN_REVIEW_RESULT_GENERATED = NOT_REACHED
VENDOR_BILL_CREATED = NO
DATABASE_TEST_RECORDS_CREATED = NONE
GATE_3_BUSINESS_PIPELINE = FAIL
NEXT_GATE = STOP_FOR_REVIEW
FAILURE_STAGE = TEST_HARNESS / PARSE_ATTEMPT_FIXTURE
ROOT_CAUSE_CATEGORY = TEST_HARNESS
EXACT_ERROR = database column observability_status is NOT NULL, but the active Odoo ORM model does not expose that field
```

The active Odoo shell loaded the older `ai_vendor_invoice` module source while
the database already contains the newer required `observability_status`
column. Attempts to proceed by direct SQL or generic Statement CRUD were not
made because that would bypass the Task aggregate boundary. No Statement,
Human Review projection, Bill Creator call, or draft Vendor Bill was created.

## 20. Gate 3 Revalidation — 2026-09-02

The same Gate 3 validation was rechecked against the active Odoo environment.
The blocker remains unchanged:

```text
VALIDATION_MODE = GATE_3_BUSINESS_PIPELINE
QUEUE_USED = NO
PROVIDER_CALLS = 0
GATE_1_SOURCE = PASS
GATE_2_SOURCE = PASS
FAILURE_STAGE = PARSE_ATTEMPT_FIXTURE
ROOT_CAUSE_CATEGORY = TEST_HARNESS / ENVIRONMENT
EXACT_ERROR = Invalid field 'observability_status' on model 'vendor.invoice.import.parse.attempt'
DATABASE_COLUMN = observability_status (NOT NULL)
ORM_FIELD = absent in active Registry
STATEMENT_CREATED = NO
HUMAN_REVIEW_RESULT_GENERATED = NOT_REACHED
VENDOR_BILL_CREATED = NO
GATE_3_BUSINESS_PIPELINE = FAIL
NEXT_GATE = STOP_FOR_REVIEW
```

The Odoo process loaded the module from the main checkout rather than the
worktree version containing the matching ORM field. The run made no Provider
call and did not persist a Task, ParseAttempt, Statement, projection, or Bill;
the transaction was aborted at ParseAttempt creation. No SQL workaround,
direct Statement CRUD, code change, or configuration change was used.

## 21. Gate 3 Revalidation — 2026-09-02 Environment Fixed, Evidence Missing

The Odoo Registry mismatch was corrected and verified: the active Registry now
loads the worktree module and exposes `observability_status`. However, the
temporary Gate 1 output file containing the actual five-page
`MODEL_CONTENT` was no longer available, and no persisted Gate 2 canonical or
mapping snapshot exists. Because Gate 3 forbids a new Provider call and forbids
hand-constructing review data, execution stopped before creating any business
records.

```text
VALIDATION_MODE = GATE_3_BUSINESS_PIPELINE
QUEUE_USED = NO
PROVIDER_CALLS = 0
GATE_1_SOURCE = PASS (historical evidence)
GATE_2_SOURCE = PASS (historical evidence)
INPUT_PAGE_RESULTS = NOT_AVAILABLE_FOR_REUSE
STATEMENT_CREATED = NO
HUMAN_REVIEW_RESULT_GENERATED = NOT_REACHED
VENDOR_BILL_CREATED = NO
DATABASE_TEST_RECORDS_CREATED = NONE
FAILURE_STAGE = INPUT_EVIDENCE_REUSE
ROOT_CAUSE_CATEGORY = TEST_HARNESS
EXACT_ERROR = Gate 1 MODEL_CONTENT temporary output was unavailable
GATE_3_BUSINESS_PIPELINE = BLOCKED
NEXT_GATE = STOP_FOR_REVIEW
```

No Provider, Normalizer, Mapping, Statement, Projection, or Bill operation was
performed in this final attempt. Gate 1 must be rerun separately with its
complete output persisted before Gate 3 can continue without violating the
zero-Provider-call constraint.

## 22. Gate 3 — Business Pipeline Execution Result

After persisting Gate 1 evidence and correcting the active Registry, Gate 3 was
executed as the existing Reviewer user with zero Provider calls. The production
path reached Statement confirmation and Bill Creator.

```text
VALIDATION_MODE = GATE_3_BUSINESS_PIPELINE
QUEUE_USED = NO
PROVIDER_CALLS = 0
TASK_ID = 2069 (transaction-local; rolled back)
PARSE_ATTEMPT_ID = 1314 (transaction-local; rolled back)
STATEMENT_ID = 83 (transaction-local; rolled back)
STATEMENT_CREATED = YES (transaction-local)
STATEMENT_LINE_COUNT = 0
HUMAN_REVIEW_RESULT_GENERATED = YES
HUMAN_REVIEWED = YES
PROJECTION_STATUS = PASS
BILL_CREATOR_USED = PRODUCTION
VENDOR_BILL_CREATED = YES (transaction-local)
VENDOR_BILL_ID = 2148 (transaction-local; rolled back)
BILL_MOVE_TYPE = in_invoice
BILL_STATE = draft
BILL_PARTNER = Wood Corner
BILL_CURRENCY = USD
BILL_INVOICE_DATE = 2026-07-06
BILL_REFERENCE = 26022366
BILL_LINE_COUNT = 1
BILL_TOTAL = 0.0
BILL_STATEMENT_LINK = FAIL (field absent)
BILL_LINE_TRACEABILITY = FAIL (field absent)
SECOND_CREATE_ATTEMPT = blocked by task state after bill generation
DUPLICATE_BILL_CREATED = NO
DATABASE_TEST_RECORDS_CREATED = NONE (transaction rolled back)
GATE_3_BUSINESS_PIPELINE = FAIL
NEXT_GATE = STOP_FOR_REVIEW
FAILURE_STAGE = STATEMENT_CREATION / TRACEABILITY
ROOT_CAUSE_CATEGORY = STATEMENT / TRACEABILITY
```

The execution exposed two production defects without modifying them:
`action_create_statement_from_attempt` created the Statement header but did not
create its submitted lines, so Bill Creator used its fallback single line.
Additionally, `account.move` and `account.move.line` do not expose the required
Statement traceability fields. The generated draft bill existed only inside the
validation transaction; the shell transaction was rolled back, leaving no test
records in the database. No Provider, queue, Prompt, schema, Mapping, or
business configuration was changed.

## 23. FIX-GATE3-STATEMENT-LINES-TRACEABILITY-001

The focused fix completed the two reported production defects:

```text
FIX_STATUS = COMPLETE
ROOT_CAUSE_DEFECT_1 = Statement header creation omitted aggregate line creation
ROOT_CAUSE_DEFECT_2 = account.move traceability inherit models were absent
FILES_CHANGED =
  models/import_task.py
  models/account_move.py
  models/__init__.py
  services/statement_projection.py
  services/bill_creator.py
  tests/test_models.py
AUTOMATED_TESTS =
  verify.py: 19 pass, 0 fail
  Odoo focused regression suite: exit 0
CANONICAL_LINE_COUNT = 49
STATEMENT_LINE_COUNT = 49
BILL_LINE_COUNT = 49
BILL_STATEMENT_LINK = PASS
BILL_LINE_TRACEABILITY = PASS
DUPLICATE_BILL_CREATED = NO
GATE_3_BUSINESS_PIPELINE = PASS
NEXT_GATE = STOP_FOR_REVIEW
```

The real sync revalidation used the persisted Gate 1 evidence and made zero
Provider calls. Existing database master data was used for the explicit Human
Review overrides: partner `Wood Corner`, currency `USD`, product id `1`, and
purchase tax `15%`. The overrides were not represented as AI or Mapping
matches.

The Statement first, middle, and last lines were verified with descriptions,
amounts, product IDs, and tax IDs. The corresponding first, middle, and last
invoice lines pointed to Statement line IDs `50`, `74`, and `98`. The generated
bill was draft `account.move` with `move_type = in_invoice`, reference
`26022366`, and total `0.0`. The second creation attempt was rejected by the
existing task-state guard and did not create a duplicate.

The validation transaction was rolled back after assertions, so the reported
Task, Attempt, Statement, and Bill IDs were transaction-local and no test
business records remain in the database. No Prompt, schema, Normalizer,
Mapping, queue, timeout, or provider behavior was changed.
