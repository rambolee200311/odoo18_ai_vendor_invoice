# CC-08 - Task Cancellation and Error State Simplification

## Scope

- Added a `Cancel` action for Import Tasks.
- Added the `cancelled` Task and ParseAttempt states.
- Consolidated Task error states into `error` and exposed an Error Badge.
- Protected synchronous parse results from being applied after cancellation.
- Released the source PDF checksum when a Task is cancelled.
- Kept asynchronous queue execution outside the CC-08 acceptance scope because
  it has not yet passed end-to-end verification.

## Verification

```text
Python compilation: PASS
XML structure and repository verification: PASS (19 pass, 0 fail)
Focused CC-08 tests: 3 tests, 0 failed, 0 errors
```

The broader model selection also contains a pre-existing
`queue_reconciliation` audit-action test error; it is unrelated to the
CC-08 cancellation path.
