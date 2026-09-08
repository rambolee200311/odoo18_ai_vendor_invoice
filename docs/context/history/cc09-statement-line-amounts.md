# CC-09 - Statement Line Amounts and Read-only States

## Scope

- Kept `amount` as the untaxed line amount.
- Added deterministic amount, tax rate, tax amount, and total amount
  normalization, including multi-field write precedence.
- Added zero-untaxed/non-zero-tax validation.
- Reused Statement `subtotal`, `total_tax`, and `total_amount` for line
  aggregates and added the computed overall tax rate.
- Enabled Draft line Form editing with ORM and View state protection.
- Kept the CC-04 Statement states and did not change Bill Creator or accounting
  rules.

## Verification

```text
Python compilation: PASS
XML structure: PASS
Repository verification: 19 pass, 0 fail
Focused Statement tests: 4 tests, 0 failed, 0 errors
```
