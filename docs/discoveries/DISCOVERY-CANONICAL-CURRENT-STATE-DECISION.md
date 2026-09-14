# Discovery: Canonical 当前状态与最终决策

## 1. 背景

本记录用于收口 Canonical 与字段级 Evidence 的讨论。

当前生产链路保持不变：

```text
Supplier Invoice
  -> AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

详细调查证据见：

- [SPIKE-CANONICAL-FIELD-EVIDENCE.md](../experiments/SPIKE-CANONICAL-FIELD-EVIDENCE.md)

## 2. 当前发现

- Canonical 当前已经能够承载供应商发票审核所需的业务值；
- 当前 Canonical 已采用有限的 `value + confidence` 字段结构；
- ParseAttempt、ProviderCall、PageArtifact、raw response、Canonical snapshot 和 Statement 的 `source_parse_attempt_id` 已提供流程级追溯；
- 当前没有取得真实客服案例，证明字段级原文、页面位置或来源缺失已经阻塞审核；
- 当前没有取得真实人工修正记录，证明必须保存字段级修改前后值。

## 3. 今天的最终决策

### Canonical 保持现状

当前不改变 Canonical 的业务值结构。

明确不开发：

1. 将所有字段扩展为完整 provenance 对象；
2. 独立 Evidence 平台；
3. 新增字段级 provenance；
4. confidence 校准算法；
5. 自动审核或自动确认逻辑。

当前不修改：

- Structured Output schema；
- PDF projection / normalization；
- Vendor Invoice Statement；
- Business / Order Verification；
- Vendor Bill；
- 生产数据库模型和依赖。

## 4. 决策理由

在当前审核需求下，系统已经具备足够的流程级证据能力，而现有真实审核材料没有显示字段级 Evidence 正在造成业务阻塞。

在没有真实需求之前，提前引入通用字段 provenance 会增加：

- Canonical 和 Structured Output 契约复杂度；
- 历史 raw/Canonical/Statement 的兼容成本；
- Replay 和回放测试成本；
- Statement/UI 展示和权限设计成本；
- Evidence 保存、脱敏和生命周期管理成本。

因此当前最稳妥的选择是保持业务值和审核链路稳定，不为尚未出现的需求建立通用框架。

## 5. 未来重新评估条件

只有在客服或审核人员实际遇到以下问题时，才重新评估局部增强：

- 无法定位发票原文；
- 无法解释某个字段的来源；
- 必须保留字段修改前后的值；
- 无法处理多页发票中的字段争议；
- 合规、审计或客户明确要求字段级证据。

重新评估时必须先收集真实案例，至少记录：

```text
Task / Statement
具体字段
AI 原值
人工修改值
修改原因
需要的证据类型
现有证据是否足够
```

届时根据真实案例决定是否做局部增强，不预先承诺采用全字段对象化或独立 Evidence 平台。

## 6. 最终结论

> **Canonical 保持现状；不开发全字段对象化、不开发独立 Evidence 平台、不新增字段级 provenance。未来如果客服实际遇到“无法定位原文”“无法解释某个字段来源”或“必须保留修改前后值”的问题，再拿真实案例决定是否做局部增强。**
