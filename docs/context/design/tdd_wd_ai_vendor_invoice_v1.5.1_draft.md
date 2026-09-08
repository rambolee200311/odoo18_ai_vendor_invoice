# AI Vendor Invoice 技术详细设计

**版本**：TDD v1.5.1
**状态**：DRAFT - NOT FROZEN
**方法**：REVERSE ENGINEERING
**上游**：[TDD v1.5 历史冻结基线](./tdd_wd_ai_vendor_invoice_v1.5.md)
**范围**：当前同步解析实现；异步队列延期认证
**生产代码变更**：NO

## 1. 目标与边界

本文件是当前 `addons/ai_vendor_invoice` 的技术设计说明，不是旧 TDD 的差异
报告。正文只描述当前代码已经实现或明确存在的接口；未验收的异步能力不作为
同步版完成条件。

系统边界：

```text
PDF 上传 -> Import Task -> Parse Attempt -> Statement/Lines
         -> Reviewer 编辑/确认 -> HumanReviewResult -> Vendor Bill
```

Task 是技术聚合根，Statement 是唯一人工业务复核入口，Line 从属于
Statement。AI 负责解析，映射负责推荐，Reviewer 负责最终确认，Bill Creator
只读取人工复核结果。

## 2. 模块和依赖

模块目录为 `addons/ai_vendor_invoice`，manifest 当前依赖：

```text
account
contacts
queue_job
```

当前实现分层：

- `models/`：Task、Parse Attempt、Statement、配置、审计和账单扩展；
- `services/`：解析、PDF 预处理、Provider 输入、映射、投影、账单和可观测性；
- `adapters/`：DeepSeek、OpenAI、Claude 和文档归一化；
- `schemas/`：Canonical、Document、Page、Mapping、Human Review、Warning；
- `views/`：Task/Statement/Line、诊断和 Configuration；
- `static/src/owl/`：保留的前端兼容资源；
- `tests/`：模型、服务、投影、可观测性和 Intent 测试。

模块为独立 Odoo 应用，菜单为：

```text
AI Invoice
  ├─ Imports
  ├─ Statements
  └─ Configuration
```

## 3. ORM 模型

### 3.1 Import Task

模型：`vendor.invoice.import.task`。

关键字段：

| 字段 | 类型/语义 |
|---|---|
| `name` | 必填 Task 编号 |
| `company_id` | 必填，创建后不可改变 |
| `source_pdf_attachment_id` | 来源附件，restrict |
| `source_pdf_upload` | 上传内容 |
| `source_pdf_filename` | PDF 文件名 |
| `source_pdf_checksum` | SHA-256，活动 Task 唯一 |
| `state` | `to_parse`、`parsing`、`awaiting_review`、`bill_generated`、`error`、`cancelled` |
| `synchronous_parse` | 是否在当前请求同步解析，默认 true |
| `current_parse_attempt_id` | 当前 Parse Attempt |
| `parse_attempt_ids` | Attempt 历史 |
| `parse_error_summary` | 安全的用户错误摘要 |
| `parse_error_badge` | 错误徽章 |
| `human_review_result` | Bill Creator 唯一输入 |
| `statement_id` | 一对一 Statement |
| `vendor_bill_id` | Vendor Bill 追溯 |

Task 动作包括 `action_rerun_ai`、`action_cancel_task`、打开 Statement/PDF、
保存复核、创建 Statement、确认 Statement 和创建 Bill。

### 3.2 Parse Attempt

模型：`vendor.invoice.import.parse.attempt`。

Attempt 保存 Task、序号、Provider 配置快照、状态、解析结果、错误、诊断和
可选 queue job 关联。queue-job 入口是模型方法 `job_run_parse`；service
不直接作为 `with_delay` 目标。

### 3.3 Statement

模型：`vendor.invoice.statement`。

| 字段 | 类型/约束 |
|---|---|
| `name` | 必填、序列、只读 |
| `state` | 存储 Selection：`draft`、`confirmed`、`cancelled`、`bill_created` |
| `task_id` | 必填、cascade、每 Task 唯一 |
| `company_id` | Task related/store/readonly |
| `source_parse_attempt_id` | 必填、restrict |
| `source_pdf_attachment_id` | Task related/readonly |
| `source_pdf_filename` | Task related/readonly |
| `invoice_number` | 必填业务字段 |
| `invoice_number_normalized` | 业务唯一性辅助字段 |
| `invoice_date` | 发票日期 |
| `supplier_id` / `supplier_name` | 供应商身份 |
| `supplier_identity_key` | 业务唯一性辅助字段 |
| `currency_id` | 货币 |
| `subtotal` / `total_tax` / `total_amount` | Lines 汇总，只读 |
| `overall_tax_rate` | 汇总税率，只读 |
| `vendor_bill_id` | Vendor Bill，只读/restrict |
| `line_ids` | Statement Lines |
| `review_warnings` | Task related，只读 |

### 3.4 Statement Line

模型：`vendor.invoice.statement.line`。字段包括 `statement_id`、`sequence`、
`description`、`product_id`、`quantity`、`price_unit`、`amount`、
`tax_rate`、`tax_amount`、`total_amount`、`tax_raw_text`、`tax_ids`、
`reconciliation_clue`、`charge_details`、`reconciliation_clues` 和关联货币。

当前不存在且不要求补充的历史字段：`raw_fields`、`confidence`、
`mapping_status`、`human_reviewed`。

## 4. 状态和业务动作

Task 状态流：

```text
to_parse -> parsing -> awaiting_review -> bill_generated
                    \-> error
to_parse/parsing/awaiting_review -> cancelled
```

Statement 状态流：

```text
draft -> confirmed -> bill_created
draft -> cancelled
```

State 不能通过普通业务 `write` 直接修改。Draft 是唯一可编辑状态；Reviewer
权限和 ORM/View 双层规则同时生效。取消 Task 会释放 checksum，并使过期同步
结果失效。

## 5. 同步解析和数据流

1. 接收 PDF 内容和文件名；
2. 创建附件、Task 并计算 checksum；
3. 检查同公司活动重复 PDF；
4. 创建 Parse Attempt 并进入 `parsing`；
5. 使用 PDF preprocessor 和 Provider adapter；
6. 保存 Attempt 结果和错误；
7. 成功时通过 Task 聚合动作创建 Statement/Lines；
8. Task 进入 `awaiting_review`；
9. Reviewer 确认后生成 `human_review_result` 和 Vendor Bill。

Provider HTTP 调用不在数据库排他锁范围内。Provider secret 不进入 RPC、日志、
审计或用户可见错误。

## 6. Candidate 和人工复核

`Run AI` 只创建/运行新的 Parse Attempt，不自动接受结果。

后端兼容方法 `action_apply_ai_candidate` 当前会选择成功 Attempt、覆盖
Statement 表头、删除已有 Lines、重建 Lines 并更新来源 Attempt。该方法不是
人工复核入口。Statement Form 已移除 `Apply AI Candidate` 按钮；人工复核使用
Statement Form 和独立 Line Form。本版本不恢复“只覆盖未编辑字段”。

## 7. Statement 投影和账单

`services/statement_projection.py` 将 Statement 和 Lines 单向投影到
Task 的 `human_review_result`。`services/bill_creator.py` 只读取该投影，不从
Canonical 或 Mapping 结果补充账单字段。

账单创建必须检查现有 `vendor_bill_id`，避免重复创建；成功后写入 Task、
Statement 和 Invoice/Invoice Line 追溯关系。投影或账单关联失败时，业务事务
回滚，不留下孤立账单。

## 8. 金额规则

```text
amount       = 无税金额
tax_rate     = 税率百分比
tax_amount   = 税额
total_amount = 含税金额
```

公式为 `tax_amount = amount * tax_rate / 100`、`total_amount = amount +
tax_amount`。写入优先级为 `amount > tax_rate > tax_amount > total_amount`。
四个 onchange 提供实时联动，ORM normalization 提供持久化一致性。无税金额
为零且税额非零时抛出 ValidationError。表头汇总 subtotal、total_tax、
total_amount 和 overall_tax_rate。

## 9. UI、权限和数据

Imports 列表显示 File Name、Error，不显示 Company、Current Attempt；Statements
列表显示 File Name。Task、Statement、Line Form 均为原生 Odoo View。

Reviewer 编辑 Draft；Configuration Manager 维护 Provider、Vendor Alias、
Product Keyword、Tax、Currency、Threshold 和 System Configuration。普通用户
按公司规则读取。来源 PDF、Task、Statement 和 Vendor Bill 支持导航。

活动 PDF checksum 和活动 Statement 业务键受唯一性约束；取消记录允许重新使用。
开发数据库已从附件名回填五条 Task 文件名，不等同于生产迁移。

## 10. 错误、审计和可观测性

用户错误使用 `parse_error_summary`、`error_summary` 和 Error Badge；日志和
审计保留 Attempt、Provider call、错误分类、投影和账单操作，但不暴露 secret。
Queue diagnostic 只用于运行诊断，不改变同步业务状态。

## 11. 测试和验收

- Python 编译、XML 结构和仓库检查：已通过；
- CC-08 聚焦测试：3 通过；
- CC-09 金额测试：4 通过；
- onchange/ORM 金额测试：2 通过；
- Task/Statement/Line Form、菜单、文件名、Error Badge、金额联动：
  已完成浏览器验证；
- 异步队列端到端、完整并发矩阵、生产迁移：尚未验证。

异步专项不阻塞本同步版草案，后续不得将同步测试结果宣称为异步通过。

## 12. 代码对应审核记录

审核日期：2026-09-08。审核方式：模块文件清单、模型/动作/服务/Schema
符号搜索及现有测试记录交叉核对。

| 设计区域 | 对应代码 | 结果 |
|---|---|---|
| Task/状态/Cancel/文件名 | `models/import_task.py` | PASS |
| Parse Attempt/queue入口 | `models/import_parse_attempt.py` | PASS（异步未验收） |
| Statement/Line/金额/状态 | `models/statement.py` | PASS |
| Projection | `services/statement_projection.py` | PASS |
| Bill Creator | `services/bill_creator.py` | PASS |
| Provider/Schema | `adapters/`、`schemas/` | PASS |
| PDF/Provider输入 | `services/pdf_preprocessor.py`、`provider_input.py` | PASS |
| 菜单/表单/列表 | `views/import_task_views.xml`、`config_views.xml` | PASS |
| 权限/配置 | `security/`、`models/*config*.py` | PASS |
| 测试记录 | `tests/`、CC-08/CC-09 history | PASS |

审核结论：正文已移除 v1.4 的旧状态、旧字段和旧 queue 结论；当前同步版
设计均可在现有代码或已记录验收证据中找到对应。异步和生产迁移保持延期。

## 13. 修订记录与状态

- v1.5：固定为历史设计基线，不覆盖原文；
- v1.5.1：按当前同步实现反工程重写，纳入已测试和已人工确认行为；
- Candidate 覆盖/重建行为按当前代码记录，不恢复旧规则；
- 异步队列保留为后续独立认证，不阻塞同步版。

```text
TDD_V1_5 = FROZEN
TDD_V1_5_1 = DRAFT
REVISION_METHOD = REVERSE_ENGINEERING
PRODUCTION_CODE_CHANGED = NO
ASYNC_SCOPE = DEFERRED
NEXT_STEP = STOP_FOR_REVIEW
```
