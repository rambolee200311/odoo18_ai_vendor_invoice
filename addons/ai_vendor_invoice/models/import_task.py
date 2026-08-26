# © 2024 Wukong Digital. License LGPL-3.
# Architecture red-line T-025: task.company_id is immutable after creation.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class VendorInvoiceImportTask(models.Model):
    _name = "vendor.invoice.import.task"
    _description = "AI Vendor Invoice Import Task"
    _order = "id desc"

    # ── identity ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string="Task Reference",
        required=True,
        copy=False,
        default=lambda self: _("New"),
    )

    # T-025: company_id is set once at creation and must never be changed.
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    source_pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Source PDF",
        required=True,
        ondelete="restrict",
    )

    # ── state machine ─────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("to_parse", "To Parse"),
            ("parsing", "Parsing"),
            ("awaiting_review", "Awaiting Review"),
            ("bill_generated", "Bill Generated"),
            ("error_split_required", "Error: Split Required"),
            ("error_ai_unavailable", "Error: AI Unavailable"),
            ("error_timeout", "Error: Timeout"),
        ],
        string="State",
        required=True,
        index=True,
        default="to_parse",
    )

    # ── AI provider & attempt tracking ────────────────────────────────────────
    selected_provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="AI Provider",
        required=True,
    )

    enter_parsing_datetime = fields.Datetime(
        string="Entered Parsing At",
        index=True,
    )

    current_parse_attempt_id = fields.Many2one(
        "vendor.invoice.import.parse.attempt",
        string="Current Attempt",
        ondelete="set null",
        index=True,
    )

    parse_attempt_ids = fields.One2many(
        "vendor.invoice.import.parse.attempt",
        "task_id",
        string="Parse Attempts",
    )

    statement_id = fields.Many2one(
        "vendor.invoice.statement",
        string="Human Statement",
        ondelete="restrict",
        copy=False,
    )
    statement_required = fields.Boolean(
        string="Statement Required",
        default=True,
        copy=False,
        readonly=True,
    )

    # ── review & result ───────────────────────────────────────────────────────
    # T-006 / T-007: bill_creator reads ONLY human_review_result.
    human_review_result = fields.Json(
        string="Human Review Result",
        default=dict,
    )

    human_reviewed = fields.Boolean(
        string="Human Reviewed",
        default=False,
    )

    review_warnings = fields.Json(
        string="Review Warnings",
        default=list,
    )

    # ── bill link ─────────────────────────────────────────────────────────────
    # T-005: one task → at most one vendor bill; ondelete=restrict prevents re-generation
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        index=True,
        ondelete="restrict",
    )

    # ── audit ─────────────────────────────────────────────────────────────────
    audit_log_ids = fields.One2many(
        "vendor.invoice.import.log",
        "task_id",
        string="Audit Logs",
    )

    # ── ORM hooks ─────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "vendor.invoice.import.task"
                ) or _("New")
            vals.setdefault("human_review_result", {})
            vals.setdefault("review_warnings", [])
        return super().create(vals_list)

    def write(self, vals):
        # T-025: company_id is immutable after creation.
        if "company_id" in vals:
            raise ValidationError(
                _("The company of an import task cannot be changed after creation.")
            )
        if "statement_required" in vals:
            raise ValidationError(_("Statement requirement cannot be changed."))
        return super().write(vals)

    # ── helper: sequence for next attempt ─────────────────────────────────────

    def _get_next_attempt_sequence(self):
        """Return the next integer sequence number for a new ParseAttempt."""
        self.ensure_one()
        latest = self.env["vendor.invoice.import.parse.attempt"].search(
            [("task_id", "=", self.id)],
            order="sequence desc",
            limit=1,
        )
        return (latest.sequence if latest else 0) + 1

    def action_rerun_ai(self):
        """Queue a new attempt without changing historical attempts."""
        self.ensure_one()
        from ..services.parse_service import start_parse

        return start_parse(self.env, self.id, self.selected_provider_config_id.id)

    def action_save_review(self, review_result):
        """Persist the review result and its audit delta without creating a bill."""
        self.ensure_one()
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can save review data."))
        if self.state != "awaiting_review":
            raise ValidationError(_("Only an invoice awaiting review can be reviewed."))
        if not isinstance(review_result, dict) or not review_result:
            raise ValidationError(_("A non-empty review result is required."))
        old_result = self.human_review_result or {}
        config = self.env["wd.system.config"].get_config()
        from ..services import validation_service

        warnings = validation_service.check_amount_balance(
            review_result, self.company_id, config.amount_tolerance
        )
        self.write({
            "human_review_result": review_result,
            "human_reviewed": True,
            "review_warnings": warnings,
        })
        self.env["vendor.invoice.import.log"].create({
            "task_id": self.id,
            "parse_attempt_id": self.current_parse_attempt_id.id,
            "action": "human_modify",
            "snapshot_delta": "Human review result updated (%s top-level keys changed)."
            % len(set(old_result) ^ set(review_result)),
        })
        return True

    def action_create_statement_from_attempt(self, attempt_id, statement_payload):
        """Create the first human Statement from a current ParseAttempt candidate."""
        self.ensure_one()
        self._check_statement_command_access()
        attempt = self.env["vendor.invoice.import.parse.attempt"].browse(attempt_id)
        if not attempt.exists() or attempt.task_id != self or attempt.status != "success":
            raise ValidationError(_("Only a successful attempt of this task can create a Statement."))
        if self.statement_id:
            raise ValidationError(_("This task already has a human Statement."))
        from .statement import validate_statement_payload

        payload = validate_statement_payload(statement_payload)
        statement = self.env["vendor.invoice.statement"]._aggregate_create(
            self._statement_values(payload, attempt)
        )
        self.statement_id = statement.id
        self._log_statement_change("human_modify", attempt, "Statement created from ParseAttempt.")
        return statement

    def action_apply_statement_changes(self, statement_payload):
        """Apply human edits through the aggregate boundary."""
        self.ensure_one()
        self._check_statement_command_access()
        if not self.statement_id:
            raise ValidationError(_("This task has no human Statement to edit."))
        from .statement import validate_statement_payload

        payload = validate_statement_payload(statement_payload)
        statement = self.statement_id
        statement._aggregate_write(self._statement_values(payload, statement.source_parse_attempt_id))
        statement.line_ids._aggregate_unlink()
        self.env["vendor.invoice.statement.line"]._aggregate_create(
            self._statement_line_values(payload, statement)
        )
        self._log_statement_change("human_modify", statement.source_parse_attempt_id, "Human Statement changed.")
        return statement

    def action_apply_ai_candidate(self, attempt_id, statement_payload):
        """Replace a Statement with an explicitly accepted current AI candidate."""
        self.ensure_one()
        self._check_statement_command_access()
        attempt = self.env["vendor.invoice.import.parse.attempt"].browse(attempt_id)
        if not attempt.exists() or attempt.task_id != self or attempt.status != "success":
            raise ValidationError(_("Only a successful current attempt can be applied."))
        if self.current_parse_attempt_id != attempt:
            raise ValidationError(_("A stale ParseAttempt cannot be applied."))
        from .statement import validate_statement_payload

        payload = validate_statement_payload(statement_payload)
        if not self.statement_id:
            return self.action_create_statement_from_attempt(attempt.id, payload)
        statement = self.statement_id
        statement._aggregate_write(
            dict(self._statement_values(payload, attempt), source_parse_attempt_id=attempt.id)
        )
        statement.line_ids._aggregate_unlink()
        self.env["vendor.invoice.statement.line"]._aggregate_create(
            self._statement_line_values(payload, statement)
        )
        self._log_statement_change(
            "statement_candidate_apply", attempt, "AI candidate explicitly applied."
        )
        return statement

    def action_confirm_statement(self, statement_payload=None):
        """Persist the review, projection, and aggregate confirmation atomically."""
        self.ensure_one()
        self._check_statement_command_access()
        if statement_payload is not None:
            payload = self._statement_payload_from_review(statement_payload)
            if self.statement_id:
                self.action_apply_statement_changes(payload)
            else:
                self.action_create_statement_from_attempt(
                    self.current_parse_attempt_id.id, payload
                )
        if not self.statement_id:
            raise ValidationError(_("A human Statement is required."))
        from ..services.statement_projection import (
            assert_projection_consistent,
            statement_to_human_review_result,
        )

        projection = statement_to_human_review_result(self.statement_id)
        assert_projection_consistent(self.statement_id, projection)
        self.write({
            "human_review_result": projection,
            "human_reviewed": True,
            "state": "awaiting_review",
        })
        self._log_statement_change(
            "human_modify",
            self.statement_id.source_parse_attempt_id,
            "Human Statement confirmed.",
        )
        return True

    def _check_statement_command_access(self):
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can modify a human Statement."))

    def _statement_values(self, payload, attempt):
        return {
            "task_id": self.id,
            "source_parse_attempt_id": attempt.id,
            "invoice_number": payload["invoice_number"],
            "invoice_date": payload.get("invoice_date"),
            "supplier_id": payload.get("supplier_id"),
            "supplier_name": payload.get("supplier_name"),
            "currency_id": payload.get("currency_id"),
            "total_amount": payload.get("total_amount", 0.0),
            "total_tax": payload.get("total_tax", 0.0),
            "note": payload.get("note"),
        }

    def _statement_line_values(self, payload, statement):
        return [
            {
                "statement_id": statement.id,
                "sequence": index * 10,
                "description": line["description"],
                "product_id": line.get("product_id"),
                "quantity": line.get("quantity", 1.0),
                "price_unit": line.get("price_unit", 0.0),
                "amount": line["amount"],
                "tax_raw_text": line.get("tax_raw_text"),
                "tax_ids": [(6, 0, line.get("tax_ids", []))],
            }
            for index, line in enumerate(payload.get("lines", []), 1)
        ]

    def _statement_payload_from_review(self, review_payload):
        if "header" not in review_payload:
            return review_payload
        header = review_payload.get("header") or {}
        return {
            "invoice_number": header.get("invoice_number"),
            "invoice_date": header.get("invoice_date"),
            "supplier_id": header.get("supplier_id"),
            "currency_id": header.get("currency_id"),
            "total_amount": header.get("total_amount", 0.0),
            "total_tax": header.get("total_tax", 0.0),
            "lines": [
                {
                    "product_id": line.get("product_id"),
                    "description": line.get("description"),
                    "quantity": line.get("quantity", 1.0),
                    "price_unit": line.get("unit_price", 0.0),
                    "amount": line.get("line_total_amount", line.get("subtotal", 0.0)),
                    "tax_ids": line.get("tax_ids", []),
                    "tax_raw_text": line.get("tax_raw_text"),
                }
                for line in review_payload.get("lines", [])
            ],
        }

    def _statement_payload_from_record(self):
        statement = self.statement_id
        return {
            "invoice_number": statement.invoice_number,
            "lines": [
                {"description": line.description, "amount": line.amount}
                for line in statement.line_ids
            ],
        }

    def _log_statement_change(self, action, attempt, summary):
        self.env["vendor.invoice.import.log"].create({
            "task_id": self.id,
            "parse_attempt_id": attempt.id,
            "action": action,
            "snapshot_delta": summary,
        })

    def action_confirm_review_and_create_bill(self, review_payload):
        """Atomically save the review and create its draft vendor bill."""
        self.ensure_one()
        from ..services.bill_creator import confirm_review_and_create_bill

        return confirm_review_and_create_bill(self.env, self.id, review_payload)

    @api.model
    def cron_check_parsing_timeout(self):
        """Mark queued or running parsing tasks exceeding the task timeout."""
        from ..services.timeout_service import check_parsing_timeout

        check_parsing_timeout(self.env)
