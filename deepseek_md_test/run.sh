#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PY:-python3}"
REPORT_DIR="$ROOT/output/report"
STEPS_FILE="$REPORT_DIR/steps.jsonl"
RUN_REPORT="$REPORT_DIR/run_report.json"

if [ ! -f .env ]; then
  echo "缺少 .env，请先配置 DEEPSEEK_API_KEY"
  exit 1
fi

if [ ! -d samples ] || [ -z "$(ls -A samples/*.pdf 2>/dev/null)" ]; then
  echo "请在 samples/ 放入至少 1 张真实发票 PDF"
  exit 1
fi

mkdir -p output/markdown output/results "$REPORT_DIR"

# 每次运行清空 steps 文件，避免和历史混
: > "$STEPS_FILE"

RUN_STARTED_AT="$(date -Iseconds)"
RUN_START_EPOCH="$(date +%s)"
echo "RUN START: $RUN_STARTED_AT"

CMD="${1:-all}"

run_step1() {
  echo "== step 1: PDF -> Markdown =="
  "$PY" -m tools.pdf_to_markdown
}

run_step2() {
  echo "== step 2: Markdown -> DeepSeek -> JSON =="
  "$PY" -m tools.ds_markdown
}

run_step3() {
  echo "== step 3: 汇总 =="
  "$PY" -m tools.summary
}

STATUS="ok"
case "$CMD" in
  all)
    run_step1 || STATUS="error"
    [ "$STATUS" = "ok" ] && run_step2 || STATUS="error"
    [ "$STATUS" = "ok" ] && run_step3 || STATUS="error"
    ;;
  1) run_step1 || STATUS="error" ;;
  2) run_step2 || STATUS="error" ;;
  3) run_step3 || STATUS="error" ;;
  *)
    echo "用法: ./run.sh [all|1|2|3]"
    exit 1
    ;;
esac

RUN_FINISHED_AT="$(date -Iseconds)"
RUN_DURATION=$(( $(date +%s) - RUN_START_EPOCH ))

cat > "$RUN_REPORT" <<EOF
{
  "command": "$CMD",
  "started_at": "$RUN_STARTED_AT",
  "finished_at": "$RUN_FINISHED_AT",
  "duration_sec": $RUN_DURATION,
  "status": "$STATUS",
  "steps_file": "output/report/steps.jsonl"
}
EOF

echo "RUN END:   $RUN_FINISHED_AT (${RUN_DURATION}s, $STATUS)"
echo "总报告: $RUN_REPORT"
echo "分步报告: $STEPS_FILE"