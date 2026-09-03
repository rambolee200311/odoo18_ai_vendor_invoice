# Native PDF Response Contract Matrix

This matrix records only response shapes observed in saved production
evidence. It is a compatibility boundary for native document normalization;
it is not a business inference contract.

## Corpus evidence

| Sample | Evidence | Status |
| --- | --- | --- |
| 26022366 | Statement 101 / ParseAttempt 1518; no reliably linked raw ProviderCall attachment | MISSING_CORPUS_EVIDENCE |
| 26026130 | ProviderCall 146 | OBSERVED |
| 26026801 | ProviderCall 195 | OBSERVED |
| 26026807 | ProviderCall 196 | OBSERVED |

## Shape matrix

`FORMAL` means the normalized Native Document contract. `APPROVED_ALIAS`
means an explicit, deterministic compatibility mapping implemented in
`native_document_projection.py`. `REJECTED` means the shape is not accepted
without a proved alias. `NOT_OBSERVED` means it was not found in the saved
corpus reviewed for this matrix.

| Dimension | Shape | Classification | Evidence |
| --- | --- | --- | --- |
| Supplier | `invoice.supplier` string | FORMAL | ProviderCall 146/195/196 |
| Supplier | `invoice.supplier` object with `name` | APPROVED_ALIAS | ProviderCall 146/195/196 |
| Business lines | `invoice.lines` | FORMAL | ProviderCall 146/195/196 |
| Business lines | top-level `line_items` | APPROVED_ALIAS | Historical flat response for 26026130/26026801 |
| Line amount | `amount` | FORMAL | ProviderCall 195 |
| Line amount | `amount_excl_tax` | APPROVED_ALIAS | ProviderCall 146 |
| Line amount | `total_amount` | APPROVED_ALIAS | Historical flat response |
| Line amount | `line_total` | APPROVED_ALIAS | ProviderCall 196 |
| Charges | `charge_components` list | FORMAL | ProviderCall 146 |
| Charges | `charges` list | APPROVED_ALIAS | ProviderCall 195/196 |
| Charges | `charges` object | APPROVED_ALIAS | Existing compatibility regression |
| Charge description | `description` | FORMAL | ProviderCall 146/196 |
| Charge description | `label` | APPROVED_ALIAS | ProviderCall 195 |
| Totals | `subtotal` | FORMAL | Existing Canonical-compatible field |
| Totals | `subtotal_excl_tax` | APPROVED_ALIAS | ProviderCall 146 |
| Totals | `subtotal_excl_vat` | APPROVED_ALIAS | ProviderCall 195 |
| Totals | `subtotal_excluding_tax` | APPROVED_ALIAS | ProviderCall 196 |
| Totals | `total_tax` | FORMAL | Existing Canonical-compatible field |
| Totals | `tax_total` | APPROVED_ALIAS | ProviderCall 146 |
| Totals | `vat_amount` | APPROVED_ALIAS | ProviderCall 195 |
| Totals | `invoice.tax.amount` | APPROVED_ALIAS | ProviderCall 196 |
| Totals | `total_amount` | FORMAL | Existing Canonical-compatible field |
| Totals | `total_incl_tax` | APPROVED_ALIAS | ProviderCall 146 |
| Totals | `total_incl_vat` | APPROVED_ALIAS | ProviderCall 195 |
| Totals | `total_including_tax` | APPROVED_ALIAS | ProviderCall 196 |

No unknown or fuzzy aliases are accepted. Charge components remain nested
under their business line and are never promoted to top-level lines.
