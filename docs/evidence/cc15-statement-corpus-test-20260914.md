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

Prompt:

```text
version: markdown-extraction-v4
sha256: 2bd72610faee75644544c91eb436688adfe1072e85235671361ec05e5b590774
```

Normalization followed the existing V4 rules:

- text: trim and case-fold;
- invoice number: remove spaces and hyphens;
- date: `YYYY-MM-DD`;
- amount: Decimal rounded to 2 places;
- currency: normalized to uppercase ISO text (`EURO`/`EUROS` → `EUR`);
- line count: exact integer comparison.

## Results

| Statement | Matches |
|---:|---:|
| 1063 | 1/6 |
| 1144 | 6/6 |
| 1145 | 1/6 |
| 1174 | 6/6 |
| 1221 | 6/6 |
| 1254 | 6/6 |
| 1315 | 6/6 |
| 1332 | 6/6 |
| 1349 | 6/6 |

### Mixed historical baselines

```text
44 / 54 = 81.48%
```

This number is diagnostic only because two samples do not have GPT baselines.

### GPT native-PDF baselines only

```text
42 / 42 = 100.00%
```

## Decision

```text
PASS ON GPT TUNING CORPUS — 100.00%
```

The mixed 9-sample number is diagnostic only. Statements 1063 and 1145 must be
replayed through GPT native PDF or replaced with GPT-baseline samples before
using all 9 as an apples-to-apples production decision corpus.

## Isolated GPT native-PDF replay

After the corpus Statements were cancelled through the ORM state-machine
command, all nine source PDFs were replayed with the preserved
`OpenAI GPT-5.6 Luna` provider configuration and `native_pdf` input mode.
The replay called the provider adapter directly and did not create or update
Statements, Tasks, or ParseAttempts. All nine requests succeeded.

Detailed raw responses and canonical outputs are preserved separately in
[cc15-gpt-native-pdf-replay-20260914.json](./cc15-gpt-native-pdf-replay-20260914.json).
The field-level comparison is preserved in
[cc15-gpt-native-pdf-replay-comparison-20260914.json](./cc15-gpt-native-pdf-replay-comparison-20260914.json).

| Statement | Replay status | Historical GPT baseline | Matches |
|---:|---|---|---:|
| 1063 | success | none; new GPT baseline | n/a |
| 1144 | success | GPT native PDF | 6/6 |
| 1145 | success | none; new GPT baseline | n/a |
| 1174 | success | GPT native PDF | 6/6 |
| 1221 | success | GPT native PDF | 6/6 |
| 1254 | success | GPT native PDF | 6/6 |
| 1315 | success | GPT native PDF | 6/6 |
| 1332 | success | GPT native PDF | 6/6 |
| 1349 | success | GPT native PDF | 6/6 |

The apples-to-apples reproduction result remains **42/42 (100.00%)** on the
seven Statements with preserved historical GPT native-PDF results. Statements
1063 and 1145 now have independent GPT native-PDF replay baselines; their
outputs must be compared with the corresponding DeepSeek results rather than
with their historical rendered-image attempts.

## New GPT-derived Statements

To validate the business-document path itself, the nine replay results were
materialized as new independent Statement aggregates. They use new Tasks,
successful ParseAttempts, copied source-PDF attachments, and raw-response
attachments. The new Statements remain `draft`; the nine historical Statements
remain `cancelled`.

| Historical Statement | New GPT Statement | Task | ParseAttempt | Business field match |
|---:|---:|---:|---:|---:|
| 1063 | 1692 | 8903 | 6191 | 2/8 |
| 1144 | 1693 | 8904 | 6192 | 1/8 |
| 1145 | 1694 | 8905 | 6193 | 1/8 |
| 1174 | 1695 | 8906 | 6194 | 8/8 |
| 1221 | 1696 | 8907 | 6195 | 8/8 |
| 1254 | 1697 | 8908 | 6196 | 8/8 |
| 1315 | 1698 | 8909 | 6197 | 8/8 |
| 1332 | 1699 | 8910 | 6198 | 8/8 |
| 1349 | 1700 | 8911 | 6199 | 6/8 |

The comparison covers supplier, invoice number, invoice date, currency,
subtotal, total tax, total amount, and line count. The aggregate result is
**50/72 (69.44%)**, but this raw percentage is not a reliable GPT accuracy
rate: historical Statements 1063, 1144, and 1145 have mostly empty business
fields, while their historical ParseAttempts contain extraction data. The
1349 difference is specifically the historical tax/total projection versus
the new GPT projection. Full record-level data is preserved in
[cc15-gpt-new-statement-business-comparison-20260914.json](./cc15-gpt-new-statement-business-comparison-20260914.json),
and the new Statement IDs are recorded in
[cc15-gpt-native-pdf-new-statements-20260914.json](./cc15-gpt-native-pdf-new-statements-20260914.json).
