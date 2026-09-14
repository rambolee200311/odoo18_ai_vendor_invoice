# © 2024 Wukong Digital. License LGPL-3.
"""CC-10 Statement Business Authority Decoupling coverage.

Contract: docs/intents/CC-10-STATEMENT-BUSINESS-AUTHORITY-DECOUPLING.md

Covers the Test Plan (§7) scenarios:
  - Confirm/Unconfirm with a legacy/non-`parsed` Task state.
  - Confirm/Create Bill do not read `Task.state`.
  - Create Bill reads current Statement data only.
  - Task `error`/cancellation does not block an existing Statement.
  - `Task.human_reviewed` is ignored by the new workflow.
  - `Task.vendor_bill_id` is a read-only related compatibility field.
  - `Statement.vendor_bill_id` is the sole Bill authority.
"""

import base64
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase

from ..services import bill_creator


class CC10StatementAuthorityCase(TransactionCase):
    """Shared fixtures for CC-10 Confirm/Unconfirm/Create Bill coverage."""

    def setUp(self):
        super().setUp()
        admin = self.env.ref("base.user_admin")
        admin.write({
            "groups_id": [(4, self.env.ref("ai_vendor_invoice.group_reviewer").id)]
        })
        self.admin = admin
        product = self.env["product.product"].search([], limit=1)
        self.env["wd.system.config"].get_config().write({
            "default_product_id": product.id,
        })
        self.provider = self.env["wd.ai.provider.config"].create({
            "name": "CC10 Provider",
            "api_base_url": "https://example.invalid",
            "model_name": "test",
        })

    def _make_task(self, state="parsed", name="cc10.pdf"):
        attachment = self.env["ir.attachment"].create({
            "name": name,
            "datas": base64.b64encode(("PDF-cc10-%s" % name).encode()),
            "res_model": "vendor.invoice.import.task",
        })
        task = self.env["vendor.invoice.import.task"].create({
            "source_pdf_attachment_id": attachment.id,
            "selected_provider_config_id": self.provider.id,
            "state": state,
        })
        return task.with_user(self.admin)

    def _make_confirmable_statement(self, task, invoice_number):
        """Create a Statement with one checked line, ready for Confirm."""
        attempt = self.env["vendor.invoice.import.parse.attempt"].create({
            "task_id": task.id,
            "sequence": 1,
            "provider_config_id": self.provider.id,
            "status": "success",
        })
        task.current_parse_attempt_id = attempt.id
        tax = self.env["account.tax"].search([], limit=1)
        statement = task.action_create_statement_from_attempt(
            attempt.id,
            {
                "invoice_number": invoice_number,
                "invoice_date": "2026-08-21",
                "supplier_id": self.env.ref("base.res_partner_1").id,
                "currency_id": self.env.company.currency_id.id,
                "lines": [{
                    "description": "Freight",
                    "amount": 10.0,
                    "tax_ids": [tax.id] if tax else [],
                }],
            },
        )
        statement.line_ids.write({"checked": True})
        return statement


class TestStatementConfirmDecoupling(CC10StatementAuthorityCase):
    """§7: Confirm is Statement-facing and ignores Task.state."""

    def test_confirm_passes_with_legacy_task_state(self):
        task = self._make_task(state="awaiting_review")
        statement = self._make_confirmable_statement(task, "CC10-CONFIRM-1")
        statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")
        self.assertEqual(task.state, "awaiting_review")

    def test_confirm_passes_with_bill_generated_legacy_task_state(self):
        task = self._make_task(state="bill_generated")
        statement = self._make_confirmable_statement(task, "CC10-CONFIRM-2")
        statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")

    def test_confirm_does_not_read_task_state_after_cancel(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-CONFIRM-3")
        task.action_cancel_task()
        self.assertEqual(task.state, "cancelled")
        statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")

    def test_confirm_never_routes_through_task_command(self):
        """Confirm from the Statement form must not call the Task command."""
        task = self._make_task(state="awaiting_review")
        statement = self._make_confirmable_statement(task, "CC10-CONFIRM-4")
        with patch.object(
            type(task), "action_confirm_statement",
            side_effect=AssertionError("Confirm must not route through Task"),
        ):
            statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")

    def test_confirm_still_requires_checked_lines(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-CONFIRM-5")
        statement.line_ids.write({"checked": False})
        with self.assertRaises(ValidationError):
            statement.action_confirm_from_statement()


class TestStatementUnconfirmDecoupling(CC10StatementAuthorityCase):
    """§7: Unconfirm is Statement-facing and ignores Task.state."""

    def test_unconfirm_passes_with_legacy_task_state(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-UNCONFIRM-1")
        statement.action_confirm_from_statement()
        # Simulate a Task left in a legacy/non-parsed value after confirmation.
        task.write({"state": "bill_generated"})
        statement.action_unconfirm_from_statement()
        self.assertEqual(statement.state, "draft")

    def test_unconfirm_passes_after_task_cancelled(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-UNCONFIRM-2")
        statement.action_confirm_from_statement()
        task.action_cancel_task()
        self.assertEqual(task.state, "cancelled")
        statement.action_unconfirm_from_statement()
        self.assertEqual(statement.state, "draft")

    def test_unconfirm_never_routes_through_task_command(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-UNCONFIRM-3")
        statement.action_confirm_from_statement()
        with patch.object(
            type(task), "action_unconfirm_statement",
            side_effect=AssertionError("Unconfirm must not route through Task"),
        ):
            statement.action_unconfirm_from_statement()
        self.assertEqual(statement.state, "draft")


class TestCreateBillDecoupling(CC10StatementAuthorityCase):
    """§7: Create Bill is Statement-facing and reads only Statement data."""

    def test_create_bill_passes_with_legacy_task_state(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-BILL-1")
        statement.action_confirm_from_statement()
        task.write({"state": "awaiting_review"})
        bill = statement.action_create_vendor_bill_from_statement()
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(statement.vendor_bill_id, bill)

    def test_create_bill_ignores_stale_task_human_review_result(self):
        """Create Bill must read Statement data only, not Task.human_review_result."""
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-BILL-2")
        statement.action_confirm_from_statement()
        # Corrupt the legacy Task-owned mirror; the Bill Creator must ignore it.
        task.write({"human_review_result": {"header": {}, "lines": []}})
        bill = bill_creator.create_vendor_bill_for_statement(self.env, statement.id)
        self.assertEqual(bill.ref, "CC10-BILL-2")
        self.assertEqual(len(bill.invoice_line_ids), 1)

    def test_create_bill_requires_no_current_link(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-BILL-3")
        statement.action_confirm_from_statement()
        bill_creator.create_vendor_bill_for_statement(self.env, statement.id)
        with self.assertRaises(ValidationError):
            bill_creator.create_vendor_bill_for_statement(self.env, statement.id)

    def test_create_bill_requires_confirmed_statement(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-BILL-4")
        with self.assertRaises(ValidationError):
            bill_creator.create_vendor_bill_for_statement(self.env, statement.id)


class TestTaskFailureIndependence(CC10StatementAuthorityCase):
    """§7: Task error/cancellation does not block an existing Statement."""

    def test_statement_editable_after_task_error(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-ERR-1")
        task.write({"state": "error"})
        statement.write({"note": "Edited after Task error."})
        self.assertEqual(statement.note, "Edited after Task error.")

    def test_statement_can_confirm_after_task_error(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-ERR-2")
        task.write({"state": "error"})
        statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")

    def test_statement_can_create_bill_after_task_error(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-ERR-3")
        statement.action_confirm_from_statement()
        task.write({"state": "error"})
        bill = statement.action_create_vendor_bill_from_statement()
        self.assertEqual(statement.vendor_bill_id, bill)

    def test_statement_usable_after_task_cancelled(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-CANCEL-1")
        task.action_cancel_task()
        self.assertEqual(task.state, "cancelled")
        statement.action_confirm_from_statement()
        bill = statement.action_create_vendor_bill_from_statement()
        self.assertEqual(statement.vendor_bill_id, bill)

    def test_task_cancel_changes_no_statement_business_state(self):
        task = self._make_task(state="to_parse")
        statement = self._make_confirmable_statement(task, "CC10-CANCEL-2")
        state_before = statement.state
        lines_before = statement.line_ids.mapped("checked")
        task.action_cancel_task()
        self.assertEqual(statement.state, state_before)
        self.assertEqual(statement.line_ids.mapped("checked"), lines_before)
        self.assertTrue(statement.line_ids.exists())


class TestHumanReviewedDeprecation(CC10StatementAuthorityCase):
    """§7: `human_reviewed` is a legacy field the new workflow ignores."""

    def test_human_reviewed_true_does_not_bypass_line_check(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-HR-1")
        statement.line_ids.write({"checked": False})
        task.write({"human_reviewed": True})
        with self.assertRaises(ValidationError):
            statement.action_confirm_from_statement()

    def test_human_reviewed_false_does_not_block_confirm(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-HR-2")
        task.write({"human_reviewed": False})
        statement.action_confirm_from_statement()
        self.assertEqual(statement.state, "confirmed")


class TestVendorBillAuthorityConvergence(CC10StatementAuthorityCase):
    """§7: Statement.vendor_bill_id is the sole authority; Task's is a
    read-only related compatibility mirror."""

    def test_task_vendor_bill_id_is_related_and_readonly(self):
        field = self.env["vendor.invoice.import.task"]._fields["vendor_bill_id"]
        self.assertEqual(field.related, "statement_id.vendor_bill_id")
        self.assertTrue(field.readonly)
        self.assertFalse(field.store)

    def test_task_vendor_bill_id_mirrors_statement_after_bill_creation(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-LINK-1")
        statement.action_confirm_from_statement()
        bill = statement.action_create_vendor_bill_from_statement()
        self.assertEqual(statement.vendor_bill_id, bill)
        self.assertEqual(task.vendor_bill_id, bill)

    def test_bill_cancellation_clears_statement_authority_only(self):
        task = self._make_task(state="parsed")
        statement = self._make_confirmable_statement(task, "CC10-LINK-2")
        statement.action_confirm_from_statement()
        bill = statement.action_create_vendor_bill_from_statement()
        bill.button_cancel()
        self.assertFalse(statement.vendor_bill_id)
        self.assertFalse(task.vendor_bill_id)
