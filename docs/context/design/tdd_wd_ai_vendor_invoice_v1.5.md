# Invoice Statement 技术设计

> **FROZEN - HISTORICAL DESIGN BASELINE**
>
> 本文档是经人工评审冻结的 TDD v1.5 版本，不修改历史冻结 TDD v1.4.2。

**冻结版本**：TDD v1.5
**冻结日期**：2026-09-08
**对应 Git commit**：`560441e08a997a4dc062a45408f30633db5e287a`
**后续修订**：TDD v1.5.1（反工程同步版，当前为 DRAFT）
**冻结基线**：SRS v1.3.4、DDD v1.3、TDD v1.4.2

## 1. ORM 模型

### 1.1 `vendor.invoice.statement`

建议字段：

| 字段 | Odoo 类型 | 约束 |
|---|---|---|
| task_id | Many2one | required，属于 Task 聚合，cascade；禁止独立 CRUD |
| source_parse_attempt_id | Many2one | nullable；仅人工应用候选时更新 |
| company_id | Many2one related | `related="task_id.company_id"`、store、index、readonly |
| vendor_partner_id | Many2one | 供应商 |
| source_attachment_id | Many2one | 原始 PDF，restrict |
| statement_number | Char | 可空 |
| invoice_number | Char | 业务字段 |
| statement_date | Date | 可空 |
| invoice_date | Date | 业务字段 |
| currency_id | Many2one | 货币 |
| total_amount | Monetary | 使用 `currency_id` |
| total_tax | Monetary | 使用 `currency_id` |
| human_reviewed | Boolean | 当前 Statement 复核轮次 |
| raw_fields | Json | 未标准化字段和值，必须 Schema 校验 |
| state | Selection computed | readonly、派生 UI 状态，不独立写入 |

不增加 `normalized_result`。

`state` 的派生输入只能来自：

```text
task.state
statement.human_reviewed
invoice-side relation
```

### 1.2 `vendor.invoice.statement.line`

| 字段 | Odoo 类型 | 约束 |
|---|---|---|
| statement_id | Many2one | required，cascade |
| sequence | Integer | 明细顺序 |
| product_id | Many2one | 人工确认的费用产品 |
| tax_ids | Many2many | 遵循 `account.move.line.tax_ids` |
| description | Text | 标准描述 |
| quantity | Decimal | 数量 |
| unit_price | Decimal | 单价 |
| subtotal | Decimal | 未税金额 |
| tax_amount | Decimal | 税额 |
| line_total_amount | Decimal | 含税金额 |
| our_reference | Char | 稳定业务字段 |
| carrier_reference | Char | 稳定业务字段候选 |
| shipment_reference | Char | Shipment number 候选 |
| carrier_file_reference | Char | 可空、可 unmapped |
| carrier_order_reference | Char | 可空、可 unmapped |
| transport_date | Date | 运输日期 |
| pickup_date | Date | 装货日期 |
| pickup_address | Text | 装货地址 |
| delivery_date | Date | 卸货/交付日期 |
| delivery_address | Text | 卸货地址 |
| raw_fields | Json | 全部原始字段和值及字段级 metadata |
| confidence | Float | AI 提示 |
| mapping_status | Selection | normalized/manual/unmapped |

不使用单一 `source_label/source_value` 表示整条明细的原始数据。

## 2. Task 聚合与权限边界

- Task 是唯一 Aggregate Root；
- Statement/Line 创建和更新必须由 Task 领域服务调用；
- UI/job 不直接调用 Statement `create/write/unlink`；
- 任务删除时 Statement/Line 按聚合关系级联；
- Statement state 不接受独立业务写入；
- Statement company 从 Task related 读取，不重复维护来源；
- 不新增 Task/Attempt 状态。

## 3. Invoice `_inherit` 追溯扩展

采用 Odoo 标准 `_inherit`，不 monkey-patch：

```python
_inherit = "account.move"
vendor_invoice_statement_id = fields.Many2one(
    "vendor.invoice.statement",
    ondelete="restrict",
    index=True,
    readonly=True,
)

_inherit = "account.move.line"
vendor_statement_line_id = fields.Many2one(
    "vendor.invoice.statement.line",
    ondelete="set null",
    index=True,
    readonly=True,
)
```

Invoice/Invoice Line 侧 FK 是唯一数据库权威关系；Statement 侧为 computed/read-only 反向关系，不落库第二个可写 FK。

Statement 删除账单关系使用 `set null` 语义，账单删除必须保留 Statement 和审计记录。

## 4. JSON Schema

必须新增应用层 Schema：

1. `Statement.raw_fields`
2. `StatementLine.raw_fields`

建议结构：

```json
{
  "Uw ref.": {
    "value": "REF-001",
    "page": 2
  },
  "Shipment number": {
    "value": "SHP-8891",
    "page": 2
  }
}
```

Schema 要求：

- object；
- key 为原始字段名；
- value 支持字符串、数字、日期文本和字段级 metadata；
- 不允许无限递归；
- 不得携带 Provider secret；
- 非法结构阻止 Statement 保存。

## 5. Projection Service

新增领域服务：

```text
Statement + Statement Lines
    → HumanReviewResult projection
```

规则：

- 单向 Statement → Task；
- 同一事务；
- 使用现有 HumanReviewResult Schema；
- projection 失败时 Statement 保存回滚；
- 禁止 `human_review_result → Statement`；
- Bill Creator 第一阶段代码和数据源不变；
- Statement 不提供绕过 Task 的投影入口。

## 6. AI Candidate Application

流程：

```text
Task aggregate service
  → select ParseAttempt
  → validate Canonical/Mapping candidate
  → apply only untouched Statement fields
  → preserve user edits
  → update source_parse_attempt_id
  → rebuild human_review_result
```

AI 重跑只创建新 Attempt，不调用该流程。

## 7. PDF 页面语义

```text
PDF attachment
  → pdf_preprocessor
  → ProviderInput(pages)
  → one Provider request
  → one CanonicalResult
  → one Statement
```

- 汇总页提供 Header/Total；
- 明细页提供 Statement Lines；
- 不生成页级业务对象；
- 不实现页级结果合并；
- 多张独立发票继续由 Task 设置 `error_split_required`。

## 8. 事务、并发和锁

- Task 聚合变更使用现有 Task 行锁；
- 不能把锁持有到外部 Provider HTTP；
- Statement confirmation 和 Bill 关联使用短事务；
- 并发应用候选必须重新检查当前 Attempt 指针；
- 并发 Bill 生成依赖现有 Task 幂等锁；
- 任意 projection/Invoice 关联异常整体回滚；
- stale worker 只能更新自身 Attempt，不能覆盖 Statement/Task。

## 9. 权限与审计

测试并实现：

- User：按 Task 公司读取允许的 Statement；
- Reviewer：编辑 Statement、应用候选、确认复核；
- Config Manager：维护 Provider/mapping/字段别名（字段别名模型第一阶段不新增）；
- Invoice 侧追溯权限；
- raw_fields 和运输地址权限；
- raw AI response 权限；
- Provider API key 不可 RPC 明文返回；
- 候选应用、Statement 编辑、投影、Invoice 关联、账单删除写审计。

## 10. 测试计划

### Unit

- Statement/Line Schema；
- `source_parse_attempt_id` 只在应用候选时更新；
- Statement state 派生且 readonly；
- `raw_fields` 保留多个原始字段；
- unknown field 不丢失；
- `tax_ids` 使用 Odoo 18 标准；
- projection 单向一致性；
- reference 候选归一化。

### Integration

- Bring Cargo：汇总页 + 多页运输明细；
- Feelogic：`Uw ref.`、`Dossier`、`Opdracht`；
- Mainfreight：Shipment number、O.No. 和明细 reference；
- PDF → ProviderInput → Canonical → Statement；
- Statement → Task compatibility projection；
- Statement → Invoice；
- Invoice → Statement；
- Invoice Line → Statement Line；
- 原始 PDF/AI JSON/审计日志追溯；
- AI 重跑不覆盖 Statement；
- 多独立发票保持 `error_split_required`。

### Concurrency/Security/Rollback

- 并发 Statement confirmation；
- 并发候选应用；
- 并发 Bill 生成；
- projection 失败回滚；
- Invoice 关联失败回滚；
- stale worker；
- 多公司；
- User/Reviewer/Config Manager；
- raw fields、raw response、Provider secret。

## 11. 开发数据策略

当前是开发/UAT 环境，没有生产历史数据：

- 不设计 migration；
- 不写 pre/post migration；
- 不回填历史 Task；
- 不回填历史 Bill；
- module upgrade 后新流程直接创建 Statement；
- 测试数据允许重新初始化。
