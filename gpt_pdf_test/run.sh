#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PY:-python3}"
PDF="${1:-}"

if [ -z "$PDF" ]; then
  echo "用法: ./run.sh /path/to/invoice.pdf"
  exit 1
fi

if [ ! -f "$PDF" ]; then
  echo "找不到 PDF: $PDF"
  exit 1
fi

"$PY" -m tools.gpt_pdf "$PDF"
