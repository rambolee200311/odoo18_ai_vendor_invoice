# FIX-INTENT-AI-VENDOR-PROVIDER-STABILITY-001

> Status: Implemented; fixture validation pending
> Scope: DeepSeek page/batch Provider runtime stability only

## Objective

Diagnose and stabilize multi-page Vision requests without changing Statement,
Human Review, Bill Creator, Mapping, Task states, or ParseAttempt business
semantics.

One PDF remains one ParseAttempt and one merged CanonicalResult. Page retries
are internal provider transport behavior; they must not create ParseAttempts or
Statements.

## Required diagnostics

Every page/batch call records only non-sensitive metadata: Task/Attempt IDs,
page range, page/image counts, image bytes, start time, elapsed time, retry
index, HTTP status when available, exception class, provider error category,
response parse status, and canonical schema status.

Never record API keys, authorization headers, PDF/image content, base64 data,
full prompts, full provider responses, or sensitive invoice text.

## Error categories

The implementation distinguishes temporary timeout, connection, rate-limit,
and 5xx failures; permanent authentication, bad-request, and unsupported-input
failures; invalid/empty response JSON; invalid canonical schema; merge errors;
and unknown provider errors. Temporary transport errors may retry within a
fixed maximum. Permanent or response/schema errors terminate the attempt.

## Fixed transport limits

The current implementation uses one page per request
(`max_pages_per_batch = 1`) and the configured provider timeout and retry
limit. No limit may be increased dynamically after a failure.

## Merge contract

Successful page results are merged locally into one CanonicalResult. Header
values may be supplied by the first non-empty page; repeated identical values
are accepted. Conflicting invoice identity, currency, totals, or tax values
must raise a merge error rather than silently selecting the last value. Lines
retain page order and must not be duplicated by repeated page headers.

## Implementation evidence

- `DeepSeekAIProviderAdapter` sends one page per request and uses the configured
  timeout and retry limit without dynamically increasing either value. The
  OpenAI SDK's own automatic retries are disabled so the adapter remains the
  single retry-policy owner.
- Safe page/batch diagnostics are persisted on
  `vendor.invoice.import.parse.attempt.provider_diagnostics` and are also
  emitted as structured log metadata. Secrets, prompts, image data, and raw
  provider responses are excluded.
- SDK timeout, connection, rate-limit, 5xx, authentication, bad-request,
  unsupported-input, invalid JSON, schema, merge, and unknown-provider errors
  are classified separately. Only the configured temporary categories retry.
- Merge rejects conflicting header values and `is_multi_invoice` flags, keeps
  page order, and removes exact duplicate line records.

The implementation evidence is covered by the provider adapter regression
tests and the full addon test suite. The three real carrier fixture runs and
their final canonical/business-state evidence remain required for acceptance.

## Acceptance

Run Bring, Feelogic, and Mainfreight fixtures with a safe diagnostic matrix.
The fixture run passes only when every page succeeds, the merged result
conforms to the canonical schema, and the ParseAttempt reaches its expected
business state. No new Task or Attempt state is permitted.
