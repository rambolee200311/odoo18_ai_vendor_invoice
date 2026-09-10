# CC-09 Implementation Report

## Scope

CC-09 separates the AI import Task lifecycle from the human-review Statement
lifecycle and makes the Statement the sole owner of the current Vendor Bill
link.

## Implemented behavior

- Import Tasks now use `to_parse`, `parsing`, `parsed`, `error`, and
  `cancelled`; successful parsing ends in `parsed`.
- Task cancellation is restricted to incomplete parsing work. A parsed Task
  cannot be cancelled through the new workflow.
- Statements use `draft` and `confirmed` for the active review lifecycle.
- Confirmation requires a draft Statement with at least one line and every
  current line marked `checked`.
- Unconfirm returns a confirmed Statement to draft without rebuilding lines or
  clearing their existing checks.
- Changing review input fields invalidates the affected line checks; critical
  header changes invalidate all line checks.
- Create Bill requires a parsed Task, a confirmed Statement, and checked lines.
  It writes only `Statement.vendor_bill_id`; it does not introduce a new
  Statement state or move the Task to a Bill state.
- `Task.vendor_bill_id` is a read-only related compatibility surface.
- Cancelling the currently linked Vendor Bill clears the Statement link.
  Stale cancellation events do not clear a newer link.
- Existing legacy state values and `human_reviewed` data remain readable for
  compatibility but are not used by the new workflow.

## Validation

The complete addon test suite was run with:

```text
odoo-bin -c odoo.conf \
  --addons-path=addons,odoo/addons,addons/queue \
  -d odoo18e_tms -u ai_vendor_invoice \
  --test-enable --test-tags /ai_vendor_invoice --stop-after-init
```

Result: **144 tests passed, 0 failures, 0 errors**.

## Notes

The implementation preserves existing audit logging and controlled aggregate
line replacement paths. Ordinary Statement Line deletion remains protected by
ACL/model rules; only the existing internal aggregate operation may rebuild
lines.
