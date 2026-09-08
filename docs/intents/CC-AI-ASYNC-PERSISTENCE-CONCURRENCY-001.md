# CC-06 — Async AI Attempt Persistence Concurrency Repair

> Document Type: Coding Contract
> Status: `FROZEN — IMPLEMENTATION AUTHORIZED`
> `IMPLEMENTATION_AUTHORIZED = YES`
> Target: Odoo 18.0
> Trigger: Gate C AI Pipeline failure, 2026-09-08
> Frozen: 2026-09-08
> Related evidence: `docs/evidence/async-queue-gate-c-ai-pipeline-20260908.md`

## 1. Contract Goal

修复异步 AI Pipeline 在 Provider 已成功返回后，Attempt 结果持久化阶段的
并发更新冲突，确保一次合法的异步执行能够完成：

```text
queue_job
  -> job_run_parse
  -> Provider
  -> raw response / Canonical
  -> Mapping
  -> ParseAttempt success
  -> Statement
```

本 CC 只处理 ParseAttempt 生命周期与 observability 持久化之间的并发边界，
不重新设计 AI Pipeline。

## 2. 已确认问题

Gate C 实际证据：

- Job `95`、UUID `674129da-7bcb-4eb3-9493-83ecc4e5d71d`；
- Provider 请求返回 HTTP `200`；
- 同一个 Attempt 产生多次 ProviderCall；
- 在 `persist_attempt_raw_response`、`persist_canonical_snapshot` 和
  `observability_status` 更新时出现：

```text
psycopg2.errors.SerializationFailure:
could not serialize access to concurrent update
```

- queue_job 将该数据库异常延期并重复执行；
- 最终没有持久化 Canonical、Mapping，也没有创建 Statement。

## 3. In Scope

### 3.1 Attempt 持久化一致性

为 `vendor.invoice.import.parse.attempt` 的以下生命周期更新建立一致的
事务和锁边界：

- `queued -> running`；
- raw response attachment 关联；
- Canonical result；
- Mapping result；
- observability status；
- `success` / `failed` / `finished_at` / `completed_at`。

同一个 Attempt 的生命周期写入不得由互相竞争的事务无序更新。

### 3.2 Observability 写入协调

调整 `observability_service` 与主 Pipeline 事务之间的写入关系，使其：

- 不再与同一 Attempt 的主业务更新发生未协调的并发写入；
- 不破坏现有 ProviderCall、PageArtifact 和 raw response 审计证据；
- 在数据库序列化冲突时返回明确、可观察的结果；
- 不把一次持久化冲突转化为无界 Provider 重复调用。

### 3.3 Queue 重试边界

当失败发生在 Provider 已成功返回之后：

- 不得无限重复提交同一个 PDF 到 Provider；
- 失败必须落到可观察的 Attempt/Task 错误状态，或按明确且有上限的
  queue_job 重试策略处理；
- queue_job 的技术重试与 Provider 内部重试必须保持可区分；
- 不得通过手工重新入队掩盖持久化失败。

Provider 已成功返回且原始响应已可靠持久化后，后续数据库持久化失败不得
重新调用 Provider；应优先从已持久化结果继续，或进入明确的失败状态。若
原始响应尚未可靠持久化，必须采用有上限且可观察的失败处理，不得无界重复
调用 Provider。

## 4. Out of Scope

- 不修改 Prompt、Schema、Canonical 字段定义或 Mapping 规则；
- 不改变 Provider 配置、Provider 内部重试策略或 HTTP 请求格式；
- 不修改 Task/Statement 状态机；
- 不实现异步 Cancel、running Job 强制中止或 stale worker guard；
- 不引入 Redis 或替换 `queue_job`；
- 不进行多 Worker 压力测试；
- 不重新认证 AI 识别质量；
- 不改变同步解析路径；
- 不新增业务字段或第二套 Attempt/Statement 模型。

## 5. 必须保持的业务规则

1. `job_run_parse` 仍是唯一异步入口。
2. 一个 ParseAttempt 不得因为数据库重试而创建重复 Statement。
3. ProviderCall 历史记录必须保留，不得覆盖成最后一次调用。
4. 成功结果必须同时具备可追溯的 Attempt、Canonical、Mapping 和 Statement
   来源关系。
5. 失败不得伪装成成功，也不得静默吞掉持久化异常。
6. 已完成、已取消、superseded 或已进入最终失败状态的 Attempt 不得再次
   进入 Provider。允许的技术重试必须符合现有生命周期和明确的重试策略，
   不得绕过终态保护。
7. 现有同步 Pipeline 行为必须保持不变。

## 6. 技术约束

- 实现前必须先通过日志、事务调用链和目标行写入点定位实际竞争事务；
  不得把“增加行锁”直接当作已确认根因或预先确定的唯一方案；
- 优先复用现有 `lock_task`、`lock_attempt` 和 observability helper；
- 不增加 broad `try/except` 或 success-shaped fallback；
- 对序列化冲突必须有明确的日志、Attempt 错误摘要和 queue 状态；
- 若实现有限次数重试，次数、间隔和最终失败状态必须可验证；
- 任何独立数据库连接都必须明确其与主事务的提交顺序和行锁关系；
- 不得在 queue worker 中调用 `env.cr.commit()` 规避事务问题；
- 不得通过修改 `max_retries` 为超大值掩盖并发根因。

## 7. Acceptance Criteria

### AC-01 — Single async success

使用一张已通过同步验收的历史 PDF，通过正式异步入口执行一次：

```text
Task -> enqueue -> Job -> Provider -> Canonical -> Mapping -> Statement
```

必须满足：

- Job 最终 `done`；
- Task 进入预期成功状态；
- ParseAttempt 为 `success`；
- Canonical 和 Mapping 已持久化；
- Statement 恰好创建一次；
- Statement 正确关联 Task 和 ParseAttempt；
- 不需要人工补写或 Offline Replay。

### AC-02 — Controlled concurrent persistence

正常异步执行应完成结果持久化，不得因未协调的 Attempt/observability
写入而失败。可控冲突测试中，冲突必须被正确处理或进入明确失败状态，不得
造成重复 Statement 或无界 Provider 调用。

不得通过删除 observability 写入满足验收。

### AC-03 — Controlled persistence failure

在可控的数据库冲突或失败场景下：

- 错误必须可观察；
- 不得无限重复调用 Provider；
- 不得创建重复 Statement；
- Attempt/Task 最终状态必须符合现有错误规则；
- Job 的最终状态和异常必须可追溯。

### AC-04 — Regression protection

现有同步解析测试、Task/Statement 关系测试、ProviderCall/Attempt 观测测试
不得回归。必须补充至少一个针对同一 Attempt 并发持久化边界的自动化测试。

## 8. 验证证据

交付时必须记录：

```text
Task ID
Job ID / UUID
Attempt ID
ProviderCall IDs
Statement ID
Attempt lifecycle timestamps
Job retry count
Canonical / Mapping persistence
SerializationFailure count
Duplicate Statement count
```

验收结果必须明确：

```text
ASYNC_ATTEMPT_PERSISTENCE = PASS / FAIL
PROVIDER_DUPLICATE_SUBMISSION_GUARD = PASS / FAIL
STATEMENT_IDEMPOTENCY = PASS / FAIL
SYNC_PIPELINE_REGRESSION = PASS / FAIL
```

## 9. 交付边界

本 CC 仅授权一次小范围并发持久化修复和对应测试。实现完成后必须停止，
等待 Gate C 重新认证结果；不得自动开始异步取消、Worker 恢复或压力测试。
