# © 2024 Wukong Digital. License LGPL-3.
# Architecture red-line T-025: task.company_id is immutable after creation.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
        return super().write(vals)

    # ── helper: sequence for next attempt ─────────────────────────────────────

    def _get_next_attempt_sequence(self):
        """Return the next integer sequence number for a new ParseAttempt."""
        self.ensure_one()
        existing = self.parse_attempt_ids.mapped("sequence")
        return max(existing, default=0) + 1

    def action_rerun_ai(self):
        """Queue a new attempt without changing historical attempts."""
        self.ensure_one()
        from ..services.parse_service import start_parse

        return start_parse(self.env, self.id, self.selected_provider_config_id.id)

    def action_save_review(self, review_result):
        """Persist the review result and its audit delta without creating a bill."""
        self.ensure_one()
        if self.state != "awaiting_review":
            raise ValidationError(_("Only an invoice awaiting review can be reviewed."))
        if not isinstance(review_result, dict) or not review_result:
            raise ValidationError(_("A non-empty review result is required."))
        old_result = self.human_review_result or {}
        self.write({
            "human_review_result": review_result,
            "human_reviewed": True,
        })
        self.env["vendor.invoice.import.log"].create({
            "task_id": self.id,
            "parse_attempt_id": self.current_parse_attempt_id.id,
            "action": "human_modify",
            "snapshot_delta": "Human review result updated (%s top-level keys changed)."
            % len(set(old_result) ^ set(review_result)),
        })
        return True

    # ── cron stub ─────────────────────────────────────────────────────────────

    @api.model
    def cron_check_parsing_timeout(self):
        """
        Cron entry point: scan tasks in 'parsing' state and mark those that
        exceed the system timeout as error_timeout.
        T-026: timeout baseline is self.enter_parsing_datetime (covers queued + running).
        Full implementation lives in timeout_service (Intent-2).
        """
        # Intent-1: stub – no-op so cron does not crash on install.
        pass
