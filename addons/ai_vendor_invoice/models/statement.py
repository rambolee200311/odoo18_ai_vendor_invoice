# © 2024 Wukong Digital. License LGPL-3.
import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


STATEMENT_STATES = [
    ("draft", "Draft"),
    ("confirmed", "Confirmed"),
    ("cancelled", "Cancelled"),
    ("bill_created", "Bill Created"),
]


class VendorInvoiceStatement(models.Model):
    _name = "vendor.invoice.statement"
    _description = "Vendor Invoice Human Statement"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Statement Number",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "vendor.invoice.statement"
        ) or _("New"),
    )
    state = fields.Selection(
        selection=STATEMENT_STATES,
        string="Status",
        required=True,
        default="draft",
        index=True,
        copy=False,
    )
    task_id = fields.Many2one(
        "vendor.invoice.import.task",
        string="Import Task",
        required=False,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        store=True,
        index=True,
    )
    source_parse_attempt_id = fields.Many2one(
        "vendor.invoice.import.parse.attempt",
        string="Source Parse Attempt",
        required=False,
        ondelete="restrict",
        index=True,
    )
    source_pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Source PDF",
        ondelete="restrict",
    )
    source_pdf_filename = fields.Char(
        string="File Name",
    )
    source_pdf_upload = fields.Binary(
        string="Upload PDF",
        help="Upload the supplier invoice PDF before starting AI.",
    )
    ai_launch_provider_config_id = fields.Many2one(
        "wd.ai.provider.config",
        string="AI Provider",
        domain="[('active', '=', True)]",
        help="Provider used for the next AI execution before a Task exists.",
    )
    ai_launch_synchronous_parse = fields.Boolean(
        string="Synchronous Parse",
        default=False,
        help="Run the next AI execution in this request instead of using the queue.",
    )
    ai_task_state = fields.Selection(
        related="task_id.state",
        string="AI State",
        readonly=True,
    )
    ai_task_parse_status = fields.Selection(
        selection=[
            ("not_submitted", "Not Submitted"),
            ("queued", "Queued"),
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
            ("superseded", "Superseded"),
        ],
        related="task_id.parse_status",
        string="AI Status",
        readonly=True,
    )
    ai_task_error_summary = fields.Char(
        related="task_id.parse_error_summary",
        string="AI Error",
        readonly=True,
    )
    ai_task_attempt_id = fields.Many2one(
        related="task_id.current_parse_attempt_id",
        string="Current Attempt",
        readonly=True,
    )
    review_warnings = fields.Json(
        string="Review Warnings",
        default=list,
    )
    invoice_number = fields.Char(string="Invoice Number")
    invoice_number_normalized = fields.Char(
        string="Normalized Invoice Number",
        compute="_compute_business_identity",
        store=True,
        index=True,
        copy=False,
        readonly=True,
    )
    invoice_date = fields.Date(string="Invoice Date")
    supplier_id = fields.Many2one("res.partner", string="Supplier")
    supplier_name = fields.Char(string="Supplier")
    supplier_identity_key = fields.Char(
        string="Supplier Identity Key",
        compute="_compute_business_identity",
        store=True,
        index=True,
        copy=False,
        readonly=True,
    )
    currency_id = fields.Many2one("res.currency", string="Currency")
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        readonly=True,
    )
    total_tax = fields.Monetary(
        string="Total Tax",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        readonly=True,
    )
    subtotal = fields.Monetary(
        string="Subtotal",
        currency_field="currency_id",
        compute="_compute_totals",
        store=True,
        readonly=True,
    )
    overall_tax_rate = fields.Float(
        string="Overall Tax Rate",
        compute="_compute_totals",
        store=True,
        readonly=True,
    )
    all_checked = fields.Boolean(
        string="All Checked",
        compute="_compute_all_checked",
        inverse="_inverse_all_checked",
        store=True,
    )
    note = fields.Text(string="Notes")
    vendor_bill_id = fields.Many2one(
        "account.move",
        string="Vendor Bill",
        ondelete="restrict",
        index=True,
        copy=False,
        readonly=True,
    )
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

    def init(self):
        self.env.cr.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                vendor_invoice_statement_business_unique
            ON vendor_invoice_statement (
                company_id,
                supplier_identity_key,
                invoice_number_normalized
            )
            WHERE state != 'cancelled'
              AND supplier_identity_key IS NOT NULL
              AND invoice_number_normalized IS NOT NULL
            """
        )

    @api.depends("invoice_number", "supplier_id", "supplier_name")
    def _compute_business_identity(self):
        for statement in self:
            statement.invoice_number_normalized = self._normalize_invoice_number(
                statement.invoice_number
            )
            statement.supplier_identity_key = (
                "partner:%s" % statement.supplier_id.id
                if statement.supplier_id
                else self._normalize_supplier_name(statement.supplier_name)
            )

    @api.depends(
        "line_ids.amount",
        "line_ids.tax_amount",
        "line_ids.total_amount",
        "currency_id",
    )
    def _compute_totals(self):
        for statement in self:
            subtotal = sum(line.amount or 0.0 for line in statement.line_ids)
            total_tax = sum(line.tax_amount or 0.0 for line in statement.line_ids)
            total_amount = sum(line.total_amount or 0.0 for line in statement.line_ids)
            round_amount = statement.currency_id.round if statement.currency_id else lambda value: value
            statement.subtotal = round_amount(subtotal)
            statement.total_tax = round_amount(total_tax)
            statement.total_amount = round_amount(total_amount)
            statement.overall_tax_rate = (
                (total_tax / subtotal) * 100 if subtotal else 0.0
            )

    @api.depends("line_ids.checked")
    def _compute_all_checked(self):
        for statement in self:
            statement.all_checked = bool(statement.line_ids) and all(
                statement.line_ids.mapped("checked")
            )

    def _inverse_all_checked(self):
        for statement in self:
            if statement.state != "draft":
                raise ValidationError(_("Only draft Statements can change line checks."))
            statement.line_ids.write({"checked": statement.all_checked})

    @staticmethod
    def _normalize_invoice_number(value):
        return re.sub(r"\s+", "", (value or "").strip().upper()) or False

    @staticmethod
    def _normalize_supplier_name(value):
        return re.sub(r"\s+", " ", (value or "").strip().upper()) or False

    def _check_business_duplicate(self, values, exclude_ids=()):
        self.env.flush_all()
        task = (
            self.env["vendor.invoice.import.task"].browse(values["task_id"])
            if values.get("task_id")
            else self
        )
        company_id = values.get("company_id") or task.company_id.id
        invoice_number = values.get("invoice_number", self.invoice_number)
        supplier_id = values.get("supplier_id", self.supplier_id.id)
        supplier_name = values.get("supplier_name", self.supplier_name)
        normalized_invoice = self._normalize_invoice_number(invoice_number)
        supplier_key = (
            "partner:%s" % supplier_id
            if supplier_id
            else self._normalize_supplier_name(supplier_name)
        )
        if not company_id or not normalized_invoice or not supplier_key:
            return
        duplicate = self.search([
            ("company_id", "=", company_id),
            ("supplier_identity_key", "=", supplier_key),
            ("invoice_number_normalized", "=", normalized_invoice),
            ("state", "!=", "cancelled"),
            ("id", "not in", list(exclude_ids)),
        ], limit=1)
        if duplicate:
            raise ValidationError(
                _(
                    "An active Statement already exists for this supplier and "
                    "invoice number: %s."
                ) % duplicate.name
            )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
            raise AccessError(_("Only an AI Invoice User can create a Statement."))
        uploads = []
        for vals in vals_list:
            upload = vals.pop("source_pdf_upload", None)
            filename = vals.get("source_pdf_filename") or "vendor_invoice.pdf"
            if upload and vals.get("source_pdf_attachment_id"):
                raise ValidationError(
                    _("Provide either an uploaded PDF or an existing source attachment, not both.")
                )
            if upload:
                raw = base64.b64decode(upload)
                if not raw:
                    raise ValidationError(_("The supplier invoice PDF cannot be empty."))
                vals["source_pdf_filename"] = filename
            vals.setdefault("company_id", self.env.company.id)
            uploads.append((upload, filename))
        statements = super().create(vals_list)
        for statement, (upload, filename) in zip(statements, uploads):
            if upload:
                attachment = self.env["ir.attachment"].create({
                    "name": filename,
                    "datas": upload,
                    "mimetype": "application/pdf",
                    "res_model": statement._name,
                    "res_id": statement.id,
                })
                super(VendorInvoiceStatement, statement).write({
                    "source_pdf_attachment_id": attachment.id,
                })
        return statements

    def write(self, vals):
        if "state" in vals:
            raise AccessError(_("Statement state must be changed through a transition command."))
        if not self.env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
            raise AccessError(
                _("Only an AI Invoice User can edit a Statement.")
            )
        if any(statement.state != "draft" for statement in self):
            raise ValidationError(_("Only draft Statements can be edited."))
        upload = vals.pop("source_pdf_upload", None)
        if upload:
            if any(statement.task_id for statement in self):
                raise ValidationError(
                    _("The PDF cannot be replaced after an AI Task has been created.")
                )
            raw = base64.b64decode(upload)
            if not raw:
                raise ValidationError(_("The supplier invoice PDF cannot be empty."))
            filename = vals.get("source_pdf_filename")
            if all(
                statement.source_pdf_attachment_id
                and statement.source_pdf_attachment_id.raw == raw
                for statement in self
            ):
                vals.pop("source_pdf_filename", None)
                filename = None
        if any(
            field in vals
            for field in ("task_id", "company_id", "source_parse_attempt_id")
        ):
            raise AccessError(_("Statement execution relations are managed by commands."))
        critical_headers = {
            "supplier_id",
            "supplier_name",
            "invoice_number",
            "invoice_date",
            "currency_id",
        }
        def business_value(record, field):
            current = record[field]
            return current.id if hasattr(current, "id") else str(current or "")

        changed_critical_header = any(
            field in vals and any(
                business_value(statement, field)
                != (
                    vals[field]
                    if field.endswith("_id")
                    else str(vals[field] or "")
                )
                for statement in self
            )
            for field in critical_headers
        )
        for statement in self:
            statement._check_business_duplicate(vals, exclude_ids=(statement.id,))
        result = super().write(vals)
        if upload:
            for statement in self:
                filename_for_statement = (
                    filename
                    or statement.source_pdf_filename
                    or statement.source_pdf_attachment_id.name
                    or "vendor_invoice.pdf"
                )
                current_attachment = statement.source_pdf_attachment_id
                if current_attachment and current_attachment.raw == raw:
                    attachment = current_attachment
                else:
                    attachment = self.env["ir.attachment"].create({
                        "name": filename_for_statement,
                        "datas": upload,
                        "mimetype": "application/pdf",
                        "res_model": statement._name,
                        "res_id": statement.id,
                    })
                    super(VendorInvoiceStatement, statement).write({
                        "source_pdf_attachment_id": attachment.id,
                    })
                    if current_attachment:
                        current_attachment.unlink()
                super(VendorInvoiceStatement, statement).write({
                    "source_pdf_filename": filename_for_statement,
                })
        if changed_critical_header:
            self.line_ids.write({"checked": False})
        return result

    def unlink(self):
        if any(statement.state != "draft" for statement in self):
            raise ValidationError(_("Only draft Statements can be deleted."))
        raise AccessError(
            _("Statement records must be deleted through a Task aggregate command.")
        )

    def action_cancel_statement(self):
        """Cancel the business Statement without changing its review history."""
        self.ensure_one()
        self._check_statement_command_access()
        if self.state != "draft":
            raise ValidationError(_("Only a draft Statement can be cancelled."))
        if self.task_id and self.task_id.state in (
            "to_parse", "parsing", "error", "awaiting_review"
        ):
            self.task_id.action_cancel_task()
        self._aggregate_write({"state": "cancelled"})
        self.message_post(body=_("Statement cancelled by the user."))
        return True

    def action_start_ai(self):
        """Launch AI from the Statement AI/Task workspace."""
        self.ensure_one()
        if not self.env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
            raise AccessError(_("Only an AI Invoice User can start AI parsing."))
        statement = self.env["wd.lock.service"].lock_statement(self.id)
        statement.ensure_one()
        if statement.task_id:
            if statement.task_id.state in ("to_parse", "error", "awaiting_review"):
                statement.task_id.action_rerun_ai()
                return {"type": "ir.actions.client", "tag": "reload"}
            raise ValidationError(
                _("AI cannot be started again from the current Task state.")
            )
        if not statement.source_pdf_attachment_id:
            raise ValidationError(_("Upload a supplier invoice PDF before starting AI."))
        if not statement.ai_launch_provider_config_id:
            raise ValidationError(_("Select an AI provider before running AI."))
        task = self.env["vendor.invoice.import.task"].create({
            "company_id": statement.company_id.id,
            "source_pdf_attachment_id": statement.source_pdf_attachment_id.id,
            "source_pdf_filename": statement.source_pdf_filename,
            "selected_provider_config_id": statement.ai_launch_provider_config_id.id,
            "synchronous_parse": statement.ai_launch_synchronous_parse,
            "statement_id": statement.id,
        })
        statement._aggregate_write({"task_id": task.id})
        from ..services.parse_service import start_parse

        start_parse(
            self.env,
            task.id,
            task.selected_provider_config_id.id,
            synchronous=task.synchronous_parse,
        )
        return {"type": "ir.actions.client", "tag": "reload"}

    def _check_statement_command_access(self):
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can modify a human Statement."))

    def action_apply_ai_candidate_from_statement(self):
        """Apply the current ParseAttempt candidate from the business form."""
        self.ensure_one()
        if not self.task_id:
            raise ValidationError(_("This Statement has no AI Task."))
        return self.task_id.action_apply_ai_candidate_from_statement()

    def action_confirm_from_statement(self):
        """Confirm the current Statement without consulting Task lifecycle."""
        self.ensure_one()
        self._check_statement_command_access()
        if self.state != "draft":
            raise ValidationError(_("Only a draft Statement can be confirmed."))
        if not self.line_ids or not all(line.checked for line in self.line_ids):
            raise ValidationError(
                _("Every Statement line must be checked before confirmation.")
            )
        from ..services.statement_projection import (
            assert_projection_consistent,
            statement_to_human_review_result,
        )

        projection = statement_to_human_review_result(self)
        assert_projection_consistent(self, projection)
        self._aggregate_write({"state": "confirmed"})
        if self.task_id:
            self.task_id.write({"human_review_result": projection})
            self.task_id._log_statement_change(
                "statement_confirm",
                self.source_parse_attempt_id,
                "Human Statement confirmed.",
            )
        else:
            self.message_post(body="Human Statement confirmed.")
        return True

    def action_unconfirm_from_statement(self):
        """Reopen a confirmed Statement without consulting Task lifecycle."""
        self.ensure_one()
        self._check_statement_command_access()
        if self.state != "confirmed":
            raise ValidationError(_("Only a confirmed Statement can be unconfirmed."))
        if self.vendor_bill_id:
            raise ValidationError(
                _("A Statement linked to a Vendor Bill cannot be unconfirmed.")
            )
        self._aggregate_write({"state": "draft"})
        if self.task_id:
            self.task_id._log_statement_change(
                "statement_unconfirm",
                self.source_parse_attempt_id,
                "Human Statement reopened for review.",
            )
        else:
            self.message_post(body="Human Statement reopened for review.")
        return True

    def action_create_vendor_bill_from_statement(self):
        """Create the current Vendor Bill from Statement business data."""
        self.ensure_one()
        from ..services.bill_creator import create_vendor_bill_for_statement

        return create_vendor_bill_for_statement(self.env, self.id)

    def action_open_import_task(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Task"),
            "res_model": "vendor.invoice.import.task",
            "view_mode": "form",
            "res_id": self.task_id.id,
            "target": "current",
        }

    def action_open_source_pdf(self):
        self.ensure_one()
        if not self.source_pdf_attachment_id:
            raise ValidationError(_("This Statement has no source PDF."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Source PDF"),
            "res_model": "ir.attachment",
            "view_mode": "form",
            "res_id": self.source_pdf_attachment_id.id,
            "target": "current",
        }

    def action_open_vendor_bill(self):
        self.ensure_one()
        if not self.vendor_bill_id:
            raise ValidationError(_("This Statement has no Vendor Bill."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Vendor Bill"),
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.vendor_bill_id.id,
            "target": "current",
        }

    @api.model
    def _aggregate_create(self, vals):
        """Persist a validated aggregate command without exposing generic CRUD."""
        self._check_business_duplicate(vals)
        return super().create(vals)

    def _aggregate_write(self, vals):
        for statement in self:
            statement._check_business_duplicate(vals, exclude_ids=(statement.id,))
        return super().write(vals)

    def _aggregate_unlink(self):
        return self.sudo().with_context(statement_aggregate_unlink=True).unlink()

    def _attach_source_pdf_to_chatter(self):
        """Expose the existing Task PDF through native Statement Chatter."""
        self.ensure_one()
        attachment = self.source_pdf_attachment_id or (
            self.task_id.source_pdf_attachment_id if self.task_id else False
        )
        if not attachment or not attachment.exists():
            raise ValidationError(_("The source supplier invoice PDF is missing."))
        if attachment.mimetype != "application/pdf":
            raise ValidationError(_("The source supplier invoice attachment must be a PDF."))
        if attachment not in self.message_ids.mapped("attachment_ids"):
            self.message_post(
                body=_("Source supplier invoice PDF attached."),
                attachment_ids=[attachment.id],
            )
        return attachment


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
    checked = fields.Boolean(string="Checked", default=False)
    description = fields.Text(required=True)
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        domain=[("type", "=", "service")],
    )
    order_no = fields.Char(string="Transport Order No.")
    order_id = fields.Char(string="Transport Order ID")
    quantity = fields.Float(default=1.0)
    price_unit = fields.Monetary(currency_field="currency_id")
    amount = fields.Monetary(required=True, currency_field="currency_id")
    tax_raw_text = fields.Char(string="Tax")
    tax_rate = fields.Float(string="Tax Rate")
    tax_amount = fields.Monetary(string="Tax Amount", currency_field="currency_id")
    total_amount = fields.Monetary(
        string="Total Amount",
        currency_field="currency_id",
    )
    reconciliation_clue = fields.Char(string="Reconciliation Clue")
    charge_details = fields.Text(string="Charge Details")
    tax_ids = fields.Many2many("account.tax", string="Taxes")
    reconciliation_clues = fields.Json(
        string="Reconciliation Clues",
        help="Generic label/value clues preserved for a future reconciliation flow.",
    )
    currency_id = fields.Many2one(
        related="statement_id.currency_id",
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can edit Statement lines."))
        for vals in vals_list:
            statement = self.env["vendor.invoice.statement"].browse(
                vals.get("statement_id")
            )
            if not statement or statement.state != "draft":
                raise ValidationError(_("Only lines of a draft Statement can be created."))
            vals["checked"] = False
            vals.update(self._normalize_amount_values(vals, statement=statement))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can edit Statement lines."))
        if any(line.statement_id.state != "draft" for line in self):
            raise ValidationError(_("Only lines of a draft Statement can be edited."))
        review_inputs = {
            "product_id",
            "description",
            "order_no",
            "order_id",
            "quantity",
            "price_unit",
            "amount",
            "tax_ids",
            "tax_rate",
            "tax_amount",
            "total_amount",
            "tax_raw_text",
            "reconciliation_clue",
            "charge_details",
        }
        materially_changed = any(
            field in vals and any(
                line[field] != vals[field]
                for line in self
            )
            for field in review_inputs
        )
        if {"amount", "tax_rate", "tax_amount", "total_amount"} & set(vals):
            if len(self) != 1:
                raise ValidationError(_("Amount fields must be edited on one line at a time."))
            vals = dict(vals)
            vals.update(self._normalize_amount_values(vals))
        result = super().write(vals)
        if materially_changed:
            super(VendorInvoiceStatementLine, self).write({"checked": False})
        return result

    def unlink(self):
        if not self.env.user.has_group("ai_vendor_invoice.group_reviewer"):
            raise AccessError(_("Only an invoice reviewer can delete Statement lines."))
        if not self.env.context.get("statement_aggregate_unlink"):
            raise AccessError(
                _("Statement lines must be deleted through a Task aggregate command.")
            )
        if any(line.statement_id.state != "draft" for line in self):
            raise ValidationError(_("Only lines of a draft Statement can be deleted."))
        return super().unlink()

    def _normalize_amount_values(self, vals, statement=None, driver=None):
        """Normalize one monetary driver and derive the remaining amounts."""
        monetary_fields = {"amount", "tax_rate", "tax_amount", "total_amount"}
        if not monetary_fields & set(vals):
            return {}
        line = self[:1]
        statement = statement or line.statement_id
        currency = (
            statement.currency_id or self.env.company.currency_id
            if statement
            else self.env.company.currency_id
        )
        round_amount = currency.round
        amount = float(vals.get("amount", line.amount if line else 0.0) or 0.0)
        tax_rate = float(vals.get("tax_rate", line.tax_rate if line else 0.0) or 0.0)
        tax_amount = float(
            vals.get("tax_amount", line.tax_amount if line else 0.0) or 0.0
        )
        total_amount = float(
            vals.get("total_amount", line.total_amount if line else 0.0) or 0.0
        )
        keys = {key for key in monetary_fields if vals.get(key) is not None}
        if driver:
            keys = {driver}
        if "amount" in keys:
            if "tax_rate" in keys:
                tax_amount = amount * tax_rate / 100
            elif "tax_amount" in keys:
                tax_rate = tax_amount / amount * 100 if amount else 0.0
            elif "total_amount" in keys:
                tax_amount = total_amount - amount
                tax_rate = tax_amount / amount * 100 if amount else 0.0
            else:
                tax_amount = amount * tax_rate / 100
        elif "tax_rate" in keys:
            tax_amount = amount * tax_rate / 100
        elif "tax_amount" in keys:
            tax_rate = tax_amount / amount * 100 if amount else 0.0
        elif "total_amount" in keys:
            tax_amount = total_amount - amount
            tax_rate = tax_amount / amount * 100 if amount else 0.0
        if not amount and abs(tax_amount) > currency.rounding / 2:
            raise ValidationError(
                _("Tax amount must be zero when untaxed amount is zero.")
            )
        tax_amount = round_amount(tax_amount)
        total_amount = round_amount(amount + tax_amount)
        return {
            "amount": amount,
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total_amount": total_amount,
        }

    def _apply_amount_onchange(self, driver):
        for line in self:
            values = {
                field_name: line[field_name]
                for field_name in ("amount", "tax_rate", "tax_amount", "total_amount")
            }
            changed = line._normalize_amount_values(values, driver=driver)
            for field_name, value in changed.items():
                line[field_name] = value

    @api.onchange("amount")
    def _onchange_amount(self):
        self._apply_amount_onchange("amount")

    @api.onchange("tax_rate")
    def _onchange_tax_rate(self):
        self._apply_amount_onchange("tax_rate")

    @api.onchange("tax_amount")
    def _onchange_tax_amount(self):
        self._apply_amount_onchange("tax_amount")

    @api.onchange("total_amount")
    def _onchange_total_amount(self):
        self._apply_amount_onchange("total_amount")

    @api.model
    def _aggregate_create(self, vals):
        vals_list = vals if isinstance(vals, list) else [vals]
        normalized = []
        for values in vals_list:
            values = dict(values)
            statement = self.env["vendor.invoice.statement"].browse(
                values["statement_id"]
            )
            values.update(self._normalize_amount_values(values, statement=statement))
            normalized.append(values)
        return super().create(normalized)

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
