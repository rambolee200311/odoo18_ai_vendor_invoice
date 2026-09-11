# CC-13 Implementation Report

## Status

**IMPLEMENTED AND VERIFIED**

CC-13 was frozen and explicitly authorized before implementation. It supersedes
the cancelled CC-12 Wizard interaction model.

## Implemented scope

- Added a Statement-embedded `AI / Task` page.
- Added Statement launch configuration fields:

```text
Statement.ai_launch_provider_config_id
Statement.ai_launch_synchronous_parse
```

- Defaulted the launch mode to asynchronous; users may select synchronous
  execution before the first launch.
- `Run AI` is available only for a saved eligible Statement with a PDF and a
  selected provider.
- Run AI locks the Statement, rechecks the current relation, creates at most
  one Task, copies the launch configuration, establishes both relations,
  creates the first ParseAttempt, and starts the existing ParseService.
- Successful launch returns a client reload action and remains on the Statement
  form. It does not redirect to the standalone Task form.
- Existing supported reruns reuse the original Task/provider/execution mode.
- Repeated autosaves of the uploaded PDF reuse the source attachment instead
  of creating a second copy, preserving the original filename.
- Unsupported, active, parsed, or cancelled Task states reject duplicate Run AI.
- Task execution provider and mode are read-only after creation.
- Inline Statement workspace shows business-friendly execution state, current
  Attempt, error summary, Apply Candidate, and Technical Details navigation.
- Full attempt, queue, provider-call, artifact, audit, and raw diagnostics remain
  on the technical Task surface.
- Removed the CC-12 transient Wizard entry point and access/view definition.

## Boundary and compatibility

CC-10 and CC-11 authority remains unchanged:

- Statement owns Confirm, Unconfirm, and Vendor Bill decisions;
- `Statement.vendor_bill_id` remains Vendor Bill authority;
- Task remains the authority for actual execution facts;
- Task failure/cancellation does not change Statement business state;
- Statement/Task cardinality remains `0..1 <-> 0..1`;
- existing ParseService, queue, retry, stale-worker, and transaction semantics
  are reused.

The existing Task technical form remains available only through explicit
technical navigation. It is not the normal first-launch workbench.

The Apply AI Candidate action is visible for parsed Tasks from the embedded
workspace; this keeps successful synchronous and asynchronous parses usable
without requiring navigation to the technical Task form.

## Migration and rollback

The two Statement launch-preference fields are ordinary schema additions and
are handled by the module upgrade. Existing Statements and Tasks remain
readable. No semantic backfill or destructive migration was performed.

Online rollback means disabling the Statement workspace launch behavior while
preserving existing Statements, Tasks, PDFs, ParseAttempts, and audit data. It
does not create fake Tasks, delete Task-less Statements, or rewrite execution
facts.

## UAT prerequisite

The uploaded-PDF filename presentation issue identified during manual UAT is
tracked as a CC-11 defect. CC-13 keeps the Statement PDF and filename in the
Statement workspace and includes filename rendering in regression expectations;
the defect is not reclassified as a new CC-13 business capability.

## Verification

Focused model verification:

```text
0 failed, 0 errors of 36 tests
```

Full module verification:

```text
0 failed, 0 errors of 147 tests
```

The full run upgraded `ai_vendor_invoice` and loaded the Statement fields,
security metadata, views, and Task compatibility cleanup.

## Deferred

Provider pipeline redesign, Task history redesign, batch upload, Statement 1:N
Task execution, Candidate history/merge redesign, and `Retry with another
provider` remain deferred.
