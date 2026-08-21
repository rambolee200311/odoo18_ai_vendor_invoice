# © 2024 Wukong Digital. License LGPL-3.
"""Regression tests for FIX-INTENT-AI-VENDOR-001."""

from datetime import date
from decimal import Decimal
from io import BytesIO
import base64
import inspect
from unittest.mock import patch

from PyPDF2 import PdfWriter
from reportlab.pdfgen import canvas
from odoo.tests.common import TransactionCase

from ..adapters.base import AIProviderPermanentError, BaseAIProviderAdapter
from ..adapters.deepseek import DeepSeekAIProviderAdapter
from ..models.import_parse_attempt import VendorInvoiceImportParseAttempt
from ..services import parse_service, pdf_preprocessor


def _canonical_result():
    field = {"value": None, "confidence": 0.0}
    return {
        "header": {
            "invoice_number": {"value": " INV-001 ", "confidence": 0.8},
            "invoice_date": {"value": date(2026, 8, 21), "confidence": 0.8},
            "supplier_raw_text": {"value": " Supplier ", "confidence": 0.8},
            "currency_raw_text": {"value": " EUR ", "confidence": 0.8},
            "total_amount": {"value": Decimal("10.00"), "confidence": 0.8},
            "total_tax": field,
        },
        "lines": [],
        "is_multi_invoice": False,
    }


class FixIntentBase(TransactionCase):
    def _base_task(self, state="awaiting_review"):
        attachment = self.env["ir.attachment"].create({
            "name": "fix-intent.pdf",
            "datas": b"",
            "res_model": "vendor.invoice.import.task",
        })
        provider = self.env["wd.ai.provider.config"].create({
            "name": "DeepSeek Fix Intent",
            "api_base_url": "https://example.invalid",
            "model_name": "test",
            "max_internal_retry": 3,
        })
        task = self.env["vendor.invoice.import.task"].create({
            "source_pdf_attachment_id": attachment.id,
            "selected_provider_config_id": provider.id,
            "state": state,
        })
        return task, provider


class TestFixIntentParse(FixIntentBase):
    def test_rerun_preserves_human_review_result(self):
        task, provider = self._base_task()
        original = {
            "header": {
                "supplier_id": 7,
                "invoice_number": "INV-001",
                "invoice_date": "2026-08-21",
                "currency_id": 1,
                "total_amount": "10.00",
            },
            "lines": [],
        }
        task.write({
            "human_review_result": original,
            "human_reviewed": True,
        })
        with patch.object(VendorInvoiceImportParseAttempt, "action_enqueue_parse"):
            parse_service.start_parse(self.env, task.id, provider.id)
        self.assertEqual(task.human_review_result, original)
        self.assertFalse(task.human_reviewed)


class TestFixIntentAdapter(TransactionCase):
    def test_adapter_rejects_invalid_canonical_schema(self):
        invalid = _canonical_result()
        invalid["header"].pop("invoice_number")
        with self.assertRaises(AIProviderPermanentError):
            BaseAIProviderAdapter._canonical(invalid)

    def test_adapter_normalizes_valid_canonical_values(self):
        result = BaseAIProviderAdapter._canonical({
            "canonical_result": _canonical_result(),
        })
        self.assertEqual(result["header"]["invoice_number"]["value"], "INV-001")
        self.assertEqual(result["header"]["invoice_date"]["value"], "2026-08-21")
        self.assertEqual(result["header"]["total_amount"]["value"], "10.00")

    def test_adapter_accepts_provider_input_not_attachment(self):
        signature = inspect.signature(DeepSeekAIProviderAdapter.parse_pdf)
        self.assertEqual(list(signature.parameters)[1], "provider_input")


class TestFixIntentPDFPreprocessor(TransactionCase):
    @staticmethod
    def _pdf(page_count):
        output = BytesIO()
        document = canvas.Canvas(output)
        for page_number in range(page_count):
            document.drawString(72, 720, "Page %s" % (page_number + 1))
            document.showPage()
        document.save()
        return output.getvalue()

    def _attachment(self, contents):
        return self.env["ir.attachment"].create({
            "name": "preprocessor.pdf",
            "datas": base64.b64encode(contents),
            "res_model": "vendor.invoice.import.task",
        })

    def test_single_page_pdf_returns_pages_provider_input(self):
        result = pdf_preprocessor.prepare_provider_input(
            self._attachment(self._pdf(1))
        )
        self.assertEqual(result["type"], "pages")
        self.assertEqual(len(result["images"]), 1)
        self.assertTrue(result["images"][0].startswith(b"\x89PNG"))

    def test_multi_page_pdf_preserves_page_order(self):
        result = pdf_preprocessor.prepare_provider_input(
            self._attachment(self._pdf(2))
        )
        self.assertEqual(len(result["images"]), 2)
        self.assertNotEqual(result["images"][0], result["images"][1])

    def test_invalid_and_empty_pdf_are_distinguishable(self):
        with self.assertRaises(pdf_preprocessor.PDFInvalidError):
            pdf_preprocessor.prepare_provider_input(self._attachment(b"not-pdf"))
        with self.assertRaises(pdf_preprocessor.PDFInvalidError):
            pdf_preprocessor.prepare_provider_input(self._attachment(b""))

    def test_encrypted_pdf_is_distinguishable(self):
        output = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("secret")
        writer.write(output)
        with self.assertRaises(pdf_preprocessor.PDFEncryptedError):
            pdf_preprocessor.prepare_provider_input(self._attachment(output.getvalue()))


class TestFixIntentReviewWarnings(FixIntentBase):
    def test_save_review_recomputes_review_warnings(self):
        reviewer = self.env.ref("ai_vendor_invoice.group_reviewer")
        self.env.user.sudo().write({"groups_id": [(4, reviewer.id)]})
        task, _provider = self._base_task()
        task.write({
            "human_reviewed": False,
            "review_warnings": [{"code": "OLD", "message": "old"}],
        })
        review = {
            "header": {"total_amount": "10.00"},
            "lines": [{
                "subtotal": "9.00",
                "tax_amount": "0.00",
                "line_total_amount": "9.00",
            }],
        }
        task.action_save_review(review)
        self.assertTrue(task.human_reviewed)
        self.assertEqual(task.review_warnings[0]["code"], "AMOUNT_MISMATCH")
