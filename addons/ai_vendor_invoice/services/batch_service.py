# © 2024 Wukong Digital. License LGPL-3.
"""CC-14 Batch orchestration service.

Owns the multi-PDF preflight, per-file failure isolation for the initial
Batch launch, and the Retry Selected eligibility/isolation rules. Every
actual Statement launch (create-or-reuse Task + start the ParseAttempt)
goes through the shared ``statement_launch_service.launch_statement_ai``
boundary (CC-14 §13) so Batch never re-implements CC-13 launch mechanics.

See docs/intents/CC-14-MULTI-PDF-BATCH-IMPORT-SELECTED-RETRY.md.
"""
import base64
import hashlib

from odoo import _, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from psycopg2 import IntegrityError

from .statement_launch_service import launch_statement_ai


def _decode_and_validate_pdf(upload):
    """Return ``(raw_bytes, error_message)``; error_message is falsy if valid."""
    if not upload:
        return None, _("The uploaded file is empty.")
    try:
        raw = base64.b64decode(upload)
    except Exception:
        return None, _("The uploaded file could not be decoded.")
    if not raw:
        return None, _("The uploaded file is empty.")
    if not raw.startswith(b"%PDF"):
        return None, _("The uploaded file is not a valid PDF.")
    return raw, None


def start_batch(env, company_id, provider_config_id, files):
    """Run the CC-14 multi-PDF preflight and initial async launch.

    ``files`` is an iterable of ``(pdf_upload_base64, filename)`` tuples, one
    per selected PDF. Rejected files (empty, not a PDF, or a checksum
    duplicate) are reported immediately and never create a persisted
    Statement or Batch member (CC-14 §6/§10). Each accepted file is created
    and launched as an independently recoverable unit (CC-14 §15): a
    per-file failure never rolls back an already-accepted sibling file and
    never blocks the remaining files.

    Returns ``(batch, results)`` where ``results`` is a list of per-file
    outcome dicts: ``filename``, ``status`` (accepted/rejected/launch_failed),
    ``statement_id``, ``task_id``, ``message``.
    """
    if not env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
        raise AccessError(_("Only an AI Invoice User can start a Batch import."))
    files = list(files)
    if not files:
        raise ValidationError(_("Upload at least one supplier invoice PDF."))
    provider = env["wd.ai.provider.config"].browse(provider_config_id)
    if not provider.exists() or not provider.active:
        raise ValidationError(_("Select an active AI provider before starting a Batch."))

    batch = env["vendor.invoice.batch"].create({
        "company_id": company_id,
        "provider_config_id": provider_config_id,
        "started_at": fields.Datetime.now(),
    })

    Task = env["vendor.invoice.import.task"]
    seen_checksums = {}
    results = []
    for upload, filename in files:
        filename = filename or "vendor_invoice.pdf"
        outcome = {
            "filename": filename,
            "statement_id": False,
            "task_id": False,
            "message": False,
        }
        raw, error = _decode_and_validate_pdf(upload)
        if error:
            outcome.update(status="rejected", message=error)
            results.append(outcome)
            continue
        checksum = hashlib.sha256(raw).hexdigest()
        if checksum in seen_checksums:
            outcome.update(
                status="rejected",
                message=_(
                    "Duplicate PDF already selected in this Batch as %s."
                ) % seen_checksums[checksum],
            )
            results.append(outcome)
            continue
        duplicate_task = Task.search([
            ("company_id", "=", company_id),
            ("source_pdf_checksum", "=", checksum),
            ("state", "!=", "cancelled"),
        ], limit=1)
        if duplicate_task:
            outcome.update(
                status="rejected",
                message=_("This PDF was already imported as Task %s.") % duplicate_task.name,
            )
            results.append(outcome)
            continue
        seen_checksums[checksum] = filename
        try:
            with env.cr.savepoint():
                statement = env["vendor.invoice.statement"].create({
                    "company_id": company_id,
                    "source_pdf_upload": upload,
                    "source_pdf_filename": filename,
                    "batch_id": batch.id,
                    "ai_launch_provider_config_id": provider_config_id,
                    "ai_launch_synchronous_parse": False,
                })
                launch_statement_ai(env, statement.id)
            outcome.update(
                status="accepted",
                statement_id=statement.id,
                task_id=statement.task_id.id,
            )
        except (AccessError, IntegrityError, UserError, ValueError) as error:
            env.invalidate_all()
            outcome.update(status="launch_failed", message=str(error))
        results.append(outcome)
    _post_batch_start_summary(batch, results)
    return batch, results


def retry_selected(env, batch_id, statement_ids):
    """CC-14 §18/§19/§20 Retry Selected orchestration.

    Only Statements that belong to ``batch_id`` and currently satisfy the
    frozen eligibility (current Task state == error, Statement Draft, no
    active Attempt) are retried; every other selected Statement is reported
    as a per-item rejection. Each retry keeps the same Statement, the same
    Task, uses the same Provider, creates a new ParseAttempt, and runs
    asynchronously through the shared launch boundary. A retry failure for
    one Statement never affects the outcome already recorded for another.
    """
    batch = env["vendor.invoice.batch"].browse(batch_id)
    batch.ensure_one()
    if not env.user.has_group("ai_vendor_invoice.group_ai_invoice_user"):
        raise AccessError(_("Only an AI Invoice User can retry a Batch Statement."))
    statements = env["vendor.invoice.statement"].browse(statement_ids)
    Attempt = env["vendor.invoice.import.parse.attempt"]
    results = []
    for statement in statements:
        outcome = {
            "statement_id": statement.id,
            "filename": statement.source_pdf_filename,
            "message": False,
        }
        if statement.batch_id.id != batch.id:
            outcome.update(
                status="rejected",
                message=_("This Statement does not belong to the selected Batch."),
            )
            results.append(outcome)
            continue
        if statement.state != "draft":
            outcome.update(
                status="rejected",
                message=_("Only a draft Statement can be retried."),
            )
            results.append(outcome)
            continue
        task = statement.task_id
        if not task or task.state != "error":
            outcome.update(
                status="rejected",
                message=_(
                    "Retry Selected is only allowed for a current failed AI result."
                ),
            )
            results.append(outcome)
            continue
        active_attempt = Attempt.search([
            ("task_id", "=", task.id),
            ("status", "in", ("queued", "running")),
        ], limit=1)
        if active_attempt:
            outcome.update(
                status="rejected",
                message=_("This Task already has an AI parse attempt in progress."),
            )
            results.append(outcome)
            continue
        try:
            with env.cr.savepoint():
                launch_statement_ai(env, statement.id)
            outcome.update(status="accepted")
        except (AccessError, IntegrityError, UserError, ValueError) as error:
            env.invalidate_all()
            outcome.update(status="failed", message=str(error))
        results.append(outcome)
    _post_retry_summary(batch, results)
    return results


def _post_batch_start_summary(batch, results):
    lines = [_("Batch import started (%s file(s)):") % len(results)]
    for outcome in results:
        if outcome["status"] == "accepted":
            lines.append(_("- %s: accepted") % outcome["filename"])
        else:
            lines.append(
                "- %s: %s (%s)" % (
                    outcome["filename"], outcome["status"], outcome.get("message") or "",
                )
            )
    batch.message_post(body="<br/>".join(lines))


def _post_retry_summary(batch, results):
    if not results:
        return
    lines = [_("Retry Selected (%s Statement(s)):") % len(results)]
    for outcome in results:
        lines.append(
            "- Statement #%s: %s (%s)" % (
                outcome["statement_id"], outcome["status"], outcome.get("message") or "",
            )
        )
    batch.message_post(body="<br/>".join(lines))
