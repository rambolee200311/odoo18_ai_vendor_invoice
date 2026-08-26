# © 2024 Wukong Digital. License LGPL-3.
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class VendorInvoiceStatement(models.Model):
    _name = "vendor.invoice.statement"
    _description = "Vendor Invoice Human Statement"
    _order = "id desc"

    task_id = fields.Many2one(
        "vendor.invoice.import.task",
        string="Import Task",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="task_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )
    source_parse_attempt_id = fields.Many2one(
        "vendor.invoice.import.parse.attempt",
        string="Source Parse Attempt",
        required=True,
        ondelete="restrict",
        index=True,
    )
    invoice_number = fields.Char(string="Invoice Number", required=True)
    invoice_date = fields.Date(string="Invoice Date")
    supplier_id = fields.Many2one("res.partner", string="Supplier")
    supplier_name = fields.Char(string="Supplier")
    currency_id = fields.Many2one("res.currency", string="Currency")
    total_amount = fields.Monetary(string="Total Amount", currency_field="currency_id")
    total_tax = fields.Monetary(string="Total Tax", currency_field="currency_id")
    note = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "vendor.invoice.statement.line",
        "statement_id",
        string="Statement Lines",
        copy=True,
    )

    _sql_constraints = [
        (
            "task_unique",
            "unique(task_id)",
            "A task can have only one human Statement.",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(
            _("Statement records must be created through a Task aggregate command.")
        )

    def write(self, vals):
        raise AccessError(
            _("Statement records must be changed through a Task aggregate command.")
        )

    def unlink(self):
        raise AccessError(
            _("Statement records must be deleted through a Task aggregate command.")
        )

    @api.model
    def _aggregate_create(self, vals):
        """Persist a validated aggregate command without exposing generic CRUD."""
        return super().create(vals)

    def _aggregate_write(self, vals):
        return super().write(vals)

    def _aggregate_unlink(self):
        return super().unlink()


class VendorInvoiceStatementLine(models.Model):
    _name = "vendor.invoice.statement.line"
    _description = "Vendor Invoice Human Statement Line"
    _order = "sequence, id"

    statement_id = fields.Many2one(
        "vendor.invoice.statement",
        string="Statement",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(required=True, default=10)
    description = fields.Char(required=True)
    product_id = fields.Many2one("product.product", string="Product")
    quantity = fields.Float(default=1.0)
    price_unit = fields.Monetary(currency_field="currency_id")
    amount = fields.Monetary(required=True, currency_field="currency_id")
    tax_raw_text = fields.Char(string="Tax")
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    currency_id = fields.Many2one(
        related="statement_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(
            _("Statement lines must be created through a Task aggregate command.")
        )

    def write(self, vals):
        raise AccessError(
            _("Statement lines must be changed through a Task aggregate command.")
        )

    def unlink(self):
        raise AccessError(
            _("Statement lines must be deleted through a Task aggregate command.")
        )

    @api.model
    def _aggregate_create(self, vals):
        return super().create(vals)

    def _aggregate_unlink(self):
        return super().unlink()


def validate_statement_payload(payload):
    if not isinstance(payload, dict) or not payload.get("invoice_number"):
        raise ValidationError(_("A Statement requires an invoice number."))
    lines = payload.get("lines", [])
    if not isinstance(lines, list):
        raise ValidationError(_("Statement lines must be a list."))
    for line in lines:
        if not isinstance(line, dict) or not line.get("description"):
            raise ValidationError(_("Each Statement line requires a description."))
        if "amount" not in line:
            raise ValidationError(_("Each Statement line requires an amount."))
    return payload
