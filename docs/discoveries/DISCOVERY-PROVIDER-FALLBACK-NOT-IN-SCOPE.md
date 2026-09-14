# Discovery: Provider Fallback Not in Current Scope

## 1. 当前最终决策

> **增加 Provider fallback 策略：当前不考虑开发，也不做 Spike。**

当前 Provider 选择和失败语义保持不变。主 Provider 失败后，不自动切换到其他 Provider，也不静默切换到本地 OCR 或其他质量、输出能力不同的处理路径。

## 2. 当前不开发

当前不实现以下能力：

- 主 Provider → 备用 Provider 的自动切换；
- Provider 链或 fallback 优先级配置；
- 无限重试或跨 Provider 自动重试；
- Mistral OCR、Azure OCR、本地 Tesseract 等自动 fallback 链；
- fallback 后自动进入人工处理队列；
- fallback 专用 Attempt/ProviderCall 状态模型；
- fallback 成本、质量或路由策略；
- Provider 失败时的隐式模型切换。

当前 Provider 失败仍按现有 Attempt、ProviderCall、failure stage 和错误语义明确记录，不通过另一条路径伪装成成功。

## 3. 未来概念边界

未来如果业务确实需要 Provider fallback，概念上必须保持有限且可审计：

```text
主 Provider 失败
    -> 按明确上限重试同一 Provider
    -> 仍失败后，按明确策略切换备用 Provider
    -> 仍失败后，进入人工处理
```

任何未来方案都不能无限重试，也不能绕过现有业务链路：

```text
Provider extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
```

如果将来重新评估，切换 Provider、重试次数、失败原因、实际调用和最终结果都必须可追溯到 Attempt 和 ProviderCall。但这些只是未来重新评估时的边界，不是当前实施承诺。

## 4. 重新评估条件

只有出现明确的真实业务需求时，才重新打开该议题，例如：

- 客户明确要求某类真实单据必须由备用 Provider 处理；
- 当前 Provider 对某类真实单据持续失败并形成业务瓶颈；
- 业务方定义了可接受的质量、成本、延迟和失败边界；
- 业务方明确要求失败后进入人工处理，而不是直接终止。

重新评估时，应先基于真实失败案例验证备用 Provider 是否真正有价值，再决定是否需要最小范围的 fallback 设计。不得因为“理论上可以提高可用性”就提前建立通用 Provider 路由框架。

## 5. 最终结论

> **Provider fallback 策略当前不考虑开发，也不做 Spike。**

当前不增加 fallback 字段、流程、Provider 链或自动切换。外部 Provider 失败就明确失败并保留现有审计记录；未来出现真实业务需求后，再针对具体 Provider 和具体失败案例重新评估。
