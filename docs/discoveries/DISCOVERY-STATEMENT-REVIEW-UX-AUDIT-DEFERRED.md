# Discovery: Statement Review UX & Human Change Audit Deferred

## 1. 当前最终决策

> **Statement Review UX & Human Change Audit：选择 C，当前延期，不开发。**

本次 Spike 可以收口。结论不是“当前审核体验已经完美”，而是当前没有足够真实审核反馈证明需要立即开发定制 UI、字段级 Evidence 或人工修改审计增强。

## 2. 已确认的现有基础

当前原始 PDF 已作为 Task 的 `source_pdf_attachment_id` 持久化，并可以通过 Odoo 原生附件能力打开/预览。

Statement 通过：

```text
Statement
  -> task_id
  -> source Task
  -> source PDF attachment
```

关联到来源 Task。因此未来如果需要改善文档级原文访问，不需要先建设字段级 Evidence 平台，也不需要改变 Canonical 或 Statement 的业务值结构。

当前已有的审核信息包括：

- 当前 Statement 表头和明细；
- 当前 Attempt 的 Canonical candidate；
- Provider/Attempt 关联；
- 已有 confidence（不代表校准准确率）；
- schema/格式/金额等有限校验结果；
- review warnings；
- audit event 的用户、时间和事件类别。

## 3. 当前最明确的 UX 边界

原始 PDF 本身可以预览。当前更准确的 UX 缺口是：

- Statement 页面没有直接、便捷的原始 PDF 入口；
- 结构化 Statement 与 PDF 原文通常需要额外导航；
- 当前没有同一审核上下文中的 PDF 预览区域。

这与“必须开发左右分栏”不是同一个结论。未来如确有审核操作成本，优先复用：

1. Odoo 原生附件打开/预览；
2. 现有 Task/Statement 关联；
3. 原生 form/action 能力；
4. 只有原生能力不足时，才评估局部页面增强。

## 4. 人工修改审计现状

当前 audit log 可以追溯：

- 哪个 Task/Attempt 发生事件；
- 谁执行了操作；
- 操作时间；
- 操作类别，例如 `human_modify` 或 `statement_candidate_apply`。

当前不能可靠还原：

- 修改了哪个字段；
- 字段修改前值；
- 字段修改后值的完整历史；
- 明细删除、拆分、合并或重建的业务对应关系；
- 修改原因。

因此：

```text
有 audit event
  != 有字段级 before/after
  != 能还原完整人工修改历史
```

同时，当前没有稳定的字段级：

- 原文文本；
- 原始页码；
- bbox/coordinates；
- Provider → Canonical → Statement 的字段 provenance。

ProviderCall raw response、PageArtifact 和 Canonical 的存在，不应被解释成每个 Statement 字段都有可定位原文。

## 5. 当前不开发

当前明确不做：

- 左右分栏审核页面；
- Statement 内嵌 PDF viewer；
- 字段级原文高亮；
- 字段级 raw text/page/bbox；
- 新增 Canonical provenance；
- 完整 Field Evidence 平台；
- 通用 Event Sourcing 或审计框架；
- 人工修改 before/after 字段；
- 明细拆分/合并审计平台；
- Risk Score、自动确认或供应商专属模板。

当前也不因为发现审计粒度有限，就预先新增数据库字段、JSON schema 或迁移。

## 6. 未来最小处理顺序

等实际审核反馈出现后，按以下顺序处理：

```text
原文访问
  -> 现有信息展示
  -> 必要时的局部 before/after 审计
```

### 6.1 原文访问

如果审核人员明确反馈打开原始 PDF 需要过多操作，优先增加 Statement 到来源 Task/PDF 的便捷入口，并复用原生附件能力。

### 6.2 现有信息展示

如果审核人员需要更清楚地对照当前值和 AI candidate，可以在不新增 provenance 的前提下展示已有：

- Statement 当前值；
- 当前 Attempt candidate；
- Provider/Model/Attempt；
- review warnings；
- 分层校验结果。

不得伪造字段级原文、页码、坐标或校准后的 confidence。

### 6.3 局部人工 before/after 审计

只有业务明确要求追溯字段修改时，才针对当前 Statement aggregate command 评估最小记录：

```text
field
old_value
new_value
user
timestamp
reason（仅在业务要求时）
```

明细拆分、合并和删除的业务对应关系需要真实案例后单独定义，不能从当前删除/重建 lines 自动推断。

## 7. 重新评估条件

出现以下真实证据之一时，再重新评估：

1. 审核人员反馈无法方便打开或对照原始 PDF；
2. 真实审核因无法定位原文而受阻；
3. 业务要求追溯字段修改前后值；
4. 真实明细争议需要还原删除、拆分或合并关系；
5. 业务需要统计常见修改字段或 Provider 质量。

重新评估仍应从最小范围开始，不因竞品采用左右分栏或系统保存 raw response，就直接建设完整 Evidence 平台。

## 8. 最终结论

> **C. Data foundation insufficient — defer**

原始 PDF 已存在，Statement 也能关联到来源 Task，因此未来改善文档级原文访问不需要先建设字段级 Evidence 平台。当前最明确的 UX 缺口只是 Statement 页面缺少直接、便捷的原始 PDF 入口，这与必须开发左右分栏无关，原生附件能力应优先复用。

现有人工审计能追溯事件的用户、时间和类别，但不能可靠还原字段级 before/after、明细删除重建对应关系或字段级原文/页码/坐标。

因此当前不做左右分栏、不做字段高亮、不新增 provenance，也不开发人工修改审计增强。等待实际审核反馈后，优先处理原文访问，再考虑现有信息展示，最后才评估必要的局部 before/after 审计。

本次不进入 DDD、TDD、Coding Contract 或生产开发。
