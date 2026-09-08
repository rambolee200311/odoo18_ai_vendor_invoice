# Async Queue Technical Spike Report (superseded)

> 本文件中的 `80914` 端口结论错误，已由重跑报告更正。请以
> [async-queue-spike-20260908-rerun.md](./async-queue-spike-20260908-rerun.md)
> 为准。

**日期**：2026-09-08
**范围**：queue_job runtime verification only
**状态**：STOPPED AT GATE A
**生产代码变更**：NO

## Environment

| 项目 | 实际证据 |
|---|---|
| Odoo | `/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo-bin -c odoo.conf --dev=all` |
| HTTP | `127.0.0.1:8091` |
| addons path | `addons,odoo/addons,addons/queue` |
| server-wide modules | `web,queue_job` |
| Odoo workers | `0` |
| queue_job | installed, version `18.0.3.1.3` |
| queue channels | `root:2,root.ai_invoice:2` |
| queue scheme/host/port | `http`, `127.0.0.1`, `80914` |
| PostgreSQL | `127.0.0.1:5555`, database `odoo18e_tms` |
| current queue entry | `vendor.invoice.import.parse.attempt.job_run_parse` |
| current process | one Odoo process, no separate job-runner process found |

The configured queue port `80914` is invalid: TCP ports are limited to
`0..65535`. The active Odoo HTTP port is `8091`. The log shows the embedded
queue runner thread repeatedly waiting, but this does not demonstrate that it
can call a valid runner endpoint.

## Database evidence

`queue_job` is installed. The database currently contains 19 jobs in `done` and
31 in `failed`. The recent AI-related rows include:

| Job | State | Method | Exception |
|---:|---|---|---|
| 85 | failed | `job_run_parse` | `JobFoundDead` |
| 82 | failed | `job_run_parse` | `psycopg2.InterfaceError` |
| 81 | done | `job_run_parse` | none |

Only five ParseAttempt rows currently exist; four have no `queue_job_id` and one
is linked to failed Job 85. Therefore historical `done` rows cannot be treated
as proof of a current end-to-end AI result. No clean no-op queue probe was
executed in this Spike.

## Gate results

### Gate A - basic execution

**NOT RUN / FAIL FOR ACCEPTANCE**

No isolated no-op job was created because the environment check exposed an
invalid queue runner port and the existing records are business ParseAttempt
jobs, not a safe no-op probe. The required enqueue -> worker -> persist -> done
evidence tuple is therefore unavailable.

Required evidence was not produced:

```text
Job ID
Enqueue Time
Start Time
Finish Time
Job State
Worker / Runner Evidence
Result
Exception
```

### Gate B - failure and retry

`NOT_RUN` because Gate A did not pass.

### Gate C - AI pipeline

`NOT_RUN` because Gate A did not pass. No PDF, Provider call, Statement, Prompt,
Schema, Projection, or Mapping was changed or exercised.

## Root cause

**已证实的环境问题**：`odoo.conf` contains `port = 80914` under `[queue_job]`,
which is not a valid TCP port. The Odoo process listens on `8091`, and no
separate runner process was found.

**未证实**：whether correcting the port alone is sufficient. A minimal no-op
probe must be rerun after the smallest configuration correction.

## Minimal fix

1. Do not change AI business code.
2. Correct the queue runner port to the actual reachable Odoo runner port
   (`8091`) or to a separately started valid runner port.
3. Restart the existing Odoo process using the same worktree and configuration.
4. Run one isolated no-op queue task and record all Gate A timestamps and result.
5. Stop again if that probe fails.

This Spike did not modify `odoo.conf`, queue_job, the AI pipeline, or production
data.

## Final status

```text
QUEUE_BASIC_EXECUTION = NOT_RUN
QUEUE_FAILURE_OBSERVABILITY = NOT_RUN
QUEUE_RETRY_BEHAVIOR = NOT_RUN
QUEUE_AI_PIPELINE = NOT_RUN
PRODUCTION_CODE_CHANGED = NO
SYNC_PIPELINE_CHANGED = NO
REDIS_INTRODUCED = NO
RECOMMENDATION = FIX_ENVIRONMENT_THEN_RETEST
```

**NEXT_STEP = STOP_FOR_REVIEW**
