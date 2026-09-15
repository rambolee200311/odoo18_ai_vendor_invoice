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


def _resolve_line_tax_ids(env, line, company):
    explicit_tax_ids = line.get("tax_ids") or []
    if explicit_tax_ids:
        taxes = env["account.tax"].browse(explicit_tax_ids).exists()
        if len(taxes) != len(explicit_tax_ids) or any(
            tax.company_id and tax.company_id != company for tax in taxes
        ):
            raise ValidationError(_("Statement line tax configuration is invalid."))
        return taxes.ids

    treatment = line.get("tax_treatment")
    if treatment != "percentage":
        raise ValidationError(
            _(
                "A Statement Tax Contract Gap prevents resolving this line's "
                "special tax treatment."
            )
        )
    if line.get("tax_rate") in (None, False, ""):
        raise ValidationError(_("A percentage tax rate is required."))
    rate = _number(line.get("tax_rate"), "0")
    taxes = env["account.tax"].search([
        ("company_id", "=", company.id),
        ("type_tax_use", "=", "purchase"),
        ("amount_type", "=", "percent"),
        ("amount", "=", float(rate)),
        ("active", "=", True),
    ], limit=1)
    if not taxes:
        taxes = env["account.tax"].create({
            "name": "BTW %s%% Purchase" % rate.normalize(),
            "amount": float(rate),
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "company_id": company.id,
        })
    return taxes.ids


def _line_vals(env, line, company, fallback_product=None):
    quantity = Decimal("1")
    amount = line.get("subtotal")
    if amount is None:
        amount = line.get("line_total_amount")
    if amount is None:
        raise ValidationError(_("A confirmed Statement line amount is required."))

    vals = {
        "name": line.get("description") or (
            fallback_product.display_name if fallback_product else _("Vendor invoice line")
        ),
        "quantity": float(quantity),
        "price_unit": float(_number(amount)),
        "tax_ids": [Command.set(_resolve_line_tax_ids(env, line, company))],
        "reconciliation_clues": line.get("reconciliation_clues") or [],
    }
    if line.get("statement_line_id"):
        vals["vendor_statement_line_id"] = line["statement_line_id"]
    if line.get("product_id"):
        vals["product_id"] = line["product_id"]
    elif fallback_product:
        vals["product_id"] = fallback_product.id
    return vals


def _convert_review_to_move_vals(env, review_result, company, default_product):
    header = review_result["header"]
    lines = review_result.get("lines") or []
    if lines:
        invoice_lines = [_line_vals(env, line, company) for line in lines]
    else:
        if not default_product:
            raise ValidationError(
                _("A default fallback product is required for an invoice without lines.")
            )
        invoice_lines = [_line_vals(env, {
            "description": default_product.display_name,
            "subtotal": header["total_amount"],
            "tax_treatment": "percentage",
            "tax_rate": "0",
            "tax_ids": [],
        }, company, fallback_product=default_product)]

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


def _create_bill_for_statement(env, statement, task=None):
    """Create one draft bill from the current Statement business data.

    CC-10: the Statement is the sole business input for Vendor Bill creation.
    Task existence and `Task.state` (including the legacy/deprecated
    `parsed`, `awaiting_review`, `bill_generated` values) are NOT read as a
    precondition here. `task`, when available, is used only to keep the
    legacy Task-facing audit trail and diagnostic `review_warnings` field in
    sync; it is never a business gate for bill creation.
    """
    statement.ensure_one()
    statement = env["wd.lock.service"].lock_statement(statement.id)
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
    company = statement.company_id
    config = env["wd.system.config"].get_config()
    warnings = validation_service.check_amount_balance(
        review_result, company, config.amount_tolerance
    )
    if task:
        # Legacy compatibility surface only; not a business precondition.
        task.write({"review_warnings": warnings})

    move_vals = _convert_review_to_move_vals(
        env, review_result, company, config.default_product_id
    )
    # Keep this explicit even though the environment may have been switched to
    # the Statement's company: asynchronous jobs do not inherit the request
    # company.
    move_vals["company_id"] = company.id
    bill = env["account.move"].create(move_vals)

    source_attachment = statement.source_pdf_attachment_id
    if source_attachment:
        source_attachment.copy({
            "res_model": "account.move",
            "res_id": bill.id,
            "public": False,
        })
    # Statement.vendor_bill_id is the sole writable Bill authority (CC-10
    # 2.1.7); Task.vendor_bill_id is a related, read-only compatibility field
    # and is never written independently.
    statement._aggregate_write({
        "vendor_bill_id": bill.id,
    })
    if task:
        task._log_statement_change(
            "vendor_bill_created",
            statement.source_parse_attempt_id,
            "Draft vendor bill %s linked to Statement." % bill.display_name,
        )
        _audit(env, task, "bill_create", "Draft vendor bill %s created." % bill.display_name)
    return bill


def _create_locked(env, task):
    """Legacy Task-facing entry point retained for existing direct callers.

    CC-10: `Task.state` is no longer read as a precondition. A Statement is
    still required here because, in this contract, a Task owns exactly one
    Statement; the actual business input and preconditions are resolved from
    that Statement, not from the Task.
    """
    # The task carries the authoritative company for asynchronous workers.
    env = task.env
    if not task.statement_id:
        raise ValidationError(_("A Statement is required before creating a bill."))
    return _create_bill_for_statement(env, task.statement_id, task=task)


def create_vendor_bill(env, task_id):
    """Legacy Task-facing compatibility entry point.

    CC-10: business authority for bill creation now lives on the Statement
    (see `create_vendor_bill_for_statement`). This wrapper is kept only for
    existing Task-facing callers and resolves the Task's Statement before
    delegating; it does not gate on `Task.state`.
    """
    with env.cr.savepoint():
        task = env["wd.lock.service"].lock_task(task_id)
        task.ensure_one()
        task = task.with_company(task.company_id)
        return _create_locked(env, task)


def create_vendor_bill_for_statement(env, statement_id):
    """Statement-facing Bill Creator entry point (CC-10).

    Accepts a Statement as its business input and does not require a Task or
    a particular `Task.state`. Vendor Bill input is read only from the
    current Statement data, and only `Statement.vendor_bill_id` is written as
    the Bill authority.
    """
    with env.cr.savepoint():
        statement = env["vendor.invoice.statement"].browse(statement_id)
        if not statement.exists():
            raise ValidationError(_("The Statement no longer exists."))
        task = statement.task_id
        # The existing Task/Statement compatibility relationship is used only
        # to keep the current row-locking behavior; it is not a business
        # precondition (CC-10 2.1.2).
        if task:
            task = task.with_company(task.company_id)
            statement = env["wd.lock.service"].lock_statement(statement.id)
        return _create_bill_for_statement(statement.env, statement, task=task)


def confirm_review_and_create_bill(env, task_id, review_payload):
    """Persist review data and create the bill as one atomic operation.

    CC-10: this legacy Task-owned combo command no longer reads `Task.state`
    (including the legacy/deprecated values) as a Confirm or Create Bill
    precondition; confirmability and bill eligibility are decided by the
    Statement-facing commands it delegates to.
    """
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
        return _create_locked(env, task)
