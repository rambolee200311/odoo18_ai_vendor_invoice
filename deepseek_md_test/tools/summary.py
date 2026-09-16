import json
from pathlib import Path

from tabulate import tabulate

ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = ROOT / "output" / "report"
STEPS_FILE = REPORT_DIR / "steps.jsonl"
RES = ROOT / "output" / "results"

# ---- 读取分步记录 ----
step_records = []
if STEPS_FILE.exists():
    for line in STEPS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            step_records.append(json.loads(line))

print("\n== 分步时间 ==")
print(tabulate(
    [
        [
            r["step"],
            r["started_at"],
            r["finished_at"],
            r["duration_sec"],
            r["status"],
        ]
        for r in step_records
    ],
    headers=["step", "started_at", "finished_at", "duration_sec", "status"],
))

# ---- 读取 DeepSeek 请求级结果 ----
rows = []
for f in sorted(RES.glob("*.result.json")):
    stem = f.name[: -len(".result.json")]
    data = json.loads(f.read_text(encoding="utf-8"))
    rows.append([
        stem,
        data["latency_sec"],
        data["prompt_tokens"],
        data["completion_tokens"],
        data["prompt_tokens"] + data["completion_tokens"],
    ])

print("\n== Markdown 路径汇总 ==")
print(tabulate(rows, headers=[
    "invoice", "延迟(s)", "prompt_tok", "completion_tok", "total_tok",
]))

# ---- 写最终 JSON 报告 ----
final_report = {
    "steps": step_records,
    "requests": rows,
    "totals": {
        "step_count": len(step_records),
        "step_total_duration_sec": round(
            sum(r["duration_sec"] for r in step_records), 3),
        "request_count": len(rows),
        "request_total_latency_sec": round(
            sum(r[1] for r in rows), 2) if rows else 0,
        "total_prompt_tokens": sum(r[2] for r in rows) if rows else 0,
        "total_completion_tokens": sum(r[3] for r in rows) if rows else 0,
    },
}

final_path = REPORT_DIR / "final_report.json"
final_path.write_text(
    json.dumps(final_report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"\n最终报告: {final_path}")
print("人工检查：")
print("1. output/markdown/*.md 看转换质量")
print("2. output/results/*.result.json 看字段提取是否准确")
print("3. output/report/final_report.json 看时间与 token 汇总")