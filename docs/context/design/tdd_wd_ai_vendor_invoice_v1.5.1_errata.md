# TDD v1.5.1 冻结勘误：queue job 验收状态

**关联基线**：[TDD v1.5.1 冻结版](./tdd_wd_ai_vendor_invoice_v1.5.1.md)
**勘误日期**：2026-09-08
**性质**：冻结后事实补充，不修改生产代码

## 事实

截至本勘误日期，`ai_vendor_invoice` 的 queue job **没有成功完成过一次
端到端业务流程**。

因此，queue job 当前不能描述为：

- 已验收；
- 已验证可用；
- 与同步解析具有等价能力；
- 可以作为当前生产处理路径。

代码中仍存在 queue-job 依赖、`job_run_parse` 模型入口和超时/诊断服务。这些
只证明相关代码路径存在，不证明 queue job 曾经成功运行。

## 对 v1.5.1 的影响

v1.5.1 的同步版基线不变。同步解析、Task、Statement、金额联动、表单、菜单、
文件名和已记录的人工验证不受影响。

异步范围应改读为：

```text
ASYNC_SCOPE = KNOWN_FAILURE / DEFERRED
QUEUE_JOB_E2E_SUCCESS = 0
ASYNC_IS_NOT_A_CURRENTLY_USABLE_PATH = YES
```

“异步队列端到端尚未验证”在相关文档中应理解为：

> 未通过验收，并且截至目前没有一次成功的端到端 queue job 运行记录。

## 后续认证边界

后续如要恢复异步路径，必须单独完成并记录：

1. queue job 入队；
2. worker 领取并执行 `job_run_parse`；
3. Parse Attempt 状态完整流转；
4. Statement 创建；
5. 错误、重试、取消和 stale worker；
6. 多公司上下文；
7. 端到端成功样本。

本勘误不授权修改 `queue_job`、引入 Redis、改变状态机或设计异步取消。
