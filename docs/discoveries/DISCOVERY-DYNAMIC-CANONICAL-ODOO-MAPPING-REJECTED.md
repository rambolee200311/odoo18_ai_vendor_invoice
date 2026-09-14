# Discovery: Dynamic Canonical-to-Odoo Field Mapping Rejected

## 1. 当前决策

> **Dynamic Canonical-to-Odoo Field Mapping：Rejected for current scope**

当前业务不需要通用的动态字段映射平台。

当前生产链路保持不变：

```text
AI Extraction
  -> Canonical
  -> Existing Mapping Candidates
  -> Human Selection
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

## 2. 当前 Mapping 边界

现有 Mapping 继续负责为以下业务对象提供候选：

- 供应商；
- 产品；
- 税；
- 币种。

Mapping 只提供候选，不直接修改主数据或替业务员作最终选择。业务员在审核过程中人工选择正确的供应商、产品、税和币种。

当前不开发：

- 任意 Canonical 字段到任意 Odoo 模型/字段的配置平台；
- 动态模型名和字段名写入；
- 面向多个业务单据的通用映射引擎；
- 自动修改 Odoo 主数据；
- 用通用动态映射替代人工审核。

## 3. 拒绝理由

当前范围只有供应商发票审核和 Vendor Bill 流程，不存在以下真实需求：

- 大量不同目标模型；
- 大量不同业务单据类型；
- 固定映射规则维护已经成为明显瓶颈；
- 业务人员需要自行配置任意目标字段；
- 现有供应商、产品、税、币种候选能力已经无法支持审核。

在当前范围提前引入通用动态映射平台，会增加：

- 模型和字段权限风险；
- 多公司隔离和数据完整性风险；
- 字段类型、关系字段和约束处理复杂度；
- 映射版本、回放和历史数据兼容成本；
- 测试和运维成本。

这些复杂度目前没有对应的业务收益。

## 4. 当前处理方式

当前继续采用：

```text
Canonical business values
  -> Mapping candidate search
  -> Business user selects
  -> Statement stores selected business values
  -> Existing business verification
  -> Human confirmation
```

这种方式保留了明确的业务边界：

- Canonical 只表达发票识别结果；
- Mapping 只推荐候选；
- Statement 保存人工审核后的业务值；
- Vendor Bill 只使用确认后的审核结果。

## 5. 重新评估条件

只有未来出现以下真实情况时，才重新评估动态 Canonical-to-Odoo Field Mapping：

1. 大量不同目标模型需要接收 Canonical 数据；
2. 大量不同业务单据需要维护各自固定映射；
3. 人工维护固定映射已经成为明显的交付或运维瓶颈；
4. 不同公司或业务线需要由授权用户维护映射规则；
5. 现有候选 Mapping 已经无法满足真实审核工作量。

重新评估时应先收集真实数据：

```text
目标模型数量
目标单据类型数量
现有固定映射数量
每月新增/修改映射数量
人工维护耗时
映射错误造成的业务影响
权限和多公司要求
```

在这些证据出现前，不进行动态映射 Spike，也不建立通用映射框架。

## 6. 最终结论

> **Dynamic Canonical-to-Odoo Field Mapping 在当前范围内拒绝。供应商、产品、税、币种继续由现有 Mapping 提供候选，由业务员人工选择。当前不开发、不做 Spike。只有未来出现大量不同目标模型、不同业务单据，且人工维护固定映射已经成为明显瓶颈时，再重新评估。**
