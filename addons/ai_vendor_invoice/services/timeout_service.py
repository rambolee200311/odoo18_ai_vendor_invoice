# © 2024 Wukong Digital. License LGPL-3.
"""Task-level timeout recovery for queue workers that stopped responding."""

from odoo import _, fields


def check_parsing_timeout(env):
    """Mark overdue queued/running tasks and their current attempt as failed."""
    config = env["wd.system.config"].get_config()
    timeout = config.task_timeout
    now = fields.Datetime.from_string(fields.Datetime.now())
    count = 0

    candidates = env["vendor.invoice.import.task"].search([
        ("state", "=", "parsing"),
        ("enter_parsing_datetime", "!=", False),
    ])
    for candidate in candidates:
        entered = fields.Datetime.from_string(candidate.enter_parsing_datetime)
        if not entered or now - entered <= timeout:
            continue

        with env.cr.savepoint():
            task = env["wd.lock.service"].lock_task(candidate.id)
            task.ensure_one()
            if task.state != "parsing" or not task.enter_parsing_datetime:
                continue
            entered = fields.Datetime.from_string(task.enter_parsing_datetime)
            if not entered or now - entered <= timeout:
                continue
            attempt = task.current_parse_attempt_id
            if not attempt or attempt.status not in ("queued", "running"):
                continue
            attempt = env["wd.lock.service"].lock_attempt(attempt.id)
            attempt.write({
                "status": "failed",
                "finished_at": fields.Datetime.now(),
                "error_message": _(
                    "Task parsing timeout exceeded; worker did not complete."
                ),
            })
            task.write({"state": "error_timeout"})
            env["vendor.invoice.import.log"].create({
                "task_id": task.id,
                "parse_attempt_id": attempt.id,
                "action": "cron_timeout",
                "snapshot_delta": "Parsing lifecycle exceeded configured timeout.",
            })
            count += 1
    return count
