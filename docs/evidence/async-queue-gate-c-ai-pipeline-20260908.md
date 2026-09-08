# Async Queue Spike - Gate C AI Pipeline 端到端认证

**日期**：2026-09-08
**范围**：现有异步入口的真实 AI Pipeline 运行认证
**状态**：STOP FOR REVIEW
**工作树**：`/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice`
**运行配置**：原始 `odoo.conf`，addons path 为
`addons,odoo/addons,addons/queue`

## 1. 运行前检查

- Odoo HTTP：`8091`，当前服务正常；
- `queue_job`：`18.0.3.1.3`；
- `workers = 0`，内置 threaded job runner 正常启动；
- AI 异步入口：`vendor.invoice.import.parse.attempt.job_run_parse`；
- 实际调用入口：`action_enqueue_parse()` -> `with_delay(channel="root.ai_invoice")`
  -> `job_run_parse()`；
- Provider：`OpenAI GPT-5.6 Luna`，模型 `gpt-5.6-luna`；
- Provider input mode：`native_pdf`；
- Provider API key：已配置；
- 测试 PDF：`factuur_26026130.pdf`；
- 同步验收来源：历史 Task `2822`、ParseAttempt `1881`，历史 Attempt
  已有 Canonical 和 Mapping 结果。

为遵守活动 PDF checksum 唯一性，本次没有重新提交历史 Task `2822`，
也没有修改它。测试使用现有空闲测试公司 `My Company (Chicago)` 创建
隔离 Task，不创建新的 PDF 内容。

## 2. 本次执行记录

| 项目 | 结果 |
|---|---|
| PDF | `factuur_26026130.pdf` |
| Task ID | `2823` |
| Task Reference | `AIINV/2026/02841` |
| ParseAttempt ID | `1882` |
| Job ID | `95` |
| Job UUID | `674129da-7bcb-4eb3-9493-83ecc4e5d71d` |
| Enqueue time | `2026-09-08 07:57:33.254361` |
| Worker execution observed | `2026-09-08 07:57:33` 起 |
| Provider calls | `13`（Call ID `344` - `356`） |
| Provider HTTP | 每次已记录 `200` |
| Provider input | `native_pdf` / `application/pdf` / 2 pages |
| Canonical result | 未持久化到 Attempt |
| Mapping result | 未持久化到 Attempt |
| Statement | 未创建 |

Provider 请求确实到达 OpenAI，日志记录了 `/v1/files` 和 `/v1/responses`
的 HTTP `200`。这不是未入队或 worker 未执行。

## 3. 失败证据与分类

在 Provider 返回成功后，结果持久化阶段出现：

```text
psycopg2.errors.SerializationFailure:
could not serialize access due to concurrent update
```

日志定位到：

- `persist_attempt_raw_response` 更新 `raw_response_attachment_id` 时失败；
- `persist_canonical_snapshot` 更新 `canonical_result` 时失败；
- `observability_status` 同时发生并发更新失败；
- queue_job 将该 `OperationalError` 反复 postpone/reschedule；
- 同一个 Job 最终累计 `retry = 14`；
- 最终为停止继续 Provider 调用，取消隔离测试 Task。

分类：

```text
QUEUE_RUNTIME_FAILURE = NO
AI_PIPELINE_FAILURE = YES
BUSINESS_PERSISTENCE_FAILURE = YES
CONFIGURATION_FAILURE = NO
```

更精确地说，这是异步 AI Pipeline 在 Attempt/observability 结果落库时
发生的数据库并发持久化失败；Provider 本身已经返回 HTTP `200`。

## 4. 最终状态

取消前现场：

```text
Task 2823              = parsing
ParseAttempt 1882      = running
Job 95                 = pending/retrying
Statement             = not created
```

为停止重复 Provider 调用，执行了隔离测试 Task 的取消动作。最终现场：

```text
Task 2823              = cancelled
ParseAttempt 1882      = cancelled
Job 95                 = done
Statement             = not created
```

这里的 Job `done` 是取消后的 queue_job 完成，不代表 AI Pipeline 成功。
没有人工补写 Canonical、Mapping 或 Statement，也没有 Offline Replay。

## 5. Gate 结论

```text
QUEUE_BASIC_EXECUTION = PASS
QUEUE_FAILURE_OBSERVABILITY = PASS
QUEUE_RETRY_BEHAVIOR = PASS
QUEUE_AI_PIPELINE = FAIL

PRODUCTION_CODE_CHANGED = NO
SYNC_PIPELINE_CHANGED = NO
REDIS_INTRODUCED = NO
NEXT_STEP = STOP_FOR_REVIEW
```

## 6. 最小根因与建议

### 已证实根因

当前异步 AI 入口在真实 Provider 成功返回后，Attempt 的结果/观测字段
存在并发更新冲突，触发 PostgreSQL `SerializationFailure`。queue_job
随后把该异常作为可延期的运行失败重复执行，造成同一 PDF 被多次发送到
Provider。

### 最小修复建议

在另行授权的修复任务中，先针对 Attempt 的生命周期更新和
`observability_service` 的独立持久化事务设计一致的行锁/事务边界，
并确保数据库序列化冲突不会导致完整 Provider Pipeline 无界重复调用。
修复前不应宣称异步 AI Pipeline 已通过，也不应进入异步取消或压力测试。

本 Spike 不修改生产代码；Gate C 完成后停止等待人工评审。
