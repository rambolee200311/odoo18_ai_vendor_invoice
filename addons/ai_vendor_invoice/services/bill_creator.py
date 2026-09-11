# © 2024 Wukong Digital. License LGPL-3.
"""Creation of draft vendor bills from the reviewed value object only."""

from decimal import Decimal, InvalidOperation

from odoo import _
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command

from . import validation_service


def _number(value, default="0"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _line_vals(line, fallback_product=None):
    quantity = _number(line.get("quantity"), "1")
    if not quantity:
        quantity = Decimal("1")
    unit_price = line.get("unit_price")
    if unit_price is None:
        subtotal = line.get("subtotal")
        if subtotal is None:
            subtotal = line.get("line_total_amount")
        unit_price = _number(subtotal) / quantity

    vals = {
        "name": line.get("description") or (
            fallback_product.display_name if fallback_product else _("Vendor invoice line")
        ),
        "quantity": float(quantity),
        "price_unit": float(_number(unit_price)),
        "tax_ids": [Command.set(line.get("tax_ids") or [])],
        "reconciliation_clues": line.get("reconciliation_clues") or [],
    }
    if line.get("statement_line_id"):
        vals["vendor_statement_line_id"] = line["statement_line_id"]
    if line.get("product_id"):
        vals["product_id"] = line["product_id"]
    elif fallback_product:
        vals["product_id"] = fallback_product.id
    return vals


def _convert_review_to_move_vals(review_result, default_product):
    header = review_result["header"]
    lines = review_result.get("lines") or []
    if lines:
        invoice_lines = [_line_vals(line) for line in lines]
    else:
        if not default_product:
            raise ValidationError(
                _("A default fallback product is required for an invoice without lines.")
            )
        invoice_lines = [_line_vals({
            "description": default_product.display_name,
            "quantity": "1",
            "unit_price": header["total_amount"],
            "tax_ids": [],
        }, fallback_product=default_product)]

    return {
        "move_type": "in_invoice",
        "partner_id": header["supplier_id"],
        "invoice_date": header["invoice_date"],
        "currency_id": header["currency_id"],
        "ref": header["invoice_number"],
        "vendor_invoice_statement_id": review_result.get("statement_id"),
        "invoice_line_ids": [Command.create(line) for line in invoice_lines],
    }


def _audit(env, task, action, summary):
    env["vendor.invoice.import.log"].create({
        "task_id": task.id,
        "parse_attempt_id": task.current_parse_attempt_id.id,
        "action": action,
        "snapshot_delta": summary,
    })


def _create_locked(env, statement):
    """Create a bill from the current Statement projection."""
    if statement._name == "vendor.invoice.import.task":
        statement = statement.statement_id
    statement.ensure_one()
    task = statement.task_id
    env = statement.env
    company = statement.company_id
    if statement.state != "confirmed":
        raise ValidationError(
            _("A Statement must be confirmed before creating a bill.")
        )
    if statement.vendor_bill_id:
        raise ValidationError(_("A bill is already linked to this Statement."))
    if not statement.line_ids or not all(statement.line_ids.mapped("checked")):
        raise ValidationError(
            _("Every current Statement Line must be checked before creating a bill.")
        )
    from .statement_projection import statement_to_human_review_result

    review_result = statement_to_human_review_result(statement)
    validation_service.pre_check_integrity(review_result)
    config = env["wd.system.config"].get_config()
    warnings = validation_service.check_amount_balance(
        review_result, company, config.amount_tolerance
    )
    statement._aggregate_write({"review_warnings": warnings})

    move_vals = _convert_review_to_move_vals(
        review_result, config.default_product_id
    )
    move_vals["company_id"] = company.id
    bill = env["account.move"].create(move_vals)

    if statement.source_pdf_attachment_id:
        statement.source_pdf_attachment_id.copy({
            "res_model": "account.move",
            "res_id": bill.id,
            "public": False,
        })
    statement._aggregate_write({
        "vendor_bill_id": bill.id,
    })
    summary = "Draft vendor bill %s linked to Statement." % bill.display_name
    if task:
        task._log_statement_change(
            "vendor_bill_created",
            statement.source_parse_attempt_id,
            summary,
        )
        _audit(env, task, "bill_create", "Draft vendor bill %s created." % bill.display_name)
    else:
        statement.message_post(body=summary)
    return bill


def create_vendor_bill_for_statement(env, statement_id):
    """Create one draft bill from a Statement in the caller's transaction."""
    with env.cr.savepoint():
        statement = env["vendor.invoice.statement"].browse(statement_id).exists()
        statement.ensure_one()
        if statement.task_id:
            task = env["wd.lock.service"].lock_task(statement.task_id.id)
            task.ensure_one()
            statement = statement.with_company(statement.company_id)
        else:
            statement = env["wd.lock.service"].lock_statement(statement.id)
            statement = statement.with_company(statement.company_id)
        return _create_locked(env, statement)


def create_vendor_bill(env, task_id):
    """Legacy Task-facing wrapper; business input remains the Statement."""
    task = env["vendor.invoice.import.task"].browse(task_id).exists()
    task.ensure_one()
    if not task.statement_id:
        raise ValidationError(_("A Statement is required before creating a bill."))
    return create_vendor_bill_for_statement(env, task.statement_id.id)


def confirm_review_and_create_bill(env, task_id, review_payload):
    """Persist review data and create the bill as one atomic operation."""
    if not env.user.has_group("ai_vendor_invoice.group_reviewer"):
        raise AccessError(_("Only an invoice reviewer can confirm a bill."))
    if not isinstance(review_payload, dict) or not review_payload:
        raise ValidationError(_("A non-empty review result is required."))

    with env.cr.savepoint():
        task = env["wd.lock.service"].lock_task(task_id)
        task.ensure_one()
        task = task.with_company(task.company_id)
        if task.statement_id:
            task.action_confirm_statement(review_payload)
        else:
            task.write({
                "human_review_result": review_payload,
            })
        _audit(env, task, "human_modify", "Human review confirmed.")
        return _create_locked(env, task.statement_id)
