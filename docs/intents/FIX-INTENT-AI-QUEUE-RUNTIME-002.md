# FIX-INTENT-AI-QUEUE-RUNTIME-002

> Document Type: Investigation and Fix Intent / Draft
> Status: Draft - not authorized for implementation
> Scope: Reliable queue consumption and terminal state convergence for AI invoice parsing
> Related: `INTENT-REFACTOR-AI-PARSE-UX-001`, Sprint 1-Fix

## 1. Purpose

This Intent defines the investigation and acceptance contract for the failed
Sprint 1-Fix real asynchronous validation. It is intentionally limited to
queue runtime reliability and does not authorize changes to invoice extraction
or review behavior.

The investigation must keep these two properties separate:

1. **Queue concurrency**: whether two AI parse jobs have an actual overlap in
   worker execution time.
2. **State convergence**: whether each queue job and its ParseAttempt reliably
   reaches a consistent terminal state after success, failure, retry, requeue,
   worker restart, or transaction rollback.

A job being marked `running` by the scheduler is not evidence of worker
execution overlap. A ParseAttempt remaining `queued` is not, by itself, proof
that the scheduler failed to dispatch the job. Both claims require correlated
timestamps and durable database evidence.

## 2. Current failure baseline

The following evidence must remain recorded as the baseline for this Intent:

```text
Observed at: 2026-08-27
Configuration: root:1,root.ai_invoice:2
Task A: 1584
Task B: 1585
Task A channel: root.ai_invoice
Task B channel: root.ai_invoice
Task A queue wait observed: 25 seconds
Task B Attempt status: queued
Task B queue job state: pending
```

The baseline is inconclusive about concurrency and failed the usability gate
because it did not prove both worker starts, running-time overlap, terminal
convergence, or job/attempt consistency.

Historical runtime signals that must be correlated rather than assumed to be
causal include:

- `cursor already closed`;
- `psycopg2.InterfaceError`;
- `JobFoundDead`;
- `OperationalError` and postponed/requeued jobs;
- transaction rollback;
- worker/jobrunner stop and restart;
- provider response or provider schema errors.

## 3. Implementation boundary

### 3.1 In scope

- Inspecting and, after separate authorization, fixing queue job dispatch,
  worker lifecycle, retry/requeue handling, and state persistence.
- Establishing the actual semantics of parent and child channel capacities.
- Correlating scheduler, HTTP worker, queue job, ParseAttempt, and transaction
  timestamps.
- Ensuring a job and its ParseAttempt converge to a valid, mutually
  explainable terminal state.
- Preserving truthful `queued` and `running` observability.
- Testing duplicate protection and stale-worker behavior after runtime changes.

### 3.2 Explicitly out of scope

This Intent must not:

- modify Prompt or Prompt visibility/editing/snapshots;
- modify Extraction, Normalizer, Canonical, mapping, or provider contracts;
- modify Statement, Human Review, or Bill Creator;
- add timeout changes to conceal queue or provider problems;
- use `QUEUE_JOB__NO_DELAY`;
- add synchronous AI fallback;
- modify database rows solely to make a test pass;
- add a new Task state or ParseAttempt status;
- assume `root:1` is the sole root cause before evidence proves it;
- modify Odoo core or the queue_job framework without a separately approved
  architecture decision.

## 4. Investigation questions

The implementation team must answer all of the following with source, log, and
database evidence:

1. What is the official queue_job channel hierarchy and scheduling rule for
   `root:1,root.ai_invoice:2`?
2. Does a child capacity of 2 remain constrained by the parent capacity of 1?
3. Does the configured channel name match the channel used by the persisted
   queue job and by the worker request?
4. Why can the scheduler log a job as running while the corresponding
   ParseAttempt remains `queued`?
5. Why did Jobs 41 and 42 return to `pending`?
6. Did either job execute more than once, get postponed, become dead, or get
   requeued?
7. Did a transaction rollback undo Attempt lifecycle writes while preserving
   or reusing the queue job row?
8. Can the lifecycle publisher use an independent transaction without closing
   or invalidating the queue request cursor?
9. Are `cursor already closed`, `InterfaceError`, and `JobFoundDead` causes,
   consequences, or unrelated historical noise?
10. What does a worker stop/restart do to in-flight jobs and Attempts?
11. Are provider latency, provider response validation, or local resource
    limits preventing terminal state writes?
12. What configuration and code changes are required to make both concurrency
    and convergence pass without changing business semantics?

No root cause may be declared until these questions are answered or explicitly
marked not reproducible with the evidence collected.

## 5. Required observability

For every test job, capture a correlation record containing:

- Task ID, ParseAttempt ID, queue job ID, and queue job UUID;
- configured channel and persisted channel;
- enqueue timestamp;
- scheduler pending/running timestamps;
- worker request accepted and entered timestamps;
- Attempt `queued`, `running`, and terminal timestamps;
- job state transitions, retry count, postpone/requeue reason, and exception;
- transaction commit/rollback boundaries;
- worker/jobrunner start, stop, and restart events;
- provider request start/end and provider error category;
- CPU, memory, and database connection counts during the test.

The evidence must distinguish scheduler state from actual worker execution.
The preferred overlap proof is an interval intersection:

```text
max(TASK_A_WORKER_START, TASK_B_WORKER_START)
<
min(TASK_A_WORKER_END, TASK_B_WORKER_END)
```

If an end timestamp is unavailable because the job did not converge, the
concurrency result is `FAIL`, not `UNKNOWN` promoted to pass.

## 6. Real two-task acceptance contract

The test must submit two independent AI invoice parse tasks through the normal
business entry point with `QUEUE_JOB__NO_DELAY` absent and with no direct
database manipulation.

Both jobs must use the same approved test provider and equivalent source
documents. The test must record all transitions and wait for a terminal result
or an explicitly diagnosed failure.

The required result fields are:

```text
TASK_A_ENQUEUED = PASS/FAIL
TASK_B_ENQUEUED = PASS/FAIL
TASK_A_STARTED = PASS/FAIL
TASK_B_STARTED = PASS/FAIL
RUNNING_TIME_OVERLAP = PASS/FAIL
TASK_A_TERMINAL = PASS/FAIL
TASK_B_TERMINAL = PASS/FAIL
JOB_ATTEMPT_STATE_CONSISTENCY = PASS/FAIL
NO_DELAY_DISABLED = PASS/FAIL
```

### 6.1 Concurrency pass criteria

`RUNNING_TIME_OVERLAP = PASS` only when both jobs have durable worker-start
evidence and their actual worker execution intervals overlap. Scheduler
channel counters alone are insufficient.

### 6.2 State convergence pass criteria

`TASK_A_TERMINAL` and `TASK_B_TERMINAL` require each job and Attempt to reach a
documented terminal outcome:

- success/success;
- failed/failed with the approved safe error summary; or
- superseded/superseded only when a real newer Attempt caused supersession.

`JOB_ATTEMPT_STATE_CONSISTENCY = PASS` requires that:

- a successful job has a successful Attempt;
- a terminal failed job has a failed or superseded Attempt with persisted
  completion timestamps and error information;
- a pending/running job has a non-terminal Attempt only while active execution
  is demonstrably possible;
- retries and worker restarts do not leave an orphaned, contradictory pair;
- no terminal Attempt is later executed as an active parse.

## 7. Regression acceptance

The following regressions are mandatory after any authorized implementation:

1. Ordinary background jobs remain usable through the configured root channel.
2. Duplicate active AI submissions remain rejected/idempotent.
3. A stale worker cannot overwrite a newer Attempt.
4. Failure, provider error, validation error, and retry paths converge.
5. Worker restart and postponed/requeued jobs converge without manual row edits.
6. `QUEUE_JOB__NO_DELAY` remains disabled for the business AI entry point.
7. Task and ParseAttempt state values remain unchanged.

## 8. Required deliverables before implementation approval

Before code changes are authorized, provide:

- queue_job channel hierarchy findings with source references;
- a transition timeline for Tasks 1584 and 1585;
- explanation of every `pending`, `running`, `started`, postponed, and retry
  transition;
- a root-cause classification for historical cursor and dead-job errors;
- a proposed minimal fix with touched files and transaction boundaries;
- a risk assessment for worker restarts, retries, and provider failures;
- the automated test plan and the manual browser/runtime test procedure;
- explicit evidence that no out-of-scope invoice domain behavior changes.

## 9. Stop conditions

Stop investigation and report without changing capacity or code if:

- the channel hierarchy semantics cannot be established;
- the two jobs cannot be correlated across scheduler and worker logs;
- a worker or database lifecycle problem can corrupt state;
- provider/resource behavior prevents a reliable test;
- the proposed fix requires changing business states or synchronous fallback;
- the evidence suggests multiple independent causes that need separate
  approval.

This Intent remains **not authorized for implementation** until the
investigation deliverables are reviewed and a separate implementation decision
approves the selected fix.
