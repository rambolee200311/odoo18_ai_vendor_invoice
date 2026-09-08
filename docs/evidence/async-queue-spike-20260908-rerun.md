# Async Queue Technical Spike Report - Rerun

**日期**：2026-09-08
**范围**：queue_job runtime verification only
**状态**：STOPPED AFTER GATE B
**生产代码变更**：NO

## Environment evidence

| 项目 | 实际值 |
|---|---|
| Odoo | `odoo-bin -c odoo.conf --dev=all` |
| HTTP / queue runner | `127.0.0.1:8091` |
| addons_path | `addons,odoo/addons,addons/queue` |
| server-wide modules | `web,queue_job` |
| workers | `0` |
| queue_job | `installed`, version `18.0.3.1.3` |
| channels | `root:2,root.ai_invoice:2` |
| queue port | `8091` |
| database | `odoo18e_tms` at `127.0.0.1:5555` |
| AI queue entry | `vendor.invoice.import.parse.attempt.job_run_parse` |

没有发现独立 runner 进程；当前使用 Odoo 内置 queue runner。原报告把
`port = 8091` 与 manifest 输出拼接误读为 `80914`，该结论已撤回。

## Gate A - Basic Execution

使用 `ir.config_parameter.set_param` 创建隔离 no-op 任务。该任务不调用 AI、
不创建 Task、Statement 或 Vendor Bill，只将临时 probe 值持久化到配置表，
完成后已清理 probe 数据。

| 项目 | 结果 |
|---|---|
| Job ID | `90` |
| Job UUID | `c18163d9-d141-4a89-bcd5-83d00463eff7` |
| Enqueue time | `2026-09-08 07:44:34.625370 UTC` |
| Start time | `2026-09-08 07:44:34.697767 UTC` |
| Finish time | `2026-09-08 07:44:34.709998 UTC` |
| Job state | `done` |
| Worker evidence | Odoo queue runner completed the job |
| Persisted result | `queue_spike_probe_20260908 = gate-a-pass` |
| Exception | none |

```text
QUEUE_BASIC_EXECUTION = PASS
```

## Gate B - Failure and Retry

使用现有 `ir.config_parameter.set_param` 方法，但故意不传参数，制造可控
`TypeError`。没有调用 Provider，也没有修改 AI 业务数据。

| 项目 | 结果 |
|---|---|
| Job ID | `91` |
| Job UUID | `9369ef2d-8950-4600-819c-45410c9f96de` |
| Job state | `failed` |
| Start time | `2026-09-08 07:45:10.807622 UTC` |
| Exception | `TypeError` |
| Retry counter | `1` |
| Failure observability | 失败状态和异常类型已持久化 |

```text
QUEUE_FAILURE_OBSERVABILITY = PASS
QUEUE_RETRY_BEHAVIOR = NOT_PROVEN
```

当前可控异常在第一次执行后进入最终 `failed`。本次没有证明按配置执行
自动重试，也没有继续等待或修改 retry 配置，因此 Gate B 不整体判定 PASS。

## Gate C - AI Pipeline

由于 Gate B 的 retry 行为尚未通过认证，按 Spike 停止规则不执行 Gate C。
没有调用历史 PDF、Provider、Statement 或 AI Pipeline，也没有改变 Prompt、
Schema、Projection、Canonical、Mapping 或业务规则。

```text
QUEUE_AI_PIPELINE = NOT_RUN
```

## 结论

这次 Spike 证明了当前环境中存在一个可工作的基本 queue runtime：

```text
enqueue -> runner executes -> result persists -> job done
```

但尚不能证明失败任务会按预期自动重试，也不能证明 AI Pipeline 的异步
端到端链路可靠。此前“80914 端口无效”的结论是工具输出误读，已撤回。

```text
QUEUE_BASIC_EXECUTION = PASS
QUEUE_FAILURE_OBSERVABILITY = PASS
QUEUE_RETRY_BEHAVIOR = NOT_PROVEN
QUEUE_AI_PIPELINE = NOT_RUN
PRODUCTION_CODE_CHANGED = NO
SYNC_PIPELINE_CHANGED = NO
REDIS_INTRODUCED = NO
RECOMMENDATION = FIX_RETRY_CERTIFICATION_THEN_RETEST
NEXT_STEP = STOP_FOR_REVIEW
```
