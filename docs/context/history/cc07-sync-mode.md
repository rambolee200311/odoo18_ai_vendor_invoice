# CC-07 - Import Task Parse Mode

## Scope

- Removed the `Company` field from the Import Task form while retaining the
  immutable company field and backend company isolation.
- Added a `Synchronous Parse` checkbox to the Task form.
- Defaulted the checkbox to enabled for manual verification.
- The existing `Run AI` action now uses the checkbox to select synchronous
  execution or the existing queue-backed asynchronous execution.

## Verification

```text
Python compilation: PASS
XML structure and CC-07 view assertions: PASS
Repository verification: 19 pass, 0 fail
Odoo model tests after module update: PASS
```
