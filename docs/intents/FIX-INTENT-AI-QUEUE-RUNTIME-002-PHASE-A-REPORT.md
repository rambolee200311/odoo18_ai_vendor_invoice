# FIX-INTENT-AI-QUEUE-RUNTIME-002 - Phase A Investigation Report

> Status: Investigation only. No fix implemented.
> Observation date: 2026-08-27
> Database: `odoo18e_tms`
> Configuration under test: `root:1,root.ai_invoice:2`

## 1. Executive result

The queue hierarchy is proven to be a limiting factor for two concurrent
`root.ai_invoice` jobs: child jobs consume capacity in every parent channel,
and only jobs that reach the root channel are sent to the Odoo HTTP endpoint.
With `root:1`, the configuration cannot provide two simultaneous worker
requests through `root.ai_invoice`.

The investigation also found an independent state-convergence failure. Jobs
41 and 42 were repeatedly represented as scheduler/channel running, pending,
and requeued while the ParseAttempt rows did not converge. The available logs
do not prove a complete provider interval for either task, so concurrency is
not credited as a pass.

## 2. Channel hierarchy findings

The local OCA queue_job source proves the following:

- [`Channel.get_jobs_to_run()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py:528)
  recursively obtains jobs from child channels, adds them to the parent
  queue, and yields only while the current channel has capacity.
- [`Channel.set_running()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py:496)
  adds a running job to the child and recursively to every parent.
- [`Channel.has_capacity()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py:519)
  checks the current channel's running set.
- [`QueueJobRunner.run_jobs()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py:414)
  sends an HTTP request only for jobs yielded by the root traversal.
- The source documentation in [`channels.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py:360)
  explicitly states that downstream capacity limits upstream channels and that
  only jobs marked running in root are sent to Odoo.

Therefore:

```text
root:1
  root.ai_invoice:2
```

means a child capacity of two, but a downstream/root capacity of one. Two jobs
can be marked running in the child's in-memory queue, while only one can pass
the root capacity gate and receive an HTTP request. `root.ai_invoice:2` under
`root:1` cannot produce two actual worker executions at the same time.

## 3. Task 1584 / 1585 timeline

Times below are database/log local timestamps. Where the available evidence
cannot correlate a provider event to a specific job, the value is `UNKNOWN`.

| Event | Task 1584 / Attempt 852 / Job 41 | Task 1585 / Attempt 853 / Job 42 |
| --- | --- | --- |
| Business enqueue | 08:16:18 | 08:18:44 |
| Persisted channel | `root.ai_invoice` | `root.ai_invoice` |
| Queue job persisted | PASS, job 41 | PASS, job 42 |
| Scheduler child pending | 08:16:18.813 | 08:18:44.042 |
| Scheduler child running | 08:16:18.813 | 08:18:44.043 |
| Root running | 08:16:43.820 | UNKNOWN |
| Scheduler HTTP request | 08:16:43.820 | UNKNOWN |
| HTTP worker endpoint entered | 08:16:43.833 | UNKNOWN |
| Attempt `running` durable write | UNKNOWN; row later showed running | UNKNOWN; row remained queued |
| Provider request start/end | UNKNOWN per task | UNKNOWN per task |
| Retry/postpone/requeue | Requeued as dead at 08:19:17.082 and repeatedly thereafter | Re-entered child pending at 08:19:17.076 and remained pending |
| Attempt terminal | NOT OBSERVED; row remained running | NOT OBSERVED; row remained queued |
| Queue terminal | NOT OBSERVED; job row remained pending/started across recovery | NOT OBSERVED; job row remained pending |

The provider `HTTP 200` lines in the log cannot safely be assigned to Task
1584 or 1585 because the log has no task/job correlation identifier. They are
not used as proof of either task's provider interval.

## 4. Jobs 41 / 42 pending and requeue analysis

The scheduler log shows Job 42 marked running in the child but no corresponding
`asking Odoo to run job 42` line before recovery. This is consistent with the
root capacity gate: child state is not equivalent to dispatched worker state.

The source recovery SQL in
[`QueueJobRunner._query_requeue_dead_jobs()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py:215)
changes old `enqueued` or `started` jobs to `pending` when the lock is absent or
skippable. A started job increments `retry`; after the retry limit it becomes
`failed` with `JobFoundDead`.

The source comments state that this handles:

- a crashed or force-stopped worker that released its lock;
- an orphaned `enqueued` job whose HTTP request never reached Odoo.

Observed evidence:

- Job 41 was marked root running and its endpoint logged `started`.
- Job 42 was marked child running, but worker dispatch is not evidenced.
- Job 41 was logged as `Re-queued dead job` at 08:19:17.082.
- Both jobs were repeatedly returned to child pending/running in scheduler
  memory.
- No evidence proves a normal completed retry, a terminal failure, or a
  successful worker completion for either job.

Classification: the observed pending transitions are **scheduler dead-job
recovery/requeue**, with the exact initiating event (HTTP failure, worker
termination, or lock loss) **not fully proven** from the available logs.

## 5. Attempt queued versus scheduler running

The queue scheduler's `running` is an in-memory channel state. In
[`Channel.set_running()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/channels.py:496),
it means the job has moved downstream in the channel graph; it does not mean
the HTTP endpoint has started.

The worker endpoint acquires a job in
[`RunJobController._acquire_job()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py:55):

1. select the row in `enqueued` state;
2. call `job.set_started()`;
3. store and commit the queue-job state;
4. acquire the lock.

The AI Attempt lifecycle write is in
[`run_parse_attempt()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice.worktrees/docsintentsinvoice-statement-review/addons/ai_vendor_invoice/services/parse_service.py:106)
and is invoked after the queue endpoint has entered the model job. The current
publisher attempts to write `running` in a separate `db_connect()` cursor at
[`_publish_attempt_running()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice.worktrees/docsintentsinvoice-statement-review/addons/ai_vendor_invoice/services/parse_service.py:50).

This creates a real observability gap: scheduler running, queue-job started,
HTTP request entered, and Attempt running are separate events and transactions.
For Task 1585, only the first two child-channel events are proven; its Attempt
remaining queued is therefore not contradictory to the scheduler's in-memory
child state, but it is a state-convergence failure once the job is no longer
actively executable.

## 6. Cursor and transaction classification

| Signal | Classification | Evidence and interpretation |
| --- | --- | --- |
| `cursor already closed` | CONSEQUENCE; originating trigger NOT_REPRODUCIBLE in this run | Historical queue-controller traceback occurred while persisting Attempt data. It demonstrates a failed request/transaction path, but does not prove which cursor owner closed it. |
| `psycopg2.InterfaceError` | CONSEQUENCE; originating trigger NOT_REPRODUCIBLE in this run | Same historical traceback family; it can prevent job and Attempt convergence but was not observed as a new, task-correlated 41/42 root event in this run. |
| `JobFoundDead` | CONSEQUENCE of lost/absent queue lock or unreachable worker | This is explicitly produced by the runner dead-job recovery SQL after retry exhaustion; it is a recovery classification, not proof of the original crash. |
| `OperationalError` / serialization failure | CAUSE of the observed Attempt write failure; task correlation to 41/42 NOT_PROVEN | The log contains `could not serialize access due to concurrent update` during an Attempt update, followed by queue postponement/retry behavior. It can cause state divergence, but the logged row was not conclusively 852/853. |

The current AI worker does create an independent cursor and Environment in
`_publish_attempt_running()`. That is a transaction boundary requiring
separate correctness validation. Phase A does not authorize changing or
removing it, and does not claim it is the sole cause of the historical cursor
errors.

## 7. Worker restart and retry behavior

[`QueueJobRunner.run()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py:494)
initializes database connections, calls `requeue_dead_jobs()` on each loop,
processes notifications, dispatches jobs, and waits for notifications. An
outer exception handler closes database connections and retries the runner
after the configured recovery delay.

[`RunJobController._runjob()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py:149)
postpones retryable concurrency errors and requeues the job. Other exceptions
store queue-job failure information and re-raise.

Consequently, this state is possible after interruption or failed lifecycle
publication:

```text
queue_job = pending or started
ParseAttempt = running
```

The current `ai_vendor_invoice` module has stale-worker guards before and
after parsing, but Phase A found no separate reconciliation process that
repairs an orphaned non-terminal Attempt after queue recovery. This is a
state-convergence gap.

## 8. Root-cause report

### ROOT-CAUSE-01 - Parent channel limits actual dispatch

- **Evidence:** `Channel.set_running()`, `Channel.get_jobs_to_run()`, and
  `run_jobs()` source behavior; child Job 42 was marked running without a
  corresponding HTTP dispatch log.
- **Impact:** `root.ai_invoice:2` does not provide two actual worker
  executions while `root:1` is the downstream gate.
- **Confidence:** HIGH.
- **Minimal Fix:** propose a channel topology/configuration that provides two
  root-dispatch capacity slots while preserving an explicitly measured limit
  for ordinary jobs. Do not apply in Phase A.
- **Touched Files:** configuration and/or queue-entry routing only, to be
  determined after approval.
- **Regression Risk:** root-channel starvation or unexpected total worker
  concurrency if capacity is raised without a resource test.

### ROOT-CAUSE-02 - Scheduler/channel running is not worker execution

- **Evidence:** child `set_running()` precedes root yielding and HTTP dispatch;
  Job 42 has child-running evidence but no worker-request evidence.
- **Impact:** scheduler logs can overstate execution and UI Attempt status can
  remain queued.
- **Confidence:** HIGH.
- **Minimal Fix:** define and persist a worker-entry correlation event, then
  make Attempt lifecycle publication and queue state transitions converge
  explicitly. Do not implement in Phase A.
- **Touched Files:** likely queue entry/lifecycle integration and diagnostics.
- **Regression Risk:** duplicate lifecycle writes or stale-worker overwrite if
  transaction ordering is wrong.

### ROOT-CAUSE-03 - Dead-job recovery can requeue without Attempt reconciliation

- **Evidence:** runner SQL requeues old enqueued/started jobs based on lock
  state; Jobs 41/42 repeatedly returned to pending/running while Attempts did
  not reach terminal states.
- **Impact:** `job=pending, attempt=running` and
  `job=pending, attempt=queued` can persist without an explicit reconciliation
  outcome.
- **Confidence:** HIGH for the mechanism; MEDIUM for the exact first trigger.
- **Minimal Fix:** add an idempotent, transaction-safe recovery/reconciliation
  contract for queue/Attempt pairs. Do not directly edit rows to pass tests.
- **Touched Files:** queue lifecycle integration and targeted tests.
- **Regression Risk:** incorrectly failing a still-running provider request or
  creating duplicate parses after recovery.

### ROOT-CAUSE-04 - Transaction/serialization failures can prevent convergence

- **Evidence:** historical `cursor already closed`/`InterfaceError` traces and
  a current log entry showing Attempt update serialization failure; the worker
  uses an independent lifecycle cursor.
- **Impact:** queue state and Attempt state may commit independently or fail at
  different points.
- **Confidence:** MEDIUM; exact causality for Jobs 41/42 is not proven.
- **Minimal Fix:** first establish an explicit transaction ownership and error
  propagation contract for lifecycle publication; then test rollback and
  cursor lifetime. Do not solve only by increasing channel capacity.
- **Touched Files:** parse worker lifecycle integration and tests, only after
  transaction design approval.
- **Regression Risk:** closed cursors, lost error writes, duplicate execution,
  or lock release while a provider call is active.

## 9. Required minimal-fix direction (not implemented)

The preferred order is:

1. Prove and repair transaction correctness and state convergence.
2. Add correlation-level tests for scheduler selection, HTTP worker entry,
   Attempt start, provider interval, and terminal writes.
3. Select a channel topology that can actually dispatch two jobs concurrently,
   based on the proven hierarchy and resource/provider limits.
4. Re-run the single controlled two-task acceptance once, without changing
   unrelated invoice behavior.

A capacity-only change is insufficient if the queue/Attempt transaction can
still diverge.

## 10. Final Phase A status

```text
CHANNEL_HIERARCHY_PROVEN = YES
PARENT_CAPACITY_LIMITS_CHILD = YES
TASK_1584_TIMELINE_COMPLETE = NO
TASK_1585_TIMELINE_COMPLETE = NO
PENDING_REQUEUE_ROOT_CAUSE = scheduler dead-job recovery after lost/absent lock; initiating failure not fully proven
CURSOR_ERROR_CLASSIFICATION = CONSEQUENCE / origin NOT_REPRODUCIBLE in this run
STATE_DIVERGENCE_ROOT_CAUSE = scheduler/worker/Attempt transaction boundaries plus missing recovery reconciliation (MEDIUM confidence for exact trigger)
MINIMAL_FIX_IDENTIFIED = YES
IMPLEMENTATION_RECOMMENDED = NO
```

No formal fix, configuration change, retry change, timeout change, transaction
change, business-code change, or database state manipulation was performed.

## 11. Phase A.2 - single-job terminal convergence

### 11.1 Controlled reproduction

One new task was submitted through the normal UI/business entry point:

```text
Task: 1586
Attempt: 854
Queue job: 43
Queue UUID: f92ef4c0-8b88-4091-977e-06f4914b2407
QUEUE_JOB__NO_DELAY: unset
```

No channel capacity, retry, timeout, queue_job source, or production business
code was changed for this reproduction.

Observed sequence:

```text
09:05:48       Attempt 854 queued; Job 43 pending
09:05:48       child scheduler marked Job 43 running
09:07:56.283   HTTP worker endpoint entered Job 43
09:07:56.461   provider attempt started (diagnostic snapshot)
09:08:13.922   provider response 200 (correlated by the worker diagnostic)
09:10:34.901   expected schema failure; Attempt 854 failed write attempted
09:10:34.901   PostgreSQL serialization failure on Attempt 854 UPDATE
09:10:34.901   queue controller classified OperationalError as retryable
09:10:34.908   Job 43 postponed and requeued
09:15:45.117   Job 43 re-queued dead by runner
09:15:45.138   Job 43 worker entered again
09:17:35.652   another OperationalError; Job 43 postponed
09:17:40.667   Job 43 worker entered again
```

At the first terminal-observation cutoff, the database still contained:

```text
Attempt 854: running
Job 43: started
Job retry: 3
Job date_done: NULL
Attempt completed_at: NULL
Task terminal/error state: not reached
```

The provider diagnostic records four internal provider attempts for Attempt
854. The provider interval is therefore proven for this job, but the provider
response/schema result is not the first failure point: the subsequent Attempt
failure write is.

### 11.2 Transaction map

#### T1 - queue scheduler database connection

- **Owner:** `QueueJobRunner` / `Database` connection.
- **Cursor:** runner database cursor in `set_job_enqueued()` and notification
  queries.
- **Writes:** queue job `state=enqueued` and `date_enqueued`; scheduler
  in-memory channel state is separate from PostgreSQL.
- **Commit:** connection transaction handling after the runner update.
- **Rollback condition:** runner/database exception or connection recovery.
- **Relevant source:** [`runner.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py:205)
  and [`run_jobs()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/jobrunner/runner.py:414).

#### T2 - HTTP worker acquisition transaction

- **Owner:** queue_job `RunJobController`.
- **Cursor:** `request.env.cr`.
- **Writes:** queue job `state=started`, `date_started`, `worker_pid`, and
  `queue_job_lock`.
- **Commit:** explicit `env.cr.commit()` immediately after `job.store()` in
  [`_acquire_job()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py:57).
- **Rollback condition:** acquisition failure, request failure, or outer Odoo
  transaction handling.
- **Important:** this commit occurs before `job_run_parse()` and before the
  provider call.

#### T3 - queue job execution transaction

- **Owner:** same HTTP worker request and same `request.env.cr`.
- **Cursor:** `env.cr`; `job.env.cr is env.cr` is asserted.
- **Writes:** all ORM writes made by `job_run_parse()` and
  `run_parse_attempt()`, including ordinary Attempt failure and Task state
  writes; queue job completion/failure writes.
- **Commit:** successful execution commits after `job.set_done()` and
  `job.store()` in [`_try_perform_job()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py:95).
- **Rollback condition:** `OperationalError` is converted to
  `RetryableJobError`; the retry path postpones and then rolls back. Other
  exceptions are stored as queue-job failure information and re-raised to the
  Odoo request wrapper.
- **Commit prevention:** [`_prevent_commit()`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue/queue_job/controllers/main.py:30)
  rejects commits during `job.perform()`.

#### T4 - Attempt running publisher transaction

- **Owner:** `parse_service._publish_attempt_running()`.
- **Cursor:** a new cursor from `db_connect(env.cr.dbname).cursor()`.
- **Environment:** a new `api.Environment` bound to that cursor.
- **Writes:** Attempt `status=running`, `started_at`, and `last_activity_at`.
- **Commit:** explicit `lifecycle_cr.commit()` before returning to T3.
- **Rollback condition:** cursor context exit or publisher exception.
- **Close:** the cursor context closes `lifecycle_cr`; it does not intentionally
  close T3's `env.cr`.
- **Relevant source:** [`parse_service.py`](/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice.worktrees/docsintentsinvoice-statement-review/addons/ai_vendor_invoice/services/parse_service.py:50).

#### T5 - Attempt failure write in the execution transaction

- **Owner:** T3 queue HTTP worker.
- **Cursor:** T3 `env.cr`.
- **Writes:** `_failed_attempt()` writes Attempt `failed`, completion times,
  safe error fields, and diagnostics supplied by the current ORM cache.
- **Commit:** no local commit; it relies on T3's successful job completion
  commit.
- **Rollback condition:** any exception during `_failed_attempt()` or later
  execution. In the reproduction, PostgreSQL raised
  `could not serialize access due to concurrent update` during this UPDATE.
- **Observed result:** the write did not commit; the `OperationalError` escaped
  the parse exception handler and was converted by queue_job into postpone /
  requeue.

#### T6 - Task error state write

- **Owner:** T3 queue HTTP worker.
- **Cursor:** T3 `env.cr`.
- **Writes:** Task `error_ai_unavailable` after `_failed_attempt()` for provider
  or generic parse exceptions.
- **Commit:** same as T3; it is not reached when `_failed_attempt()` itself
  raises.
- **Observed result:** not reached for Attempt 854 because T5 failed first.

### 11.3 First failure and convergence result

The first task-correlated failure point is the Attempt failure UPDATE at
09:10:34.901, not the provider schema error itself:

```text
ERROR: could not serialize access due to concurrent update
```

The expected schema error was caught by `run_parse_attempt()`, but the
subsequent `_failed_attempt()` write raised `OperationalError`. Because that
write is inside the inner parse exception handler, it is not caught by a
second local handler. It escapes to queue_job `_runjob()`, is classified as
retryable, and the queue job is postponed/requeued. The Attempt failed write
is consequently rolled back/not committed, leaving `Attempt=running`.

The same pattern was observed for the earlier Attempt 853 and is consistent
with the current single-job reproduction. `cursor already closed` was not
reproduced in this new run. The current run did, however, prove an independent
cursor/Environment exists in T4 and that the failure path depends on a write
from the main execution transaction.

### 11.4 Phase A.2 result

```text
JOB_ENQUEUED = PASS
HTTP_WORKER_ENTERED = PASS
ATTEMPT_RUNNING_COMMITTED = PASS
PROVIDER_STARTED = PASS
PROVIDER_ENDED = PASS
EXCEPTION_RAISED = PASS
ATTEMPT_FAILED_WRITTEN = ATTEMPTED, NOT COMMITTED
ATTEMPT_FAILED_COMMITTED = NO
QUEUE_JOB_TERMINAL = NO
DEAD_JOB_REQUEUE = PASS
```

```text
STATE_CONVERGENCE_ROOT_CAUSE =
  Attempt failure persistence raises a serialization OperationalError inside
  the parse exception handler; queue_job then postpones/requeues the job,
  rolling back the failure write while no recovery reconciliation closes the
  Attempt.

FIRST_FAILURE_POINT =
  PostgreSQL serialization failure during _failed_attempt() UPDATE for
  Attempt 854 at 09:10:34.901.

FAILED_WRITE_ROLLED_BACK = YES
INDEPENDENT_CURSOR_INVOLVED = YES
REQUEST_CURSOR_CLOSED_BY_MODULE = NO EVIDENCE IN THIS REPRODUCTION
DEAD_JOB_REQUEUE_IS_CAUSE_OR_CONSEQUENCE =
  CONSEQUENCE of the uncommitted/retryable execution failure; it later
  perpetuates the non-terminal Attempt state.
MINIMAL_STATE_FIX_IDENTIFIED = YES
CONFIDENCE = HIGH
```

The minimal fix is only proposed, not implemented: make Attempt failure
publication transaction-safe and idempotent under concurrent updates, define
which transaction owns the lifecycle write, and add recovery reconciliation for
an Attempt left non-terminal after queue requeue/dead-job recovery. A capacity
or timeout change alone would not fix this failure.

Subsequent passive observation showed the same non-convergent pattern
continuing (`Attempt=running`, `queue_job=started`, retry increasing to 4);
the job was not manually retried or altered.
