# Spike: Statement Review UX & Human Change Audit

## 1. Objective

本 Spike 只读调查当前 Statement 审核页面、原始 PDF 访问能力、Canonical/Attempt/Statement 信息和人工修改审计，回答：

> 当前是否可以在不新增字段级 provenance 的前提下，改善 Statement 原文对照审核？当前人工修改审计是否足以支持实际追溯？

本次不调查或开发 Vendor Bill Creator，不改变人工最终确认边界，也不重新引入完整 Field Evidence、动态 Mapping、Risk Score 或自动确认。

本次没有修改生产代码、视图、模型、权限、真实 PDF 或生产数据，也没有调用真实 AI。

## 2. Current Statement review workflow

当前主要对象关系是：

```text
Task
  -> source_pdf_attachment_id
  -> ParseAttempt(s)
      -> Canonical / ProviderCall / PageArtifact
  -> Statement
      -> Statement Lines
  -> Human Review
```

### 2.1 Task review page

[`views/import_task_views.xml`](../../addons/ai_vendor_invoice/views/import_task_views.xml) 中的 Task form 已提供：

- 原始 PDF attachment 字段；
- AI Attempts notebook；
- 当前 Attempt 的 sequence、Provider、status、submitted/started/completed/finished 时间；
- Review notebook；
- `human_review_result` 的 `vendor_invoice_review` widget；
- review warnings；
- `statement_id`；
- Audit Log notebook。

Task 页面是当前最接近完整审核上下文的入口。

### 2.2 Statement page

现有 Statement form 仅展示：

- supplier；
- invoice number/date；
- currency；
- subtotal、tax、total；
- Statement lines 中的 description、amount、tax、reconciliation clue。

Statement 模型有 `task_id` 和 `source_parse_attempt_id` 关联，但 Statement form 没有显示原始 PDF、Task、来源 Attempt 或 PDF 预览按钮。

### 2.3 Review widget

现有 `vendor_invoice_review` OWL widget：

- 从 `human_review_result` 编辑当前审核值；
- 从当前 Attempt 的 Canonical 读取 AI candidate；
- 支持将未人工编辑字段应用为 candidate；
- 根据 Canonical 中已有 confidence 添加低置信度样式；
- 通过 `action_confirm_statement` 提交审核结果。

该 widget 只显示结构化审核值，没有将字段与 PDF 页面、原文片段或坐标连接起来。

## 3. Existing document preview capabilities

### 3.1 原始 PDF 是否可以访问

可以。Task 通过 `source_pdf_attachment_id` 持有原始 PDF attachment，且该 attachment 是当前导入任务的来源文件。

### 3.2 是否已有 Statement 内的 PDF 预览

原始 PDF attachment 本身可以通过 Odoo 原生附件能力打开/预览。当前没有发现 Statement form 内嵌的 PDF 预览区域、专用附件 action、页面 iframe、PDF viewer 或自定义原文查看组件。

当前用户可以从 Task 上下文看到 `source_pdf_attachment_id`，并可通过原生附件入口打开 PDF。代码没有提供 Statement 到该原始附件的直接快捷入口，因此“可预览”与“在 Statement 审核页面内便捷对照”是两个不同问题。

### 3.3 是否可以不离开审核上下文查看原文

当前 Task form 把结构化审核结果和附件字段放在同一个 form，但没有原文预览区域；用户通常需要通过附件入口打开 PDF。Statement 独立页面没有直接看到原始 PDF 的入口。

### 3.4 原生组件是否足够

文档级对照可以优先考虑 Odoo 原生附件访问或现有 form/action 复用，不需要因为竞品使用左右分栏就立即引入 OWL/JS 重做页面。

但当前代码没有证明原生 form 已经提供“同一审核上下文内的 PDF 预览”。如果未来真实审核反馈证明离开页面造成明显操作成本，最小候选应先评估：

1. 在 Task/Statement 上显示可访问的来源 Task/PDF；
2. 复用原生附件预览或打开 action；
3. 只有原生能力无法满足时，才考虑局部 UI。

## 4. Field information availability matrix

状态定义：

- `PERSISTED`：稳定保存在模型字段或受控 JSON/attachment 中；
- `DERIVABLE`：可以从当前持久化关联可靠推导；
- `MISSING`：当前没有可靠数据；
- `NOT APPLICABLE`：当前设计不提供该能力；
- `UNKNOWN`：代码或历史数据不足以确认。

| 信息 | 状态 | 当前证据 | 边界 |
|---|---|---|---|
| AI 提取值 | `PERSISTED` | 当前 Attempt `canonical_result`；Review widget 可读取 current Attempt candidate | 是 Canonical 结果，不等于原始 PDF 字段证据 |
| Canonical / 当前 Attempt | `PERSISTED` | Task `current_parse_attempt_id`、Attempt `canonical_result`、`mapping_result` | 可关联当前 Attempt；历史 Attempt 也保留 |
| 当前 Statement 值 | `PERSISTED` | Statement header 和 Statement line fields | 是当前人工审核工作值，不一定是 AI 原值 |
| 原始 PDF | `PERSISTED` | Task `source_pdf_attachment_id` | 可访问原始附件，但 Statement form 未直接展示 |
| Provider | `PERSISTED` | Attempt `provider_config_id`、ProviderCall `provider_snapshot` | 可以关联 Provider；失败早期可能尚未产生业务供应商 |
| ProviderCall / Attempt 来源 | `PERSISTED` | Statement `source_parse_attempt_id`；Attempt 关联 ProviderCall | 能追溯流程来源，不等于字段级来源 |
| Confidence | `PERSISTED` | Canonical 字段中的 `value + confidence` | 存在，但不是经过校准的准确率，也不是人工审批条件 |
| Schema validation status | `PERSISTED`（有限） | ProviderCall `validation_status` | 表示 extraction/schema 阶段，不等于业务校验 |
| Mapping / 基础校验 | `PERSISTED`（部分） | Attempt `mapping_result`、Task `review_warnings` | 不能压缩成统一 `valid` |
| 金额校验 | `PERSISTED`（结果有限） | `review_warnings` 和 validation service 结果 | 表示金额检查，不等于业务/订单核验 |
| Business verification | `MISSING`（本范围内） | 当前 Statement 页面未发现独立业务核验结果字段 | 不应由 schema 或金额结果替代 |
| Human confirmed | `PERSISTED` | Task `human_reviewed`、`human_review_result` | 表示人工结果已保存，不表示每个字段都被人工逐项确认 |
| 字段级 raw text | `MISSING` | PageExtraction/raw response 可能保存原始响应，但未稳定投影到每个 Statement 字段 | ProviderCall raw response 不等于字段级 raw text |
| 字段级原始页码 | `MISSING` | PageArtifact 有页号；部分 page extraction 可能有 page metadata | 没有稳定的 Canonical/Statement 字段到页码映射 |
| 字段级 bbox/coordinates | `MISSING` | 未发现 Statement/Canonical/ProviderCall 的坐标字段 | 不能实现可靠字段高亮 |
| 人工是否修改 | `DERIVABLE`（粗粒度） | `human_modify` audit event、`human_review_result` 更新 | 只能知道发生过修改事件，不能可靠知道字段列表 |
| 修改前值 | `MISSING` | `action_save_review()` 只计算 top-level key 数量变化 | 没有 before snapshot 或字段 delta |
| 修改后值 | `PERSISTED` | 当前 `human_review_result`、Statement 字段和 lines | 只有当前值，不是每次修改的历史值 |
| 修改字段名 | `MISSING` | audit `snapshot_delta` 不保存字段列表 | 不能统计常见修改字段 |
| 修改原因 | `MISSING` | audit model 无 reason 字段；command 未要求 reason | 当前没有业务要求时不应预设必填 reason |
| 修改用户 | `PERSISTED` | audit log `user_id` | 事件级用户可追溯 |
| 修改时间 | `PERSISTED` | audit log `action_datetime` | 事件级时间可追溯 |
| AI Candidate 应用 vs 人工修改 | `PERSISTED`（事件类型） | `statement_candidate_apply` 与 `human_modify` action | 能区分事件类别，但不能提供字段级 before/after |

必须严格区分：

```text
ProviderCall raw response
  != Canonical field evidence
  != Statement current value
  != Human correction record
```

## 5. Document-level vs field-level comparison feasibility

### 5.1 A：文档级对照

**可行性：有限可行，现有数据基础足够。**

原始 PDF 已由 Task attachment 保存，Statement 也能通过 `task_id` 间接找到 Task。未来若实际审核反馈证明需要文档级对照，最小方向可以是复用原生附件打开/预览能力，而不是增加 Canonical 字段对象或 Evidence 平台。

当前缺口是 UX 入口：

- Statement form 没有直接的 Task/PDF 入口；
- 没有发现内嵌 PDF viewer；
- Task form 也没有明确的“在审核区域预览原文”布局。

这属于文档访问/布局问题，不是字段级 provenance 问题。

### 5.2 B：字段级对照

**可行性：当前不可行。**

当前能够同时看到 AI candidate 和当前审核值，但无法可靠显示：

- 该字段在 PDF 中的原文；
- 原文所在页；
- 原文坐标；
- AI 原值与人工修改前值；
- 字段级 Provider/Attempt 来源。

PageArtifact 的页号和 ProviderCall 的 raw response 能提供流程级或页面级证据，但不能自动生成字段级定位。不能为了让 UI 看起来像字段对照，就从整个 raw response 猜测字段原文或页码。

### 5.3 C：校验提示

当前可展示或关联部分校验信息：

```text
Schema valid
  != Field format valid
  != Amount balanced
  != Odoo completeness
  != Business verified
  != Human confirmed
```

当前 `review_warnings` 和基础 validation 可继续作为人工提示，但不能汇总成单一“通过”，也不能转化为 Risk Score 或自动确认资格。

## 6. Current human change audit

### 6.1 已记录的内容

`vendor.invoice.import.log` 当前记录：

- `task_id`；
- 可选 `parse_attempt_id`；
- action；
- `action_datetime`；
- `user_id`；
- `snapshot_delta` 文本摘要。

当前 action 至少可以区分：

- `human_modify`；
- `statement_candidate_apply`；
- `ai_parse`；
- `ai_re_run`；
- 其他流程事件。

因此当前能够回答：

> 谁在什么时间对哪个 Task/Attempt 触发了哪类审核事件？

### 6.2 当前不能可靠回答的内容

当前不能可靠回答：

- 哪个字段被修改；
- 修改前具体值；
- 修改后具体值的历史版本；
- 明细哪一行被删除、拆分、合并或重建；
- 修改原因；
- AI Candidate 应用后哪些字段被人工再次修改；
- 同一个字段被修改了多少次。

`action_save_review()` 只将 old/new review result 的 top-level key 集合差异计数写入摘要；`action_apply_statement_changes()` 和 `action_apply_ai_candidate()` 也只写固定摘要文本。事件存在不等于保存了字段级 before/after。

### 6.3 明细删除/重建

Statement 修改 command 会删除现有 Statement lines，再按 payload 重建 lines。当前没有稳定的 line identity、before/after line mapping 或拆分/合并语义，因此无法从 audit log 还原业务上的明细变化。

### 6.4 重复 Apply Candidate

AI Candidate 应用和人工修改使用不同的 audit action，因而事件类别可以区分。重复应用仍可能产生新的 `statement_candidate_apply` 事件，并重建 lines；当前没有字段级 delta 或去重的审计语义。

## 7. Minimal enhancement candidates

### Candidate A：仅改善原文访问

如果真实审核反馈证明原文对照需要减少页面跳转，优先考虑：

- 在 Task/Statement 审核入口显示来源 Task；
- 复用现有 source PDF attachment 的原生打开/预览；
- 保持现有 Canonical、Statement 和字段结构不变。

这只解决文档级访问，不提供字段级定位。

### Candidate B：仅展示现有 AI / Statement 信息

可以在不新增 provenance 的前提下，明确展示：

- 当前 Statement 值；
- 当前 Attempt 的 Canonical candidate；
- Provider/Model/Attempt reference；
- 已有 confidence（明确标注其不是校准准确率）；
- `review_warnings`；
- schema/格式/金额校验的分层结果。

这不会制造 raw text、page、bbox 或人工 before/after。

### Candidate C：最小人工修改 before/after 审计

如果未来出现真实追溯要求，可以只针对当前 Statement aggregate command 评估最小记录：

```text
field
old_value
new_value
user
timestamp
reason（只有业务确实要求时）
```

明细行拆分、合并、删除需要另行定义业务对应关系，不能仅靠当前 line 删除/重建自动还原。

本 Spike 不设计数据库模型、JSON schema、迁移或实施方案。

## 8. Verified gaps

### GAP-01：Statement 没有直接原文访问入口

原始 PDF attachment 已存在，并可通过 Odoo 原生附件能力打开/预览；但 Statement form 没有直接显示该附件或跳转到原文的入口。文档级对照因此可能需要额外导航，具体操作成本尚未有真实审核记录量化。

### GAP-02：当前审计是事件级摘要，不是字段级 before/after

当前已能记录用户、时间、Task/Attempt 和事件类型，但不能可靠记录字段名、修改前值、修改后值、明细对应关系或原因。

### GAP-03：字段级 provenance 不足以支持字段高亮

当前没有稳定的 field → raw text → page → bbox 链路。raw response、PageArtifact 和 Canonical 的存在不能被解释成字段级原文证据。

### GAP-04：真实审核收益证据不足

本次没有取得可用于量化以下问题的真实客服/审核记录：

- 因无法打开原文而产生的额外操作；
- 因无法定位原文而无法完成审核；
- 字段修改次数和常见修改字段；
- 明细拆分/合并争议；
- 因缺少 before/after 而无法追责的案例。

## 9. Non-issues

以下不属于本次应扩大范围的事项：

1. 没有字段级 raw text，不等于必须建立完整 Evidence 平台。
2. 没有 bbox，不等于当前必须开发 PDF OCR 坐标链路。
3. `confidence` 已存在，但不应被解释成准确率或自动确认条件。
4. 有 ProviderCall raw response，不等于每个 Statement 字段都有可定位原文。
5. 有 audit event，不等于已经能够还原完整人工修改历史。
6. AI Candidate 应用和人工修改可以按 event action 粗粒度区分，不代表有字段级 delta。
7. Schema、格式、金额、业务核验和人工确认是不同层次，不能合并成单一 valid 状态。
8. Vendor Bill Creator 和 Confirm → Bill 幂等不属于本 Spike。

## 10. Recommendation

### Decision: C. Data foundation insufficient — defer

当前不直接选择 B，原因是：

- 文档级原文访问存在明确的 UX 缺口，但没有真实审核数据证明左右分栏或自定义 UI 已经是必要开发；
- 字段级对照缺少稳定 provenance，不能通过 UI 假设或从 raw response 猜测来补齐；
- 当前人工审计能追溯事件的用户、时间和类别，但不能支持字段级 before/after；
- 尚未取得真实案例证明字段级审计或原文定位已经阻塞当前审核；
- 现有审核链路可以继续使用 Statement、Review widget、校验警告和 audit event。

因此当前：

- 不开发左右分栏；
- 不开发字段级原文高亮；
- 不新增字段级 provenance；
- 不建立完整 Evidence 平台；
- 不新增通用 Event Sourcing 或审计框架；
- 不新增 Risk Score、自动确认或供应商专属模板。

## 11. Re-open trigger

未来出现以下真实证据之一时，再针对最小缺口重新评估：

1. 审核人员明确反馈无法在当前流程中打开或对照原始 PDF；
2. 真实案例因无法定位原文而无法完成字段审核；
3. 业务要求追溯某字段的修改前后值；
4. 真实明细拆分/合并争议需要还原业务上的前后对应；
5. 业务需要统计字段修改频率或使用人工结果评估 Provider。

重新评估时优先顺序应是：

```text
文档级访问
  -> 现有信息展示
  -> 必要时的局部人工 before/after 审计
```

不因单纯存在 raw response 或 confidence，就提前建设字段级 Evidence 平台。

## 12. Scope closure

最终回答：

> 当前原始 PDF 已持久化，并可通过 Odoo 原生附件能力打开/预览；Task/Attempt/Canonical/Statement 也已关联，因此未来可以在不改变 Canonical 业务值的前提下改善 Statement 内的文档级访问。当前缺少的是 Statement 页面内的直接、便捷入口，而不是 PDF 本身不可预览。字段级 raw text/page/bbox 和人工 before/after 均不存在。现有人工审计足以追溯事件的用户、时间和类别，但不足以支持字段级修改历史。

由于缺少真实审核阻塞案例和量化需求，本次选择 **C. Data foundation insufficient — defer**。当前不开发 UI、字段级 Evidence 或人工修改审计增强，等待真实需求出现后再处理最小具体缺口。

本 Spike 到此收口，不进入 DDD、TDD、Coding Contract 或生产开发。
