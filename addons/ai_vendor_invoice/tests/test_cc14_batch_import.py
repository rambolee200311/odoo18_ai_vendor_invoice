# © 2024 Wukong Digital. License LGPL-3.
"""CC-14 Multi-PDF Batch Import and Selected Retry coverage.

Contract: docs/intents/CC-14-MULTI-PDF-BATCH-IMPORT-SELECTED-RETRY.md

Covers the Test Contract (§28) scenarios:
  - one Batch creates one Statement per accepted PDF;
  - one Statement has at most one Task;
  - each Task owns independent Attempt history;
  - filename preservation and Provider copy;
  - initial launch is async-only;
  - a single-file preflight rejection never persists a Batch member;
  - a single-file launch failure never rolls back sibling Statements;
  - current progress never counts historical failures;
  - the failed-Statement filter;
  - Retry Selected keeps the Statement/Task, creates a new Attempt, reuses
    the Provider, and stays async;
  - Retry Selected partial-failure isolation;
  - terminal Statements are never overwritten by Retry Selected;
  - duplicate PDF and company/security boundaries.
"""
import base64
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase

from ..models.import_parse_attempt import VendorInvoiceImportParseAttempt
from ..services import batch_service


class CC14BatchImportCase(TransactionCase):
    """Shared fixtures for CC-14 Batch/Retry Selected coverage."""

    def setUp(self):
        super().setUp()
        admin = self.env.ref("base.user_admin")
        admin.write({
            "groups_id": [(4, self.env.ref("ai_vendor_invoice.group_ai_invoice_user").id)]
        })
        admin.write({"company_id": self.env.company.id})
        self.admin = admin
        self.provider = self.env["wd.ai.provider.config"].create({
            "name": "CC14 Provider",
            "api_base_url": "https://example.invalid",
            "model_name": "test-model",
        })

    def _pdf(self, content):
        return base64.b64encode(b"%PDF-1.4 " + content)

    def _admin_env(self):
        return self.env(user=self.admin)

    def _start_batch(self, files, provider=None, env=None):
        """Run start_batch with the queue enqueue call stubbed out.

        Mirrors the existing CC-13 test pattern of patching
        ``action_enqueue_parse`` so no real queue_job worker is required;
        each launched Task/Attempt stops at ``queued``/``parsing``.
        """
        with patch.object(VendorInvoiceImportParseAttempt, "action_enqueue_parse"):
            return batch_service.start_batch(
                env or self._admin_env(),
                company_id=self.env.company.id,
                provider_config_id=(provider or self.provider).id,
                files=files,
            )

    def _retry_selected(self, batch_id, statement_ids, env=None):
        with patch.object(VendorInvoiceImportParseAttempt, "action_enqueue_parse"):
            return batch_service.retry_selected(
                env or self._admin_env(), batch_id, statement_ids
            )

    def _fail_current_attempt(self, task):
        """Simulate a queue worker recording a failed current Attempt."""
        attempt = task.current_parse_attempt_id
        attempt.write({"status": "failed", "error_summary": "boom"})
        task.write({"state": "error"})

    def _succeed_current_attempt(self, task):
        attempt = task.current_parse_attempt_id
        attempt.write({"status": "success"})
        task.write({"state": "parsed"})

    def _make_failed_batch_statement(self, content=b"retry-target", filename="retry.pdf"):
        batch, _results = self._start_batch([(self._pdf(content), filename)])
        statement = batch.statement_ids
        self._fail_current_attempt(statement.task_id)
        statement.invalidate_recordset(["batch_ai_status"])
        return batch, statement


class TestBatchInitialLaunch(CC14BatchImportCase):
    """§4/§10/§11/§12/§13/§14 initial multi-PDF launch."""

    def test_batch_creates_one_statement_and_task_per_accepted_pdf(self):
        files = [
            (self._pdf(b"invoice-a"), "a.pdf"),
            (self._pdf(b"invoice-b"), "b.pdf"),
        ]
        batch, results = self._start_batch(files)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "accepted" for r in results))
        self.assertEqual(len(batch.statement_ids), 2)
        filenames = sorted(batch.statement_ids.mapped("source_pdf_filename"))
        self.assertEqual(filenames, ["a.pdf", "b.pdf"])
        for statement in batch.statement_ids:
            self.assertEqual(statement.batch_id, batch)
            self.assertTrue(statement.task_id)
            # one Statement <-> at most one Task (existing task_unique constraint).
            self.assertEqual(len(statement.task_id), 1)
            self.assertEqual(
                statement.task_id.selected_provider_config_id, self.provider
            )
            self.assertFalse(statement.task_id.synchronous_parse)
            self.assertEqual(statement.task_id.state, "parsing")

    def test_batch_tasks_have_independent_attempt_history(self):
        files = [
            (self._pdf(b"invoice-a2"), "a2.pdf"),
            (self._pdf(b"invoice-b2"), "b2.pdf"),
        ]
        batch, _results = self._start_batch(files)
        task_a, task_b = batch.statement_ids.mapped("task_id")
        self.assertNotEqual(task_a, task_b)
        self.assertNotEqual(task_a.parse_attempt_ids, task_b.parse_attempt_ids)
        self.assertEqual(len(task_a.parse_attempt_ids), 1)
        self.assertEqual(len(task_b.parse_attempt_ids), 1)

    def test_batch_status_is_processing_while_all_queued(self):
        files = [(self._pdf(b"invoice-c"), "c.pdf")]
        batch, _results = self._start_batch(files)
        self.assertEqual(batch.total_count, 1)
        self.assertEqual(batch.processing_count, 1)
        self.assertEqual(batch.status, "processing")


class TestBatchPreflight(CC14BatchImportCase):
    """§6/§10/§23 pre-Statement preflight and duplicate handling."""

    def test_empty_file_is_rejected_without_persisting_statement(self):
        batch, results = self._start_batch([(False, "empty.pdf")])
        self.assertEqual(results[0]["status"], "rejected")
        self.assertFalse(results[0]["statement_id"])
        self.assertEqual(len(batch.statement_ids), 0)
        self.assertEqual(batch.total_count, 0)

    def test_non_pdf_file_is_rejected_without_persisting_statement(self):
        upload = base64.b64encode(b"this is not a pdf")
        batch, results = self._start_batch([(upload, "bad.txt")])
        self.assertEqual(results[0]["status"], "rejected")
        self.assertIn("not a valid PDF", results[0]["message"])
        self.assertEqual(len(batch.statement_ids), 0)

    def test_duplicate_within_same_batch_is_rejected(self):
        payload = self._pdf(b"same-content")
        batch, results = self._start_batch([
            (payload, "first.pdf"),
            (payload, "second.pdf"),
        ])
        self.assertEqual(results[0]["status"], "accepted")
        self.assertEqual(results[1]["status"], "rejected")
        self.assertIn("Duplicate PDF", results[1]["message"])
        self.assertEqual(len(batch.statement_ids), 1)

    def test_duplicate_against_existing_active_task_is_rejected(self):
        payload = self._pdf(b"already-imported")
        first_batch, first_results = self._start_batch([(payload, "first.pdf")])
        self.assertEqual(first_results[0]["status"], "accepted")
        second_batch, second_results = self._start_batch([(payload, "resend.pdf")])
        self.assertEqual(second_results[0]["status"], "rejected")
        self.assertIn("already imported", second_results[0]["message"])
        self.assertEqual(len(second_batch.statement_ids), 0)

    def test_cancelled_duplicate_task_does_not_block_reimport(self):
        payload = self._pdf(b"cancel-then-reimport")
        batch, results = self._start_batch([(payload, "first.pdf")])
        statement = batch.statement_ids
        statement.task_id.write({"state": "cancelled"})
        second_batch, second_results = self._start_batch([(payload, "again.pdf")])
        self.assertEqual(second_results[0]["status"], "accepted")
        self.assertEqual(len(second_batch.statement_ids), 1)


class TestBatchLaunchIsolation(CC14BatchImportCase):
    """§15 initial failure isolation: one PDF failing must not affect others."""

    def test_single_launch_failure_does_not_roll_back_siblings(self):
        files = [
            (self._pdf(b"ok-1"), "ok-1.pdf"),
            (self._pdf(b"boom"), "boom.pdf"),
            (self._pdf(b"ok-2"), "ok-2.pdf"),
        ]
        call_count = {"n": 0}
        real_launch = batch_service.launch_statement_ai

        def flaky_launch(env, statement_id):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise ValidationError("Simulated launch failure.")
            return real_launch(env, statement_id)

        with patch.object(batch_service, "launch_statement_ai", side_effect=flaky_launch):
            batch, results = self._start_batch(files)
        statuses = [r["status"] for r in results]
        self.assertEqual(statuses, ["accepted", "launch_failed", "accepted"])
        # Only the two accepted PDFs persisted a Statement; the failed unit
        # (Statement + Task + Attempt) was rolled back as one atomic unit.
        self.assertEqual(len(batch.statement_ids), 2)
        self.assertEqual(
            sorted(batch.statement_ids.mapped("source_pdf_filename")),
            ["ok-1.pdf", "ok-2.pdf"],
        )
        for statement in batch.statement_ids:
            self.assertTrue(statement.task_id)
            self.assertEqual(statement.task_id.state, "parsing")


class TestBatchProgressAndFilter(CC14BatchImportCase):
    """§16/§17 current progress and the failed-Statement filter."""

    def test_progress_does_not_count_historical_failures_after_success(self):
        batch, _results = self._start_batch([(self._pdf(b"retry-me"), "retry.pdf")])
        statement = batch.statement_ids
        self._fail_current_attempt(statement.task_id)
        statement.invalidate_recordset(["batch_ai_status"])
        batch.invalidate_recordset(["failed_count", "success_count", "status"])
        self.assertEqual(batch.failed_count, 1)
        self.assertEqual(batch.status, "completed_with_errors")
        self._retry_selected(batch.id, [statement.id])
        self._succeed_current_attempt(statement.task_id)
        statement.invalidate_recordset(["batch_ai_status"])
        batch.invalidate_recordset(["failed_count", "success_count", "status"])
        self.assertEqual(batch.failed_count, 0)
        self.assertEqual(batch.success_count, 1)
        self.assertEqual(batch.status, "completed")

    def test_failed_statement_filter_returns_only_current_failed(self):
        batch, _results = self._start_batch([
            (self._pdf(b"fail-me"), "fail.pdf"),
            (self._pdf(b"stay-ok"), "ok.pdf"),
        ])
        failing, healthy = batch.statement_ids.sorted("id")
        self._fail_current_attempt(failing.task_id)
        failing.invalidate_recordset(["batch_ai_status"])
        healthy.invalidate_recordset(["batch_ai_status"])
        failed = self.env["vendor.invoice.statement"].search([
            ("batch_id", "=", batch.id),
            ("batch_ai_status", "=", "failed"),
        ])
        self.assertEqual(failed, failing)
        self.assertNotIn(healthy, failed)


class TestRetrySelected(CC14BatchImportCase):
    """§18/§19/§20/§21 Retry Selected."""

    def test_retry_keeps_same_statement_and_task_creates_new_attempt(self):
        batch, statement = self._make_failed_batch_statement()
        original_task = statement.task_id
        original_attempt = original_task.current_parse_attempt_id
        results = self._retry_selected(batch.id, [statement.id])
        self.assertEqual(results[0]["status"], "accepted")
        statement.invalidate_recordset()
        self.assertEqual(statement.task_id, original_task)
        self.assertEqual(len(original_task.parse_attempt_ids), 2)
        new_attempt = original_task.current_parse_attempt_id
        self.assertNotEqual(new_attempt, original_attempt)
        self.assertEqual(new_attempt.sequence, 2)
        self.assertIn(original_attempt, original_task.parse_attempt_ids)
        self.assertEqual(new_attempt.provider_config_id, self.provider)
        self.assertFalse(original_task.synchronous_parse)
        self.assertEqual(original_task.state, "parsing")

    def test_retry_eligibility_matrix_rejects_non_error_states(self):
        rejected_states = [
            "to_parse", "awaiting_review", "parsing", "parsed", "cancelled",
            "bill_generated",
        ]
        for state in rejected_states:
            batch, statement = self._make_failed_batch_statement(
                content=("state-%s" % state).encode(),
                filename="state-%s.pdf" % state,
            )
            statement.task_id.write({"state": state})
            results = self._retry_selected(batch.id, [statement.id])
            self.assertEqual(
                results[0]["status"], "rejected",
                "Task state %s must reject Retry Selected" % state,
            )
            self.assertEqual(len(statement.task_id.parse_attempt_ids), 1)

    def test_retry_rejects_when_active_attempt_in_progress(self):
        batch, statement = self._make_failed_batch_statement()
        # Simulate a race: put the Task back into an active parse.
        statement.task_id.write({"state": "error"})
        active = self.env["vendor.invoice.import.parse.attempt"].create({
            "task_id": statement.task_id.id,
            "sequence": 2,
            "provider_config_id": self.provider.id,
            "status": "queued",
        })
        results = self._retry_selected(batch.id, [statement.id])
        self.assertEqual(results[0]["status"], "rejected")
        self.assertIn("in progress", results[0]["message"])
        active.unlink()

    def test_retry_selected_launch_failure_does_not_affect_sibling(self):
        batch, statement_a = self._make_failed_batch_statement(
            content=b"iso-a", filename="iso-a.pdf"
        )
        _batch_unused, statement_b = self._make_failed_batch_statement(
            content=b"iso-b", filename="iso-b.pdf"
        )
        # Re-home B onto the same batch as A via direct SQL-level aggregate
        # write is not part of the public contract; instead simulate by
        # creating both under one batch directly.
        batch2, results2 = self._start_batch([
            (self._pdf(b"iso-c"), "iso-c.pdf"),
            (self._pdf(b"iso-d"), "iso-d.pdf"),
        ])
        stmt_c, stmt_d = batch2.statement_ids.sorted("id")
        self._fail_current_attempt(stmt_c.task_id)
        self._fail_current_attempt(stmt_d.task_id)
        stmt_c.invalidate_recordset(["batch_ai_status"])
        stmt_d.invalidate_recordset(["batch_ai_status"])

        real_launch = batch_service.launch_statement_ai

        def flaky_launch(env, statement_id):
            if statement_id == stmt_d.id:
                raise ValidationError("Simulated retry failure for D.")
            return real_launch(env, statement_id)

        with patch.object(batch_service, "launch_statement_ai", side_effect=flaky_launch):
            results = self._retry_selected(batch2.id, [stmt_c.id, stmt_d.id])
        by_id = {r["statement_id"]: r for r in results}
        self.assertEqual(by_id[stmt_c.id]["status"], "accepted")
        self.assertEqual(by_id[stmt_d.id]["status"], "failed")
        stmt_c.invalidate_recordset()
        stmt_d.invalidate_recordset()
        self.assertEqual(len(stmt_c.task_id.parse_attempt_ids), 2)
        # D's retry failed before completing; its original failed Attempt
        # history is preserved untouched (no synthetic success/second entry
        # persisted for a launch that never got created).
        self.assertEqual(len(stmt_d.task_id.parse_attempt_ids), 1)
        self.assertEqual(stmt_d.task_id.state, "error")

    def test_terminal_statement_is_not_overwritten_by_retry(self):
        batch, statement = self._make_failed_batch_statement()
        # A Statement is only retry-eligible while Draft; simulate a
        # terminal (non-draft) Statement even though its Task is `error`.
        statement._aggregate_write({"state": "cancelled"})
        results = self._retry_selected(batch.id, [statement.id])
        self.assertEqual(results[0]["status"], "rejected")
        self.assertEqual(statement.state, "cancelled")
        self.assertEqual(len(statement.task_id.parse_attempt_ids), 1)


class TestBatchSecurityAndCompany(CC14BatchImportCase):
    """§24 security/company boundary."""

    def test_start_batch_requires_ai_invoice_user_group(self):
        outsider = self.env["res.users"].sudo().create({
            "name": "No Group",
            "login": "cc14-no-group@example.com",
            "email": "cc14-no-group@example.invalid",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self._start_batch(
                [(self._pdf(b"blocked"), "blocked.pdf")],
                env=self.env(user=outsider),
            )

    def test_retry_selected_requires_ai_invoice_user_group(self):
        batch, statement = self._make_failed_batch_statement()
        outsider = self.env["res.users"].sudo().create({
            "name": "No Group Retry",
            "login": "cc14-no-group-retry@example.com",
            "email": "cc14-no-group-retry@example.invalid",
            "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        with self.assertRaises(AccessError):
            self._retry_selected(
                batch.id, [statement.id], env=self.env(user=outsider)
            )

    def test_retry_rejects_statement_from_a_different_batch(self):
        batch_one, statement_one = self._make_failed_batch_statement(
            content=b"company-a", filename="company-a.pdf"
        )
        batch_two, _statement_two = self._make_failed_batch_statement(
            content=b"company-b", filename="company-b.pdf"
        )
        results = self._retry_selected(batch_two.id, [statement_one.id])
        self.assertEqual(results[0]["status"], "rejected")
        self.assertIn("does not belong", results[0]["message"])
        self.assertEqual(len(statement_one.task_id.parse_attempt_ids), 1)
