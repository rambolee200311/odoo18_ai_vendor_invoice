# Async Queue Spike - Gate B 重试认证结果

**日期**：2026-09-08
**范围**：queue_job 层自动重试
**状态**：STOP FOR REVIEW
**生产代码变更**：NO

## 1. 正式重试机制

当前 queue_job 版本为 `18.0.3.1.3`。正式可重试异常为：

```python
odoo.addons.queue_job.exception.RetryableJobError
```

该异常可以指定延迟秒数；未指定时使用 Job Function 的 retry pattern，
再无配置时使用默认重试间隔。Job 的 `retry` 从 0 开始，每次执行递增。
普通 `TypeError`、未知方法或业务异常不会自动变成可重试异常。

本机制属于 queue_job 层，不等同于：

- Provider HTTP 内部重试；
- Task/ParseAttempt 的重新解析；
- 用户点击 Run AI 产生的新 Attempt。

## 2. 已执行的可控失败任务

为避免 AI 和业务数据，使用现有 `ir.config_parameter.set_param` 方法，但
故意不传参数制造 `TypeError`：

| 项目 | 结果 |
|---|---|
| Job ID | `91` |
| Job UUID | `9369ef2d-8950-4600-819c-45410c9f96de` |
| Attempt 1 | 已启动 |
| Exception | `TypeError` |
| Retry counter | `1` |
| Final state | `failed` |
| Persisted exception | `TypeError` |

该任务证明失败可观察，但因为异常不可重试，不能证明自动重试配置。

## 3. 重试认证限制

要满足“第一次执行抛出 `RetryableJobError`、第二次执行成功”的测试，当前
运行环境需要一个可持久化计数的测试方法。当前生产模块和已安装 queue_job
模块没有可安全复用的此类 no-op 方法。

本次不新增测试模型、不修改生产模块、不临时修改 AI 模型，也不通过手工
重新入队伪造第二次执行。因此没有产生同一个 Job 的自动重试成功证据。

## 4. Gate 结论

```text
QUEUE_BASIC_EXECUTION = PASS
QUEUE_FAILURE_OBSERVABILITY = PASS
QUEUE_RETRY_BEHAVIOR = NOT_PROVEN
QUEUE_AI_PIPELINE = NOT_RUN
PRODUCTION_CODE_CHANGED = NO
NEXT_STEP = STOP_FOR_REVIEW
```

当前最小结论：queue runtime 能执行成功任务，也能持久化不可重试失败；
queue_job 的 `RetryableJobError` 自动重试尚未认证。不能把 Job 91 的
`TypeError` 失败解释为 queue_job 重试失败，也不能宣称重试通过。
