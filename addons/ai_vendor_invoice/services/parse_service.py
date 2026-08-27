# © 2024 Wukong Digital. License LGPL-3.
from odoo import fields

from ..adapters import (
    AIProviderPermanentError,
    AIProviderTemporaryError,
    adapter_for,
)
from ..adapters.deepseek import (
    EXTRACTION_CONTRACT_VERSION,
    PROMPT_VERSION,
)
from .mapping_service import do_mapping
from .pdf_preprocessor import PDFPreprocessorError, prepare_provider_input


def _audit(env, task, attempt, action, snapshot_delta):
    env["vendor.invoice.import.log"].create({
        "task_id": task.id,
        "parse_attempt_id": attempt.id if attempt else False,
        "action": action,
        "snapshot_delta": snapshot_delta,
    })


def start_parse(env, task_id, provider_config_id):
    task = env["wd.lock.service"].lock_task(task_id)
    task.ensure_one()
    if task.state not in ("to_parse", "awaiting_review", "error_ai_unavailable",
                          "error_timeout", "error_split_required"):
        raise ValueError("Task cannot start an AI parse in its current state.")
    provider_config = env["wd.ai.provider.config"].browse(provider_config_id)
    attempt = env["vendor.invoice.import.parse.attempt"].create({
        "task_id": task.id,
        "sequence": task._get_next_attempt_sequence(),
        "provider_config_id": provider_config_id,
        "status": "queued",
        "prompt_version": PROMPT_VERSION,
        "extraction_contract_version": EXTRACTION_CONTRACT_VERSION,
        "model_name_snapshot": provider_config.model_name,
    })
    task.write({
        "current_parse_attempt_id": attempt.id,
        "state": "parsing",
        "enter_parsing_datetime": fields.Datetime.now(),
        "human_reviewed": False,
    })
    _audit(env, task, attempt, "ai_re_run" if attempt.sequence > 1 else "ai_parse",
           "Queued parse attempt %s" % attempt.sequence)
    attempt.action_enqueue_parse()
    return attempt


def run_parse_attempt(env, task_id, attempt_id):
    task = env["vendor.invoice.import.task"].browse(task_id)
    task = task.with_company(task.company_id)
    attempt = env["vendor.invoice.import.parse.attempt"].browse(attempt_id)
    attempt.ensure_one()
    if not (task.state == "parsing" and task.current_parse_attempt_id == attempt
            and attempt.status in ("queued", "running")):
        attempt.write({
            "status": "superseded",
            "error_message": "Stale worker skipped; attempt superseded by newer attempt.",
        })
        return False
    attempt.write({
        "status": "running",
        "started_at": fields.Datetime.now(),
        "last_activity_at": fields.Datetime.now(),
    })
    try:
        provider_input = prepare_provider_input(task.source_pdf_attachment_id)
        canonical, raw = adapter_for(env, attempt.provider_config_id).parse_pdf(
            provider_input, attempt.provider_config_id,
            attempt.provider_config_id.max_internal_retry, attempt,
        )
    except PDFPreprocessorError as error:
        attempt.write({
            "status": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": str(error),
        })
        return False
    except (AIProviderTemporaryError, AIProviderPermanentError) as error:
        attempt.write({
            "status": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": str(error),
        })
        if task.current_parse_attempt_id == attempt:
            task.write({"state": "error_ai_unavailable"})
            _audit(env, task, attempt, "ai_parse", "AI parse failed.")
        return False
    mapping = do_mapping(env, canonical)
    attachment = env["ir.attachment"].create({
        "name": "ai-response-%s.json" % attempt.sequence,
        "type": "binary",
        "datas": raw,
        "res_model": attempt._name,
        "res_id": attempt.id,
        "public": False,
    })
    # Re-check after HTTP/mapping: the worker may have been superseded.
    if not (task.state == "parsing" and task.current_parse_attempt_id == attempt
            and attempt.status == "running"):
        attempt.write({
            "status": "superseded",
            "canonical_result": canonical,
            "mapping_result": mapping,
            "raw_response_attachment_id": attachment.id,
            "finished_at": fields.Datetime.now(),
        })
        return False
    attempt.write({
        "status": "success",
        "canonical_result": canonical,
        "mapping_result": mapping,
        "raw_response_attachment_id": attachment.id,
        "finished_at": fields.Datetime.now(),
        "last_activity_at": fields.Datetime.now(),
    })
    task.write({"state": "error_split_required" if canonical.get("is_multi_invoice")
                else "awaiting_review"})
    _audit(env, task, attempt, "ai_parse", "AI parse completed successfully.")
    return True
