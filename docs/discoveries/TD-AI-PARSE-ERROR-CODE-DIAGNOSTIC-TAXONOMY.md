# TD — AI Parse Error Code & Diagnostic Taxonomy

> Document Type: Technical Debt
> Status: `DEFERRED / NOT IMPLEMENTED`
> Scope: AI parse diagnostics

## Problem

当前 AI 解析链路已有 `failure_stage`、`error_summary`、Provider Call、
HTTP 状态及相关诊断记录，但缺少稳定、可检索、可统计的标准
`error_code`。

当前错误信息主要依赖安全用户提示和阶段字段。上线后如果继续仅按文本
日志定位和统计问题，同类错误可能因 Provider、异常类型或用户文案变化
而被拆散，导致失败聚合、告警和客服排障不稳定。

## Deferred Direction

后续在生产运维需求明确后，引入统一错误诊断层：

```text
error_code
+ failure_stage
+ retryable
+ safe user message
+ technical detail
```

错误码字典至少应覆盖：

- 输入文件和 PDF 预处理错误；
- Provider 配置和模型错误；
- 网络、超时、限流及 HTTP 错误；
- Provider 响应格式和 Canonical Schema 错误；
- Mapping、Persistence 及其他内部错误。

错误码应保持稳定、可检索、可统计，并与用户可见文案和技术诊断详情
分离。错误码不应包含 Attempt ID、页码、Provider 响应内容等动态数据。

## Non-Goals and Boundaries

- 错误码不得成为新的业务状态机。
- 不改变 Task 生命周期。
- 不改变 ParseAttempt 生命周期。
- 不改变现有重试语义。
- 不以错误码替代 `failure_stage`。
- 不在错误码中记录 API Key、完整发票内容或完整 Provider 原始响应。

## Trigger for Implementation

当上线运行后出现以下任一情况时，重新评估并实施：

1. 错误定位明显依赖人工检索文本日志；
2. 失败统计需要按稳定错误类别聚合；
3. 告警规则需要区分可重试与不可重试故障；
4. 客服或运维排障需要引用稳定错误标识；
5. 不同 Provider 的同类故障需要统一比较。

## Implementation Acceptance Criteria

实施时应至少满足：

1. 定义集中维护的错误码字典；
2. 在 ParseAttempt 和 Provider Call 诊断记录中保存标准 `error_code`；
3. 保留现有 `failure_stage`、安全用户提示和技术详情；
4. 明确每个错误码的默认用户提示、失败阶段和 `retryable` 属性；
5. 对 HTTP 400、认证失败、超时、连接失败、限流、Schema 校验失败和
   内部持久化失败建立回归测试；
6. 能按错误码进行失败统计，而不依赖用户提示文本。
