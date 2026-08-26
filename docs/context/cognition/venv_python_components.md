# Python Components Required in `venv`

本文档记录本项目运行 `ai_vendor_invoice`、执行 PDF 预处理、调用
DeepSeek Vision API 以及运行测试所需的 Python 组件。

## Installation

在项目根目录执行：

```bash
cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice
source venv/bin/activate
python3 -m pip install -r requirements.txt
```

如果只需要补装本项目额外使用的组件：

```bash
python3 -m pip install PyMuPDF jsonschema openai
```

## Required components

| Component | Python import | Purpose |
| --- | --- | --- |
| `PyMuPDF` | `fitz` | Render PDF pages into ordered PNG images before Vision requests. |
| `jsonschema` | `jsonschema` | Validate canonical, mapping, human-review, and warning JSON structures. |
| `openai` | `openai` | Call the OpenAI-compatible DeepSeek API. |

Odoo itself and its transitive dependencies are installed through the
repository's normal `requirements.txt`; do not install a second Odoo runtime
inside the project virtual environment.

## Verification

```bash
python3 - <<'PY'
import fitz
import jsonschema
import openai

print("PyMuPDF: PASS")
print("jsonschema: PASS")
print("openai: PASS")
PY
```

Then verify the addon:

```bash
python3 execution/scripts/verify.py
```

For database-backed tests:

```bash
python3 odoo-bin -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,addons \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init
```

## Secret handling

The DeepSeek API key must be read from the protected
`wd.ai.provider.config` record through the configured server-side access path.
Do not put API keys in this document, shell history, source code, test
fixtures, logs, or command output.
