# Spike: Canonical & Field Evidence

## 1. Objective

本 Spike 只回答：

> 现有 Canonical 是否已经足够支撑供应商发票审核？是否存在真实需求，需要为字段增加来源、原文、位置或其他 Evidence？如果需要，这些信息应该放在哪里？

当前生产架构保持不变：

```text
Supplier Invoice
  -> AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

本次不重新讨论结构化电子发票 XML/UBL/Factur-X/ZUGFeRD，也不修改生产 Canonical、Structured Output、Statement、Bill Creator、数据库模型或依赖。

### Scope result

本次调查的结论是：

- 当前 Canonical 已经能承载审核所需的业务值；
- 当前 Canonical 实际已经是有限的字段对象结构（`value + confidence`），不是只有裸值；
- Attempt、ProviderCall、PageArtifact 和 raw response 已提供跨字段的运行证据；
- PageExtraction 还保存了部分 `raw_facts`、`raw_fields` 和页号；
- 但没有取得真实客服/审核记录，证明字段级原文、位置或来源缺失已经阻塞审核；
- 因此当前选择 **A. Keep current Canonical**。

## 2. Current implementation evidence

以下结论来自当前工作树实际代码，而不是仅根据旧 TDD 推断。

### 2.1 Canonical schema

实现位置：

- [`schemas/canonical.py`](../../addons/ai_vendor_invoice/schemas/canonical.py)
- [`schemas/document_extraction.py`](../../addons/ai_vendor_invoice/schemas/document_extraction.py)

当前 Canonical 顶层结构为：

```text
{
  "header": {...},
  "lines": [...],
  "is_multi_invoice": boolean
}
```

可提取字段采用：

```text
{
  "value": value,
  "confidence": number
}
```

Header 中已经对象化的字段包括：

- `invoice_number`
- `invoice_date`
- `supplier_raw_text`
- `currency_raw_text`
- `total_amount`
- `total_tax`
- `subtotal`

Line 中已经对象化的字段包括：

- `description`
- `amount`
- `tax_raw_text`
- `tax_rate`
- `tax_amount`

Line 还保留了：

- `reconciliation_clue`
- `charge_details`
- `reconciliation_clues`

因此，候选设计 A 中的“普通裸值 Canonical”并不是当前实际实现；当前实现已经接近有限范围的对象化结构，但没有把每个字段扩展成完整 provenance 对象。

### 2.2 Structured Output 与 Canonical 的关系

当前不是 Provider 直接返回 Canonical：

```text
AI/Page or Native Document Output
  -> schema validation
  -> document normalization / native projection
  -> Canonical validation
  -> Mapping
  -> Statement
```

#### AI/page path

`page_extraction.py` 允许页面级：

```text
page_number
header
lines
raw_facts
lines[].raw_fields
```

页面结果中的 `raw_facts` 和 `raw_fields` 要求至少包含：

```text
source_label
source_value
```

`document_normalizer.py` 会把页号写入这些事实，形成 `source_page`，然后把多页结果归并为一个 Canonical。

但是归并结果只保留业务字段的 `value + confidence`。当前归一化实现为 Canonical 字段生成的 `confidence` 是 `0.0`，没有把 `source_label`、`source_value` 或 `source_page` 投影到 Canonical 字段。

#### Native PDF path

`document_extraction.py` 定义独立的文档级提取结构，`native_document_projection.py` 的 `document_to_canonical()` 负责：

- 校验文档级提取结果；
- 处理字段别名；
- 规范化日期和金额；
- 把供应商、币种、金额和行项目映射成 Canonical；
- 保留 `charge_details` 和 reconciliation clues。

Native projection 同样把 Canonical 字段的 `confidence` 设为 `0.0`，没有输出 source 类型或页面位置。

### 2.3 Attempt、ProviderCall、PageArtifact 与 raw response

实现位置：

- [`models/import_parse_attempt.py`](../../addons/ai_vendor_invoice/models/import_parse_attempt.py)
- [`models/provider_call.py`](../../addons/ai_vendor_invoice/models/provider_call.py)
- [`models/page_artifact.py`](../../addons/ai_vendor_invoice/models/page_artifact.py)
- [`services/observability_service.py`](../../addons/ai_vendor_invoice/services/observability_service.py)

当前已有的证据能力：

| Evidence 层 | 已保存内容 | 语义 |
|---|---|---|
| Source PDF | `Task.source_pdf_attachment_id` | 原始输入文件 |
| ParseAttempt | 状态、序号、Provider 配置、Prompt/Contract/Model snapshot、失败阶段、诊断状态 | 一次完整解析尝试 |
| ProviderCall | 调用序号、重试序号、Provider/Model、输入模式、页数、时间、HTTP outcome、validation status、failure stage | 一次实际 Provider 调用 |
| ProviderCall raw response | 私有 JSON attachment | Provider 原始响应 |
| ProviderCall page extraction | `page_extraction_result` | 页面级提取结果，包括可存在的 raw facts |
| PageArtifact | 页号、图片附件、MIME、checksum、byte size、rendered time | 实际发送给 Provider 的页面证据 |
| Attempt canonical snapshot | `canonical_result` JSON | 归一化后的业务结果 |
| Attempt mapping result | `mapping_result` JSON | 供应商/产品/税/币种候选 |
| Audit log | action、task、attempt、用户、时间、摘要 | 流程事件摘要 |

这些对象已经能回答：

- 哪个 Task 的哪次 Attempt 产生了结果；
- 使用了哪个 Provider、模型和 Prompt 版本；
- 实际发送了哪些页；
- Provider 原始响应是什么；
- 哪一页、哪一次调用失败；
- Canonical 和 Mapping 结果是什么。

它们目前不能稳定回答：

- Canonical 的某个字段来自哪一个 `source_label`；
- 该字段对应原始文本在第几页的哪个坐标；
- 该字段是 PDF 直接提取、AI 识别、AI 推断还是人工修改；
- 字段级 confidence 是否与真实准确率校准；
- 人工把某字段从什么值改成了什么值以及修改原因。

### 2.4 Statement 与 source ParseAttempt

实现位置：

- [`models/statement.py`](../../addons/ai_vendor_invoice/models/statement.py)
- [`models/import_task.py`](../../addons/ai_vendor_invoice/models/import_task.py)
- [`services/statement_projection.py`](../../addons/ai_vendor_invoice/services/statement_projection.py)

Statement 当前保存的是审核权威业务值：

- `invoice_number`
- `invoice_date`
- `supplier_id`
- `supplier_name`
- `currency_id`
- `total_amount`
- `total_tax`
- `subtotal`
- `line_ids`
- 行上的 description、quantity、price_unit、amount、tax、reconciliation clue 等

Statement 还保存：

```text
source_parse_attempt_id
```

因此 Statement 可以追溯到产生候选值的 ParseAttempt，但不能追溯到某个字段或某一行的具体 PageArtifact、ProviderCall 或原始文本位置。

`human_review_result` 保存最终审核值，Bill Creator 只读取该人工审核结果。Statement/Review 投影没有写入字段级 source 或 raw text。

### 2.5 人工修改与审核日志

当前 `action_save_review()` 和 Statement aggregate command 会记录：

```text
action = human_modify
snapshot_delta = 摘要
```

实际摘要是顶层 key 数量或固定说明，不是字段级 old value/new value/reason diff。

因此当前系统能证明“发生过人工修改动作”，但不能从现有审计日志重建：

```text
哪个字段
AI 原值
人工值
修改原因
修改人
```

## 3. Real review cases

优先检查了现有真实样本执行报告、人工审核模板、Closure 报告和测试证据。没有为了本 Spike 重新调用 AI，也没有创建或修改业务数据。

现有真实 Provider 报告记录了三张代表性运输发票：

| 实际文件 / Task evidence | 代表场景 | AI 结果 | 人工修正记录 | 原文需求 | 页面位置需求 | 来源类型需求 | 现有能力是否足够 | Evidence |
|---|---|---|---|---|---|---|---|---|
| `bring_26022366.pdf`；Task 904 / Attempt 680 | 多页发票，5 页、22 行 | Canonical PASS；22 lines；最终 `awaiting_review` | **未取得** | 未取得 | 未取得 | 未取得 | 无法从现有审核记录判定 | [Closure report](../reports/INTENT-IMPLEMENT-INVOICE-STATEMENT-001-CLOSURE-REPORT.md) |
| `feelogic_35318.pdf`；Task 905 / Attempt 659 | 单页/少量业务行，1 页、2 行 | Canonical PASS；2 lines；最终 `awaiting_review` | **未取得** | 未取得 | 未取得 | 未取得 | 无法从现有审核记录判定 | [Closure report](../reports/INTENT-IMPLEMENT-INVOICE-STATEMENT-001-CLOSURE-REPORT.md) |
| `mainfreight_1727001370.pdf`；Task 906 / Attempt 660 | 多页发票，3 页、14 行；存在 timeout retry recovery | Canonical PASS；14 lines；最终 `awaiting_review` | **未取得** | 未取得 | 未取得 | 未取得 | 无法从现有审核记录判定 | [Closure report](../reports/INTENT-IMPLEMENT-INVOICE-STATEMENT-001-CLOSURE-REPORT.md) |

### 3.1 已观察到的技术事实，不等同于客服需求

- Bring 的跨页 header disagreement 被 document normalization 的候选选择策略处理，没有形成已记录的人工字段修正案例。
- Mainfreight 的 Provider timeout retry 被恢复，没有形成字段级人工争议案例。
- PageArtifact 已被人工与源 PDF 对照验证，但这是证据保存/技术验证，不是客服要求字段坐标的记录。
- Human Review manifest 和 case template 主要是验收模板；其中案例多数为 `NOT_RUN` 或待人工配置，不能当作实际客服反馈。
- Closure 报告明确指出三张真实发票的 human-reviewed field values 尚未记录。

因此，本次没有取得：

- 实际人工修正字段；
- 实际字段争议；
- 因无法查看原文而阻塞审核的案例；
- 因无法确认来源而阻塞审核的案例。

## 4. Existing capabilities vs actual gaps

| 审核问题 | 当前能力 | 当前缺口 | 是否有真实阻塞证据 | 证据位置 |
|---|---|---|---|---|
| 查看 AI 产生的业务值 | Canonical snapshot、Statement、Human Review result | UI/结果投影不总是展示完整 Canonical 元数据 | 否；未取得客服阻塞记录 | `canonical_result`、Statement、review dialog |
| 追溯到哪次解析 | Task → current ParseAttempt；Statement → `source_parse_attempt_id` | 不在字段级关联 | 否 | `import_task.py`、`statement.py` |
| 查看 Provider 原始响应 | ProviderCall private attachment、Attempt attachment | 需要 reviewer/config manager 权限；不是字段级索引 | 否 | `provider_call.py`、`observability_service.py` |
| 查看发送给 AI 的原始页面 | PageArtifact image attachment、页号、checksum | 不是字段级位置标注 | 否 | `page_artifact.py` |
| 查看页面提取的原始事实 | ProviderCall `page_extraction_result` 可包含 `raw_facts`/`raw_fields`/`source_page` | 未归并到 Canonical 字段；不是稳定的字段级 contract | 否 | `page_extraction.py`、`document_normalizer.py` |
| 识别字段来自 PDF/AI/人工 | Attempt/ProviderCall 能识别流程来源；Statement 可识别人工审核阶段 | 没有字段级 source 枚举 | 否 | Attempt、ProviderCall、audit log |
| 使用字段 confidence | Canonical 有 0..1 结构约束；UI 有阈值高亮逻辑 | 当前 AI/native projection 可产生 `0.0`；没有校准准确率证据 | 否 | `canonical.py`、`native_document_projection.py`、review dialog |
| 解释 confidence 是否可信 | 只能知道数值范围合法 | 没有 calibration、样本准确率或定义 | 否 | Schema 约束仅为结构约束 |
| 查看人工修改历史 | 有 `human_modify` audit event 和摘要 | 无 old/new field diff、原因和字段来源 | 否；没有实际修正记录 | `import_log.py`、`import_task.py` |
| 进行金额/格式/基础完整性校验 | `validation_service`、review warnings、bill pre-check | 不存在统一的单字段 `valid`；这是有意的分层 | 否 | `validation_service.py`、bill creator |
| 进行业务/订单核验 | 保持在 Statement/业务流程边界 | 本 Spike 不调查或修改该层 | 未调查 | 生产架构边界 |

### 4.1 `validation_status` 的实际语义

当前 `ProviderCall.validation_status` 只表示 Provider response/page extraction 的验证结果：

```text
not_run / pass / fail
```

它不等价于以下任何一个状态：

- JSON/schema 合法；
- 字段格式合法；
- 金额计算一致；
- Odoo 基础数据完整；
- 业务/订单核验通过；
- 人工确认完成。

这些层次目前分别由 schema validation、normalization、`validation_service`、Statement 约束、bill pre-check、Task state 和 human review flags 表达。当前没有把它们压缩成一个字段级 `valid`，这是正确的语义分层。

## 5. Metadata reliability findings

### 5.1 `source`

当前可以可靠区分的层级是：

- Source PDF：Task 的原始附件；
- Provider input：PageArtifact 记录实际发送的页面；
- Provider response：ProviderCall raw response；
- Page extraction：ProviderCall 的页面结果；
- Canonical：归一化后的业务值；
- Statement：人工审核权威值。

当前不能可靠区分的字段级来源是：

```text
PDF 原文直接提取
AI 识别
AI 推断
人工修改
```

PageExtraction 的 `raw_facts` / `raw_fields` 带有 `source_label`、`source_value` 和 `source_page` 的潜力，但这些信息只存在于页面级 ProviderCall 结果，不是 Canonical 字段的稳定来源契约。不能仅因为出现 `source_page` 就声称 Canonical 已具备字段级 provenance。

### 5.2 `confidence`

Canonical schema 对 confidence 只做结构约束：

```text
number, minimum 0, maximum 1
```

当前没有发现：

- 字段级人工标注准确率；
- Provider 间统一 confidence 定义；
- calibration 数据；
- 由 confidence 推导审核通过的验证；
- 证明 `0.97` 等于 97% 实际准确率的证据。

因此 confidence 当前只能作为候选 UI 提示或诊断元数据，不能单独作为自动审核、自动确认或业务通过条件。

### 5.3 `raw_text` 与 `source_location`

当前 raw response 可以追溯 Provider 返回的原始 JSON，PageArtifact 可以打开实际输入页面，PageExtraction raw facts 可以包含原始 label/value 和 page number。

但当前没有统一可靠的：

- 字段级 `raw_text`；
- PDF 文本坐标；
- 页面 bounding box；
- Canonical field → PageArtifact/ProviderCall 的直接引用；
- 人工字段修改前后的原文证据。

如果未来要求这些信息，需要定义新的稳定输出契约或从现有 PageExtraction raw facts 建立受控投影。这会涉及 Structured Output/normalization 与 UI/存储边界，不能在本 Spike 中假设为零成本。

### 5.4 `validation_status`

`validation_status` 目前是 ProviderCall 级别、阶段级别的技术验证结果。它不应被扩展成含义不清的字段级 `valid`。

当前正确的解释应是：

```text
Provider response/page extraction validation
```

而不是：

```text
业务发票最终有效
```

## 6. A / B / C / D comparison

| 方案 | 真实审核收益 | 对已观察问题的解决 | Canonical 业务值稳定性 | 是否需要改 Structured Output | 是否需要改 Projection | 是否需要改 Statement/UI | 历史数据/Replay 风险 | 复杂度 |
|---|---|---|---|---|---|---|---|---|
| **A. Keep current Canonical** | 保持现有审核值和 Attempt/Provider evidence 链路 | 当前没有已证实的字段级 Evidence 阻塞 | **不变** | 否 | 否 | 否 | 最低；保留现有 raw/Canonical/Statement | 最低 |
| **B. Full field-object model** | 理论上可统一 value/source/confidence/raw/location/validation | 可覆盖未来多种 provenance，但当前没有真实案例证明需要全部字段 | 高风险；当前已是部分对象化，继续扩展会改变契约 | 是 | 是 | 是 | 高；影响历史 Canonical、Replay、映射和 UI | 最高，容易过度设计 |
| **C. Separate Canonical + Evidence** | 保持业务值稳定，同时提供独立证据层 | 能解决字段与原文/页/Provider 关联，但当前没有实际阻塞案例 | Canonical 可不变；需增加关联边界 | 通常需要输出稳定 evidence contract | 需要把 evidence 关联到 Canonical | 未来需要展示和权限设计 | 中高；需处理历史 Attempt 缺 Evidence | 高；接近通用 provenance 平台 |
| **D. Add limited evidence only** | 针对明确字段或审核问题增加最小证据 | 若未来出现具体争议，可精确解决 | 可保持业务值结构；只增加受控附加信息 | 需要针对已确认字段修改 | 可能需要小范围改动 | 可能需要小范围展示 | 中；取决于字段和历史兼容策略 | 中；但当前尚无确定字段范围 |

### 6.1 特别检查：是否可以业务值不变、证据独立增加？

可以。从概念上看，Canonical 业务值不必改成完整字段对象，也不必把所有 Evidence 塞进每个字段。未来如果真实审核案例证明某个字段必须显示原文或页码，可以在不改变业务值的前提下增加受控证据关联。

但当前没有真实案例告诉我们：

- 哪些字段需要；
- 需要哪种证据；
- 审核人员需要文字、页码、坐标还是 Provider 原文；
- 证据是否应该保存为永久数据；
- 历史 Attempt 缺少证据时如何呈现。

因此“可以这样做”不等于“现在应该这样做”。

## 7. Recommendation

### Decision: A. Keep current Canonical

当前不修改 Canonical，也不增加字段级 Evidence 框架。

理由：

1. 现有 Canonical 已能表达当前审核业务值，并且已经使用 `value + confidence` 的有限对象结构；
2. Task、ParseAttempt、ProviderCall、PageArtifact、raw response、Canonical snapshot 和 Statement source attempt 已提供足够的流程级追溯；
3. PageExtraction 已保留部分 raw facts/page 信息，但尚未证明这些信息需要成为 Canonical 的字段级契约；
4. 当前没有取得真实客服/审核案例，证明缺少字段原文、页码或来源已经阻塞审核；
5. 现有审计确实缺少 old/new 字段 diff，但也没有实际人工修正记录证明该缺口正在造成业务问题；
6. B、C、D 都会提前引入契约、回放、历史数据、权限或 UI 复杂度，当前证据不足以证明其收益。

当前继续维持：

```text
AI/page/native extraction
  -> existing Canonical
  -> existing Statement
  -> existing Business Verification
  -> existing Human Confirm
  -> existing Vendor Bill
```

本结论不是声称“字段 Evidence 永远不需要”，而是：

> 目前没有真实审核阻塞证据，因此不增加复杂度。

## 8. Unsupported assumptions

本 Spike 明确不作以下假设：

- 不假设客服一定需要字段级 provenance；
- 不假设 `confidence=0.97` 代表 97% 准确率；
- 不假设 `raw_facts` 自动等于最终 Canonical 字段来源；
- 不假设 PDF 文本可复制就有可靠字段位置；
- 不假设 Provider raw response 一定永久可用或适合作为审核 UI；
- 不假设所有历史 Attempt 都有 PageArtifact；
- 不假设 Statement 的 `source_parse_attempt_id` 等于字段级来源；
- 不假设 audit log 摘要可以重建人工 old/new 值；
- 不假设 schema validation 通过就代表业务或订单核验通过；
- 不因为候选设计 B/C 更完整，就认为它们现在更合适；
- 不重新打开结构化电子发票 XML/UBL/Factur-X/ZUGFeRD 决策；
- 不通过新 AI 调用制造人工修正或字段争议证据。

## 9. Re-open trigger

只有出现以下真实证据时，才重新评估字段级 Evidence：

1. 审核人员实际因为无法查看原文而无法确认某个字段；
2. 审核人员实际因为无法定位字段所在页而无法处理多页或拆分争议；
3. 供应商/Provider 的结果在多次真实案例中需要区分“识别”与“推断”；
4. 真实人工修正案例需要保留 old value、new value 和修改原因；
5. 合规、审计或客户明确要求保留字段来源；
6. 现有 `raw_facts` 已经被业务流程实际使用，但当前无法稳定关联到 Canonical/Statement 字段。

重新评估时，应先收集 3–5 个真实审核案例，逐字段记录：

```text
Task / Statement
字段
AI 原值
实际值
人工修正值
修正原因
需要的证据类型
现有证据是否足够
```

在重新取得这类证据之前，不进入 DDD、TDD、Coding Contract 或生产实现。
