# CC-06 实施记录

**日期**：2026-09-08
**Contract**：[CC-AI-ASYNC-PERSISTENCE-CONCURRENCY-001.md](../intents/CC-AI-ASYNC-PERSISTENCE-CONCURRENCY-001.md)
**状态**：IMPLEMENTED — TESTED
**生产代码范围**：AI Attempt 结果持久化与异步失败收敛

## 实施内容

1. 增加 Attempt 结果持久化的严格路径：
   `persist_attempt_raw_response` 和 `persist_canonical_snapshot` 不再吞掉
   数据库异常。
2. 在 Provider 已返回后，Attempt 结果持久化发生异常时，`run_parse_attempt`
   将异常归类为 `PERSISTENCE`，收敛到 Attempt `failed` 和 Task `error`。
3. 该路径返回正常业务失败结果，不把持久化冲突重新抛给 queue_job，
   因而不会再次提交同一 PDF 到 Provider。
4. 保留原有 observability 的 partial 证据逻辑；没有删除 ProviderCall、
   PageArtifact 或 raw response 记录。
5. 增加测试，覆盖：
   - 数据库持久化异常不会被严格 Attempt 持久化函数吞掉；
   - Provider 已调用后发生持久化冲突时，不再次调用 Provider；
   - Attempt/Task 进入明确失败状态。

## 实际竞争事务定位

Gate C 日志确认竞争发生在：

- worker 开始阶段的独立生命周期事务更新 Attempt；
- 主 Pipeline 随后更新同一 Attempt 的 raw response、Canonical 和
  observability 字段。

本次没有把“加行锁”预设为唯一方案，而是采用更小的行为修复：结果持久化
异常必须被显式收敛，禁止 queue_job 将 Provider 已成功返回后的持久化冲突
转化为重复 Provider 调用。

## 测试记录

### CC-06 针对性测试

在隔离数据库 `odoo18e_tms_cc06_test` 执行：

```text
TestObservabilityFailureIsolation
TestFailureDiagnostics
Result = PASS
```

覆盖总计：6 tests，全部通过。

### ai_vendor_invoice 全量测试

在隔离数据库 `odoo18e_tms_cc06_full` 执行 136 tests，结果：

```text
1 failure, 10 errors
```

失败主要来自本次之前已存在的测试/工作树问题，包括：

- `adapters/base.py` 中 `provider_input` 未定义的 `NameError`；
- `TestTimeoutService`、`TestBillCreatorGuards` 等既有失败；
- 测试数据库中的 Task/ParseAttempt 唯一性和历史测试数据污染；
- 既有 stale-worker / lifecycle 测试错误。

CC-06 新增的针对性测试在干净隔离数据库中通过。本次未修改上述无关问题。

## 变更边界

```text
SYNC_PIPELINE_CHANGED = NO
PROMPT_SCHEMA_MAPPING_CHANGED = NO
QUEUE_JOB_REPLACED = NO
REDIS_INTRODUCED = NO
ASYNC_CANCEL_IMPLEMENTED = NO
```

实现完成后应重新执行 Gate C；本记录不宣称异步 AI Pipeline 已重新通过。
