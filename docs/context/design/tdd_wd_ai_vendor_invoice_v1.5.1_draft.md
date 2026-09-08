# AI Vendor Invoice - TDD v1.5.1 反工程技术设计草案

> **状态：DRAFT - NOT FROZEN**
>
> 本文档是基于当前代码、测试记录和人工页面验证反向整理的同步版
> 技术基线草案。不授权生产代码修改，不自动冻结 v1.5.1。

## 1. 版本与上游基线

| 项目 | 内容 |
|---|---|
| 当前草案版本 | TDD v1.5.1 |
| 反工程方法 | 以实现事实为准，结合仍有效的业务契约 |
| 上游历史基线 | TDD v1.5，已于 2026-09-08 固定为历史设计基线 |
| 对应冻结提交 | `560441e08a997a4dc062a45408f30633db5e287a` |
| 本次代码变更 | 无 |
| 技术范围 | 当前同步解析版 |
| 异步范围 | 延后，不阻塞本草案 |

历史 v1.5 保留原有设计内容，不要求当前代码回退以符合历史设计。

## 2. 当前架构

```text
PDF 上传
  -> Import Task（技术聚合根）
  -> Parse Attempt（AI 解析尝试）
  -> Vendor Invoice Statement（业务单据）
  -> 人工编辑/确认/取消
  -> Vendor Bill
```

- `vendor.invoice.import.task` 是技术聚合根，负责 PDF、解析尝试、状态和
  错误。
- `vendor.invoice.statement` 是人工复核和业务单据入口。
- Task 与 Statement 为一对一关系；Statement Line 从属于 Statement。
- Task 聚合动作负责系统创建、解析和账单流程；普通 Statement CRUD 不是
  系统流程入口。
- AI Invoice 是独立应用，菜单包含 Imports、Statements、Configuration。

## 3. 模型与字段

### 3.1 Import Task

Task 当前状态为：

```text
to_parse
parsing
awaiting_review
bill_generated
error
cancelled
```

关键能力：

- 保存上传 PDF 的 `source_pdf_filename`；
- 保存 `source_pdf_attachment_id` 和 PDF SHA-256 checksum；
- 同公司、相同活动 PDF 默认不能重复创建 Task；
- Cancel 后释放 checksum，允许重新导入；
- 使用统一 `error` 状态和 `parse_error_summary`；
- 支持同步解析模式；
- 取消后的同步解析结果失效，不得创建 Statement 或 Vendor Bill。

### 3.2 Vendor Invoice Statement

模型：`vendor.invoice.statement`。

| 字段 | 当前实现 |
|---|---|
| `name` | 必填、序列生成、只读的 Statement 编号 |
| `task_id` | 必填 Many2one；Task 聚合关系；cascade；每个 Task 至多一个 Statement |
| `company_id` | 从 Task related/store/index/readonly |
| `supplier_id` / `supplier_name` | 供应商身份 |
| `source_pdf_attachment_id` | 来源 PDF 的只读关联 |
| `source_pdf_filename` | 从 Task 关联的只读文件名 |
| `source_parse_attempt_id` | 必填的来源 Parse Attempt 关联 |
| `invoice_number` | 发票号 |
| `invoice_date` | 发票日期 |
| `currency_id` | 单据货币 |
| `subtotal` | Statement Lines 未税金额汇总 |
| `total_tax` | Statement Lines 税额汇总 |
| `total_amount` | 含税金额汇总 |
| `overall_tax_rate` | 汇总税率 |
| `vendor_bill_id` | 只读 Vendor Bill 追溯关联 |
| `line_ids` | Statement Lines |
| `state` | 存储 Selection，由业务动作控制 |

当前 Statement 状态为：

```text
draft
confirmed
cancelled
bill_created
```

活动 Statement 使用公司、供应商身份和标准化发票号进行业务唯一性控制；
取消的 Statement 不占用该业务唯一键。

### 3.3 Vendor Invoice Statement Line

模型：`vendor.invoice.statement.line`。

| 字段 | 当前实现 |
|---|---|
| `statement_id` | 必填 Many2one，cascade |
| `sequence` | 明细顺序 |
| `description` | 必填描述 |
| `product_id` | 产品 |
| `quantity` | 数量，默认 1 |
| `price_unit` | 单价 |
| `amount` | 未税金额 |
| `tax_rate` | 百分比税率 |
| `tax_amount` | 税额 |
| `total_amount` | 含税金额 |
| `tax_raw_text` | 原始税文本 |
| `tax_ids` | Odoo 税配置 |
| `reconciliation_clue` | 对账线索 |
| `charge_details` | 费用明细 |
| `reconciliation_clues` | JSON 对账线索 |
| `currency_id` | 从 Statement 关联的货币 |

历史 v1.5 中未被当前业务使用的 `raw_fields`、`confidence`、
`mapping_status`、`human_reviewed` 等字段不属于 v1.5.1 当前基线；本草案
不授权补充这些字段。

## 4. 状态与业务动作

### 4.1 Task

- `Run AI` 执行新的 Parse Attempt；重跑本身不等于接受候选结果。
- `Cancel` 将 Task 置为 `cancelled`，释放 PDF checksum，并阻断过期同步结果。
- 解析成功进入 `awaiting_review`，失败统一进入 `error`。
- 账单生成成功后进入 `bill_generated`。

### 4.2 Statement

- 新建单据处于 `draft`；
- Draft 可由 Reviewer 编辑；
- Confirmed、Cancelled、Bill Created 为业务只读；
- 状态字段不能通过普通 `write` 直接修改；
- 状态转换通过 Task/Statement 业务动作完成；
- Bill 创建后 Statement 进入 `bill_created`。

## 5. 同步解析流程

```text
上传 PDF
  -> 创建 Task 与来源附件
  -> 计算 checksum 并检查活动重复项
  -> 同步调用 PDF 预处理和 Provider
  -> 创建 Parse Attempt
  -> 生成 Statement 与 Lines
  -> awaiting_review
```

同步模式是 v1.5.1 的验收范围。取消后，解析结果必须再次检查 Task 是否
仍然有效；失效结果不得写入 Statement 或创建 Bill。

异步队列端到端尚未验收，作为后续独立技术认证事项，不属于本次同步版冻结
门槛；本次不修改 queue_job、不引入 Redis、不设计异步取消。

## 6. AI Candidate 当前行为

后端兼容方法当前会：

1. 选择并校验当前成功的 Parse Attempt；
2. 覆盖 Statement 表头候选值；
3. 删除已有 Statement Lines；
4. 按候选结果重建 Lines；
5. 更新 `source_parse_attempt_id`。

该方法是技术兼容操作，不是人工复核入口。Statement 表单上的
`Apply AI Candidate` 按钮已经移除；人工复核直接使用 Statement Form 和
Line Form。v1.5.1 不自动恢复历史版本“只覆盖未编辑字段”的行为。

## 7. 金额联动与只读规则

金额语义：

```text
amount       = 无税金额
tax_rate     = 税率百分比
tax_amount   = 税额
total_amount = 含税金额
```

公式：

```text
tax_amount = amount * tax_rate / 100
total_amount = amount + tax_amount
tax_rate = tax_amount / amount * 100
```

多字段同时写入时优先级为：

```text
amount > tax_rate > tax_amount > total_amount
```

四个字段分别有 onchange，可在表单中实时联动；ORM 归一化作为持久化
一致性保障。无税金额为零时，税额必须为零，否则抛出 ValidationError。

Statement 表头自动汇总 `subtotal`、`total_tax`、`total_amount` 和
`overall_tax_rate`。

Reviewer 只能编辑 Draft Statement 及其 Lines。非 Reviewer、非 Draft 的
create/write/unlink 均由 ORM 拒绝，视图同时提供只读控制。

## 8. UI、菜单与权限

菜单结构：

```text
AI Invoice
  ├── Imports
  ├── Statements
  └── Configuration
```

Imports 列表显示 File Name 和 Error，不显示 Company、Current Attempt。
Statements 列表显示 File Name。

已验证的表单包括：

- Task Form：PDF 上传、Run AI、Cancel、Error Badge、Statement/PDF 导航；
- Statement Form：表头、状态动作、来源追溯、汇总和 Lines；
- Statement Line Form：独立编辑界面；
- Configuration：Provider、Alias、Keyword、Tax、Currency、Threshold、
  System Configuration 子菜单。

权限边界：

- Reviewer 负责 Draft Statement/Line 人工编辑和业务确认；
- Configuration Manager 维护配置；
- Task 保持技术信息和解析历史；
- 来源 PDF、Parse Attempt、Task、Statement、Vendor Bill 之间可追溯导航。

## 9. 数据约束与回填

- PDF checksum 对活动 Task 唯一；取消 Task 后可复用；
- Statement 活动业务唯一键为公司、供应商身份、标准化发票号；
- Task 与 Statement 一对一；
- Statement Lines cascade 隶属 Statement；
- 状态转换受业务动作和 ORM 权限保护；
- 新建 Task 时持久化上传文件名。

开发数据库中曾从 `ir.attachment.name` 对 5 条既有 Task 执行一次性文件名
回填。这是开发/UAT 数据操作，不代表所有环境已经迁移，也不构成生产
migration 设计。

## 10. 测试与验收

### Automated Tests

- Python 编译：通过；
- XML 结构和仓库检查：19 pass，0 fail；
- CC-08 聚焦测试：3 tests，0 failed，0 errors；
- CC-09 金额聚焦测试：4 tests，0 failed，0 errors；
- 实时 onchange 与 ORM 金额测试：2 tests，0 failed，0 errors。

### Manual Browser UAT

开发数据库已人工验证：

- AI Invoice、Imports、Statements、Configuration 菜单；
- Task Form、Statement Form、Statement Line Form；
- Task Cancel 和 Error Badge；
- 金额实时联动；
- Imports 的 File Name/Error；
- Statements 的 File Name；
- Apply AI Candidate 按钮已移除；
- 新旧 Task/Statement 文件名显示。

### Not Yet Verified

- 异步队列端到端执行和中断；
- 完整并发矩阵；
- 所有 Bill Creator 边界转换；
- 生产环境迁移和生产数据回填。

## 11. v1.5.1 相对 v1.5 的简短修订记录

1. 将 v1.5 内容固定为历史设计基线，不覆盖原文。
2. 按当前实现同步 Statement、Line、Task 字段和关系名称。
3. 纳入已测试、已人工确认的 Cancel、统一 error、同步解析、金额联动、
   表单、菜单和文件名行为。
4. 记录 Candidate 当前覆盖并重建 Lines 的技术行为，以及 UI 按钮移除事实。
5. 将当前不需要的历史字段标记为废止，不产生补字段要求。
6. 将异步队列明确延期，不阻塞同步版技术基线。

```text
TDD_V1_5 = FROZEN
TDD_V1_5_1 = DRAFT
REVISION_METHOD = REVERSE_ENGINEERING
PRODUCTION_CODE_CHANGED = NO
ASYNC_SCOPE = DEFERRED
NEXT_STEP = STOP_FOR_REVIEW
```
