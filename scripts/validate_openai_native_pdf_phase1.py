#!/usr/bin/env python3
"""Execute exactly one OpenAI native-PDF diagnostic request."""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ODOO_ROOT = REPO_ROOT.parents[1] / "odoo18_ai_vendor_invoice"
sys.path.insert(0, str(ODOO_ROOT))

import fitz
import odoo
from odoo import api
from openai import APIStatusError


DEFAULT_CONFIG = ODOO_ROOT / "odoo.conf"
DEFAULT_DB = "odoo18e_tms"
DEFAULT_PDF = ODOO_ROOT / "docs" / "carrier_invoice" / "bring_26022366.pdf"

DIAGNOSTIC_INSTRUCTIONS = """Extract the visible invoice facts from every page of the supplied PDF.
Return valid JSON only. Preserve the model's natural document-level structure for this diagnostic;
do not return a pages envelope unless that is the model's natural response. Preserve one
independent transport business record as one invoice line, with its charge components kept
within that record. Do not guess, calculate, merge distinct transport records, or add
explanation outside JSON."""


def _json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def run(args):
    odoo.tools.config.parse_config([
        "-c", str(args.config),
        "-d", args.db,
        "--addons-path", ",".join((
            str(ODOO_ROOT / "odoo" / "addons"),
            str(ODOO_ROOT / "addons" / "queue"),
            str(REPO_ROOT / "addons"),
        )),
    ])
    registry = odoo.registry(args.db)
    with registry.cursor() as cr:
        from odoo.addons.ai_vendor_invoice.adapters.openai import (
            OpenAIAIProviderAdapter,
        )
        from odoo.addons.ai_vendor_invoice.services.provider_input import ProviderInput

        env = api.Environment(cr, 1, {})
        provider = env["wd.ai.provider.config"].browse(args.provider_id).exists()
        if not provider:
            raise RuntimeError("Requested Provider Config was not found.")
        pdf_path = args.pdf.resolve()
        pdf_bytes = pdf_path.read_bytes()
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page_count = document.page_count
        finally:
            document.close()
        provider_input = ProviderInput(
            mode="native_pdf",
            source={
                "source_name": pdf_path.name,
                "page_count": page_count,
                "mime_type": "application/pdf",
                "checksum": hashlib.sha256(pdf_bytes).hexdigest(),
            },
            document_bytes=pdf_bytes,
        )
        adapter = OpenAIAIProviderAdapter(env)
        started_at = datetime.now(timezone.utc)
        monotonic_started = time.monotonic()
        error = None
        body = None
        raw_response = None
        content = None
        http_status = None
        try:
            body, raw_response, content = adapter.parse_native_pdf(
                provider_input,
                provider,
                DIAGNOSTIC_INSTRUCTIONS,
            )
        except Exception as caught:
            error = caught
            http_status = (
                caught.status_code if isinstance(caught, APIStatusError) else None
            )
            if isinstance(caught, APIStatusError) and caught.response is not None:
                raw_response = caught.response.content
        elapsed = round(time.monotonic() - monotonic_started, 3)
        response_received_at = datetime.now(timezone.utc)
        artifact_path = Path("/tmp") / (
            "ai_vendor_invoice_openai_native_pdf_%s.json" % args.provider_id
        )
        if raw_response:
            artifact_path.write_bytes(raw_response)
        parsed_type = type(body).__name__ if body is not None else "NOT_AVAILABLE"
        report = {
            "VALIDATION_MODE": "SYNC_OPENAI_NATIVE_PDF_PHASE_1",
            "PROVIDER_CONFIG_ID": provider.id,
            "PROVIDER_NAME": provider.name,
            "PROVIDER_TYPE": "openai",
            "MODEL": provider.model_name,
            "API_KEY_CONFIGURED": "YES" if provider.sudo().api_key else "NO",
            "QUEUE_USED": "NO",
            "TASK_CREATED": "NO",
            "PARSE_ATTEMPT_CREATED": "NO",
            "SOURCE_PDF": pdf_path.name,
            "PAGE_COUNT": page_count,
            "INPUT_MODE": provider_input["mode"],
            "INPUT_DOCUMENT_TYPE": provider_input["source"]["mime_type"],
            "RENDERED_IMAGE_COUNT": 0,
            "HTTP_CALL_COUNT": 2 if raw_response else "UNKNOWN",
            "REQUEST_STARTED_AT": started_at.isoformat(),
            "RESPONSE_RECEIVED_AT": (
                response_received_at.isoformat() if raw_response else "UNKNOWN"
            ),
            "ELAPSED_SECONDS": elapsed,
            "HTTP_STATUS": http_status or (200 if content else "UNKNOWN"),
            "RAW_RESPONSE_RECEIVED": "YES" if raw_response else "NO",
            "RAW_RESPONSE_BYTE_SIZE": len(raw_response) if raw_response else 0,
            "RAW_RESPONSE_ARTIFACT": str(artifact_path) if raw_response else "NONE",
            "MODEL_CONTENT_RECEIVED": "YES" if content else "NO",
            "MODEL_CONTENT_BYTE_SIZE": len(content.encode()) if content else 0,
            "TOP_LEVEL_JSON_TYPE": parsed_type,
            "TOP_LEVEL_KEYS": (
                sorted(body.keys()) if isinstance(body, dict) else []
            ),
            "VALID_JSON": "YES" if body is not None else "NO",
            "REQUEST_OPTIONS": {
                "model": provider.model_name,
                "reasoning_effort": "low",
                "stream": False,
                "max_retries": 0,
                "input_type": "input_file",
            },
            "OUTPUT_CONTRACT_VALIDATION": "NOT_RUN",
            "CANONICAL_RESULT_GENERATED": "NO",
            "NORMALIZER_RUN": "NO",
            "ERROR": str(error) if error else "NONE",
            "NEXT_STEP": "STOP_FOR_REVIEW",
        }
        print(_json_text(report))
        return 0 if raw_response else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--provider-id", type=int, required=True)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    raise SystemExit(run(parser.parse_args()))
