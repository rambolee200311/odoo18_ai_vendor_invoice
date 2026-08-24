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
