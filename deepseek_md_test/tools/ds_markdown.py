import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from tools.timing import StepRecorder

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MD_DIR = ROOT / "output" / "markdown"
OUT = ROOT / "output" / "results"
OUT.mkdir(parents=True, exist_ok=True)

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

SYSTEM_PROMPT = """你是供应商发票字段提取助手。
用户会给你一段发票的 Markdown 内容。
请只输出 JSON，不要任何解释、不要 markdown 代码块。

JSON schema:
{
  "supplier_name": string | null,
  "invoice_number": string | null,
  "invoice_date": "YYYY-MM-DD" | null,
  "currency": string | null,
  "subtotal": number | null,
  "tax_amount": number | null,
  "total_amount": number | null,
  "lines": [
    {
      "description": string,
      "quantity": number | null,
      "unit_price": number | null,
      "amount": number | null
    }
  ]
}

无法确定的字段用 null。
"""


def extract(md_text: str):
    t0 = time.time()
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": md_text},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    dt = time.time() - t0
    usage = resp.usage
    return {
        "latency_sec": round(dt, 2),
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "content": resp.choices[0].message.content,
    }


def main():
    mds = sorted(MD_DIR.glob("*.md"))
    with StepRecorder("ds_markdown",
                      meta={"model": MODEL, "md_count": len(mds)}) as rec:
        rec.extra["requests"] = []
        for md in mds:
            md_text = md.read_text(encoding="utf-8")
            print(f"\n===== {md.name} =====")

            request_record = {
                "markdown": md.name,
                "started_at": None,
                "finished_at": None,
            }

            try:
                result = extract(md_text)
            except Exception as e:
                print(f"FAILED: {e}")
                request_record["status"] = "error"
                request_record["error"] = str(e)
                rec.extra["requests"].append(request_record)

                (OUT / f"{md.stem}.error.json").write_text(
                    json.dumps({"error": str(e)},
                               ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                continue

            request_record.update({
                "status": "ok",
                "latency_sec": result["latency_sec"],
                "prompt_tokens": result["prompt_tokens"],
                "completion_tokens": result["completion_tokens"],
            })
            rec.extra["requests"].append(request_record)

            print(f"延迟: {result['latency_sec']}s  "
                  f"prompt_tokens={result['prompt_tokens']}  "
                  f"completion_tokens={result['completion_tokens']}")

            try:
                parsed = json.loads(result["content"])
                print(json.dumps(parsed, ensure_ascii=False, indent=2))
            except Exception:
                print("(响应不是合法 JSON，原样打印)")
                print(result["content"])

            target = OUT / f"{md.stem}.result.json"
            target.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()