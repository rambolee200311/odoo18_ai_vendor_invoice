# CC-15 Statement Corpus Test — 2026-09-14

## Scope

通过主工作区 Odoo venv 和 `odoo-bin shell`，使用 ORM 读取现有
`vendor.invoice.statement` 的前 9 个 source-PDF Statement，执行：

```text
source_pdf_attachment_id
→ PDF → Markdown
→ DeepSeek Markdown V4
→ Canonical JSON
→ historical Canonical baseline comparison
```

## Corpus

| Statement ID | Historical successful provider | Input mode |
|---:|---|---|
| 1063 | DeepSeek API | rendered_images |
| 1144 | OpenAI GPT-5.6 Luna | native_pdf |
| 1145 | DeepSeek API | rendered_images |
| 1174 | OpenAI GPT-5.6 Luna | native_pdf |
| 1221 | OpenAI GPT-5.6 Luna | native_pdf |
| 1254 | OpenAI GPT-5.6 Luna | native_pdf |
| 1315 | OpenAI GPT-5.6 Luna | native_pdf |
| 1332 | OpenAI GPT-5.6 Luna | native_pdf |
| 1349 | OpenAI GPT-5.6 Luna | native_pdf |

The current database contains 16 Statements with source PDFs. Only 7 of the
selected 9 have historical GPT native-PDF baselines. Statements 1063 and 1145
have DeepSeek rendered-image baselines and are not valid GPT-vs-DeepSeek
comparisons.

## Comparison fields

- supplier
- invoice_number
- invoice_date
- currency
- subtotal
- line_count

Normalization followed the existing V4 rules:

- text: trim and case-fold;
- invoice number: remove spaces and hyphens;
- date: `YYYY-MM-DD`;
- amount: Decimal rounded to 2 places;
- currency: case-folded text comparison;
- line count: exact integer comparison.

## Results

| Statement | Matches |
|---:|---:|
| 1063 | 1/6 |
| 1144 | 5/6 |
| 1145 | 1/6 |
| 1174 | 6/6 |
| 1221 | 5/6 |
| 1254 | 5/6 |
| 1315 | 6/6 |
| 1332 | 5/6 |
| 1349 | 5/6 |

### Mixed historical baselines

```text
39 / 54 = 72.22%
```

This number is diagnostic only because two samples do not have GPT baselines.

### GPT native-PDF baselines only

```text
37 / 42 = 88.10%
```

## Decision

```text
FAIL — below the 90% V4 target
```

The implementation path is executable, but this run does not authorize
production substitution. The two non-GPT baseline samples must be replaced or
replayed through the GPT native-PDF route before a final apples-to-apples
decision.

