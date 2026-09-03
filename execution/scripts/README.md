# Verification scripts

`verify.py` performs static repository checks. The historic `wd_tlms` invocation
remains the default:

```bash
python execution/scripts/verify.py
```

To verify the AI vendor invoice addon and emit the frozen Coding Contract gates:

```bash
python execution/scripts/verify.py --module ai_vendor_invoice
```

The AI vendor invoice mode checks Python/XML structure and emits
`GATE-01` through `GATE-15` individually. A failed gate returns exit status
`1`; the script reports evidence only and does not modify source, tests, or
documentation.

## New invoice samples: schema-first

New supplier or materially different invoice samples must follow this order:

1. Run the strict Structured Outputs experiment first, using the fixed
   `InvoiceExtractionResult` contract:

   ```bash
   python execution/experiments/test_luna_structured_pdf.py
   ```

2. For a new supplier, run the multi-PDF compatibility experiment with three
   to five representative historical PDFs. Reuse the same model, prompt,
   schema, reasoning settings, and Responses API parameters for every PDF.
3. Record Gate 1 evidence before assessing extraction values:
   HTTP success, structured output success, JSON parse success, Schema validity,
   unknown keys, provider-drift keys, and recursive structure compatibility.
4. Only after Gate 1 passes, assess extraction quality. Only after both gates
   pass, run the Odoo Production pipeline.

Do not add provider aliases, relax `additionalProperties`, or change Mapping
and Statement code in response to a new sample before diagnosing the strict
Provider contract. Extraction accuracy and Schema stability are separate
acceptance results. Failed samples are recorded and the next sample may
continue, but the failing sample is not silently promoted to Production.
