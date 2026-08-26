# INTENT-IMPLEMENT-INVOICE-STATEMENT-001 Closure Evidence

> Date: 2026-08-26
> Database: `odoo18e_tms`
> Status: `PAGE_EXTRACTION_FIX_PASS`

## 1. Verification environment

The database-backed checks use the existing project environment:

```text
cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice
source venv/bin/activate
```

The addon under test is the current Statement worktree. The Odoo addons path
places the worktree addon after the Odoo core and queue-job addon paths, so the
tests load the current implementation.

## 2. Fixture profiles

Acceptance fixtures are read from the main project's:

```text
/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/carrier_invoice
```

The fixtures are used to exercise generic normalization and candidate
processing. They do not authorize carrier-specific branches.

| Fixture | Supplier | Invoice number | Invoice date | Currency | Total / tax | Line and reference semantics |
| --- | --- | --- | --- | --- | --- | --- |
| `bring_26022366.pdf` | Bring Cargo B.V. | `26022366` | `06/07/26` | EUR | `5,107.70` incl. VAT; `886.46` VAT | Summary/detail transport rows; `Uw referentie` and shipment references remain candidates. |
| `feelogic_35318.pdf` | Feelogic | `35318` | Fixture invoice date | EUR | `3,820.00` total; `0.00` VAT | `Dossier`, `Opdracht`, and `Uw ref.` remain candidate references, not hard-coded fields. |
| `mainfreight_1727001370.pdf` | Mainfreight | `1727001370` | Fixture invoice date | EUR | Extracted from invoice total | Shipment number and `O.No.` remain candidate references. |

The expected human review fields are:

```text
supplier
invoice number
invoice date
currency
total
tax
line items
transport number/reference candidate
```

## 3. Gate evidence

The existing regression gates were executed with:

```text
python3 execution/scripts/verify.py
```

Result:

```text
19 pass, 0 fail
```

The database suite was executed with:

```text
python3 odoo-bin -c odoo.conf \
  --addons-path=<odoo-core>,<queue-job>,<statement-worktree>/addons \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init
```

Result:

```text
Full addon test command exited with status 0 after fixture cleanup.
```

The suite includes Statement creation/provenance, direct CRUD rejection,
projection generation, projection inconsistency rejection, bill closure,
concurrency, stale-worker, permission, rollback, attachment, and
company-context coverage.

| Gate | Evidence | Status |
| --- | --- | --- |
| `STATEMENT-GATE-01..08` | Statement models, provenance commands, and model tests | PASS |
| `STATEMENT-GATE-09..12` | Aggregate command boundary, CRUD rejection, and confirmation tests | PASS |
| `STATEMENT-GATE-13..18` | Projection service, consistency test, and Bill Creator integration | PASS |
| `STATEMENT-GATE-19..23` | Existing bill transaction, idempotency, permission, attachment, and company tests | PASS |
| `STATEMENT-GATE-24` | Carrier fixture profile and carrier-neutral source inspection | PASS |
| `STATEMENT-GATE-25` | Final full Gate report and production-scale concurrency evidence | PENDING |

## 4. Authorized DeepSeek execution

The configured provider was read without exposing its secret:

```text
Provider: deepseek API
Endpoint root: https://api.deepseek.com
Model: deepseek-v4-flash-vision-exp
Active: True
API key configured: True
```

The adapter now uses the OpenAI SDK and the official OpenAI-compatible call:
`OpenAI(api_key=..., base_url=...)`,
`chat.completions.create(...)`, `reasoning_effort="high"`, and
`thinking={"type": "enabled"}`. The SDK is declared in `requirements.txt`.
The response is unwrapped from `choices[0].message.content`; the raw response
is retained only in the private audit attachment.

To avoid oversized multi-page requests, the adapter now sends one rendered PDF
page per SDK request, validates page facts, and normalizes the ordered page
results into the frozen document-level CanonicalResult. Each page request uses
the configured retry policy; no raw response is written to `error_message`.

The stability fix also persists a non-sensitive diagnostic entry for every
page/batch attempt on `ParseAttempt.provider_diagnostics`. Each entry contains
the task/attempt identifiers, page range, page and image counts, image byte
count, start time, elapsed time, retry index, HTTP status when available,
exception class, provider error category, response parse status, and canonical
schema status. The logger receives the same metadata, but never receives API
keys, authorization headers, prompts, image data, invoice text, or full
provider responses.

Temporary timeout, connection, rate-limit, and 5xx failures retry only within
the configured limit. Authentication, bad-request, unsupported-input,
invalid-JSON, schema, merge, and unknown-provider failures terminate the
attempt. The local merge rejects conflicting header values and
`is_multi_invoice` flags, preserves line order, and removes exact duplicate
line records.

Non-sensitive health checks returned HTTP 200, including a one-page vision
request. Full execution of the three fixtures was rerun in `odoo18e_tms` using the
current worktree and the SDK. The layered results are:

| Fixture | Task / attempt | Page extraction | Document normalization | Canonical | Final state |
| --- | --- | --- | --- | --- | --- |
| `bring_26022366.pdf` | 904 / 680 | PASS (5/5 HTTP 200; 5/5 page facts) | PASS | PASS; 22 lines | `awaiting_review` |
| `feelogic_35318.pdf` | 905 / 659 | PASS (1/1 HTTP 200; 1/1 page facts) | PASS | PASS; 2 lines | `awaiting_review` |
| `mainfreight_1727001370.pdf` | 906 / 660 | PASS (3/3 pages; 2 timeout retries recovered) | PASS | PASS; 14 lines | `awaiting_review` |

No raw provider response or API key was printed or persisted in the report.
The provider transport, timeout retry, page extraction, and canonical
validation paths are proven for all three fixtures. Bring initially exposed a
cross-page header disagreement; the generic evidence-weighted candidate policy
resolved it without carrier-specific logic.

## Page extraction architecture follow-up

The follow-up fix `FIX-INTENT-AI-VENDOR-PAGE-EXTRACTION-001` changes the
provider-internal pipeline to page extraction followed by document-level
normalization. It does not change the frozen CanonicalResult, mapping,
Statement, review, bill, or Task contracts. The next fixture run must report
the separate stages:

```text
Vision page extraction -> PageExtractionResult[] -> document normalization
-> Canonical Schema validation
```

The Bring rerun now passes all layers. The three-fixture matrix is green for
page extraction, document normalization, and Canonical validation.

## 5. Open closure items

The implementation does not claim final closure until:

1. the three carrier PDFs are run through the configured AI/provider pipeline
   and their human-reviewed field values are recorded;
2. a multi-transaction PostgreSQL concurrency run is recorded separately from
   the normal Odoo test suite;
3. the individual `STATEMENT-GATE-01..25` checks are emitted by the verifier
   rather than represented only by grouped evidence.

These are evidence and verification tasks, not requests for new business
behavior. Carrier-specific parsing branches remain prohibited.
