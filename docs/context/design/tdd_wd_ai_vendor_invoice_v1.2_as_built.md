# AI Vendor Invoice — Technical Detailed Design

**文档版本**：TDD v1.2
**文档状态**：CLOSED — RELEASE 1.2 AS-BUILT BASELINE
**冻结日期**：2026-09-16
**方法**：REVERSE ENGINEERING + AS-BUILT VERIFICATION
**模块**：`ai_vendor_invoice`
**运行平台**：Odoo 18 / PostgreSQL / Owl / queue-job

> 本文档按既有 TDD 模板记录 Release 1.2 的实际实现。本文不新增业务
> 需求、不重构既有架构、不改变 Statement、Task、Canonical、Provider 或
> Vendor Bill 的 authority 边界。

## 修订记录

|版本|日期|状态|说明|
|---|---|---|---|
|v1.1|2026-09-15|FROZEN|Release 1.1 As-Built Baseline；收口 Statement-first、Extraction Profile、UPS VAT 和 Batch Supplier 实现|
|v1.2|2026-09-16|CLOSED|Release 1.2 As-Built；完成 Confirmed Statement 到 Draft Vendor Bill、税务事实解析、幂等、取消重建和 GPT Native PDF Schema 修复|

## 目录

1. [总体技术栈与架构红线](#1-总体技术栈与架构红线)
2. [模块目录与依赖](#2-模块目录与依赖)
3. [入口、UI 与实际业务流程](#3-入口ui-与实际业务流程)
4. [ORM 数据模型与关系](#4-orm-数据模型与关系)
5. [Canonical、Extraction Schema 与 Projection](#5-canonicalextraction-schema-与-projection)
6. [Provider、Input Mode 与 Prompt Registry](#6-providerinput-mode-与-prompt-registry)
7. [Extraction Profile Framework](#7-extraction-profile-framework)
8. [Batch Import 与 Supplier Assignment](#8-batch-import-与-supplier-assignment)
9. [ParseService、Attempt 与状态机](#9-parseserviceattempt-与状态机)
10. [并发、事务与错误语义](#10-并发事务与错误语义)
11. [安全、权限与审计](#11-安全权限与审计)
12. [Statement 与 Vendor Bill 边界](#12-statement-与-vendor-bill-边界)
13. [测试与人工 UAT](#13-测试与人工-uat)
14. [部署与运行核对](#14-部署与运行核对)
15. [技术不变量与冻结范围](#15-技术不变量与冻结范围)

## 1. 总体技术栈与架构红线

### 1.1 技术栈

|层|实现|
|---|---|
|应用|Odoo 18 ORM、Owl Web Client|
|数据库|PostgreSQL|
|异步|OCA `queue_job`|
|AI Provider|OpenAI-compatible adapter、DeepSeek adapter|
|校验|Python `jsonschema`|
|附件|Odoo `ir.attachment`|

### 1.2 As-Built Architecture

```text
Statement / Batch Wizard
        |
        v
  trusted Supplier / explicit Profile Assignment
        |
        v
  Profile Resolver
        |
        +--> Generic Profile
        +--> UPS Profile
        |
        v
  Input Mode Prompt Registry
  Native PDF / Markdown
        |
        v
  Provider Adapter
        |
        v
  Structured Extraction
        |
        v
  Canonical Result
        |
        v
  Statement Projection
        |
        v
  Human Review -> Confirm -> Vendor Bill
```

### 1.3 架构红线

1. Statement 是人工业务工作台和业务 authority。
2. Task 是 AI 技术执行上下文，不替代 Statement authority。
3. ParseAttempt 是一次实际执行和审计快照。
4. Provider 只负责 Provider protocol，不选择供应商业务语义。
5. Input Mode 只负责 Native PDF/Markdown transport，不选择 Profile。
6. Profile 只扩展 extraction semantics，不复制 Pipeline、Canonical 或
   Projection。
7. 所有 Profile 输出使用同一个 Canonical。
8. AI 提取出的当前 Attempt supplier 不得选择当前 Attempt 的 Profile。
9. 显式或可信预解析 Supplier 才能选择 Specialized Profile。
10. 无匹配 Supplier 使用 Generic；显式 Profile 无效时不得静默回退。
11. `human_review_result`/Statement 人工事实是 Vendor Bill 的唯一业务来源。
12. 数据库锁不得跨越外部 AI HTTP 调用。
13. 不提交密钥、原始 Provider secret 或敏感响应到日志。

## 2. 模块目录与依赖

### 2.1 运行时依赖

`__manifest__.py` 的运行时依赖为：

```text
account
contacts
mail
queue_job
```

已实现目录职责：

```text
addons/ai_vendor_invoice/
├── models/       ORM、Statement、Task、Attempt、Batch
├── services/     ParseService、BatchService、Profile Resolver
├── adapters/     Provider adapter、Prompt Registry
├── schemas/      Canonical、page/document extraction schema
├── views/        Statement、Task、Batch、Wizard、Config
├── static/       Owl review components
└── tests/        Model、service、projection、profile、batch tests
```

### 2.2 菜单与入口

```text
AI Invoice
├── Imports
├── Statements
├── Start Batch Import
├── Batches
└── Configuration
```

正常单票入口是 Statements。批量入口是 Start Batch Import。

## 3. 入口、UI 与实际业务流程

### 3.1 单票 Statement 流程

```text
Statements -> New
           -> AI / Task 页面上传 PDF
           -> Save
           -> 选择 Provider / Execution Mode
           -> Run AI
           -> 自动 Projection
           -> 人工核对和修正
           -> Confirm
           -> Create Vendor Bill
```

Statement 的 `AI / Task` 页面实际展示：

|区域|字段/动作|
|---|---|
|Source|Source PDF、原始 File Name|
|Launch|AI Provider、Synchronous Parse|
|Execution|Run AI、Technical Details|
|Status|AI State、AI Status、AI Error、Current Attempt|
|Result|Statement Header、Statement Lines|

解析成功后自动将当前成功 Attempt 投影到 Draft Statement，不需要额外点击
Apply Candidate。

### 3.2 Rerun 入口

Draft Statement 的 Task 在以下状态允许 Run AI/rerun：

|Task state|是否允许|
|---|---|
|`to_parse`|是|
|`error`|是|
|`awaiting_review`|是，兼容历史数据|
|`parsed`|是，允许 Profile/Prompt 修正后的重新执行|
|`parsing`|否|
|`cancelled`|否|
|`bill_generated`|否|

Rerun 不创建第二个 Task，只创建新的 ParseAttempt。若历史 Attempt 中已有
Specialized Profile，后续 rerun 保留该 Profile，不被中间 Generic Attempt
覆盖。

### 3.3 Batch Import Wizard

Wizard 字段：

|字段|约束|说明|
|---|---|---|
|`company_id`|required|当前公司|
|`supplier_id`|optional|批次级可信 Supplier|
|`provider_config_id`|required|批次 Provider|
|`attachment_ids` / `line_ids`|至少一个 PDF|批量文件|

推荐操作：

```text
Start Batch Import
 -> Supplier = United Parcel Service Nederland B.V.
 -> AI Provider
 -> 多个 UPS PDF
 -> Start Batch
```

选择 Supplier 后，Supplier 和对应 Profile 会传递到每一个新 Statement、
Task 和 ParseAttempt。Supplier 留空时使用 Generic。一个 Batch 应只包含
同一供应商的文件；混合供应商应拆分为多个 Batch。

## 4. ORM 数据模型与关系

### 4.1 Statement

模型：`vendor.invoice.statement`

|字段|类型|约束/语义|
|---|---|---|
|`name`|Char|required、sequence、readonly|Statement number|
|`state`|Selection|required|draft/confirmed/cancelled/bill_created|
|`task_id`|Many2one|一对一技术 Task|
|`batch_id`|Many2one|可选 Batch member|
|`company_id`|Many2one|required|公司|
|`source_parse_attempt_id`|Many2one|当前投影结果来源|
|`source_pdf_attachment_id`|Many2one|源 PDF authority|
|`source_pdf_filename`|Char|用户原始文件名|
|`source_pdf_upload`|Binary|Draft 上传入口|
|`ai_launch_provider_config_id`|Many2one|首次 Provider|
|`ai_launch_synchronous_parse`|Boolean|首次执行模式|
|`supplier_id`|Many2one|供应商业务字段|
|`supplier_name`|Char|原始/展示供应商|
|`currency_id`|Many2one|币种|
|`subtotal`/`total_tax`/`total_amount`|Monetary|Statement 汇总|
|`overall_tax_rate`|Float|汇总税率|
|`line_ids`|One2many|Statement Line|

### 4.2 Statement Line

模型：`vendor.invoice.statement.line`

|字段|语义|
|---|---|
|`description`|业务记录描述|
|`quantity`/`price_unit`/`amount`|Statement 业务字段；`amount`由当前 Projection 填充，`quantity`/`price_unit`按实际 Canonical 字段可用性填充或由人工维护|
|`tax_rate`|该业务行税率|
|`tax_amount`|该业务行税额|
|`total_amount`|amount + tax_amount|
|`tax_raw_text`|原始税文本|
|`charge_details`|嵌套 Charge/Discount/Net Charge|
|`reconciliation_clue`|主要对账线索|
|`reconciliation_clues`|原始 label/value 线索|

字段来源分类：

- AI-projected fields：`description`、`amount`、`tax_rate`、`tax_amount`、
  `tax_raw_text`、`charge_details` 和 reconciliation clues；`price_unit`
  在当前 Canonical Projection 中取 line `amount`，`quantity` 在没有
  Canonical quantity 时默认为 `1.0`；
- Human-editable business fields：`product_id`、`quantity`、`price_unit`、
  `tax_ids` 及人工修正后的 Statement 内容；
- Derived fields：`total_amount`、Statement totals 和 `overall_tax_rate`。

`quantity`/`price_unit` 是否由当前 Canonical Projection 填充，以实际
Projection contract 为准；不存在的 AI 值不得从 Provider response 旁路补入。

### 4.3 Task

模型：`vendor.invoice.import.task`

Task 保存 source PDF、Provider、Input Mode、当前 Attempt、状态、错误和
Statement 关系。Task 是执行上下文，不拥有 Statement 的人工确认 authority。

### 4.4 ParseAttempt

模型：`vendor.invoice.import.parse.attempt`

至少保存：

```text
task_id
sequence
provider_config_id
model_name_snapshot
prompt_version
extraction_contract_version
profile_key
profile_version
profile_extension_version
profile_extension_checksum
status
canonical_result
mapping_result
raw_response_attachment_id
diagnostic fields
```

`profile_*` 字段是实际执行 Profile 的审计快照，不是未来配置模型。

### 4.5 Batch

模型：`vendor.invoice.batch`

|字段|语义|
|---|---|
|`company_id`|批次公司|
|`supplier_id`|Wizard 选择的可信 Supplier|
|`provider_config_id`|批次 Provider|
|`statement_ids`|Batch 生成的 Statements|
|`status`|draft/processing/completed/completed_with_errors|
|progress counters|total/pending/processing/success/failed|

Batch 只编排多个独立 Statement/Task，不成为发票业务 authority。

## 5. Canonical、Extraction Schema 与 Projection

### 5.1 Canonical Result

所有 Generic、UPS、Provider 和 Input Mode 共用 Canonical：

```json
{
  "header": {
    "invoice_number": {"value": "...", "confidence": 0.0},
    "invoice_date": {"value": "YYYY-MM-DD", "confidence": 0.0},
    "supplier_raw_text": {"value": "...", "confidence": 0.0},
    "currency_raw_text": {"value": "EUR", "confidence": 0.0},
    "subtotal": {"value": "...", "confidence": 0.0},
    "total_tax": {"value": "...", "confidence": 0.0},
    "total_amount": {"value": "...", "confidence": 0.0}
  },
  "lines": [
    {
      "description": {"value": "...", "confidence": 0.0},
      "amount": {"value": "...", "confidence": 0.0},
      "tax_rate": {"value": 21, "confidence": 0.0},
      "tax_amount": {"value": "2.69", "confidence": 0.0},
      "tax_raw_text": {"value": "21,00 % BTW", "confidence": 0.0},
      "charge_details": "...",
      "reconciliation_clues": []
    }
  ]
}
```

Profile 不创建 UPS-specific Canonical。若事实无法由现有 Canonical 无损
表达，应报告 Canonical Contract Gap，而不是塞入无关字段。

### 5.2 Native PDF Extraction Contract

Native PDF Structured Output 的每个业务 line 支持：

```text
tax_rate: number | null
tax_amount: number | null
```

这两个字段经 `native_document_projection.document_to_canonical()` 投影到
共享 Canonical，再投影到 Statement Line。

### 5.3 UPS VAT Projection

UPS 文档中的：

```text
Total Charges / Net Charges: 12.79
21.00 % BTW: 2.69
```

投影为：

```text
Statement Line amount       = 12.79
Statement Line tax_rate     = 21
Statement Line tax_amount   = 2.69
Statement Line total_amount = 15.48
```

`Transportation` 和 `Fuel Surcharge` 仍是同一业务 line 的嵌套 charge facts，
不分别创建顶层税行。

## 6. Provider、Input Mode 与 Prompt Registry

### 6.1 Ownership

|概念|authority|
|---|---|
|Provider|Provider adapter 和 protocol|
|Input Mode|Native PDF / Markdown transport|
|Prompt Registry|现有 Input-Mode base Prompt|
|Profile|供应商/文档 extraction semantics extension|
|Canonical|系统可表达的共享事实结构|
|Statement Projection|Canonical 到人工 Statement 的统一投影|

### 6.2 Prompt Composition

```text
prompt_for_mode(input_mode)
        +
Profile Extension
        =
effective Prompt
```

Profile Extension 不复制 Generic Prompt，不改变 Provider protocol，也不
根据 Input Mode 拒绝供应商 Profile。

## 7. Extraction Profile Framework

### 7.1 Code-managed Registry

Release 1.1 仅使用 immutable code-managed registry：

|key|用途|version|
|---|---|---|
|`generic`|未知/无匹配 Supplier 的默认 Profile|`generic-v1`|
|`ups_transport`|UPS confirmed semantics|`ups-transport-v5`|

用户可配置 Profile、Odoo Profile model、ACL、动态 priority 和生命周期
不属于 Release 1.1。

### 7.2 Resolver v1

```text
explicit extraction_profile_key
        ↓
trusted Batch/Statement Supplier mapping
        ↓
Generic
```

当前 Attempt 自己提取的 Supplier 不得选择当前 Attempt 的 Profile。
显式 Profile 不存在或不兼容时受控报错，不静默回退 Generic。

### 7.3 UPS Extension

UPS Profile 只增加已确认的 extraction semantics：

- `BTW` = `Belasting over de toegevoegde waarde`；
- `21% BTW` = VAT rate；
- BTW 位于 Total Charges 下方时，作用于 consolidated transport line；
- Charge、Discount、Net Charge 保持为嵌套事实；
- 适用时输出 line `tax_rate` 和 `tax_amount`；
- 不把 Returned Date 无依据改写成 Loading/Unloading Date。

## 8. Batch Import 与 Supplier Assignment

### 8.1 创建顺序

```text
Wizard.supplier_id
        ↓
profile_key_for_supplier()
        ↓
Batch.supplier_id
        ↓
Statement.supplier_id
        ↓
env(context={"extraction_profile_key": profile_key})
        ↓
launch_statement_ai()
        ↓
ParseAttempt profile snapshot
```

批量文件逐个执行 preflight。无效 PDF、重复 checksum 或已有 Task 的文件
单独 rejected，不回滚已接受的 sibling。

### 8.2 Batch 不变量

1. 一个 Batch 内的文件使用同一个批次级 Supplier 选择。
2. 未选择 Supplier 时所有文件按 Generic 进入。
3. Batch 不从当前 AI response 反推并改变本次 Attempt Profile。
4. 混合供应商由用户拆分 Batch，不做隐式推断。
5. 每个文件仍拥有独立 Statement、Task 和 ParseAttempt 历史。

## 9. ParseService、Attempt 与状态机

### 9.1 ParseService

`start_parse()` 负责：

1. 锁定 Task 并校验状态；
2. 检查 queued/running Attempt 重复提交；
3. 复用 rerun 的历史 Specialized Profile；
4. 创建新 ParseAttempt；
5. 保存 Provider、Prompt、Profile 快照；
6. 同步执行或提交 queue job。

### 9.2 Task 状态

当前技术生命周期：

```text
to_parse -> parsing -> parsed
                 \-> error
to_parse/error/awaiting_review/parsed -> rerun
to_parse/parsing/error -> cancelled
```

兼容性历史状态：

```text
awaiting_review
bill_generated
```

`awaiting_review` 和 `bill_generated` 仅为既有数据兼容状态；Release 1.1
当前 Statement-first 流程不把它们作为新的主路径。`bill_generated` 是否由
历史业务流程写入不改变当前 Statement authority。Statement Draft 才允许
自动 Projection。

### 9.3 Attempt 状态

```text
queued -> running -> success
                 \-> failed
queued/running -> superseded
```

过期 worker 只能更新自身 Attempt 为 `superseded`，不得修改 Task 状态。

## 10. 并发、事务与错误语义

### 10.1 锁边界

- Statement/Task/Attempt 使用短事务行锁；
- AI HTTP 调用期间不持有业务行锁；
- ParseService 防止一个 Task 同时产生多个 active Attempt；
- Batch 每个文件使用 savepoint，单文件失败不阻塞 sibling。

### 10.2 错误语义

|阶段|行为|
|---|---|
|PDF preflight|文件 rejected，不创建 Statement|
|重复 checksum|当前文件 rejected|
|Task/Attempt launch|记录 launch_failed，保留 Batch 其他文件|
|Provider temporary/permanent error|Attempt failed，Task error|
|Statement 自动 Projection 权限失败|不绕过 ACL，保留技术错误|
|Invalid explicit Profile|controlled error，不 Generic fallback|

## 11. 安全、权限与审计

### 11.1 用户组

- AI Invoice User：运行单票/Batch AI；
- Invoice Reviewer：修改/应用人工 Statement；
- Config Manager：维护 Provider 和敏感配置。

### 11.2 敏感数据

Provider API key 只在服务端受控读取。密钥不得进入日志、RPC error、
ProviderCall snapshot 或 raw response display。

### 11.3 审计快照

ParseAttempt 必须记录：

```text
provider model snapshot
prompt version
extraction contract version
profile key/version
profile extension version/checksum
raw response attachment reference
```

## 12. Statement 与 Vendor Bill 边界

```text
AI Candidate / Canonical
        ↓
Statement draft facts
        ↓ human review
Statement Confirm
        ↓
Vendor Bill boundary
```

Release 1.1 只冻结 Vendor Bill 的 authority boundary：Vendor Bill 必须
来源于经人工审核的 Statement，不得绕过 Statement 直接读取 AI、Canonical、
Mapping 或 Provider response 结果。

Release 1.2 已完成并冻结 Confirmed Statement 到 Draft Vendor Bill 的实际
实现契约，包括确认前置条件、完整字段映射、税务事实解析、金额校验、幂等、
取消重建和异常处理；具体以 §16 为准。已 Confirm、Bill Created 或
Cancelled 的 Statement 不得被 AI Projection 覆盖。

## 13. 测试与人工 UAT

### 13.1 自动测试证据

Release 1.1 的回归测试覆盖仍作为 Release 1.2 基线：

- Profile Resolver：Generic、UPS、explicit assignment、rerun inheritance；
- Prompt Composition：Native PDF、Markdown；
- Historical Vision compatibility tests remain in the repository, but
  DeepSeek Vision/PDF-to-PNG is not a Release 1.1 production route；
- Native Projection：line tax rate/amount；
- Batch：initial launch、preflight、failure isolation、progress/filter、
  security/company；
- Task/Attempt：状态、重跑、审计快照；
- Statement：税率、税额、总额 Projection。

### 13.2 人工 UAT 证据

|场景|结论|
|---|---|
|UPS Statement 1708/1790/1791|UPS Profile VAT 与 Charge 语义核对|
|UPS Statement 1807 vs 1811|GPT Native PDF 与 DeepSeek Markdown 核心业务结果一致|
|DHL Statement 1809/1810|Generic Compatibility PASS，不创建 DHL Profile|
|Batch Supplier = UPS|人工验证 Supplier 显式传递到 Batch/Statement/Attempt|

Release 1.2 的 Vendor Bill closure verification 见 §16.4。当前记录包含
ORM 事务验证和生产数据验证；本文件不将未单独留存的浏览器人工 UAT 记录
表述为已完成的人工 UAT。

### 13.3 Runtime Verification 与限制

最终组合回归曾在共享 `odoo18e_tms` 数据库遇到已有 DDL session 导致
`LockNotAvailable`。该退出不是测试断言失败；已完成的针对性测试和运行时
健康检查仍作为本版本验证记录。共享数据库锁问题不改变 Release 1.2
运行时契约。

## 14. 部署与运行核对

部署后必须确认：

1. `ai_vendor_invoice` 模块升级成功；
2. Batch Import Wizard 显示 Supplier；
3. Statement `AI / Task` 页面显示 Run AI；
4. UPS batch ParseAttempt 的 Profile 为 `ups_transport-v5`；
5. Generic/DHL 不产生 UPS Profile；
6. 8091 `/web/login` 返回 HTTP 200；
7. queue worker 可执行异步 Attempt。

## 15. 技术不变量与冻结范围

|编号|不变量|
|---|---|
|T-1|Statement 是业务 authority|
|T-2|一个 Task 属于一个 Statement，rerun 不创建第二个 Task|
|T-3|一个 ParseAttempt 代表一次实际执行|
|T-4|Provider、Input Mode、Profile 三者职责正交|
|T-5|所有 Profile 共用 Canonical 和 Projection|
|T-6|当前 Attempt supplier 不得选择当前 Attempt Profile|
|T-7|显式 Batch Supplier 可以选择 Profile|
|T-8|UPS `21% BTW` 投影为业务行 `tax_rate=21`|
|T-9|UPS `2.69` 投影为业务行 `tax_amount=2.69`|
|T-10|Mixed-supplier Batch 不做隐式推断|
|T-11|Invalid explicit Profile 不静默 fallback|
|T-12|AI HTTP 期间不持有数据库业务锁|

### 15.1 Release 1.2 Not Implemented / Out of Scope

- DHL/FedEx/其他 Supplier-specific Profile；
- 用户可配置 Profile Model；
- Canonical V2；
- 新 Provider；
- OCR；
- BatchItem 独立模型；
- Mixed-supplier auto routing；
- 新的 Statement authority；
- 新的 Retry/Queue 语义。

Release 1.2 的完整 Out of Scope 清单以 §16.5 为准；本节保留的项目用于
标识从 Release 1.1 延续、但在 Release 1.2 仍未实施的技术范围。

**Release 1.2 TDD Close：本文档只描述已实现 As-Built 行为。**

## 16. Release 1.2 As-Built Closure

### 16.1 Confirmed Statement to Draft Vendor Bill

Release 1.2 已实现并冻结以下业务边界：

- 只有人工 Confirmed 的 Statement 才能创建 Draft Vendor Bill；
- Vendor Bill 只读取确认后的 Statement，不读取 Provider response、Canonical
  或 Mapping 作为旁路业务来源；
- Statement 与 `account.move` 双向关联并保留审计链；
- 一个 Statement 存在 active Draft Bill 时，重复请求幂等返回现有 Bill；
- 取消当前 Bill 后释放 active link，但保留历史 Bill，允许从同一 Confirmed
  Statement 重建新的 Draft Bill；
- Bill 保持 `draft`，不自动 Post、Payment 或 Reconciliation；
- Bill 行使用 `quantity=1.0`，`price_unit=Statement Line.amount`。

### 16.2 Tax Fact and Odoo Tax Boundary

AI Parse 只提取发票税务事实：

```text
tax_rate
tax_amount
tax_raw_text
tax_treatment
```

这些字段不是 Odoo `account.tax` ID，也不是 AI 直接生成的税码。人工确认后，
Bill Creator 才根据 Statement 中确认的税务事实选择或受控创建 Purchase Tax。
特殊税务性质在事实不足时必须失败，不能猜测。

为兼容 OpenAI Strict Structured Outputs，Native PDF Schema 要求每个
`properties` 字段都出现在 `required` 中；`tax_raw_text` 和
`tax_treatment` 仍允许为 `null`，不改变无税发票的业务语义。

### 16.3 Provider Verification

- DeepSeek Markdown 独立测试通过；
- GPT Native PDF 使用生产 PDF、生产模型和生产 Prompt 验证通过；
- 修复前 GPT 失败原因为 OpenAI HTTP 400：Native PDF response schema
  缺少 `tax_raw_text` 和 `tax_treatment`；
- 修复后同一 PDF 成功返回 5 条明细；
- Provider 错误提示已区分 HTTP 拒绝、网络连接、超时、Schema 校验和
  Provider 响应错误；
- AI Parse Error Code & Diagnostic Taxonomy 保持 Deferred，不属于本版本
  实现范围。

### 16.4 Release 1.2 Verification

|验证项|结果|
|---|---|
|CC-17 ORM Bill creation/idempotency/cancel-rebuild|PASS|
|历史无税 Statement 兼容|PASS|
|历史百分比税兼容|PASS|
|Statement/Bill 双向关联|PASS|
|Bill 行 quantity/price_unit 契约|PASS|
|GPT Native PDF production-schema regression|PASS|
|Odoo service HTTP health check|PASS (`200`)|

### 16.5 Release 1.2 Out of Scope

- 自动 Post、付款、对账；
- Provider fallback；
- 新的 OCR Provider；
- 用户可配置错误码字典；
- 自动 Confirm Statement；
- 自动选择业务 Partner、Currency 或会计科目；
- 多张 Statement 合并为一张 Vendor Bill。
