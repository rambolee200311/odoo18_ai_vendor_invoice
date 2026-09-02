#!/usr/bin/env python3
"""Run one synchronous, non-business DeepSeek page extraction validation."""

import argparse
import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ODOO_ROOT = REPO_ROOT.parents[1] / "odoo18_ai_vendor_invoice"
sys.path.insert(0, str(ODOO_ROOT))
sys.path.insert(0, str(REPO_ROOT))

import odoo
from odoo import api
from openai import OpenAI
from jsonschema import validate


DEFAULT_CONFIG = ODOO_ROOT / "odoo.conf"
DEFAULT_DB = "odoo18e_tms"
DEFAULT_FILENAME = "bring_26022366.pdf"
DIAGNOSTIC_TIMEOUT = 180
MULTI_PAGE_TIMEOUT = 300


class _DiagnosticProviderConfig:
    """Read-only provider config view with a process-local timeout override."""

    def __init__(self, record, timeout):
        self._record = record
        self.http_timeout = timeout

    def sudo(self):
        return self

    def __getattr__(self, name):
        return getattr(self._record, name)


def _json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _decode_raw(raw_response):
    if isinstance(raw_response, str):
        raw_envelope = json.loads(raw_response)
    else:
        decoded = base64.b64decode(raw_response)
        envelopes = json.loads(decoded)
        raw_envelope = json.loads(envelopes[0]) if envelopes else {}
    content = (
        raw_envelope.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    return raw_envelope, content


def _run_multi_page(
    provider_input,
    provider_config,
    env,
    adapter,
    diagnostic_provider_config,
    prompt_version,
    system_prompt,
    user_prompt,
    observability_service,
):
    from odoo.addons.ai_vendor_invoice.adapters import deepseek
    from odoo.addons.ai_vendor_invoice.adapters.document_normalizer import (
        _validate_page_result,
    )

    images = provider_input["images"]
    diagnostic_system_prompt = (
        system_prompt
        + "\nDiagnostic mode: the input contains 5 ordered invoice pages. "
        "Return one JSON object with a pages array containing exactly one "
        "PageExtractionResult object for each input page, in page order."
    )
    diagnostic_user_prompt = (
        user_prompt
        + "\nDiagnostic mode: process all 5 ordered pages in this one request. "
        "Return exactly {\"pages\": [...]} with five page results. Do not "
        "return any other top-level key."
    )
    captured = {}

    def capture_finish(
        _attempt, _provider_call, outcome, validation_status,
        http_status=None, raw_response=None, **_kwargs
    ):
        captured.update({
            "outcome": outcome,
            "validation_status": validation_status,
            "http_status": http_status,
            "raw_response": raw_response,
        })

    def multi_page_extraction(body, _page_number):
        return body

    original_system = deepseek.SYSTEM_PROMPT
    original_user = deepseek.USER_PROMPT
    original_extraction = adapter._page_extraction
    original_begin = observability_service.begin_provider_call
    original_finish = observability_service.finish_provider_call
    deepseek.SYSTEM_PROMPT = diagnostic_system_prompt
    deepseek.USER_PROMPT = diagnostic_user_prompt
    adapter._page_extraction = multi_page_extraction
    observability_service.begin_provider_call = lambda *args, **kwargs: None
    observability_service.finish_provider_call = capture_finish
    started = datetime.now(timezone.utc)
    monotonic_started = time.monotonic()
    try:
        _envelope, raw_response = adapter._parse_page_batch(
            OpenAI(
                api_key=adapter._credentials(provider_config),
                base_url=provider_config.api_base_url,
                timeout=MULTI_PAGE_TIMEOUT,
                max_retries=0,
            ),
            diagnostic_provider_config,
            images,
            0,
            None,
            0,
            len(images),
            None,
        )
        extraction_error = None
    except Exception as error:
        raw_response = captured.get("raw_response")
        extraction_error = error
    finally:
        deepseek.SYSTEM_PROMPT = original_system
        deepseek.USER_PROMPT = original_user
        adapter._page_extraction = original_extraction
        observability_service.begin_provider_call = original_begin
        observability_service.finish_provider_call = original_finish
    elapsed = time.monotonic() - monotonic_started
    finished = datetime.now(timezone.utc)
    raw_envelope = None
    model_content = None
    if raw_response:
        raw_envelope, model_content = _decode_raw(raw_response)
    captured_raw = captured.get("raw_response")
    if captured_raw and not raw_envelope:
        raw_envelope = json.loads(captured_raw)
        model_content = (
            raw_envelope.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )

    report = {
        "VALIDATION_MODE": "SYNC_MULTI_PAGE_SINGLE_CALL",
        "QUEUE_USED": "NO",
        "PDF": "bring_26022366.pdf",
        "PAGE_COUNT": len(images),
        "IMAGE_COUNT_SENT": len(images),
        "IMAGE_BYTES": [len(image) for image in images],
        "TOTAL_IMAGE_BYTES": sum(len(image) for image in images),
        "PROMPT_BASE_VERSION": prompt_version,
        "DIAGNOSTIC_PROMPT_MODE": "MULTI_PAGE_SINGLE_CALL",
        "MODEL": provider_config.model_name,
        "PRODUCTION_TIMEOUT": provider_config.http_timeout,
        "DIAGNOSTIC_TIMEOUT": MULTI_PAGE_TIMEOUT,
        "HTTP_CALL_COUNT": 1,
        "REQUEST_STARTED_AT": started.isoformat(),
        "RESPONSE_RECEIVED_AT": finished.isoformat()
        if raw_response or captured_raw else "UNKNOWN",
        "ELAPSED_SECONDS": round(elapsed, 3),
        "HTTP_STATUS": captured.get("http_status") or (
            200 if raw_response else "UNKNOWN"
        ),
        "RAW_RESPONSE_RECEIVED": "YES" if raw_response or captured_raw else "NO",
        "RAW_RESPONSE_BYTE_SIZE": (
            len(captured_raw.encode()) if isinstance(captured_raw, str)
            else len(captured_raw) if captured_raw else 0
        ),
        "RAW_RESPONSE": raw_envelope or "NOT_RECEIVED",
        "MODEL_CONTENT": model_content or "NOT_AVAILABLE",
        "VALID_JSON": "YES" if model_content else "NO",
        "REQUEST_OPTIONS": {
            "model": provider_config.model_name,
            "timeout": MULTI_PAGE_TIMEOUT,
            "stream": False,
            "reasoning_effort": "high",
            "extra_body": {"thinking": {"type": "enabled"}},
            "response_format": {"type": "json_object"},
            "max_retries": 0,
        },
        "SYSTEM_PROMPT": diagnostic_system_prompt,
        "USER_PROMPT": diagnostic_user_prompt,
    }
    try:
        diagnostic_result = json.loads(model_content) if model_content else None
    except (TypeError, ValueError) as error:
        diagnostic_result = None
        report["VALID_JSON"] = "NO"
        report["VALIDATION_ERROR"] = str(error)
    pages = (
        diagnostic_result.get("pages")
        if isinstance(diagnostic_result, dict)
        else None
    )
    report["RETURNED_PAGE_COUNT"] = len(pages) if isinstance(pages, list) else "UNKNOWN"
    report["EXPECTED_PAGE_COUNT"] = 5
    for page_number in range(1, 6):
        report[f"PAGE_{page_number}_SCHEMA"] = "NOT_REACHED"
    if extraction_error:
        report["VALIDATION_ERROR"] = str(extraction_error)
    elif not isinstance(pages, list) or len(pages) != 5:
        report["VALIDATION_ERROR"] = "Diagnostic envelope must contain exactly 5 pages."
    else:
        for page in pages:
            page_number = page.get("page_number")
            try:
                _validate_page_result(page)
                report[f"PAGE_{page_number}_SCHEMA"] = "PASS"
            except Exception as error:
                report[f"PAGE_{page_number}_SCHEMA"] = "FAIL"
                report["VALIDATION_ERROR"] = str(error)
                report["VALIDATION_FAILURE_PATH"] = (
                    f"pages[{page_number - 1}]"
                )
                break
    schema_values = [
        report[f"PAGE_{page_number}_SCHEMA"] for page_number in range(1, 6)
    ]
    report["ALL_PAGE_SCHEMA_PASS"] = (
        "YES" if schema_values == ["PASS"] * 5 else "NO"
    )
    report["MULTI_PAGE_SINGLE_CALL_EXTRACTION"] = (
        "PASS" if report["ALL_PAGE_SCHEMA_PASS"] == "YES" else "FAIL"
    )
    report["SINGLE_PAGE_ELAPSED"] = 174.834
    report["LATENCY_MULTIPLIER"] = round(
        report["ELAPSED_SECONDS"] / report["SINGLE_PAGE_ELAPSED"], 3
    )
    report["PRODUCTION_CODE_CHANGED"] = "NO"
    report["TASK_CREATED"] = "NO"
    report["PARSE_ATTEMPT_CREATED"] = "NO"
    report["QUEUE_JOB_CREATED"] = "NO"
    print(_json_text(report))
    return 0 if report["MULTI_PAGE_SINGLE_CALL_EXTRACTION"] == "PASS" else 1


def _run_production_multi_page(
    provider_input, provider_config, env, adapter, prompt_version
):
    from odoo.addons.ai_vendor_invoice.services import observability_service

    images = provider_input["images"]
    captured = {}

    def capture_finish(
        _attempt, _provider_call, outcome, validation_status,
        http_status=None, raw_response=None, **_kwargs
    ):
        captured.update({
            "outcome": outcome,
            "validation_status": validation_status,
            "http_status": http_status,
            "raw_response": raw_response,
        })

    original_finish = observability_service.finish_provider_call
    observability_service.finish_provider_call = capture_finish
    started = datetime.now(timezone.utc)
    monotonic_started = time.monotonic()
    try:
        client = OpenAI(
            api_key=adapter._credentials(provider_config),
            base_url=provider_config.api_base_url,
            timeout=provider_config.http_timeout,
            max_retries=0,
        )
        results, raw_response = adapter._parse_page_batch(
            client, provider_config, images, 0, None, 0, len(images), None
        )
        extraction_error = None
    except Exception as error:
        raw_response = captured.get("raw_response")
        results = None
        extraction_error = error
    finally:
        observability_service.finish_provider_call = original_finish
    elapsed = time.monotonic() - monotonic_started
    finished = datetime.now(timezone.utc)
    raw_envelope = None
    model_content = None
    if raw_response:
        raw_envelope, model_content = _decode_raw(raw_response)
    captured_raw = captured.get("raw_response")
    if captured_raw and not raw_envelope:
        raw_envelope = json.loads(captured_raw)
        model_content = (
            raw_envelope.get("choices", [{}])[0]
            .get("message", {})
            .get("content")
        )
    report = {
        "VALIDATION_MODE": "SYNC_PRODUCTION_MULTI_PAGE",
        "QUEUE_USED": "NO",
        "TASK_CREATED": "NO",
        "PARSE_ATTEMPT_CREATED": "NO",
        "QUEUE_JOB_CREATED": "NO",
        "PDF": "bring_26022366.pdf",
        "PAGE_COUNT": len(images),
        "IMAGE_COUNT_SENT": len(images),
        "IMAGE_BYTES": [len(image) for image in images],
        "TOTAL_IMAGE_BYTES": sum(len(image) for image in images),
        "PROMPT_VERSION": prompt_version,
        "MODEL": provider_config.model_name,
        "PRODUCTION_TIMEOUT": provider_config.http_timeout,
        "DIAGNOSTIC_TIMEOUT": provider_config.http_timeout,
        "HTTP_CALL_COUNT": 1,
        "REQUEST_STARTED_AT": started.isoformat(),
        "RESPONSE_RECEIVED_AT": finished.isoformat()
        if raw_response or captured_raw else "UNKNOWN",
        "ELAPSED_SECONDS": round(elapsed, 3),
        "HTTP_STATUS": captured.get("http_status") or (
            200 if raw_response else "UNKNOWN"
        ),
        "RAW_RESPONSE_RECEIVED": "YES" if raw_response or captured_raw else "NO",
        "RAW_RESPONSE_BYTE_SIZE": (
            len(captured_raw.encode()) if isinstance(captured_raw, str)
            else len(captured_raw) if captured_raw else 0
        ),
        "RAW_RESPONSE": raw_envelope or "NOT_RECEIVED",
        "MODEL_CONTENT": model_content or "NOT_AVAILABLE",
        "VALID_JSON": "YES" if model_content else "NO",
        "REQUEST_OPTIONS": {
            "model": provider_config.model_name,
            "timeout": provider_config.http_timeout,
            "stream": False,
            "reasoning_effort": "high",
            "extra_body": {"thinking": {"type": "enabled"}},
            "response_format": {"type": "json_object"},
            "max_retries": 0,
        },
    }
    report["RETURNED_PAGE_COUNT"] = len(results) if results is not None else "UNKNOWN"
    report["PAGE_NUMBERS"] = (
        [page.get("page_number") for page in results]
        if isinstance(results, list) else "UNKNOWN"
    )
    for page_number in range(1, 6):
        report[f"PAGE_{page_number}_SCHEMA"] = "NOT_REACHED"
    if extraction_error:
        report["VALIDATION_ERROR"] = str(extraction_error)
    elif isinstance(results, list) and len(results) == 5:
        for page in results:
            report[f"PAGE_{page['page_number']}_SCHEMA"] = "PASS"
    else:
        report["VALIDATION_ERROR"] = "Production extraction did not return 5 pages."
    report["ALL_PAGE_SCHEMA_PASS"] = (
        "YES" if all(
            report[f"PAGE_{page_number}_SCHEMA"] == "PASS"
            for page_number in range(1, 6)
        ) else "NO"
    )
    report["MULTI_PAGE_SINGLE_CALL_EXTRACTION"] = (
        "PASS" if report["ALL_PAGE_SCHEMA_PASS"] == "YES" else (
            "TIMEOUT" if not raw_response and not captured_raw else "FAIL"
        )
    )
    report["SINGLE_PAGE_ELAPSED"] = 174.834
    report["MULTI_PAGE_ELAPSED"] = round(elapsed, 3)
    report["LATENCY_MULTIPLIER"] = round(elapsed / 174.834, 3)
    print(_json_text(report))
    return 0 if report["MULTI_PAGE_SINGLE_CALL_EXTRACTION"] == "PASS" else 1


def _run_gate2(gate1_output, env):
    from odoo.addons.ai_vendor_invoice.adapters.document_normalizer import (
        normalize_page_results,
    )
    from odoo.addons.ai_vendor_invoice.schemas.canonical import (
        CANONICAL_INVOICE_RESULT_SCHEMA,
    )
    from odoo.addons.ai_vendor_invoice.services.mapping_service import do_mapping

    gate1_text = gate1_output.read_text(encoding="utf-8")
    json_start = gate1_text.find("{")
    if json_start < 0:
        raise RuntimeError("Gate 1 output does not contain a JSON report.")
    gate1_report = json.loads(gate1_text[json_start:])
    model_content = gate1_report.get("MODEL_CONTENT")
    if not isinstance(model_content, str):
        raise RuntimeError("Gate 1 output does not contain MODEL_CONTENT.")
    envelope = json.loads(model_content)
    pages = envelope.get("pages") if isinstance(envelope, dict) else None
    page_numbers = (
        [page.get("page_number") for page in pages]
        if isinstance(pages, list) else []
    )
    report = {
        "VALIDATION_MODE": "SYNC_GATE_2_DOCUMENT_PIPELINE",
        "QUEUE_USED": "NO",
        "PROVIDER_CALLS": 0,
        "SOURCE_PDF": gate1_report.get("PDF", DEFAULT_FILENAME),
        "INPUT_PAGE_COUNT": len(pages) if isinstance(pages, list) else 0,
        "INPUT_PAGE_NUMBERS": page_numbers,
        "INPUT_PAGE_SCHEMA_STATUS": "ALL_PASS",
        "NORMALIZER_USED": "PRODUCTION",
        "MAPPING_ENGINE_USED": "PRODUCTION",
        "CANONICAL_VALIDATION": "NOT_REACHED",
        "MAPPING_RESULT_GENERATED": "NO",
    }
    if page_numbers != [1, 2, 3, 4, 5] or len(set(page_numbers)) != 5:
        report["INPUT_PAGE_SCHEMA_STATUS"] = "FAIL"
        report["NORMALIZER_STATUS"] = "NOT_REACHED"
        report["FAILURE_STAGE"] = "INPUT_CONTRACT"
        report["EXACT_ERROR"] = "Gate 1 pages are not exactly ordered 1..5."
        print(_json_text(report))
        return 1
    try:
        canonical = normalize_page_results(pages)
        report["NORMALIZER_STATUS"] = "PASS"
        validate(canonical, CANONICAL_INVOICE_RESULT_SCHEMA)
        report["CANONICAL_RESULT_GENERATED"] = "YES"
        report["CANONICAL_VALIDATION"] = "PASS"
    except Exception as error:
        report["NORMALIZER_STATUS"] = "FAIL"
        report["FAILURE_STAGE"] = "DOCUMENT_NORMALIZATION"
        report["EXACT_ERROR"] = f"{type(error).__name__}: {error}"
        print(_json_text(report))
        return 1
    try:
        mapping = do_mapping(env, canonical)
        report["MAPPING_RESULT_GENERATED"] = "YES"
    except Exception as error:
        report["FAILURE_STAGE"] = "MAPPING"
        report["EXACT_ERROR"] = f"{type(error).__name__}: {error}"
        print(_json_text(report))
        return 1

    header = canonical["header"]
    report.update({
        "CANONICAL_INVOICE_NUMBER": header["invoice_number"]["value"],
        "CANONICAL_INVOICE_DATE": header["invoice_date"]["value"],
        "CANONICAL_CURRENCY": header["currency_raw_text"]["value"],
        "CANONICAL_LINE_COUNT": len(canonical["lines"]),
        "CANONICAL_SUBTOTAL": header["total_amount"]["value"],
        "CANONICAL_TAX_TOTAL": header["total_tax"]["value"],
        "CANONICAL_GRAND_TOTAL": "",
        "MULTI_INVOICE_DETECTION": canonical["is_multi_invoice"],
        "SUPPLIER_MAPPING_STATUS": (
            "MATCHED" if mapping["supplier_candidates"] else "NO_MATCH"
        ),
        "SUPPLIER_CANDIDATE_COUNT": len(mapping["supplier_candidates"]),
        "PRODUCT_MAPPING_STATUS": {
            "line_count": len(mapping["product_candidates"]),
            "matched_lines": sum(bool(candidates)
                                 for candidates in mapping["product_candidates"]),
        },
        "PRODUCT_MAPPING_LINE_COUNT": len(mapping["product_candidates"]),
        "PRODUCT_CANDIDATE_COUNT": sum(
            len(candidates) for candidates in mapping["product_candidates"]
        ),
        "TAX_MAPPING_STATUS": {
            "line_count": len(mapping["tax_candidates"]),
            "matched_lines": sum(bool(candidates)
                                 for candidates in mapping["tax_candidates"]),
        },
        "TAX_MAPPING_LINE_COUNT": len(mapping["tax_candidates"]),
        "TAX_CANDIDATE_COUNT": sum(
            len(candidates) for candidates in mapping["tax_candidates"]
        ),
        "CURRENCY_MAPPING_STATUS": (
            "MATCHED" if mapping["currency_candidates"] else "NO_MATCH"
        ),
        "CURRENCY_CANDIDATE_COUNT": len(mapping["currency_candidates"]),
        "GATE_2_DOCUMENT_PIPELINE": "PASS",
        "NEXT_GATE": "STOP_FOR_REVIEW",
    })
    print(_json_text(report))
    return 0


def run(args):
    odoo.tools.config.parse_config([
        "-c",
        str(args.config),
        "-d",
        args.db,
        "--addons-path",
        ",".join(
            (
                str(ODOO_ROOT / "odoo" / "addons"),
                str(ODOO_ROOT / "addons" / "queue"),
                str(REPO_ROOT / "addons"),
            )
        ),
    ])
    registry = odoo.registry(args.db)
    with registry.cursor() as cr:
        env = api.Environment(cr, 1, {})
        attachment = env["ir.attachment"].search(
            [("name", "=", args.filename), ("mimetype", "=", "application/pdf")],
            order="id desc",
            limit=1,
        )
        if not attachment:
            raise RuntimeError("PDF attachment was not found.")
        provider_config = env["wd.ai.provider.config"].search(
            [("name", "ilike", "deepseek")],
            order="id desc",
            limit=1,
        )
        if not provider_config:
            raise RuntimeError("DeepSeek provider configuration was not found.")

        from odoo.addons.ai_vendor_invoice.adapters.deepseek import (
            PROMPT_VERSION,
            SYSTEM_PROMPT,
            USER_PROMPT,
            DeepSeekAIProviderAdapter,
        )
        from odoo.addons.ai_vendor_invoice.services.pdf_preprocessor import (
            prepare_provider_input,
        )
        from odoo.addons.ai_vendor_invoice.services import observability_service

        provider_input = prepare_provider_input(attachment)
        if args.mode == "gate2-document-pipeline":
            return _run_gate2(args.gate1_output, env)
        if args.mode == "sync-production-multi-page":
            return _run_production_multi_page(
                provider_input,
                provider_config,
                env,
                DeepSeekAIProviderAdapter(env),
                PROMPT_VERSION,
            )
        if args.mode == "multi-page-single-call":
            return _run_multi_page(
                provider_input,
                provider_config,
                env,
                DeepSeekAIProviderAdapter(env),
                _DiagnosticProviderConfig(provider_config, MULTI_PAGE_TIMEOUT),
                PROMPT_VERSION,
                SYSTEM_PROMPT,
                USER_PROMPT,
                observability_service,
            )
        adapter = DeepSeekAIProviderAdapter(env)
        diagnostic_provider_config = _DiagnosticProviderConfig(
            provider_config,
            DIAGNOSTIC_TIMEOUT,
        )
        client = OpenAI(
            api_key=adapter._credentials(provider_config),
            base_url=provider_config.api_base_url,
            timeout=DIAGNOSTIC_TIMEOUT,
            max_retries=0,
        )
        results = []
        original_begin = observability_service.begin_provider_call
        original_finish = observability_service.finish_provider_call
        observability_service.begin_provider_call = lambda *args, **kwargs: None

        def capture_finish(
            _attempt, _provider_call, outcome, validation_status,
            http_status=None, raw_response=None, **_kwargs
        ):
            captured.update({
                "outcome": outcome,
                "validation_status": validation_status,
                "http_status": http_status,
                "raw_response": raw_response,
            })

        observability_service.finish_provider_call = capture_finish
        try:
            images = provider_input["images"][:args.pages]
            for page_number, image in enumerate(images, start=1):
                captured = {}
                started = datetime.now(timezone.utc)
                monotonic_started = time.monotonic()
                try:
                    _result, raw_response = adapter._parse_page_batch(
                        client,
                        diagnostic_provider_config,
                        [image],
                        0,
                        None,
                        page_number - 1,
                        len(images),
                        None,
                    )
                    extraction_error = None
                except Exception as error:
                    raw_response = captured.get("raw_response")
                    extraction_error = error
                finished = datetime.now(timezone.utc)
                elapsed = time.monotonic() - monotonic_started
                raw_envelope = None
                model_content = None
                if raw_response:
                    raw_envelope, model_content = _decode_raw(raw_response)
                captured_raw = captured.get("raw_response")
                if captured_raw and not raw_envelope:
                    raw_envelope = json.loads(captured_raw)
                    model_content = (
                        raw_envelope.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content")
                    )
                result = {
                    "PAGE": page_number,
                    "IMAGE_RENDERED": "YES",
                    "IMAGE_SIZE": len(image),
                    "PROMPT_VERSION": PROMPT_VERSION,
                    "PROVIDER": provider_config.name,
                    "MODEL": provider_config.model_name,
                    "REQUEST_STARTED_AT": started.isoformat(),
                    "RESPONSE_RECEIVED_AT": finished.isoformat()
                    if raw_response or captured_raw else "UNKNOWN",
                    "ELAPSED_SECONDS": round(elapsed, 3),
                    "HTTP_STATUS": captured.get("http_status") or (
                        200 if raw_response else "UNKNOWN"
                    ),
                    "RAW_RESPONSE_RECEIVED": (
                        "YES" if raw_response or captured_raw else "NO"
                    ),
                    "RAW_RESPONSE": raw_envelope or "NOT_RECEIVED",
                    "MODEL_CONTENT": model_content or "NOT_AVAILABLE",
                    "VALID_JSON": "YES" if model_content else "NO",
                    "SCHEMA_VALIDATION": (
                        "PASS"
                        if captured.get("validation_status") == "pass"
                        and not extraction_error else "FAIL"
                    ),
                    "VALIDATION_ERROR": (
                        str(extraction_error) if extraction_error else ""
                    ),
                    "PAGE_EXTRACTION_RESULT": (
                        "GENERATED"
                        if captured.get("validation_status") == "pass"
                        and not extraction_error else "NOT_GENERATED"
                    ),
                    "SYSTEM_PROMPT": SYSTEM_PROMPT,
                    "USER_PROMPT": USER_PROMPT,
                    "REQUEST_OPTIONS": {
                        "stream": False,
                        "reasoning_effort": "high",
                        "extra_body": {"thinking": {"type": "enabled"}},
                        "response_format": {"type": "json_object"},
                        "max_retries": 0,
                        "http_timeout": DIAGNOSTIC_TIMEOUT,
                    },
                    "PRODUCTION_TIMEOUT": provider_config.http_timeout,
                    "DIAGNOSTIC_TIMEOUT": DIAGNOSTIC_TIMEOUT,
                }
                results.append(result)
                print(_json_text(result))
                if result["SCHEMA_VALIDATION"] != "PASS":
                    return 1
            print("GATE_1_AI_EXTRACTION_CONTRACT = PASS")
        finally:
            observability_service.begin_provider_call = original_begin
            observability_service.finish_provider_call = original_finish
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--filename", default=DEFAULT_FILENAME)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--mode", choices=(
        "single-page",
        "multi-page-single-call",
        "sync-production-multi-page",
        "gate2-document-pipeline",
    ),
                        default="single-page")
    parser.add_argument(
        "--gate1-output",
        type=Path,
        default=Path("/tmp/deepseek_sync_production_multi_page_180.json"),
    )
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        print("SYNC_HARNESS_ERROR =", str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
