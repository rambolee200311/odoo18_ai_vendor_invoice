# Discovery: Risk-based Auto-confirm Rejected

## 1. 当前决策

> **Risk-based Auto-confirm：Rejected for current scope**

当前保持人工最终确认，不开发风险评分或自动确认流程。

现有生产链路保持不变：

```text
AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Basic Validation / Mapping Candidates
  -> Human Final Confirmation
  -> Vendor Bill
```

## 2. 当前保留能力

以下能力继续保留：

- 基础字段和格式校验；
- 金额平衡检查和审核警告；
- 供应商、产品、税、币种 Mapping 候选；
- Statement 中的人工审核和修改；
- Vendor Bill 创建前的完整性校验；
- 人工确认后的 Vendor Bill 创建边界。

这些能力用于帮助人工审核，不代表系统可以自动批准业务单据。

## 3. 当前不开发

当前不开发、不做 Spike：

- Risk Score；
- Auto-confirm eligibility；
- 自动确认；
- 快速确认规则；
- 基于置信度或金额的自动审批；
- 低风险发票自动跳过人工审核；
- 自动根据校验结果创建 Vendor Bill。

现有基础校验和 Mapping 候选不扩展为自动业务审批。

## 4. 拒绝理由

当前没有真实证据证明：

- 审核量已经形成明确瓶颈；
- 业务方已经定义可执行的自动化审批规则；
- 哪些字段和业务条件足以支持自动确认；
- AI confidence、金额平衡或 Mapping 命中可以代表业务批准；
- 自动确认后的责任、审计和异常回退边界已经确定。

在这些条件未明确前，引入风险评分或自动确认会把“识别结果正确”错误地扩大为“业务单据可以批准”。

发票金额、供应商、税码和业务引用即使通过基础校验，也不等于对应采购或运输业务已经完成核验。

## 5. 当前审核边界

当前明确保持：

```text
基础校验
  -> 提供错误或警告
  -> Mapping 提供候选
  -> 业务员人工选择和确认
  -> Business / Order Verification
  -> Human Final Confirmation
  -> Vendor Bill
```

校验通过不自动确认，Mapping 命中不自动批准，AI 置信度也不作为自动审批条件。

## 6. 重新评估条件

只有未来同时具备真实业务依据时，才重新评估自动确认：

1. 实际审核量已经形成明确瓶颈；
2. 业务方提出具体、可验证的自动化需求；
3. 业务方能够定义允许自动确认的字段和规则；
4. 能够提供历史审核结果用于验证规则；
5. 能够明确异常、撤销、审计和责任边界；
6. 自动化不会绕过必要的业务/订单核验。

重新评估时应先收集：

```text
审核量和人工耗时
历史人工确认结果
字段错误率
供应商/税/金额异常率
可接受的误确认率
必须人工审核的例外条件
审计和责任要求
```

在这些真实证据出现前，不建立 Risk Score，也不设计 Auto-confirm eligibility。

## 7. 最终结论

> **Risk-based Auto-confirm 在当前范围内拒绝。当前保持人工最终确认，不开发 Risk Score、Auto-confirm eligibility、自动确认或快速确认规则，不做 Spike。现有基础校验和 Mapping 候选继续保留，不扩展为自动业务审批。未来只有在实际审核量形成明确瓶颈、且业务方提出可验证的自动化需求时，才重新评估。**
