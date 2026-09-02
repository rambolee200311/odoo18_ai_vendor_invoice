# FIX-INTENT-AI-QUEUE-RUNTIME-002
## Phase C — Lock Lifecycle Diagnostic Reproduction Report

**Scope:** diagnostic instrumentation plus one controlled single-job reproduction  
**Implementation:** not authorized and not performed  
**Task:** existing Task 1689, new ParseAttempt 931, Queue Job 52  
**Reproduction date:** 2026-08-28

## Result Summary

The reproduction did not produce valid lock-lifecycle evidence. The first instrumented request reached
`_acquire_job()` and committed the queue job's `started` state, but the temporary diagnostic code then accessed
an invalid `Job.id` attribute and raised `AttributeError` before the lock inspection/perform instrumentation could
run. The runner received HTTP 500 and naturally retried the same queue job.

After the diagnostic code was removed and Odoo was reloaded, Job 52 naturally converged:

```text
queue_job 52  = done
Attempt 931   = failed
Task 1689     = error state
```

No second AI task was submitted. No database row was manually repaired. The provider was not retried manually.

## Observed Timeline

| Event | Timestamp (local, +08:00) | Evidence | Valid for lock conclusion |
|---|---|---|---|
| Attempt 931 submitted | 09:14:46 | database | yes |
| Job 52 created | 09:14:46.326 | database | yes |
| Runner dispatched | 09:14:46.344 | runner log | yes |
| HTTP request entered | 09:14:46.365 | diagnostic log | yes |
| Queue job started commit | 09:14:46.372 | diagnostic log | yes |
| Diagnostic exception | 09:14:46.372 | `AttributeError: 'Job' object has no attribute 'id'` | invalidates remainder |
| HTTP 500 returned | 09:14:46.374 | runner log | yes |
| Dead-job requeue | 09:15:46.380 | diagnostic runner log | yes, but this was caused by the instrumentation failure |
| Clean process loaded | after one corrective reload | process/HTTP check | yes |
| Job 52 final terminal | 09:18:48.133 | database | yes |
| Attempt 931 final terminal | 09:18:48 | database | yes |

The `queue_job_lock` value logged during the invalid run was not captured: the exception occurred before the
inspection query. Therefore this run cannot answer whether the lock was created, visible during provider work,
or deleted by a transaction.

## Interpretation

This reproduction proves only that:

1. The queue controller can commit the `started` state before the temporary diagnostic failure.
2. An HTTP 500 causes the runner to leave the job eligible for natural dead-job recovery/retry.
3. The existing State Convergence implementation eventually projected the retry outcome to Attempt `failed` and
   the Task error state.

It does **not** prove the cause of the historical lock loss in Tasks 1689/1690. In particular, it does not prove
request abort, transaction rollback, cursor closure, worker restart, or a dead-job false positive.

The temporary diagnostic modifications were removed from the working tree. The second reload was authorized only
to restore the clean code after the instrumentation error; no runtime fix was implemented.

## Required Final Output

```text
LOCK_CREATED = UNKNOWN
LOCK_VISIBLE_DURING_PROVIDER_CALL = UNKNOWN
LOCK_LOST = UNKNOWN
LOCK_LOST_AT = UNKNOWN
LOCK_LOSS_ROOT_CAUSE = NOT_PROVEN
ROOT_CAUSE_CATEGORY = UNKNOWN

REQUEST_ABORTED = UNKNOWN
TRANSACTION_ROLLED_BACK = UNKNOWN
MODULE_CLOSED_REQUEST_CURSOR = NO
DEAD_JOB_FALSE_POSITIVE = UNKNOWN

MINIMAL_FIX_IDENTIFIED = NO
IMPLEMENTATION_RECOMMENDED = NO

PRODUCTION_BEHAVIOR_CHANGED = NO
CONFIG_CHANGED = NO
QUEUE_JOB_SOURCE_CHANGED = NO
```

## Next Step

Stop Phase C pending review. A further reproduction would require corrected diagnostic instrumentation and a new
explicit restart authorization. It must first validate the instrumentation itself without changing queue behavior,
then run one single job and capture lock creation, lock visibility, request exit, transaction rollback, and dead scan
evidence. No additional reproduction is started by this report.
