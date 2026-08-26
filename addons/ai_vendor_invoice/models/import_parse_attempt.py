# © 2024 Wukong Digital. License LGPL-3.
# T-018: (task_id, sequence) must be unique at DB level.
# T-022: status queued → running only when worker actually starts.
# T-024: job_run_parse is the sole queue_job entry point (service must not with_delay directly).
from odoo import fields, models


class VendorInvoiceImportParseAttempt(models.Model):
    _name = "vendor.invoice.import.parse.attempt"
    _description = "AI Vendor Invoice Parse Attempt"
    _order = "task_id, sequence"

    task_id = fields.Many2one(
        "vendor.invoice.import.task",
        string="Import Task",
        required=True,
        ondelete="cascade",
        index=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        required=True,
    )

    provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="AI Provider Config",
        required=True,
    )

    started_at = fields.Datetime(
        string="Started At",
        index=True,
    )

    finished_at = fields.Datetime(
        string="Finished At",
    )

    attempt_internal_retry_count = fields.Integer(
        string="Internal Retry Count",
        default=0,
    )

    status = fields.Selection(
        selection=[
            ("queued", "Queued"),
            ("running", "Running"),
            ("success", "Success"),
            ("failed", "Failed"),
            ("superseded", "Superseded"),
        ],
        string="Status",
        required=True,
        index=True,
        default="queued",
    )

    # last_activity_at: local-only diagnostics; NOT used for cross-transaction
    # heartbeat / timeout decisions (T-026).
    last_activity_at = fields.Datetime(
        string="Last Activity At",
        index=True,
    )

    provider_diagnostics = fields.Json(
        string="Provider Diagnostics",
        help="Non-sensitive page and transport metadata for provider diagnosis.",
    )

    canonical_result = fields.Json(
        string="Canonical Result",
    )

    mapping_result = fields.Json(
        string="Mapping Result",
    )

    raw_response_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Raw AI Response",
        ondelete="set null",
    )

    error_message = fields.Text(
        string="Error Message",
    )

    # ── DB constraints ────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "task_sequence_unique",
            "unique(task_id, sequence)",
            "Parse attempt sequence must be unique per task.",
        )
    ]

    # ── queue_job entry point (T-024) ─────────────────────────────────────────

    def job_run_parse(self):
        """
        queue_job delayed-task entry point.
        This ORM method is the ONLY allowed with_delay() target.
        Business logic lives in parse_service; this method is only the queue entry.
        """
        self.ensure_one()
        from ..services.parse_service import run_parse_attempt

        return run_parse_attempt(self.env, self.task_id.id, self.id)

    def action_enqueue_parse(self):
        """Queue the model method; services must not call with_delay directly."""
        self.ensure_one()
        return self.with_delay(
            description="AI Vendor Invoice Parse #%s" % self.sequence,
        ).job_run_parse()
