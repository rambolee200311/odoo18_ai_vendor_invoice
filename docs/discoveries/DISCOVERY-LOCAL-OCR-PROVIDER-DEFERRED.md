# Discovery: Local OCR Provider Deferred

## 1. 当前决策

> **Local OCR Provider：Deferred — No current business requirement**

当前不开发本地 OCR Provider，也不针对本地 OCR 单独开展 Spike。

现有生产链路保持不变：

```text
Supplier Invoice
  -> Existing Provider
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

## 2. 延期理由

当前没有真实业务需求证明必须增加本地 OCR：

- 没有客户提出“发票不得上传第三方云服务”；
- 没有证据证明现有 Provider 无法处理某类真实供应商发票；
- 没有真实样本证明本地 OCR 能提供足够的文字、字段和运输业务信息；
- 当前引入本地 OCR 会增加部署依赖、模型/引擎维护、质量验证和运行差异。

因此，不因为“本地部署可能更安全”或“未来可能需要离线处理”就提前建立通用 OCR Provider 框架。

## 3. 不设计自动 fallback

当前不设计：

```text
External Provider failed
  -> silently switch to Local OCR
```

外部服务失败时，应保留当前明确失败语义：

```text
External Provider failed
  -> ParseAttempt failed
  -> record failure stage and ProviderCall evidence
  -> surface explicit failure
```

原因是外部 OCR 与本地 OCR 可能在以下方面不同：

- 文字识别质量；
- 表格和运输明细识别能力；
- 输出字段结构；
- 多页处理方式；
- 税额、金额和业务引用识别能力；
- 超时、重试和错误分类；
- 运行成本和处理速度。

如果失败后悄悄切换路径，可能导致同一张发票在不同 Provider 下得到不同结果，也会改变已经确定的 Provider 选择和失败语义。

## 4. 重新评估条件

只有出现以下真实条件之一，才重新评估本地 OCR：

1. 实际客户明确提出发票不得上传第三方云服务；
2. 现有 Provider 无法处理某类真实供应商单据；
3. 现有 Provider 的可用性、合规性或成本已经成为实际业务问题；
4. 客户能够提供代表该问题的真实发票样本和验收要求。

重新评估时，第一步只验证：

- 本地 OCR 能否可靠提取足够的文字；
- 能否识别供应商、发票号、日期、金额、税额和发票行；
- 能否保留运输业务需要的订单、装卸或参考信息；
- 多页和复杂明细是否满足当前审核要求；
- 输出是否可以进入现有 Canonical 和 Statement 流程。

不预先承诺：

- 增加通用 OCR Provider 抽象；
- 支持自动 Provider fallback；
- 修改 Canonical；
- 修改 Statement 或 Vendor Bill；
- 自动确认或自动建账。

## 5. 最终结论

> **当前不开发 Local OCR Provider，不做 Local OCR Spike。只有实际客户提出“发票不得上传第三方云服务”，或者现有 Provider 无法处理某类真实单据且本地 OCR 有明确价值时，再重新评估。届时先验证 OCR 能否提供足够的文字和业务信息，不预先承诺增加通用 OCR Provider 框架。**

> **外部 API 失败时不自动切换本地 OCR。外部服务失败就明确失败，不悄悄换用质量和输出能力不同的路径。**
