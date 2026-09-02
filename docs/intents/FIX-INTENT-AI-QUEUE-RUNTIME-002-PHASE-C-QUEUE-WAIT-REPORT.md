# FIX-INTENT-AI-QUEUE-RUNTIME-002
## Phase C — Queue Wait Investigation Report

**Investigation type:** read-only  
**Implementation authorized:** no  
**Evidence window:** 2026-08-27, local UI time (UTC database/log timestamps are shown with `+8h` conversion where applicable)

## 1. Executive Summary

Tasks 1689 and 1690 did achieve real concurrent execution and both converged to terminal states. The apparent
`Submitted → Started` waits of 172 seconds and 128 seconds do **not** represent an initial scheduler wait until
18:19:23.

The runtime log proves that:

1. Job 50 (Task 1689) was selected and HTTP-dispatched at `10:16:31.730 UTC` (`18:16:31.730` local).
2. Job 51 (Task 1690) was selected and HTTP-dispatched at `10:17:15.108 UTC` (`18:17:15.108` local).
3. Both HTTP requests reached the queue controller within milliseconds.
4. At `10:19:23.370 UTC`, the runner re-queued both jobs as dead.
5. The runner then dispatched both jobs again at `10:19:23.372 UTC`; both controller requests started at `10:19:23.424–.425 UTC`.
6. The second execution completed successfully at the queue layer and produced the observed concurrent worker intervals.

Therefore, the same-second start is explained as a **common dead-job recovery and redispatch event**. The exact
reason the first execution no longer had a detectable `queue_job_lock` is not proven by the available evidence.
The report does not attribute that missing lock to channel capacity, provider latency, a worker restart, or a
specific cursor failure without evidence.

## 2. Existing Evidence

### 2.1 Durable database records

| Task | Attempt | Queue job | `date_created` UTC | final `date_enqueued` UTC | final `date_started` UTC | final `date_done` UTC | retry | state |
|---|---:|---:|---|---|---|---|---:|---|
| 1689 | 929 | 50 | 10:16:31.7238 | 10:19:23 | 10:19:23.403787 | 10:20:27.236316 | 2 | done |
| 1690 | 930 | 51 | 10:17:15.099651 | 10:19:23 | 10:19:23.403212 | 10:20:45.280280 | 2 | done |

The final `date_enqueued` and `date_started` describe the second attempt. The first dispatch's `date_enqueued`
value was overwritten when the dead-job recovery changed the jobs back to `pending` and the runner dispatched
them again.

### 2.2 Runtime log records

Source: [`odoo_181.log`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice.worktrees/docsintentsinvoice-statement-review/debug_logs/odoo_181.log),
PID 50443.

Evidence includes:

- `10:16:31.729–.730`: Job 50 marked running in `root.ai_invoice` and `root`; runner logs “asking Odoo to run”.
- `10:16:31.740`: Job 50 controller logs `started`.
- `10:17:15.107–.108`: Job 51 marked running and dispatched.
- `10:17:15.123`: Job 51 controller logs `started`.
- `10:19:23.365`: runner marks both jobs running in the in-memory channels.
- `10:19:23.370`: runner logs `Re-queued dead job` for both UUIDs.
- `10:19:23.371–.373`: both jobs are marked pending/running again and dispatched.
- `10:19:23.424–.425`: both controller requests log `started`.
- `10:20:27.238` and `10:20:45.283`: the second executions log `done`.

The provider log records requests during both execution waves. Provider request timestamps alone do not prove
the business Attempt `started_at` write, because the current application logs do not log that write separately.

## 3. Runtime Configuration

Observed configuration, read-only during this Phase C investigation:

```ini
workers = 0
http_port = 8091

[queue_job]
channels = root:2,root.ai_invoice:2
scheme = http
host = 127.0.0.1
port = 8091
```

The `root:2,root.ai_invoice:2` change predates Phase C and was not made by this investigation. No configuration was
changed during this Phase C work.

Runtime observations:

- Odoo PID 50443 remained alive during inspection.
- `pg_stat_activity` showed one active inspection connection and idle Odoo connections; no evidence of an Odoo
  restart in the relevant log interval.
- No child HTTP worker processes were present. With `workers = 0`, queue HTTP dispatch and Odoo request handling
  occur in the same single-process runtime.
- The queue runner emitted regular `select() timeout: 60.00 sec` messages. This proves the runner's select loop was
  alive, but does not prove the notification or dispatch latency for an individual job.
- The available snapshot does not provide per-request HTTP access-log entries, PostgreSQL NOTIFY timestamps, or
  lock acquire/release audit records.

## 4. Task 1689 Full Timeline

Times below use local UI time; source timestamps in the log/database are UTC and are eight hours earlier.

| Point | Timestamp | Evidence | Durable/committed | Confidence |
|---|---|---|---|---|
| T0 user/action enters | 18:16:31 | `submitted_at` and `date_created` | yes | HIGH |
| T1 Attempt created | 18:16:31 | Attempt 929 `submitted_at`; application create path | yes | HIGH |
| T2 queue job created | 18:16:31.7238 | queue job 50 `date_created` | yes | HIGH |
| T3 business transaction commit | UNKNOWN | no commit audit at enqueue boundary | UNKNOWN | LOW |
| T4 job visible to runner | UNKNOWN | notification/discovery timestamp absent | UNKNOWN | LOW |
| T5 PostgreSQL NOTIFY | UNKNOWN | notification payload not logged | UNKNOWN | LOW |
| T6 runner first discovery | 18:16:31.729 (first observed selection) | runner channel log | runner in-memory event | HIGH |
| T7 scheduler selectable | 18:16:31.729–.730 | channel marked running | in-memory event | HIGH |
| T8 HTTP dispatch | 18:16:31.730 | `asking Odoo to run` | request initiated | HIGH |
| T9 HTTP accepted | 18:16:31.740 | controller `started` | queue controller transaction started/committed acquire path per source | HIGH |
| T10 controller processing | 18:16:31.740 | controller log | UNKNOWN beyond entry | HIGH |
| T11 `perform()` / T12 `job_run_parse()` | UNKNOWN | no dedicated entry log | UNKNOWN | LOW |
| T13 Attempt running write | UNKNOWN for first wave | no per-write log; final durable write belongs to second wave | UNKNOWN | LOW |
| T14 Attempt running commit | UNKNOWN | no lifecycle commit audit | UNKNOWN | LOW |
| T15 provider request | 18:16:32.313 | `httpx` provider response log | request completed | HIGH |
| T16 provider end | 18:16:32.313 | HTTP 200 response log | external event | HIGH |
| T17 terminal write | 18:19:23 or later | first-wave terminal write is not separately logged | UNKNOWN | LOW |
| T18 queue terminal | 18:19:23 recovery followed by second run; final done 18:20:27.238 | runner/controller log and DB | yes for final run | HIGH |
| dead recovery | 18:19:23.370 | `Re-queued dead job` | yes | HIGH |
| second controller start | 18:19:23.425 | controller log | yes | HIGH |
| final queue terminal | 18:20:27.238 | controller `done`, DB `done` | yes | HIGH |
| final Attempt/Task terminal | 18:20:27 local UI time | DB snapshot | yes | HIGH |

The first HTTP execution is therefore proven to have started, but the first execution's complete business
transaction timeline is incomplete.

## 5. Task 1690 Full Timeline

| Point | Timestamp | Evidence | Durable/committed | Confidence |
|---|---|---|---|---|
| T0 user/action enters | 18:17:15 | `submitted_at` and `date_created` | yes | HIGH |
| T1 Attempt created | 18:17:15 | Attempt 930 `submitted_at`; application create path | yes | HIGH |
| T2 queue job created | 18:17:15.099651 | queue job 51 `date_created` | yes | HIGH |
| T3 business transaction commit | UNKNOWN | no commit audit | UNKNOWN | LOW |
| T4 job visible to runner | UNKNOWN | no discovery audit | UNKNOWN | LOW |
| T5 PostgreSQL NOTIFY | UNKNOWN | payload not logged | UNKNOWN | LOW |
| T6 runner first discovery | 18:17:15.107 (first observed selection) | runner channel log | in-memory event | HIGH |
| T7 scheduler selectable | 18:17:15.107 | channel marked running | in-memory event | HIGH |
| T8 HTTP dispatch | 18:17:15.108 | `asking Odoo to run` | request initiated | HIGH |
| T9 HTTP accepted | 18:17:15.123 | controller `started` | acquire path entered | HIGH |
| T10 controller processing | 18:17:15.123 | controller log | UNKNOWN beyond entry | HIGH |
| T11 `perform()` / T12 `job_run_parse()` | UNKNOWN | no dedicated entry log | UNKNOWN | LOW |
| T13 Attempt running write | UNKNOWN for first wave | no per-write log | UNKNOWN | LOW |
| T14 Attempt running commit | UNKNOWN | no lifecycle commit audit | UNKNOWN | LOW |
| T15 provider request | 18:17:15.637 | `httpx` provider response log | request completed | HIGH |
| T16 provider end | 18:17:15.637 | HTTP 200 response log | external event | HIGH |
| T17 terminal write | UNKNOWN for first wave | no dedicated log | UNKNOWN | LOW |
| T18 queue terminal | 18:19:23 recovery followed by second run; final done 18:20:45.283 | runner/controller log and DB | yes for final run | HIGH |
| dead recovery | 18:19:23.370 | `Re-queued dead job` | yes | HIGH |
| second controller start | 18:19:23.424 | controller log | yes | HIGH |
| final queue terminal | 18:20:45.283 | controller `done`, DB `done` | yes | HIGH |
| final Attempt/Task terminal | 18:20:45 local UI time | DB snapshot | yes | HIGH |

## 6. Queue Wait Segmentation

The reported waits are calculated from the UI's local timestamps:

```text
Task 1689: 18:19:23 - 18:16:31 = 172 seconds
Task 1690: 18:19:23 - 18:17:15 = 128 seconds
```

The evidence does not support treating the entire interval as scheduler wait:

| Segment | Task 1689 | Task 1690 | Result |
|---|---:|---:|---|
| Business request → durable job creation | approximately 0 sec | approximately 0 sec | observed at creation-second precision |
| Business transaction commit → runner discovery | UNKNOWN | UNKNOWN | commit/NOTIFY/discovery not separately instrumented |
| Runner discovery → scheduler selection | approximately 0 sec | approximately 0 sec | first observed channel selection is immediate |
| Scheduler selection → HTTP dispatch | <0.001 sec | <0.001 sec | log timestamps |
| HTTP dispatch → controller acceptance | 0.010 sec | 0.015 sec | observed |
| HTTP acceptance → final successful Attempt start | UNKNOWN; first wave later recovered | UNKNOWN; first wave later recovered | first wave did not converge to the final durable start |
| Initial dispatch → dead requeue | 171.640 sec | 128.262 sec | observed waiting/recovery interval |

The initial dispatch-to-requeue interval is the only large measured segment. Its internal cause is **UNKNOWN**:
the evidence proves dead-job recovery, but does not prove whether a worker crash, request interruption, lock
release, cursor/transaction issue, or another runtime failure removed the lock. It must not be filled with zero or
assigned to channel capacity.

## 7. Same-Second Start Analysis

`18:19:23` is explained by a common runtime event:

1. `requeue_dead_jobs()` ran at `10:19:23.370 UTC`.
2. It logged both jobs as dead and changed them back to `pending`.
3. The scheduler immediately selected both jobs (`10:19:23.371–.373`).
4. It issued both HTTP requests in the same scheduler pass.
5. Both controller requests entered at `10:19:23.424–.425`.

Thus:

```text
SAME_SECOND_START_EXPLAINED = YES
```

This explains the synchronized second execution, not the underlying reason both first executions became
requeue-eligible. No evidence proves that PostgreSQL LISTEN/NOTIFY, a 60-second select timeout, an HTTP worker
queue, or a service restart caused the common event. Those possibilities remain unproven.

## 8. queue_job Source Semantics

Read-only source reviewed:

- [`runner.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py)
- [`channels.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py)
- [`main.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py)

Relevant behavior:

- `runner.py::run_jobs()` obtains jobs from `channel_manager.get_jobs_to_run()`, sets the database row to
  `enqueued`, then sends the HTTP request.
- `runner.py::wait_notification()` uses PostgreSQL connection notifications and a safety select timeout of
  60 seconds.
- `main.py::_acquire_job()` accepts only `state=enqueued`, sets `started`, stores it, commits, then acquires the
  queue job lock.
- `main.py::_try_perform_job()` executes `job.perform()` and commits the terminal queue state on success.
- `runner.py::_query_requeue_dead_jobs()` considers `enqueued` or `started` jobs older than 10 seconds when the
  corresponding `queue_job_lock` is absent or skip-locked. It changes them to `pending` (or failed after retry
  exhaustion) and increments retry for `started` jobs.

The logs match this recovery algorithm exactly. The source does not identify why the lock was absent in this
specific run.

## 9. Runtime / Worker Evidence

- `workers=0`; no separate Odoo worker process was observed.
- PID 50443 remained alive; no relevant restart marker was found.
- Queue runner was active before and after the recovery event and continued emitting select-loop messages.
- Two jobs were held in the in-memory channel as running before the dead sweep, then both were re-queued together.
- The first-wave provider responses show that the requests progressed beyond HTTP dispatch.
- There is no access log with request completion/status for either first-wave `/queue_job/runjob` request.
- There is no durable queue-lock history, PostgreSQL NOTIFY timestamp, transaction commit trace, or per-stage application
  correlation log for the first wave.

## 10. Root Cause

### Proven runtime fact

`queue_job` treated both first-wave executions as dead because, at the sweep time, their database lock was not
detectable. The runner then re-queued and redispatched them together.

**Confidence:** HIGH  
**Impact:** adds 128–172 seconds to observed Attempt start time and causes misleading “queued” UX.  
**Root cause status:** mechanism proven; underlying lock-loss cause not proven.

### Not proven

The evidence does not distinguish among:

- first HTTP request interruption or incomplete request lifecycle;
- queue lock release before job completion;
- transaction/cursor failure;
- process/runtime scheduling interruption;
- another queue runtime condition.

No claim is made that any one of these caused the event.

## 11. Minimal Fix Proposal (not implemented)

`PROPOSED_MINIMAL_FIX`

1. **Runtime observability first:** add correlation logging around runner dispatch, controller request entry,
   `_acquire_job()` lock acquisition/release, `job.perform()` entry/exit, and request completion. Record job UUID,
   DB PID, process PID, Attempt ID, and timestamps.
2. **Lock/transaction correctness:** verify that the queue job lock remains held for the entire perform lifecycle
   and that no application-owned cursor/transaction operation closes or invalidates the queue controller cursor.
   If a code defect is proven, change only the lifecycle transaction boundary in the queue entry/service layer.
3. **Recovery reconciliation:** retain reconciliation as an exception safety net, but make it explicitly correlate
   a recovered queue retry with the Attempt lifecycle rather than treating a missing lock as a normal long wait.
4. **Environment alternative:** if evidence proves the single-process `workers=0` HTTP runtime is the cause, propose
   a supported worker/runtime configuration separately. Do not apply it based on this report alone.

Potential touched files, only after approval and evidence:

- `addons/ai_vendor_invoice/models/import_parse_attempt.py`
- `addons/ai_vendor_invoice/services/parse_service.py`
- queue runtime configuration or deployment process, if environment evidence proves it necessary
- automated lifecycle/recovery tests

No queue_job source change is proposed at this stage. Ordinary background jobs must remain on `root`; AI jobs
must remain on `root.ai_invoice`. Rollback would be a normal code/config rollback, with no manual database repair.

## 12. Risks

- Additional logging must avoid provider payloads and secrets.
- Changing transaction ownership without a reproduction could reintroduce orphan running Attempts.
- Increasing channel capacity cannot fix a missing queue lock and may increase provider/resource pressure.
- Changing workers or restart behavior without evidence could alter the diagnosis and invalidate comparison.

## 13. Additional Reproduction Requirement

```text
ADDITIONAL_REPRODUCTION_REQUIRED = YES
```

The existing evidence is sufficient to identify dead-job recovery as the measured wait mechanism, but insufficient
to identify the first lock-loss failure point. No new AI job was started in this Phase C investigation.

An approved, single controlled reproduction should add only diagnostic instrumentation (not business behavior):

- enqueue transaction commit timestamp and PostgreSQL backend PID;
- runner notification receipt, first discovery, selection, and HTTP dispatch timestamp;
- HTTP request entry/exit and response status for `/queue_job/runjob`;
- `_acquire_job()` state transition, lock acquisition, and lock release;
- `job.perform()` and `job_run_parse()` entry/exit;
- Attempt running write and commit;
- provider request start/end;
- every rollback/exception with job UUID and backend PID;
- periodic read-only lock presence for the job UUID.

The reproduction must keep `QUEUE_JOB__NO_DELAY` unset and must not modify capacity, retry, timeout, source data,
or database rows.

## 14. Recommended Next Step

Do not enter implementation or run another batch of AI jobs yet. Obtain approval for one diagnostic-only
reproduction with the correlation points above. Use its first failure event to decide whether the minimal fix is:

- application transaction/cursor correctness;
- queue HTTP/runtime lifecycle;
- environment/process configuration;
- or a combination.

## Final Result

```text
CONCURRENCY = PASS
STATE_CONVERGENCE = PASS

TASK_1689_QUEUE_WAIT_SECONDS = 172
TASK_1690_QUEUE_WAIT_SECONDS = 128

QUEUE_WAIT_ROOT_CAUSE = NOT_PROVEN
PRIMARY_WAIT_SEGMENT = UNKNOWN

SAME_SECOND_START_EXPLAINED = YES

CODE_FIX_REQUIRED = UNKNOWN
CONFIG_FIX_REQUIRED = UNKNOWN
ENVIRONMENT_FIX_REQUIRED = UNKNOWN

ADDITIONAL_REPRODUCTION_REQUIRED = YES

PRODUCTION_CODE_CHANGED = NO
QUEUE_JOB_SOURCE_CHANGED = NO
CONFIG_CHANGED = NO
DATABASE_ROWS_MANUALLY_REPAIRED = NO

PHASE_C_IMPLEMENTATION_AUTHORIZED = NO
```
