# © 2024 Wukong Digital. License LGPL-3.
"""Traceability links from generated vendor bills to the reviewed Statement."""

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vendor_invoice_statement_id = fields.Many2one(
        "vendor.invoice.statement",
        string="Vendor Invoice Statement",
        ondelete="restrict",
        index=True,
        copy=False,
    )

    def button_cancel(self):
        result = super().button_cancel()
        for move in self:
            statement = move.vendor_invoice_statement_id
            if statement and statement.vendor_bill_id == move:
                statement._aggregate_write({"vendor_bill_id": False})
                if statement.task_id:
                    self.env["vendor.invoice.import.log"].create({
                        "task_id": statement.task_id.id,
                        "parse_attempt_id": statement.source_parse_attempt_id.id,
                        "action": "vendor_bill_cancelled",
                        "snapshot_delta": "Current Vendor Bill %s cancelled."
                        % move.display_name,
                    })
                else:
                    statement.message_post(
                        body="Current Vendor Bill %s cancelled." % move.display_name,
                    )
        return result


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    vendor_statement_line_id = fields.Many2one(
        "vendor.invoice.statement.line",
        string="Vendor Statement Line",
        ondelete="restrict",
        index=True,
        copy=False,
    )
    reconciliation_clues = fields.Json(
        string="Reconciliation Clues",
        help="Generic invoice-line clues preserved for future reconciliation.",
        copy=False,
    )
