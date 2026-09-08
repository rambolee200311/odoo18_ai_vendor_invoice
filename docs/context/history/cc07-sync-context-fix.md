# CC-07 - Synchronous Parse Context Fix

## Issue

The synchronous parse path attempted to call `with_context()` on an Odoo
`Environment`, which caused an RPC error when running AI from the Task form.

## Resolution

The parser now derives the context from the Task recordset and passes its
Environment to the existing parse pipeline. The queue-backed asynchronous
path is unchanged.

## Verification

```text
Python compilation: PASS
Repository verification: 19 pass, 0 fail
Odoo model tests: 33 tests, 0 failed, 0 errors
```
