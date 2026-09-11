# © 2024 Wukong Digital. License LGPL-3.
"""CC-14 persistent Batch: multi-PDF import orchestration only.

Batch owns one multi-file import operation, the grouping of Statements it
creates, the initial Provider selection, current aggregate progress, and
Retry Selected orchestration. Batch never becomes invoice business
authority: it does not own supplier/invoice data, human review, Confirm, or
Vendor Bill creation, all of which remain with Statement (CC-10/CC-11/CC-13).

See docs/intents/CC-14-MULTI-PDF-BATCH-IMPORT-SELECTED-RETRY.md.
"""
from odoo import _, api, fields, models

BATCH_STATES = [
    ("draft", "Draft"),
    ("processing", "Processing"),
    ("completed", "Completed"),
    ("completed_with_errors", "Completed with Errors"),
]


class VendorInvoiceBatch(models.Model):
    _name = "vendor.invoice.batch"
    _description = "Vendor Invoice Multi-PDF Batch Import"
    _order = "id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Batch Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "vendor.invoice.batch"
        ) or _("New"),
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="AI Provider",
        required=True,
        domain="[('active', '=', True)]",
        help="Provider copied onto every Statement this Batch creates.",
    )
    started_at = fields.Datetime(
        string="Started At",
        readonly=True,
        default=fields.Datetime.now,
    )
    statement_ids = fields.One2many(
        "vendor.invoice.statement",
        "batch_id",
        string="Statements",
    )
    total_count = fields.Integer(string="Total", compute="_compute_counts", store=True)
    pending_count = fields.Integer(string="Pending", compute="_compute_counts", store=True)
    processing_count = fields.Integer(
        string="Processing", compute="_compute_counts", store=True
    )
    success_count = fields.Integer(string="Success", compute="_compute_counts", store=True)
    failed_count = fields.Integer(string="Failed", compute="_compute_counts", store=True)
    status = fields.Selection(
        selection=BATCH_STATES,
        string="Batch Status",
        compute="_compute_status",
        store=True,
        help=(
            "Current orchestration view, not an immutable business workflow "
            "(CC-14 §8). Historical failures are preserved only through "
            "Task and ParseAttempt history."
        ),
    )

    @api.depends("statement_ids.batch_ai_status")
    def _compute_counts(self):
        for batch in self:
            statuses = batch.statement_ids.mapped("batch_ai_status")
            batch.total_count = len(statuses)
            batch.pending_count = statuses.count("pending")
            batch.processing_count = statuses.count("processing")
            batch.success_count = statuses.count("success")
            batch.failed_count = statuses.count("failed")

    @api.depends("total_count", "pending_count", "processing_count", "failed_count")
    def _compute_status(self):
        for batch in self:
            if not batch.total_count:
                batch.status = "draft"
            elif batch.pending_count or batch.processing_count:
                batch.status = "processing"
            elif batch.failed_count:
                batch.status = "completed_with_errors"
            else:
                batch.status = "completed"

    def action_retry_selected(self, statement_ids):
        """CC-14 §18 Retry Selected orchestration entry point.

        ``statement_ids`` must belong to this Batch; unrelated ids are
        reported as a per-item rejection by the underlying service rather
        than raising for the whole selection.
        """
        self.ensure_one()
        from ..services.batch_service import retry_selected

        return retry_selected(self.env, self.id, statement_ids)

    def action_open_statements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Statements"),
            "res_model": "vendor.invoice.statement",
            "view_mode": "list,form",
            "domain": [("batch_id", "=", self.id)],
        }

    def action_open_failed_statements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Failed Statements"),
            "res_model": "vendor.invoice.statement",
            "view_mode": "list,form",
            "domain": [("batch_id", "=", self.id), ("batch_ai_status", "=", "failed")],
        }
