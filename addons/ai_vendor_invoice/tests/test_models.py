# © 2024 Wukong Digital. License LGPL-3.
"""
Intent-1 Foundation: model-only tests.
Covers: field definitions, DB constraints, immutability guards, schema
        validation, and lock_service signatures.
"""
import jsonschema
from unittest.mock import patch
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from ..schemas.canonical import CANONICAL_INVOICE_RESULT_SCHEMA
from ..schemas.human_review import HUMAN_REVIEW_RESULT_SCHEMA
from ..schemas.mapping import MAPPING_RESULT_SCHEMA
from ..schemas.warning import REVIEW_WARNINGS_SCHEMA


def _minimal_canonical(is_multi=False):
    """Build a minimal valid CanonicalInvoiceResult fixture."""
    field = {"value": None, "confidence": 0.0}
    return {
        "header": {
            "invoice_number": field,
            "invoice_date": field,
            "supplier_raw_text": field,
            "currency_raw_text": field,
            "total_amount": field,
            "total_tax": field,
        },
        "lines": [],
        "is_multi_invoice": is_multi,
    }


class TestImportTaskModel(TransactionCase):
    """Tests for vendor.invoice.import.task model (no AI services)."""

    def _make_attachment(self):
        return self.env["ir.attachment"].create(
            {
                "name": "test.pdf",
                "datas": b"",
                "res_model": "vendor.invoice.import.task",
            }
        )

    def _make_provider(self):
        return self.env["wd.ai.provider.config"].create(
            {
                "name": "Test Provider",
                "api_base_url": "https://example.com",
                "model_name": "test-model",
            }
        )

    def _make_task(self):
        return self.env["vendor.invoice.import.task"].create(
            {
                "source_pdf_attachment_id": self._make_attachment().id,
                "selected_provider_config_id": self._make_provider().id,
            }
        )

    # ── field & default tests ─────────────────────────────────────────────────

    def test_task_default_state_is_to_parse(self):
        task = self._make_task()
        self.assertEqual(task.state, "to_parse")

    def test_task_name_sequence_generated(self):
        task = self._make_task()
        self.assertTrue(task.name, "Task name should be auto-generated")
        self.assertNotEqual(task.name, "New")

    def test_task_default_company_is_env_company(self):
        task = self._make_task()
        self.assertEqual(task.company_id, self.env.company)

    def test_new_task_requires_statement(self):
        self.assertTrue(self._make_task().statement_required)

    def test_statement_generic_crud_is_not_a_business_entry_point(self):
        task = self._make_task()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": task.selected_provider_config_id.id,
                "status": "success",
            }
        )
        values = {
            "task_id": task.id,
            "source_parse_attempt_id": attempt.id,
            "invoice_number": "INV-001",
        }
        with self.assertRaises(AccessError):
            self.env["vendor.invoice.statement"].create(values)

    def test_statement_first_creation_keeps_attempt_provenance(self):
        admin = self.env.ref("base.user_admin")
        admin.write({
            "groups_id": [(4, self.env.ref("ai_vendor_invoice.group_reviewer").id)]
        })
        task = self._make_task().with_user(admin)
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": task.selected_provider_config_id.id,
                "status": "success",
            }
        )
        task.current_parse_attempt_id = attempt.id
        statement = task.action_create_statement_from_attempt(
            attempt.id,
            {"invoice_number": "INV-001", "lines": [{"description": "Freight", "amount": 10.0}]},
        )
        self.assertEqual(statement.source_parse_attempt_id, attempt)
        self.assertEqual(task.statement_id, statement)

    def test_statement_confirmation_projects_human_review_result(self):
        admin = self.env.ref("base.user_admin")
        admin.write({
            "groups_id": [(4, self.env.ref("ai_vendor_invoice.group_reviewer").id)]
        })
        task = self._make_task().with_user(admin)
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": task.selected_provider_config_id.id,
                "status": "success",
            }
        )
        task.current_parse_attempt_id = attempt.id
        task.action_confirm_statement({
            "header": {
                "supplier_id": self.env.ref("base.res_partner_1").id,
                "invoice_number": "INV-002",
                "invoice_date": "2026-08-25",
                "currency_id": self.env.company.currency_id.id,
                "total_amount": "10.0",
                "total_tax": "0.0",
            },
            "lines": [{
                "description": "Freight",
                "quantity": "1",
                "unit_price": "10.0",
                "subtotal": "10.0",
                "tax_ids": [],
                "line_total_amount": "10.0",
            }],
        })
        self.assertEqual(task.state, "awaiting_review")
        self.assertEqual(task.human_review_result["header"]["invoice_number"], "INV-002")
        self.assertEqual(task.human_review_result["header"]["supplier_id"],
                         self.env.ref("base.res_partner_1").id)

    def test_statement_projection_rejects_inconsistent_result(self):
        admin = self.env.ref("base.user_admin")
        admin.write({
            "groups_id": [(4, self.env.ref("ai_vendor_invoice.group_reviewer").id)]
        })
        task = self._make_task().with_user(admin)
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": task.selected_provider_config_id.id,
                "status": "success",
            }
        )
        task.current_parse_attempt_id = attempt.id
        task.action_confirm_statement({
            "header": {
                "supplier_id": self.env.ref("base.res_partner_1").id,
                "invoice_number": "INV-003",
                "invoice_date": "2026-08-25",
                "currency_id": self.env.company.currency_id.id,
                "total_amount": "10.0",
                "total_tax": "0.0",
            },
            "lines": [],
        })
        from ..services.statement_projection import assert_projection_consistent

        inconsistent = dict(task.human_review_result)
        inconsistent["header"] = dict(inconsistent["header"], invoice_number="OLD")
        with self.assertRaises(ValidationError):
            assert_projection_consistent(task.statement_id, inconsistent)

    # ── T-025: company_id immutability ────────────────────────────────────────

    def test_task_company_id_immutable(self):
        """T-025: writing company_id after creation must raise ValidationError."""
        task = self._make_task()
        with self.assertRaises(ValidationError):
            task.write({"company_id": self.env.company.id})

    # ── JSON field defaults ───────────────────────────────────────────────────

    def test_task_human_review_result_default_is_dict(self):
        task = self._make_task()
        self.assertEqual(task.human_review_result or {}, {})

    def test_task_review_warnings_default_is_list(self):
        task = self._make_task()
        self.assertEqual(task.review_warnings or [], [])

    def test_task_human_reviewed_default_is_false(self):
        task = self._make_task()
        self.assertFalse(task.human_reviewed)

    # ── next sequence helper ──────────────────────────────────────────────────

    def test_next_attempt_sequence_starts_at_one(self):
        task = self._make_task()
        self.assertEqual(task._get_next_attempt_sequence(), 1)

    def test_next_attempt_sequence_increments(self):
        task = self._make_task()
        provider = self._make_provider()
        self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": provider.id,
                "status": "queued",
            }
        )
        self.assertEqual(task._get_next_attempt_sequence(), 2)

    # ── cron stub ─────────────────────────────────────────────────────────────

    def test_cron_check_parsing_timeout_is_callable(self):
        """Cron entry point must be callable without raising in Intent-1."""
        # Should return None (no-op stub)
        result = self.env["vendor.invoice.import.task"].cron_check_parsing_timeout()
        self.assertIsNone(result)


class TestParseAttemptModel(TransactionCase):
    """Tests for vendor.invoice.import.parse.attempt model."""

    def _make_base(self):
        att = self.env["ir.attachment"].create(
            {"name": "test.pdf", "datas": b"", "res_model": "vendor.invoice.import.task"}
        )
        provider = self.env["wd.ai.provider.config"].create(
            {"name": "P", "api_base_url": "https://x.com", "model_name": "m"}
        )
        task = self.env["vendor.invoice.import.task"].create(
            {
                "source_pdf_attachment_id": att.id,
                "selected_provider_config_id": provider.id,
            }
        )
        return task, provider

    # ── creation ──────────────────────────────────────────────────────────────

    def test_attempt_default_status_queued(self):
        task, provider = self._make_base()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {
                "task_id": task.id,
                "sequence": 1,
                "provider_config_id": provider.id,
            }
        )
        self.assertEqual(attempt.status, "queued")

    def test_attempt_default_retry_count_zero(self):
        task, provider = self._make_base()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
        )
        self.assertEqual(attempt.attempt_internal_retry_count, 0)

    def test_attempt_captures_extraction_contract_and_model_snapshot(self):
        task, provider = self._make_base()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
        )
        provider.write({"model_name": "changed-after-attempt"})
        self.assertEqual(attempt.prompt_version, "vision-extraction-v1.1")
        self.assertEqual(
            attempt.extraction_contract_version,
            "transport-invoice-page-v1",
        )
        self.assertEqual(attempt.model_name_snapshot, "m")

    # ── T-018: unique(task_id, sequence) ─────────────────────────────────────

    def test_attempt_task_sequence_unique_constraint(self):
        """T-018: duplicate (task_id, sequence) must be rejected at DB level."""
        from psycopg2 import IntegrityError

        task, provider = self._make_base()
        self.env["vendor.invoice.import.parse.attempt"].create(
            {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
        )
        with self.assertRaises(Exception):  # IntegrityError wrapped by Odoo
            self.env["vendor.invoice.import.parse.attempt"].create(
                {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
            )
            self.env.cr.flush()

    # ── T-024: job_run_parse delegates to the Intent-2 parse service ─────────

    def test_job_run_parse_delegates_to_parse_service(self):
        task, provider = self._make_base()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
        )
        with patch(
            "odoo.addons.ai_vendor_invoice.services.parse_service.run_parse_attempt",
            return_value=True,
        ) as run_parse:
            attempt.job_run_parse()
        run_parse.assert_called_once_with(self.env, task.id, attempt.id)

    # ── cascade delete ────────────────────────────────────────────────────────

    def test_attempt_cascade_deleted_with_task(self):
        task, provider = self._make_base()
        attempt = self.env["vendor.invoice.import.parse.attempt"].create(
            {"task_id": task.id, "sequence": 1, "provider_config_id": provider.id}
        )
        attempt_id = attempt.id
        task.unlink()
        self.assertFalse(
            self.env["vendor.invoice.import.parse.attempt"].browse(attempt_id).exists()
        )


class TestImportLogModel(TransactionCase):
    """Tests for vendor.invoice.import.log model."""

    def _make_task(self):
        att = self.env["ir.attachment"].create(
            {"name": "t.pdf", "datas": b"", "res_model": "vendor.invoice.import.task"}
        )
        provider = self.env["wd.ai.provider.config"].create(
            {"name": "P2", "api_base_url": "https://y.com", "model_name": "m2"}
        )
        return self.env["vendor.invoice.import.task"].create(
            {
                "source_pdf_attachment_id": att.id,
                "selected_provider_config_id": provider.id,
            }
        )

    def test_log_creation_with_required_fields(self):
        task = self._make_task()
        log = self.env["vendor.invoice.import.log"].create(
            {
                "task_id": task.id,
                "action": "ai_parse",
                "user_id": self.env.user.id,
            }
        )
        self.assertTrue(log.id)
        self.assertEqual(log.action, "ai_parse")

    def test_log_cascade_deleted_with_task(self):
        task = self._make_task()
        log = self.env["vendor.invoice.import.log"].create(
            {"task_id": task.id, "action": "ai_parse", "user_id": self.env.user.id}
        )
        log_id = log.id
        task.unlink()
        self.assertFalse(
            self.env["vendor.invoice.import.log"].browse(log_id).exists()
        )


class TestSystemConfig(TransactionCase):
    """Tests for wd.system.config model."""

    def test_get_config_returns_record(self):
        cfg = self.env["wd.system.config"].get_config()
        self.assertTrue(cfg.id)

    def test_task_timeout_is_timedelta(self):
        import datetime

        cfg = self.env["wd.system.config"].get_config()
        self.assertIsInstance(cfg.task_timeout, datetime.timedelta)
        self.assertGreater(cfg.task_timeout.total_seconds(), 0)


class TestLockServiceSignatures(TransactionCase):
    """Verify lock_service AbstractModel exposes the expected methods."""

    def test_lock_service_has_lock_task(self):
        svc = self.env["wd.lock.service"]
        self.assertTrue(hasattr(svc, "lock_task"), "lock_service must have lock_task()")

    def test_lock_service_has_lock_attempt(self):
        svc = self.env["wd.lock.service"]
        self.assertTrue(
            hasattr(svc, "lock_attempt"), "lock_service must have lock_attempt()"
        )


class TestJsonSchemas(TransactionCase):
    """Pure Python schema validation tests – no DB interaction needed."""

    # ── canonical ─────────────────────────────────────────────────────────────

    def test_canonical_valid_minimal(self):
        jsonschema.validate(_minimal_canonical(), CANONICAL_INVOICE_RESULT_SCHEMA)

    def test_canonical_valid_with_lines(self):
        data = _minimal_canonical()
        data["lines"] = [
            {
                "description": {"value": "Service A", "confidence": 0.95},
                "amount": {"value": "100.00", "confidence": 0.9},
                "tax_raw_text": {"value": "13%", "confidence": 0.8},
            }
        ]
        jsonschema.validate(data, CANONICAL_INVOICE_RESULT_SCHEMA)

    def test_canonical_missing_required_field_fails(self):
        data = _minimal_canonical()
        del data["header"]["invoice_number"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, CANONICAL_INVOICE_RESULT_SCHEMA)

    def test_canonical_extra_property_fails(self):
        data = _minimal_canonical()
        data["unexpected_key"] = "oops"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, CANONICAL_INVOICE_RESULT_SCHEMA)

    def test_canonical_confidence_out_of_range_fails(self):
        data = _minimal_canonical()
        data["header"]["invoice_number"]["confidence"] = 1.5
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, CANONICAL_INVOICE_RESULT_SCHEMA)

    def test_canonical_is_multi_invoice_true(self):
        data = _minimal_canonical(is_multi=True)
        jsonschema.validate(data, CANONICAL_INVOICE_RESULT_SCHEMA)

    # ── mapping ───────────────────────────────────────────────────────────────

    def test_mapping_valid_empty(self):
        jsonschema.validate({}, MAPPING_RESULT_SCHEMA)

    def test_mapping_valid_with_candidates(self):
        data = {
            "supplier_candidates": [
                {
                    "partner_id": 1,
                    "name": "ACME",
                    "match_score": 0.9,
                    "match_type": "alias",
                    "matched_rule_id": 5,
                }
            ],
            "product_candidates": [],
            "tax_candidates": [],
            "currency_candidates": [],
        }
        jsonschema.validate(data, MAPPING_RESULT_SCHEMA)

    # ── human review ──────────────────────────────────────────────────────────

    def test_human_review_valid_empty(self):
        jsonschema.validate({}, HUMAN_REVIEW_RESULT_SCHEMA)

    def test_human_review_valid_full(self):
        data = {
            "header": {
                "supplier_id": 10,
                "invoice_number": "INV-001",
                "invoice_date": "2024-01-15",
                "currency_id": 1,
                "total_amount": "1130.00",
                "total_tax": "130.00",
            },
            "lines": [
                {
                    "product_id": 5,
                    "description": "Consulting",
                    "quantity": "1",
                    "unit_price": "1000.00",
                    "subtotal": "1000.00",
                    "tax_ids": [1],
                    "tax_amount": "130.00",
                    "line_total_amount": "1130.00",
                }
            ],
        }
        jsonschema.validate(data, HUMAN_REVIEW_RESULT_SCHEMA)

    # ── warnings ──────────────────────────────────────────────────────────────

    def test_warnings_valid_empty_list(self):
        jsonschema.validate([], REVIEW_WARNINGS_SCHEMA)

    def test_warnings_valid_with_item(self):
        data = [{"code": "AMOUNT_MISMATCH", "message": "Total amount does not match"}]
        jsonschema.validate(data, REVIEW_WARNINGS_SCHEMA)

    def test_warnings_extra_field_fails(self):
        data = [{"code": "X", "message": "Y", "extra": "bad"}]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(data, REVIEW_WARNINGS_SCHEMA)
