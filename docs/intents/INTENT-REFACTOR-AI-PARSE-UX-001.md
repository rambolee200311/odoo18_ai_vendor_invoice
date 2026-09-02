# INTENT-REFACTOR-AI-PARSE-UX-001

## Sprint 1 — Async Runtime & State Observability

This sprint is limited to the server-side asynchronous parse lifecycle:

- enqueue a real `queue.job` through the ParseAttempt model entry point;
- keep the ParseAttempt `queued` until the worker enters `job_run_parse`;
- record submission, worker start, and completion timestamps;
- expose read-only task parse status and a safe error summary;
- prevent duplicate active submissions with an identity key and task guard;
- expose `QUEUE_WAIT_EXCESSIVE` only as an operational diagnostic.

Task state values and ParseAttempt status values are unchanged. The diagnostic
does not fail, retry, or otherwise change a task. `QUEUE_JOB__NO_DELAY` must
not be set in the server environment: it is a queue-job test switch and would
make the lifecycle synchronous and observability untruthful.

Sprint 2 (dialogs, editing, snapshots/history UI, polling and toasts) and
Sprint 3 (extraction, normalization, canonical/statement/review/bill changes)
are intentionally out of scope.

