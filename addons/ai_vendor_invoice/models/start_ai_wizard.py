# © 2024 Wukong Digital. License LGPL-3.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class VendorInvoiceStartAiWizard(models.TransientModel):
    _name = "vendor.invoice.start.ai.wizard"
    _description = "Start AI Configuration"

    statement_id = fields.Many2one(
        "vendor.invoice.statement",
        string="Statement",
        required=True,
        readonly=True,
    )
    provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="Provider",
        required=True,
        domain="[('active', '=', True)]",
    )
    synchronous_parse = fields.Boolean(
        string="Synchronous Parse",
        default=True,
        help="Run AI parsing in this request instead of submitting a queue job.",
    )
    provider_usable = fields.Boolean(
        compute="_compute_provider_usable",
        readonly=True,
    )

    @api.model
    def _usable_provider_domain(self):
        return [
            ("active", "=", True),
            ("api_base_url", "!=", False),
            ("model_name", "!=", False),
            ("api_key", "!=", False),
        ]

    @api.model
    def _default_provider(self):
        provider = self.env["wd.ai.provider.config"].sudo().search(
            self._usable_provider_domain(),
            order="sequence, id",
            limit=1,
        )
        return provider.id

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if "provider_config_id" in fields_list and not values.get("provider_config_id"):
            values["provider_config_id"] = self._default_provider()
        return values

    @api.depends("provider_config_id")
    def _compute_provider_usable(self):
        for wizard in self:
            provider = wizard.provider_config_id.sudo()
            wizard.provider_usable = bool(
                provider
                and provider.id in wizard._usable_provider_ids()
            )

    def _usable_provider_ids(self):
        return self.env["wd.ai.provider.config"].sudo().search(
            self._usable_provider_domain()
        ).ids

    def action_start(self):
        self.ensure_one()
        if not self.env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
            raise AccessError(_("Only an AI Invoice User can start AI parsing."))
        statement = self.env["wd.lock.service"].lock_statement(self.statement_id.id)
        statement.ensure_one()
        if statement.task_id:
            raise ValidationError(_("This Statement already has an AI Task."))
        if not statement.source_pdf_attachment_id:
            raise ValidationError(_("Upload a supplier invoice PDF before starting AI."))
        provider = self.provider_config_id
        usable_provider_ids = self._usable_provider_ids()
        if not provider or provider.id not in usable_provider_ids:
            raise ValidationError(
                _("Select an active AI provider with complete configuration.")
            )

        task = self.env["vendor.invoice.import.task"].create({
            "company_id": statement.company_id.id,
            "source_pdf_attachment_id": statement.source_pdf_attachment_id.id,
            "source_pdf_filename": statement.source_pdf_filename,
            "selected_provider_config_id": provider.id,
            "synchronous_parse": self.synchronous_parse,
            "statement_id": statement.id,
        })
        statement._aggregate_write({"task_id": task.id})
        from ..services.parse_service import start_parse

        start_parse(
            self.env,
            task.id,
            provider.id,
            synchronous=self.synchronous_parse,
        )
        return statement.action_open_import_task()
