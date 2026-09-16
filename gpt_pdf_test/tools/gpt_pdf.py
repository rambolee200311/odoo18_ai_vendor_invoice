import argparse
import ast
import copy
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from jsonschema import validate
from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
REPO_SCHEMA = ROOT / "addons" / "ai_vendor_invoice" / "schemas" / "document_extraction.py"
REPO_PROMPTS = ROOT / "addons" / "ai_vendor_invoice" / "adapters" / "prompts.py"
TEST_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = TEST_ROOT / "output"


def _load_literal_assignment(path, assignment_name):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == assignment_name:
                    return ast.literal_eval(node.value)
    raise RuntimeError(f"Missing assignment {assignment_name} in {path}")


def production_schema():
    return _load_literal_assignment(
        REPO_SCHEMA,
        "INVOICE_EXTRACTION_RESULT_SCHEMA",
    )


def production_prompt():
    return _load_literal_assignment(REPO_PROMPTS, "NATIVE_PDF_PROMPT")


def schema_diagnostics(schema):
    line_schema = schema["properties"]["lines"]["items"]
    properties = set(line_schema["properties"])
    required = set(line_schema["required"])
    return {
        "line_properties": sorted(properties),
        "line_required": sorted(required),
        "missing_required": sorted(properties - required),
        "extra_required": sorted(required - properties),
    }


def run(pdf_path, repair_schema=False):
    load_dotenv(TEST_ROOT / ".env")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing OPENAI_API_KEY; set it in gpt_pdf_test/.env or the environment."
        )
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
    schema = production_schema()
    if repair_schema:
        schema = copy.deepcopy(schema)
        line_schema = schema["properties"]["lines"]["items"]
        line_schema["required"] = sorted(line_schema["properties"])
    prompt = production_prompt()
    diagnostics = schema_diagnostics(schema)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {
        "pdf": str(pdf_path),
        "model": model,
        "base_url": base_url,
        "repair_schema": repair_schema,
        "schema_diagnostics": diagnostics,
        "status": "not_started",
    }
    started = time.monotonic()

    client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)
    try:
        with pdf_path.open("rb") as source:
            uploaded = client.files.create(
                file=("source.pdf", source, "application/pdf"),
                purpose="user_data",
            )
        report["uploaded_file_id"] = uploaded.id
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": uploaded.id},
                    {"type": "input_text", "text": prompt},
                ],
            }],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "InvoiceExtractionResult",
                    "strict": True,
                    "schema": schema,
                },
            },
            stream=False,
        )
        parsed = json.loads(response.output_text)
        validate(parsed, schema)
        report.update({
            "status": "success",
            "response_id": response.id,
            "line_count": len(parsed["lines"]),
        })
        print(f"SUCCESS model={model} lines={len(parsed['lines'])}")
    except Exception as error:
        report.update({
            "status": "error",
            "exception_class": type(error).__name__,
            "error": " ".join(str(error).split())[:1000],
        })
        print(f"FAILED {type(error).__name__}: {report['error']}")
    finally:
        report["elapsed_sec"] = round(time.monotonic() - started, 2)
        (OUTPUT / "last_run.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print("Schema diagnostics:")
        print(json.dumps(diagnostics, ensure_ascii=False, indent=2))
        print(f"Report: {OUTPUT / 'last_run.json'}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--repair-schema",
        action="store_true",
        help="临时将行级 schema 的全部 properties 加入 required，仅用于验证 Provider",
    )
    args = parser.parse_args()
    run(args.pdf, repair_schema=args.repair_schema)


if __name__ == "__main__":
    main()
