# AI Vendor Invoice 技术详细设计

**版本**：TDD v1.6
**状态**：FROZEN - CC-13 IMPLEMENTATION BASELINE
**冻结日期**：2026-09-11
**方法**：REVERSE ENGINEERING
**上游**：[TDD v1.5.1](./tdd_wd_ai_vendor_invoice_v1.5.1.md)
**范围**：Statement-first AI Task Workspace；同步和异步执行均复用现有 ParseService

## 1. 目标与边界

系统边界：

```text
Statement -> source PDF -> Task -> ParseAttempt -> AI result
          -> automatic candidate projection -> reviewer edit/check
          -> Confirm -> Vendor Bill
```

Statement 是业务工作台和业务 authority。Task 是 AI 技术执行上下文。
独立 Task Form 只提供 Technical Details，不是正常首发入口。

CC-12 的 Wizard 交互已作废。正常流程是：

```text
New Statement -> Upload PDF -> Save
-> AI / Task page -> Provider / Execution Mode -> Run AI
-> stay on Statement -> successful result is applied automatically
-> review/edit -> Confirm -> Create Vendor Bill
```

## 2. 模块和依赖

模块目录为 `addons/ai_vendor_invoice`，依赖 `account`、`contacts` 和 `queue_job`。
分层仍为 `models/`、`services/`、`adapters/`、`schemas/`、`views/`、`tests/`。

菜单：

```text
AI Invoice
  ├─ Imports
  ├─ Statements
  └─ Configuration
```

## 3. ORM 模型

### 3.1 Import Task

模型：`vendor.invoice.import.task`。

关键字段包括 `name`、`company_id`、`source_pdf_attachment_id`、
`source_pdf_filename`、`source_pdf_checksum`、`state`、`synchronous_parse`、
`selected_provider_config_id`、`current_parse_attempt_id`、`parse_attempt_ids`、
`parse_error_summary`、`human_review_result`、`statement_id` 和 `vendor_bill_id`。

Task 状态为 `to_parse`、`parsing`、`awaiting_review`、`parsed`、`error`、
`bill_generated`、`cancelled`。Provider 和 execution mode 在创建后不可修改。

### 3.2 Parse Attempt

模型：`vendor.invoice.import.parse.attempt`。保存 Task、序号、Provider 快照、
状态、Canonical/Mapping 结果、错误、诊断和可选 queue job。`job_run_parse` 是
queue-job 入口，Provider secret 不进入日志或用户可见错误。

### 3.3 Statement

模型：`vendor.invoice.statement`。

| 字段 | 类型/语义 |
|---|---|
| `name` | 必填、序列、只读 |
| `state` | `draft`、`confirmed`、`cancelled`、`bill_created` |
| `task_id` | 可选，一对一 Task 关系 |
| `company_id` | Statement 公司 |
| `source_parse_attempt_id` | 当前应用结果的来源 Attempt |
| `source_pdf_attachment_id` | Statement 拥有的源 PDF |
| `source_pdf_filename` | 用户上传的原始文件名 |
| `source_pdf_upload` | Draft 上传入口 |
| `ai_launch_provider_config_id` | 首次 Task 的 Provider 配置 |
| `ai_launch_synchronous_parse` | 首次 Task 的执行模式，默认 False |
| `invoice_number` / `invoice_date` | 发票表头 |
| `supplier_id` / `supplier_name` | 供应商 |
| `currency_id` | 币种 |
| `subtotal` / `total_tax` / `total_amount` | Statement Lines 汇总 |
| `overall_tax_rate` | 汇总税率 |
| `vendor_bill_id` | Vendor Bill authority |
| `line_ids` | Statement Lines |

Statement 的 launch fields 只在 Task 创建前可编辑。Task 创建后，实际 Provider
和 mode 来自 Task，页面只读显示。

### 3.4 Statement Line

模型：`vendor.invoice.statement.line`。包含 `statement_id`、`sequence`、
`description`、`product_id`、`quantity`、`price_unit`、`amount`、`tax_rate`、
`tax_amount`、`total_amount`、`tax_raw_text`、`tax_ids`、`reconciliation_clue`、
`charge_details` 和 `reconciliation_clues`。

## 4. 状态和业务动作

Task 当前主动技术状态：

```text
to_parse -> parsing -> parsed
                 \-> error
to_parse/parsing/error -> cancelled
```

历史兼容状态：

```text
awaiting_review / bill_generated
```

历史状态仅为兼容既有数据保留，不再作为当前 Statement-first 业务流程的
authority 或主要状态驱动。当前允许的 rerun 矩阵为：

| Task state | Statement `Run AI` / rerun |
|---|---|
| `to_parse` | allowed |
| `error` | allowed |
| `awaiting_review` | allowed for legacy data |
| `parsing` | rejected |
| `parsed` | rejected |
| `cancelled` | rejected |
| `bill_generated` | rejected |

Statement：

```text
draft -> confirmed -> bill_created
draft -> cancelled
```

只有 Draft Statement 可以取消；Confirmed -> Cancelled 不允许。
Draft 是唯一可编辑状态。Statement Cancel 会取消不完整的 owning Task；
已完成 Task 的技术历史保留不删除。Cancelled 和 Bill Created 是终态。

Statement Confirm、Unconfirm、Create Bill 由 Statement-facing commands 执行；
Task 不能替代 Statement 的业务 authority。

## 5. Statement AI / Task Workspace

Statement Form 的 `AI / Task` page 展示：

- Source PDF 和原始 File Name；
- Provider 和 Execution Mode；
- Run AI；
- Task、ParseAttempt、AI State、AI Status、Error summary；
- 当前执行结果；
- Technical Details。

基础信息页不展示 Upload PDF、Source PDF 或 File Name；Currency、Subtotal、
Total Tax、Total Amount、Overall Tax Rate 位于 Invoice Date 下方。
Statement Header 不再提供 Open Import Task 或 Open Source PDF 按钮。

## 6. Run AI 数据流

`vendor.invoice.statement.action_start_ai()` 的实际流程：

1. 检查 AI Invoice User 权限；
2. 使用 `wd.lock.service.lock_statement()` 锁定 Statement；
3. 重新检查 Task 关系；
4. 无 Task 时验证 PDF 和显式 Provider；
5. 创建唯一 Task，并复制 Statement launch Provider/mode；
6. 建立 Statement/Task 双向关系；
7. 调用 `services.parse_service.start_parse()` 创建首个 Attempt；
8. 同步执行或加入 queue；
9. 返回 client reload，保持 Statement 页面。

已有 Task 按上表的明确 rerun 矩阵处理，不创建第二个 Task。`start_parse()` 还会
拒绝已有 `queued` 或 `running` Attempt 的重复提交。
解析成功后，`run_parse_attempt()` 使用 Task 当前成功 Attempt 自动调用
`action_apply_ai_candidate_from_statement()`；因此 Run AI 不再要求用户额外
点击 Apply Candidate。自动 projection 只允许在 `Statement.state == draft` 时执行：
`confirmed`、`bill_created` 和 `cancelled` Statement 不得被 AI 覆盖。多发票结果
不自动覆盖单一 Statement。

## 7. 附件和文件名

Statement 是 PDF authority，Task 只保存 execution-input compatibility reference。
上传附件的 `name` 和 Statement `source_pdf_filename` 保持用户原始文件名。

相同 PDF 被 Binary widget 因 autosave 重复提交时，`models/statement.py` 会复用
现有附件并忽略过期默认文件名；不同 PDF 才创建替换附件。Task 创建和自动结果
应用均优先保留 Statement 文件名。

## 8. 并发和失败语义

Statement/Task 保持 `0..1 <-> 0..1`：

```text
statement.task_id == task
task.statement_id == statement
```

Statement row lock、关系重查、Task/Attempt 的显式 `SELECT ... FOR UPDATE`
以及 ParseService 的 Attempt concurrency guards 共同保证并发 Run AI 最多创建
一个 Task、一个关系对和一次首发执行。

事务语义分为两个阶段：

**Phase A — launch preparation**

- 验证 PDF 和 Provider；
- 创建 Task；
- 建立 Statement/Task 关系；
- 准备初始 Attempt。

目标是失败时不得留下不一致的 partial relation。

**Phase B — execution**

- 进入 ParseService、queue 和 Provider call；
- 保存成功、失败、timeout、HTTP error、retry exhaustion 或 worker failure。

目标是执行失败保留已经合法建立的 Task/Attempt execution context 和技术诊断，
而不是将失败伪装成没有执行记录。

## 9. Provider、执行模式和权限

Provider 使用既有 ProviderConfig 的 active、访问和 company 规则，不新增权限模型，
不自动选择或静默 fallback Provider。首次 Run AI 必须显式选择 Provider。

Statement 首次 launch 默认异步：

```text
ai_launch_synchronous_parse = False
```

用户可在首次 Run AI 前切换同步；映射为 Task `synchronous_parse=True`。

## 10. Candidate、复核和账单

成功解析结果自动应用到 Draft Statement，更新表头、替换 Lines 并记录来源
ParseAttempt。其 invariant 是：AI 只能更新 `Statement.state == draft` 的结构化
数据；`confirmed`、`bill_created` 和 `cancelled` 均不可被 AI overwrite。用户随后
仍必须人工检查、修改和 Check。AI 结果不能替代人工确认。

`services/statement_projection.py` 将人工 Statement 投影到 Task
`human_review_result`；它是当前 Statement review result 的技术/会计投影，不是
可独立编辑的业务 authority。Bill Creator 只读取该投影，Statement 仍是业务
source of truth。`vendor_bill_id` 防止重复建单。

## 11. 金额规则

```text
amount       = 无税金额
tax_rate     = 税率百分比
tax_amount   = 税额
total_amount = 含税金额
```

公式为 `tax_amount = amount * tax_rate / 100`、`total_amount = amount +
tax_amount`。四个 onchange 提供实时联动，ORM normalization 提供持久化一致性。
无税金额为零且税额非零时抛出 ValidationError。Statement header 的 subtotal、
total_tax、total_amount 和 overall_tax_rate 由 Lines 汇总。

## 12. 错误、审计和可观测性

用户可见错误使用 `parse_error_summary`、`error_summary` 和 Error Badge。
Attempt、Provider call、错误分类、投影和账单动作保留技术审计；Provider secret
不进入 RPC、日志、审计或用户可见错误。Queue diagnostic 只用于运行诊断，
不绕过 Statement 的业务状态。

## 13. UI、权限和唯一性

Imports 列表显示 File Name 和 Error；Statements 列表显示 File Name。
Configuration Manager 维护 Provider、Vendor Alias、Product Keyword、Tax、
Currency、Threshold 和 System Configuration。普通用户按公司规则读取。

唯一性具体语义如下：

- Task 上的部分唯一索引为
  `(company_id, source_pdf_checksum)`，仅对 `source_pdf_checksum IS NOT NULL`
  且 `state != 'cancelled'` 的记录生效，用于阻止活动 Task 重复导入同一 PDF；
- Statement 上的部分唯一索引为
  `(company_id, supplier_identity_key, invoice_number_normalized)`，仅对
  `state != 'cancelled'` 且两个 normalized key 均非空的记录生效，用于阻止
  活动 Statement 重复业务发票；
- `vendor.invoice.statement` 另有 `unique(task_id)`，保证一个 Task 最多一个
  Statement。

Cancelled 记录不参与上述活动唯一性索引，因此取消后允许重新使用。
来源 PDF、Task、Statement 和 Vendor Bill 保留追溯关系。

## 14. 测试和验收

测试覆盖模型、服务、投影、可观测性、权限、状态、PDF、附件、Task/Statement
关系、Provider/mode 映射、自动 Candidate application 和视图加载。

关键回归组：

- Statement-first creation；
- Task `0..1` relation；
- concurrent Run AI 和 duplicate parse submission；
- Provider/mode copy；
- asynchronous queue entry；
- automatic AI projection to Draft Statement；
- filename preservation 和 autosave attachment reuse；
- Statement Confirm/Create Bill authority；
- Draft-only cancellation boundary。

最近完整模块验证：

```text
0 failed, 0 errors of 148 tests
```

文件名回归验证：Automated regression PASS，覆盖同 PDF autosave 的附件复用和
原始文件名保持；针对本次文档版本的 Manual UAT 未重新执行，状态为 PENDING。
异步 queue 的生产环境认证仍需独立部署验收，不将本地测试结果扩大解释。

## 15. 代码对应审核记录

| 设计区域 | 主要实现位置 | 审核结果 |
|---|---|---|
| Statement launch/Run AI/Cancel | `models/statement.py` | PASS |
| Task/Attempt/filename/candidate | `models/import_task.py` | PASS |
| Parse lifecycle/automatic apply | `services/parse_service.py` | PASS |
| Projection/Bill Creator | `services/statement_projection.py`、`services/bill_creator.py` | PASS |
| Provider/PDF/Schema | `adapters/`、`services/pdf_preprocessor.py`、`schemas/` | PASS |
| Statement/Task views | `views/import_task_views.xml` | PASS |
| Regression tests | `tests/test_models.py` | PASS |

## 16. 兼容性和范围

保留 CC-10 的 Statement Confirm/Unconfirm/Create Bill authority、CC-11 的
Statement-first lifecycle、历史 Task/Attempt 可读性、queue/retry/stale-worker
机制和 legacy states。

不包含 batch upload、Statement 1:N Task、Provider fallback、Retry with another
provider、Candidate merge/history redesign 或新的权限模型。后续 Batch 能力如
实现，应在现有单文档执行单元之上编排多个独立的 Statement/Task，不得以 Batch
为由改变 `Statement 0..1 ↔ 0..1 Task` 的单文档 cardinality。

## 17. 修订记录与状态

- v1.5.1：同步实现历史基线，保留为历史文件；
- v1.6：同步 CC-13 Statement AI Task Workspace、自动结果应用、Draft-only
  Statement cancellation、附件文件名保护和当前 UI；
- CC-12 Wizard：SUPERSEDED - CANCELLED AFTER MANUAL UAT。

```text
TDD_V1_5_1 = HISTORICAL_BASELINE
TDD_V1_6 = FROZEN
IMPLEMENTATION_BASELINE = CC_13
REVISION_METHOD = REVERSE_ENGINEERING
```
