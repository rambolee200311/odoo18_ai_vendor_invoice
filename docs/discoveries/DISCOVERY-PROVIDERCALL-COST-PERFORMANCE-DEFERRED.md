# Discovery: ProviderCall Cost & Performance Deferred

## 1. 当前最终决策

> **ProviderCall 成本与性能分析：选择 D，证据不足；当前延期，不开发。**

本次 Spike 可以收口。当前不因为“未来可能需要统计”就补齐通用成本、性能或质量观测平台，也不把现有有限数据夸大为完整分析能力。

## 2. 当前已有能力

现有 ProviderCall、ParseAttempt、ProviderConfig 和 PageArtifact 数据已经能够支持以下分析：

- 实际 ProviderCall 调用次数；
- Provider 名称；
- 调用时的 Model snapshot；
- `rendered_images` / `native_pdf` 输入模式；
- 输入页数和图片页证据；
- retry index 和 Attempt 内调用序列；
- HTTP 状态码（Provider 返回响应时）；
- `outcome`、`failure_stage` 等有限失败分类；
- ProviderCall 层的部分耗时；
- ParseAttempt 层的部分生命周期耗时；
- Provider/Model 的有限失败率和 retry 分布。

分析时必须保持粒度边界：

```text
ProviderCall duration
  != ParseAttempt duration
  != Task end-to-end duration
```

一次 ParseAttempt 可能包含多个 ProviderCall，retry 也会产生新的 ProviderCall；成本和调用次数不能只按 Attempt 数量统计。

## 3. 当前明确缺口

当前没有可靠的结构化数据支持：

- Provider 返回的 input/output Token usage；
- cached input token；
- reasoning token；
- 调用时价格快照；
- Provider 实际费用或账单；
- 按历史价格计算的费用；
- 独立模型版本；
- 字段级人工接受/修正 ground truth；
- 字段修改前值、修改后值和修改原因。

因此当前不能可靠计算：

- 单次 ProviderCall 实际 API 费用；
- ParseAttempt 总成本；
- 单张发票处理成本；
- Provider/Model 累计费用；
- Token-based 估算费用；
- Provider 字段准确率；
- 字段修改频率。

现有 raw response attachment 主要用于审计和诊断，不等于已经具备统一、可聚合的 Token usage 数据。PageArtifact 的页数、图片字节数和 checksum 是输入证据，也不等于 Token 或费用。

## 4. 当前不开发

当前明确不新增：

- usage/token 字段；
- cached/reasoning usage 字段；
- 价格表；
- 调用时费用快照；
- 账单 API；
- 成本模型；
- Dashboard 或统计页面；
- 字段级 Evidence 平台；
- 字段级人工修正审计平台；
- 新的 fallback 或自动模型切换；
- Provider 选择策略变更。

缺少统计字段不等于现在必须补齐。当前 Provider 选择、retry 和失败语义保持不变。

## 5. 重新评估条件

只有出现明确的真实需求时，才重新评估最小范围：

1. **成本对账需求**：业务需要将 Provider usage 或账单与内部发票处理关联；
2. **性能分析需求**：业务需要按 Provider/Model 比较延迟，并先定义 API、Attempt、Task 的时间边界；
3. **容量或失败分析需求**：实际调用量要求可靠统计 retry、timeout 或 Provider 失败率；
4. **质量评估需求**：业务能够提供可关联的人工接受/修正样本，并定义准确率分母。

重新评估时先取得真实 Provider response、账单/usage 语义或人工审核样本，再针对最小缺口决定是否做局部增强。不预先承诺建设通用 AI Observability Platform。

## 6. 最终结论

> **D. Evidence insufficient — defer**

现有 ProviderCall 已能支持调用次数、Provider/Model、输入模式、retry、HTTP 状态、失败率和部分耗时分析；但缺少结构化 Token usage、费用基础数据和字段级人工修正 ground truth，因此不能可靠计算完整成本或准确率。

本次不进入 DDD、TDD、Coding Contract，也不继续进行统计平台调查。等待实际成本对账、性能分析或质量评估需求出现后，再基于真实证据处理具体缺口。
