# CC-14 — Multi-PDF Batch Invoice Import and Selected Retry

**Status：FROZEN — APPROVED FOR IMPLEMENTATION**
**冻结日期：2026-09-11**

## 1. Contract Goal

为多个供应商发票 PDF 提供批量导入和失败项重试能力：

```text
Upload multiple PDFs
→ select one Provider
→ Start Batch
→ one Statement per PDF
→ one Task per Statement
→ asynchronous ParseAttempt
→ monitor current progress
→ filter failed Statements
→ Retry Selected
→ same Task, new ParseAttempt
→ continue existing CC-13 Statement review flow
```

CC-14 只负责 Batch orchestration，不重新定义发票业务 authority。

## 2. Frozen Baseline

- CC-10：Statement 是业务 authority，Task 是技术执行上下文；
- CC-11：Statement-first，单 PDF 对应单 Statement；
- CC-13：Statement 内嵌 AI / Task Workspace；
- Statement 负责人工编辑、Check、Confirm、Create Vendor Bill；
- Task 负责 AI execution facts；
- ParseAttempt 负责单次执行历史；
- Batch 不得成为 Vendor Bill 或发票业务 authority。

## 3. Scope

包含：

- 持久化 Batch；
- 多 PDF 上传；
- 每个 PDF 创建一个独立 Statement；
- 每个 Statement 最多一个 Task；
- 异步初次 AI launch；
- 当前 Batch progress；
- 过滤当前失败 Statement；
- Retry Selected；
- 同一 Statement、同一 Task、新 ParseAttempt；
- 每个 PDF 独立失败隔离。

不包含：

- 修改 CC-13 单 Statement workflow；
- Batch Confirm、Batch Create Vendor Bill、Batch Apply Candidate；
- 一个 Task 处理多个 PDF；
- 一个 Statement 处理多个 PDF；
- Provider fallback 或 Retry with another Provider；
- 重新设计人工审核、账单流程或 Task cardinality。

## 4. Exact Business Scenarios

### Initial Batch

```text
User selects PDFs A/B/C and Provider P
→ creates persistent Batch
→ creates Statement A/B/C
→ creates Task A/B/C
→ launches each Task asynchronously
```

### Partial Failure

```text
A succeeds, B fails, C succeeds
→ Batch remains available
→ current failed filter returns B
```

### Selected Retry

```text
User selects B
→ B keeps the same Statement
→ B keeps the same Task
→ B creates a new ParseAttempt
→ B launches asynchronously
```

## 5. Responsibility Boundary

Batch owns：

- one multi-file import operation；
- grouping of Statements；
- initial Provider selection；
- creation/start metadata；
- current aggregate progress；
- navigation to related Statements；
- selected retry orchestration。

Batch does not own supplier、invoice number/date、currency、invoice lines、tax、
source business data、human review result、Confirm、Vendor Bill 或 Task history。

Statement remains invoice business authority. Task remains AI execution authority.
ParseAttempt remains execution-attempt history.

## 6. Batch vs BatchItem Model Decision

Preferred model：

```text
Batch 1:N Statement
Statement 0..1 Task
Task 1:N ParseAttempt
```

Proposed decision：

> **BATCH → STATEMENT ONLY, subject to the pre-Statement failure contract below**

CC-14 v1 采用方案 A：文件预检在 Statement 创建前完成。被拒绝的文件：

- 不成为 Batch member；
- 不创建持久化 Statement；
- 不要求持久化 BatchItem；
- 通过 Batch start 的 per-file validation result 立即返回给用户。

只有通过预检并进入 Statement 创建阶段的 PDF 才属于 Batch 的持久化发票集合。
当前证据不证明需要 BatchItem。Filename、PDF、Task、current AI status、error
和 Statement navigation 已属于 Statement/Task 或可从其派生。

## 7. Data Model Contract

应新增持久化 `vendor.invoice.batch`，仅包含必要字段：

- batch reference/name；
- company；
- creator；
- selected Provider；
- creation/start timestamps；
- related Statements；
- current aggregate counts；
- current Batch status if needed。

Statement 应获得 `batch_id` 关系。

Statement 一旦作为 Batch 成员启动，`batch_id` 不得通过普通业务 UI 移动到
另一个 Batch。历史 standalone Statement 可以保持 `batch_id = NULL`。

以下事实继续归属现有模型：

- PDF 和 filename：Statement；
- execution Provider snapshot：Task/ParseAttempt；
- AI state 和 error：Task/current Attempt；
- Attempt history：ParseAttempt；
- invoice business data、human review 和 Vendor Bill：Statement。

## 8. Batch Lifecycle

Batch lifecycle：

```text
draft → processing → completed
                   \→ completed_with_errors
```

Batch status 是当前 orchestration view，不是不可变业务 workflow。`failed_count`
大于零时，完成状态使用 `completed_with_errors`。Retry Selected 会使当前操作
重新进入 `processing`。

Batch lifecycle states are recomputable/current operational states, not immutable
historical milestones. Historical failures are preserved only through Task and
ParseAttempt history.

## 9. Current AI Status Contract

Batch counts 必须聚合关联 Statement/Task 的当前 AI 状态，不得统计全部历史
ParseAttempt。

Batch-facing current AI outcome 是简化的 current-status projection，不得把完整
Task lifecycle 直接暴露为 Batch 用户状态模型：

```text
no Task / not started       → pending
Task parsing / active       → processing
current result successful   → success
current result error        → failed
```

Batch 用户层只使用：

```text
pending / processing / success / failed
```

`awaiting_review`、`bill_generated`、`cancelled` 等历史兼容或技术状态不得直接
成为新的 Batch-facing outcome 枚举。

```text
Attempt #1 = error
Attempt #2 = success
```

当前结果必须是：

```text
success = 1
failed = 0
```

Batch 不得成为第二个可变 AI status authority。优先从 current Task/current
ParseAttempt 派生。

## 10. Multi-PDF Upload Contract

Batch entry 必须支持：

- 多 PDF 选择；
- 一次 Provider 选择；
- 不暴露 Sync/Async 选择；
- 异步执行；
- 每个 PDF 保留原始 filename；
- 一个上传文件映射一个 Statement。

无效、空文件、非 PDF 或预检阶段可确定的重复文件必须在 Batch start 时获得
明确的 per-file validation result，但不创建持久化 Batch member。只有通过预检
的 PDF 才进入 Statement 创建。

## 11. Statement Creation Contract

```text
1 PDF → 1 Statement
```

每个 Statement 必须：

- 保持 Draft；
- 拥有 source attachment；
- 保留上传 filename；
- 设置 Batch relation；
- 设置 Provider launch configuration；
- 遵守 active business duplicate 规则；
- 最多关联一个 Task。

禁止创建共享的多 PDF Statement。

## 12. Provider Contract

Batch.selected_provider 的值复制到每个 Statement 的 launch configuration；
随后由共享 launch service 写入 Task.selected_provider_config_id，成为该 Task
的 execution authority。ParseAttempt 的 Provider configuration/snapshot facts
仍由 `ParseService.start_parse()` 创建和记录，Batch 不直接写 Attempt。

Batch 不得静默 fallback、在 retry 时改变 Provider，或取代单 Task 的 Provider
诊断 authority。Retry 使用原 Task 的 Provider。

## 13. Shared Launch Service Contract

当前 `action_start_ai()` 同时包含 UI action、Statement 校验、Task 编排和
client reload，不能直接作为 Batch API。

当前 `parse_service.start_parse()` 是可复用的底层执行边界，但要求 Task 已存在。

CC-14 实施前应提取共享的单 Statement launch service：

```text
saved Statement
→ lock/recheck
→ validate PDF
→ validate Provider
→ create/reuse one Task
→ copy launch configuration
→ establish Statement/Task relation
→ call ParseService.start_parse()
→ return Task/Attempt result
```

Statement UI action 和 Batch orchestrator 都调用该 service。

## 14. Initial Async Launch Contract

Batch execution 是 **ASYNC ONLY**。Batch UI 不得暴露同步模式。

每个 PDF 必须：

```text
synchronous_parse = False
```

每个 Task 独立创建 ParseAttempt 并独立进入 queue。CC-13 单 Statement 的既有
同步能力不因本 Contract 改变。

## 15. Initial Failure Isolation Contract

每个 PDF 是独立 execution unit：

```text
PDF A failure must not roll back successful Statements B/C
```

事务机制由 TDD/实施设计决定，但以下业务语义在 CC-14 中冻结：

- 每个 Statement launch command 都必须是 independently recoverable unit；
- 可预期的单项业务/launch exception 必须被捕获并记录为该项 outcome；
- 单项失败不得使已准备成功的其他 Statement 失效，也不得阻止后续项尝试；
- 超出单项边界的系统级失败可以中止外层请求，不视为正常 per-item failure。

本 Contract 冻结结果语义，不冻结 savepoint、独立 queue job 或其他具体机制。

## 16. Batch Progress Contract

Batch 应显示当前状态的：

- total；
- pending；
- processing；
- success/parsed；
- failed/error；

历史失败 Attempt 在后续成功后不得继续计入 failed。

## 17. Failed Statement Filter Contract

Batch 相关 Statement 列表必须能按当前 AI outcome 过滤失败项。

过滤依据应为 current Task/current Attempt，不得因为旧 Attempt 失败而继续返回
已成功的 Statement。

## 18. Retry Selected Contract

Retry Selected 必须：

- 只处理属于该 Batch 的选中 Statement；
- 保持同一 Statement；
- 保持同一 Task；
- 创建新的 ParseAttempt；
- 使用相同 Provider；
- 异步执行；
- 保留全部历史 Attempt；
- 不影响其他成功 Statement。

Retry 不得创建新的 Statement 或新的 Task。

## 19. Retry Eligibility Contract

| Current Task state | Retry Selected |
|---|---|
| `error` + Draft Statement + no active Attempt | Allowed |
| `to_parse` | Rejected |
| `awaiting_review` | Rejected |
| `parsing` | Rejected |
| `parsed` | Rejected |
| `cancelled` | Rejected |
| `bill_generated` | Rejected |

CC-13 existing single-Statement rerun lifecycle remains unchanged for backward
compatibility. CC-14 Retry Selected is narrower: it only retries the current
failed/error outcome of a Draft Statement, with no active Attempt.
Confirmed、Bill Created 或 Cancelled Statement 不得被 retry 结果覆盖。

## 20. Retry Transaction Isolation Contract

Retry Selected 必须按 Statement 隔离：

```text
A retry succeeds
B retry fails
C retry succeeds
```

A、C 的结果必须保留，B 必须保留 per-item retry outcome。
如果新的 ParseAttempt 已经合法创建，后续执行失败必须记录在该 Attempt；
如果失败发生在 launch eligibility/validation 阶段，则不得创建 synthetic
failed Attempt，仅返回该项 retry rejection。

## 21. ParseAttempt History Contract

Retry 必须在同一 Task 下追加 Attempt：

```text
Task
├── Attempt #1 error
└── Attempt #2 queued/running/success/error
```

历史 Attempt 不得被删除或合并。

## 22. Automatic Projection Compatibility

成功解析结果继续复用 CC-13 的自动 Candidate projection：

```text
AI may update structured Statement data only while state == draft.
```

Confirmed、Bill Created 和 Cancelled Statement 不得被 AI overwrite。

## 23. Duplicate Handling

必须复用当前 loaded code 的 partial uniqueness constraints，不由 CC-14
重新定义 predicates：

- Task 的 `company_source_pdf_checksum_active_unique`；
- Statement 的 `vendor_invoice_statement_business_unique`；
- Statement 的 `task_unique`。

当前 loaded code 中，前两个 active partial index 排除 `cancelled`；具体字段、
非空条件和 predicate 继续以现有模型 `init()`/constraint 定义为准。

重复 PDF 必须产生明确的 per-file outcome，不能静默创建第二个 Task 或 Statement。

## 24. Security / Company

Batch 创建和 retry 需要现有 AI Invoice User 权限。Statement review 仍由
Reviewer 权限控制。

所有 PDF、Statement、Task 和 Provider 必须遵守 company isolation，不得绕过
Provider active/company 检查、重复约束或 Statement lifecycle。

## 25. UI Contract

Batch UI 应提供：

- 多文件 PDF 上传；
- Provider 选择；
- Start Batch；
- 持久化 Batch reference；
- 当前 progress；
- 关联 Statement 列表；
- 当前 AI status filter；
- 多选失败 Statement；
- Retry Selected；
- Statement navigation；
- per-item error。

不得提供 Batch Confirm 或 Batch Create Vendor Bill。

## 26. Technical Diagnostics Boundary

Task/Attempt 继续拥有技术诊断。Batch 可以显示摘要，但不得复制 Provider call、
raw response、Attempt history、queue diagnostics 或 ParseService internals。

用户需要进入 Statement 的 AI / Task workspace 查看技术详情。

## 27. Migration / Rollback

本 Draft 不授权 migration。现有 Statement、Task 和 Attempt 必须在没有 Batch
关系时继续有效。

Rollback 不得删除既有业务或技术历史。Batch 专属记录可以停用，但不能改变
CC-13 单文档行为。

## 28. Test Contract

至少覆盖：

- 一个 Batch 创建一个 Statement/PDF；
- 一个 Statement 最多一个 Task；
- 每个 Task 拥有独立 Attempt history；
- filename preservation；
- Provider copy；
- initial launch async-only；
- 单文件预检失败不进入 Batch persistence；
- 单文件 launch failure 不回滚其他文件；
- current progress 不统计历史失败；
- failed Statement filter；
- retry 保留 Statement；
- retry 保留 Task；
- retry 创建新 Attempt；
- retry 使用相同 Provider；
- retry 异步；
- selected retry partial failure isolation；
- terminal Statement 不被覆盖；
- duplicate 和 company/security boundary；
- CC-13 single Statement regression。

## 29. Deferred Scope

- Batch human review；
- Batch Confirm；
- Batch Create Vendor Bill；
- Batch Apply Candidate；
- Provider fallback；
- retry with another Provider；
- BatchItem；
- cross-company Batch；
- multi-invoice splitting；
- advanced queue throttling；
- Batch cancellation semantics。

## 30. Loaded-Code Evidence Matrix

| Contract area | Current evidence | Reuse result |
|---|---|---|
| Statement Run AI | `statement.py::action_start_ai()` | UI-coupled; extract |
| Statement/Task/Attempt locks | `models/lock_service.py` | Reusable |
| Task creation/relation | `statement.py::action_start_ai()` | Extract |
| ParseAttempt/async launch | `services/parse_service.py::start_parse()` | Reusable |
| Duplicate PDF protection | Task partial unique index | Reusable |
| Statement business duplicate | Statement partial unique index | Reusable |
| Automatic projection | ParseService + Task apply method | Reuse unchanged |
| Existing rerun | Task rerun + ParseService | Wrap with Statement command |
| Batch model/progress | Not present | New CC-14 design |
| Searchable current AI status | Not fully established | Open issue |

## 31. Risk Register

| Risk | Level | Required treatment |
|---|---|---|
| Initial Batch transaction isolation | HIGH | Freeze per-item outcome semantics; mechanism in TDD |
| Retry Selected isolation | HIGH | Freeze per-item outcome semantics; mechanism in TDD |
| Pre-Statement upload failures | MEDIUM | Immediate validation result; no Batch member |
| Duplicate/checksum failures | MEDIUM | Reuse loaded-code predicates |
| BatchItem overengineering | MEDIUM | Prefer Batch → Statement |
| Current AI status searchability | MEDIUM | Resolve minimal searchable derivation |
| Launch service extraction regression | HIGH | Preserve CC-13 tests |
| Task rerun compatibility | MEDIUM | Use explicit matrix |
| Queue burst | MEDIUM | Address if correctness is threatened |
| Multi-file upload UX | MEDIUM | Validate with standard Odoo capability |

## 32. Open Design Issues

Only the following core decisions block implementation：

1. Exact current AI status field/search implementation；
2. Confirmation that the pre-Statement validation result mechanism satisfies the
   selected `Batch → Statement only` model；
3. TDD-level implementation of the frozen per-item failure-isolation semantics。

Standard Odoo upload, list selection, refresh, and polling details belong to TDD and
implementation design and do not independently block this Contract.

## 33. Authorization Boundary

冻结本 Contract 不等于已经开始实施。除非另有明确授权，以下内容仍不自动发生：

- code implementation；
- database changes；
- migrations；
- production deployment；
- test changes；
- changes to frozen CC-10、CC-11、CC-13、TDD v1.6 或 User Guide；
- Batch model creation；
- retry implementation。

## Freeze Decision

> **FROZEN — APPROVED FOR IMPLEMENTATION**

CC-14 implementation may proceed only under this frozen Contract. The TDD and
implementation design must resolve the concrete searchable current-status
implementation and the concrete per-item isolation mechanism without changing the
frozen business semantics.
