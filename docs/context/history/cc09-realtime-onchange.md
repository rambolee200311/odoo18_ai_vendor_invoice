# CC-09 - Realtime Amount Onchange

## Issue

Browser verification showed that editing a Statement Line amount field did not
refresh the other amount fields until the line was saved.

## Resolution

Added dedicated Odoo onchange handlers for untaxed amount, tax rate, tax
amount, and total amount. Each handler recalculates the other fields
immediately in the form. ORM normalization remains the persistence-time
consistency guard.

## Verification

```text
Python compilation: PASS
Repository verification: 19 pass, 0 fail
Realtime onchange and ORM amount tests: 2 tests, 0 failed, 0 errors
```
