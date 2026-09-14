# Spike: Current Pipeline Idempotency

## 1. Objective

本 Spike 只调查当前已经存在的导入、解析和 Statement 生成链路：

```text
PDF
  -> Task
  -> Run AI
  -> ParseAttempt
  -> Canonical
  -> Vendor Invoice Statement
```

目标是回答：

> 当前已经实现的 Task → Attempt → Statement 链路，是否存在可触发的重复创建、重复推进状态或旧结果覆盖新结果问题？

本次明确排除：

- Vendor Bill 创建；
- Bill Creator；
- `account.move` 幂等；
- 重复 Confirm 创建 Bill；
- Bill-level duplicate detection；
- 自动建账和自动确认。

本次没有修改生产代码、模型、SQL constraint、queue 行为、真实 PDF 或生产业务数据，也没有重新调用真实 AI。

## 2. Current implementation scope

### 2.1 Task 与输入文件

实现位置：

- [`models/import_task.py`](../../addons/ai_vendor_invoice/models/import_task.py)
- [`services/pdf_preprocessor.py`](../../addons/ai_vendor_invoice/services/pdf_preprocessor.py)

Task 当前保存：

- `source_pdf_attachment_id`
- `company_id`
- `state`
- `current_parse_attempt_id`
- `parse_attempt_ids`
- `statement_id`

PDF 预处理阶段会对实际 PDF bytes 计算 SHA-256，并把 checksum 放入临时 Provider input source；这个 checksum 没有保存到 Task，也没有用于跨 Task 查重。

### 2.2 Task → ParseAttempt

`start_parse()` 的现有行为：

1. 锁定 Task；
2. 只允许指定业务状态启动；
3. 检查同一 Task 是否已有 `queued` 或 `running` Attempt；
4. 生成递增的 Attempt sequence；
5. 将新 Attempt 设置为当前 Attempt；
6. 将 Task 设置为 `parsing`；
7. 通过唯一 queue 入口排队。

ParseAttempt 有 SQL constraint：

```text
unique(task_id, sequence)
```

### 2.3 Queue entry 与 retry

唯一 queue 入口是 `ParseAttempt.action_enqueue_parse()`：

- 只允许状态为 `queued` 的 Attempt 入队；
- 使用 `identity_key="ai_vendor_invoice_parse:%s" % attempt.id`；
- 统一进入 `job_run_parse()`；
- `job_run_parse()` 调用 `run_parse_attempt()`；
- 不允许 no-delay execution。

Provider 内部 retry 会为每次实际请求保存 ProviderCall evidence，但只有最终成功的 Canonical 才进入 Task/Statement 业务路径。

### 2.4 Canonical 与 Statement

解析成功后：

1. Canonical 和 Mapping snapshot 写入当前 Attempt；
2. 对非多发票结果，当前 Task 生成预填充 Statement；
3. Task 保存 `statement_id`；
4. Statement 保存 `source_parse_attempt_id`；
5. 后续人工候选应用或 Statement 修改通过 Task aggregate command 执行。

Statement 具有 SQL constraint：

```text
unique(task_id)
```

因此一个 Task 在数据库中最多保存一个 Statement。

## 3. Existing idempotency mechanisms

| 机制 | 当前行为 | 防护范围 |
|---|---|---|
| Task 当前 Attempt 检查 | `start_parse()` 拒绝同一 Task 上已有 queued/running Attempt | 防止同一 Task 同时启动两个活动 Attempt |
| Attempt sequence | `_get_next_attempt_sequence()` + `unique(task_id, sequence)` | 防止同一 Task 的 sequence 重复 |
| Queue identity key | 以 Attempt id 作为 queue identity key | 防止同一 Attempt 重复排入相同 identity |
| Attempt terminal guard | `run_parse_attempt()` 对 success/failed/superseded 直接返回 | 防止已结束 Attempt 再推进业务结果 |
| Current Attempt guard | worker 执行前后检查 `task.current_parse_attempt_id` 和 Task state | 防止旧 worker 覆盖新 Attempt |
| Task row lock | parse start、worker 收口和 timeout recovery 使用 `SELECT FOR UPDATE` | 串行化 Task/Attempt lifecycle 关键操作 |
| Statement task unique | `vendor_invoice_statement.task_id` 唯一 | 防止一个 Task 持久化多个 Statement |
| Statement command guard | 创建前检查 `task.statement_id`；候选应用检查 current Attempt | 防止普通顺序调用重复创建或应用 stale candidate |
| Parse retry separation | Provider retry 创建独立 ProviderCall，不重复创建 Attempt/Statement | 重试只重复技术调用，不重复业务单据 |
| Historical Attempt preservation | rerun 创建新 sequence，不覆盖旧 Attempt | 保留旧结果和失败证据 |

这些机制保护的是当前已实现的生命周期，不代表“重复上传同一张业务发票”一定会被识别为重复业务。

## 4. Existing database constraints

| Model | Constraint / relation | 结论 |
|---|---|---|
| `vendor.invoice.import.parse.attempt` | `unique(task_id, sequence)` | 同一 Task 的 Attempt sequence 不重复 |
| `vendor.invoice.statement` | `unique(task_id)` | 同一 Task 最多一个 Statement |
| `vendor.invoice.statement.line` | `statement_id` required，cascade | 行不能脱离 Statement；删除/重建行由 aggregate command 控制 |
| Task → Attempt | `task_id` required，cascade | Attempt 隶属于 Task |
| Statement → source Attempt | `source_parse_attempt_id` required，restrict | Statement 保留来源 Attempt 关联 |
| Task → Statement | `statement_id` on Task，Statement `task_id` unique | Task 与 Statement 业务关系单一 |

当前没有发现：

- Task source PDF checksum 字段；
- Attachment checksum 的业务唯一约束；
- company + supplier + invoice number 约束；
- company + supplier + invoice number + amount 约束；
- 跨 Task 业务重复发票约束。

本 Spike 不为这些未来业务重复规则提出实现。

## 5. Scenario-by-scenario findings

结论仅使用：

- `PROTECTED`
- `VERIFIED GAP`
- `NOT IMPLEMENTED / NOT APPLICABLE`
- `UNKNOWN`

| 场景 | 当前保护机制 | 代码 / 约束证据 | 现有测试证据 | 结论 |
|---|---|---|---|---|
| 重复上传相同 PDF | 没有 Task 级 checksum 去重；PDF checksum 只在 Provider input 临时计算 | `pdf_preprocessor.prepare_provider_input()` 计算 checksum，但 Task 没有 checksum 字段或查重查询 | 未发现重复上传测试 | **VERIFIED GAP** |
| 同一 Task 重复 Run AI | `start_parse()` 检查 queued/running Attempt；完成或失败后 rerun 建立新 Attempt | `parse_service.start_parse()`；Attempt sequence 唯一 | `test_duplicate_parse_submission_is_rejected`；Attempt sequence tests | **PROTECTED** |
| Provider timeout / retry | 每次实际 Provider 请求单独 ProviderCall；最终业务结果只在 Attempt 成功收口时写入 | adapter retry；`run_parse_attempt()` 只在最终成功后写 Canonical/Statement | `test_native_pdf_timeout_retries_with_auditable_calls`；`test_each_real_retry_has_immutable_call_evidence`；retry exhaustion test | **PROTECTED** |
| Queue Job retry 同一 Job 重执行 | `run_parse_attempt()` 对 terminal Attempt 直接返回；同一 queue identity 使用 Attempt id | `job_run_parse()`、`action_enqueue_parse()`、terminal guard | `test_queue_entry_requires_real_delay`、queue channel test；没有模拟进程崩溃后的同一 Job 重放 | **UNKNOWN** |
| Stale worker | worker 前后检查 Task current Attempt/state；旧 Attempt 标记 superseded，不写当前 Task 结果 | `run_parse_attempt()` stale checks；Task/Attempt row locks | `test_stale_worker_only_supersedes_attempt`；Closure stale-worker suite | **PROTECTED** |
| 重复生成 Statement | 创建前检查 `task.statement_id`；数据库 `unique(task_id)`；预填充函数对已有 Statement 返回 | `_create_prefilled_statement_from_canonical()`；`action_create_statement_from_attempt()`；`statement.py` SQL constraint | `test_statement_first_creation_keeps_attempt_provenance`；generic Statement CRUD denied；无并发创建测试 | **PROTECTED**（顺序执行） |
| 重复 Apply Candidate | 复用同一个 Statement，删除并重建其行，不创建第二个 Statement；要求成功且 current Attempt | `action_apply_ai_candidate()` | 未发现重复 Apply Candidate 专门测试 | **UNKNOWN** |
| 两用户同时操作同一 Statement | command 没有在 `action_apply_statement_changes()` / `action_apply_ai_candidate()` / `action_confirm_statement()` 开始处锁定 Task；更新与行删除/重建可能发生竞争 | Task lock service 存在，但这些 Statement command 未调用 `lock_task()` | 未发现 Statement command 并发测试 | **UNKNOWN** |

### 5.1 重复上传的实际行为

当前相同 PDF 可以被创建为多个不同 Task：

```text
same PDF bytes
  -> attachment A -> Task A
same PDF bytes
  -> attachment B -> Task B
```

两个 Task 具有不同 identity、Attempt sequence 和 `statement_id`。当前代码没有将 PDF SHA-256 用于跨 Task 去重，因此可以产生多个独立处理链和多个 Statement。

这证明当前不存在文件级重复保护，但不等于已经确定产品必须阻止重复上传。是否需要阻止，仍属于业务规则，需要真实重复上传案例或明确产品要求。

### 5.2 重复 Run AI 的实际行为

同一 Task 在 queued/running 状态再次执行 `start_parse()` 会抛出：

```text
This task already has an AI parse attempt in progress.
```

当当前 Attempt 已完成或失败时，显式 rerun 会创建新 Attempt sequence，旧 Attempt 保留。新 Attempt 成功后，预填充 Statement 函数发现已有 `statement_id` 时不会创建第二个 Statement。

### 5.3 Provider retry 与业务结果

Provider timeout/retry 可能产生多条 ProviderCall，这是预期的技术审计结果，不是多条 ParseAttempt 或多个 Statement。

现有测试验证了：

- retry index 连续；
- 每次实际 retry 有独立 ProviderCall；
- retry exhaustion 不产生额外第四次调用；
- 最终业务结果只在成功 Attempt 收口时写入。

本 Spike 不把“重复外部 HTTP 请求”误判为“重复业务 Statement”。

### 5.4 Statement command 的当前语义

`action_apply_ai_candidate()` 和 `action_apply_statement_changes()` 不是无副作用的 no-op：

- 它们会更新 Statement；
- 删除并重建 Statement lines；
- 写入 audit log；
- 重复相同 payload 可能产生新的 line ids 和新的 audit events。

因此，当前只能说它们不会在顺序调用下创建第二个 Statement，不能声称它们具有严格意义的幂等执行语义。

## 6. Verified gaps

### GAP-01: 文件级重复上传没有保护

**事实：**

- PDF SHA-256 只在预处理的 Provider input 中临时计算；
- Task 没有持久化 checksum；
- 没有查找相同文件的现有 Task；
- 没有数据库唯一约束；
- 同一 PDF 可以形成多个 Task 和多个 Statement。

**范围：**

这是当前文件级重复保护缺失，不是对供应商发票业务重复的判断。

本 Spike 不增加 checksum 字段、去重规则或阻断逻辑。

### GAP-02: Statement command 的并发覆盖尚未被验证

代码检查发现 Statement command 没有统一的 Task row lock；两个事务可能同时读取相同的 `statement_id`，随后分别写 Statement 并删除/重建 lines。现有代码和测试不能证明并发下不会出现 last-writer-wins 或行集合覆盖。

由于本次没有执行新的并发构造验证，按照调查规则，这个问题的场景结论保持 `UNKNOWN`，不把静态风险直接升级为已验证生产缺陷。

## 7. Non-issues / already protected paths

以下不是当前已证实的重复业务问题：

1. **ParseAttempt sequence 重复**：由 SQL unique constraint 和 sequence helper 保护。
2. **同一 Task 同时 Run AI**：有 active Attempt guard，已有测试。
3. **Provider retry 产生多条 ProviderCall**：这是预期的技术审计记录，不是重复 Statement。
4. **Stale worker 覆盖当前 Attempt**：current Attempt/state 检查和现有 stale worker 测试已覆盖。
5. **顺序重复创建 Statement**：Task `statement_id` guard 和 `unique(task_id)` 保护。
6. **不同 Attempt 覆盖历史 Attempt**：rerun 创建新 Attempt，历史 Attempt 保留。
7. **Vendor Bill 幂等**：本次不调查，不能把未来 Bill Creator 需求混入当前结论。

## 8. Recommendation

### Decision: C. Evidence insufficient — specify the smallest missing verification

当前不直接选择 B，因为：

- 已验证的 GAP-01 只说明文件级重复上传没有现成保护，但当前没有明确业务规则证明重复上传必须被阻止；
- Statement 并发风险目前只有代码层疑点，没有现有或本次新增并发测试证据；
- 现有顺序 Task → Attempt → Statement 链路没有证据显示会重复创建 Statement 或让 stale worker 覆盖当前结果。

最小的后续验证范围是：

1. 向业务确认：同一 PDF 重复上传是否应该被视为禁止、警告还是允许；
2. 在测试数据库中仅针对已有 `action_apply_statement_changes()` 和 `action_apply_ai_candidate()` 做一次双事务并发验证；
3. 验证结果只关注是否出现 lost update、重复 Statement 或事务异常，不调用真实 AI、不改生产数据。

在这两个问题没有业务和并发证据之前，不新增 checksum、业务重复键、锁或通用幂等框架。

## 9. Scope closure

本 Spike 的结论是：

> 当前已经实现的 Task → Attempt → Statement 链路，在顺序执行和已覆盖的 retry/stale-worker 路径上有明确保护，没有发现已验证的重复 Statement 或旧结果覆盖新结果问题。

同时必须保留两个限定：

- 相同 PDF 跨 Task 重复上传目前可以形成多条处理链，文件级重复保护不存在；
- Statement command 的并发覆盖尚未验证，不能声称当前已具备完整并发幂等。

本次到此收口，不进入 Vendor Bill 开发、DDD、TDD 或 Coding Contract。
