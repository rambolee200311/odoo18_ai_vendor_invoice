# © 2024 Wukong Digital. License LGPL-3.
"""Shared single-Statement AI launch boundary (CC-14 §13).

Both the Statement UI action (``action_start_ai``) and the CC-14 Batch
orchestrator must go through this single launch boundary, so a
Statement/Task/ParseAttempt launch is created and started identically
regardless of the caller:

    saved Statement
    -> lock/recheck
    -> validate PDF
    -> validate Provider
    -> create/reuse one Task
    -> copy launch configuration
    -> establish Statement/Task relation
    -> call ParseService.start_parse()
    -> return Task/Attempt result

This module intentionally contains no Batch-specific logic; Batch
orchestration (preflight, per-file isolation, Retry Selected eligibility)
lives in ``services/batch_service.py`` and calls this boundary once per
Statement, exactly like the Statement UI action does.
"""
from odoo import _
from odoo.exceptions import AccessError, ValidationError


def launch_statement_ai(env, statement_id):
    """Launch (or rerun) AI parsing for exactly one Statement.

    Returns the resulting ``vendor.invoice.import.task`` record.
    """
    if not env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
        raise AccessError(_("Only an AI Invoice User can start AI parsing."))
    statement = env["wd.lock.service"].lock_statement(statement_id)
    statement.ensure_one()
    if statement.task_id:
        if statement.task_id.state not in ("to_parse", "error", "awaiting_review"):
            raise ValidationError(
                _("AI cannot be started again from the current Task state.")
            )
        statement.task_id.action_rerun_ai()
        return statement.task_id
    if not statement.source_pdf_attachment_id:
        raise ValidationError(_("Upload a supplier invoice PDF before starting AI."))
    if not statement.ai_launch_provider_config_id:
        raise ValidationError(_("Select an AI provider before running AI."))
    task = env["vendor.invoice.import.task"].create({
        "company_id": statement.company_id.id,
        "source_pdf_attachment_id": statement.source_pdf_attachment_id.id,
        "source_pdf_filename": statement.source_pdf_filename,
        "selected_provider_config_id": statement.ai_launch_provider_config_id.id,
        "synchronous_parse": statement.ai_launch_synchronous_parse,
        "statement_id": statement.id,
    })
    statement._aggregate_write({"task_id": task.id})
    from .parse_service import start_parse

    start_parse(
        env,
        task.id,
        task.selected_provider_config_id.id,
        synchronous=task.synchronous_parse,
    )
    return task
