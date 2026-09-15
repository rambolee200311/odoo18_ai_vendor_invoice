# © 2024 Wukong Digital. License LGPL-3.
"""CC-14 multi-PDF Batch import entry point.

Transient wizard: collects multiple PDFs and one Provider, then delegates
the whole preflight/create/launch orchestration to
``services/batch_service.start_batch``. The wizard itself owns no business
data and is not persisted after use.
"""
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class VendorInvoiceBatchImportWizard(models.TransientModel):
    _name = "vendor.invoice.batch.import.wizard"
    _description = "Multi-PDF Batch Import Wizard"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="AI Provider",
        required=True,
        domain="[('active', '=', True)]",
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        help=(
            "Optional trusted supplier for every PDF in this Batch. "
            "Selecting UPS explicitly enables its Extraction Profile."
        ),
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "vendor_invoice_batch_wizard_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="PDF Files",
        help="Select one or more supplier invoice PDFs in a single upload.",
    )
    line_ids = fields.One2many(
        "vendor.invoice.batch.import.wizard.line",
        "wizard_id",
        string="PDF Files",
    )

    def action_start_batch(self):
        self.ensure_one()
        files = [
            (attachment.datas, attachment.name)
            for attachment in self.attachment_ids
            if attachment.datas
        ]
        if not files:
            files = [
                (line.pdf_upload, line.pdf_filename) for line in self.line_ids
            ]
        if not files:
            raise ValidationError(_("Upload at least one supplier invoice PDF."))
        from ..services.batch_service import start_batch

        batch, _results = start_batch(
            self.env,
            company_id=self.company_id.id,
            provider_config_id=self.provider_config_id.id,
            supplier_id=self.supplier_id.id,
            files=files,
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch"),
            "res_model": "vendor.invoice.batch",
            "view_mode": "form",
            "res_id": batch.id,
            "target": "current",
        }


class VendorInvoiceBatchImportWizardLine(models.TransientModel):
    _name = "vendor.invoice.batch.import.wizard.line"
    _description = "Batch Import Wizard PDF Line"

    wizard_id = fields.Many2one(
        "vendor.invoice.batch.import.wizard",
        required=True,
        ondelete="cascade",
    )
    pdf_upload = fields.Binary(string="PDF", required=True)
    pdf_filename = fields.Char(string="File Name", required=True)
