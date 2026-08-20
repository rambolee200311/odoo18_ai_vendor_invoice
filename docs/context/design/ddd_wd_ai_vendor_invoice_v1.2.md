# 通用供应商发票AI导入模块DDD
> 文档路径：docs/context/design/ddd_wd_ai_vendor_invoice_v1.2.md
> 模块名称：wd_ai_vendor_invoice
> 文档版本：v1.2
> 前置业务基准：SRS spec_wd_ai_vendor_invoice.md v1.3.3（业务已冻结）
> 说明：领域模型、聚合根、值对象、领域服务、状态机、并发锁、架构强制约束；本文件属于**技术领域设计，不属于业务需求SRS**；本次更新全部为技术契约修正，无新增业务需求。

> 核心强制架构原则：
> **AI Provider只负责解析；Mapping只负责推荐；人工负责最终确认；Invoice Creator负责生成 Draft Vendor Bill。**

## 整体领域上下文 Context‑Map
```
┌─────────────────────────────────────────────────────────┐
│ wd_ai_vendor_invoice (本模块 Bounded Context)           │
│     Aggregate Root：vendor.invoice.import.task           │
│         ├─ vendor.invoice.import.parse.attempt（子实体，多条）
│         ├─ AI Provider Adapter（外部防腐层）
│         ├─ CanonicalInvoiceResult（值对象，每一次attempt独立持有）
│         ├─ MappingResult（值对象，与attempt一一绑定）
│         ├─ HumanReviewResult（值对象，人工复核最终数据，账单唯一数据源）
│         ├─ review_warnings（结构化警告）
│         └─ Invoice Creator（输出 account.move）
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
OCA‑edi               Odoo Core        External AI Services
account_invoice_import  account/*     DeepSeek / Claude …
```

> 聚合根：`vendor.invoice.import.task`；**所有业务变更必须通过聚合根，禁止外部直接修改子实体**。
> 子实体 `vendor.invoice.import.parse.attempt` 隶属于task聚合，不允许脱离task独立存在。

## 1 核心领域对象
### 1.1 聚合根：vendor.invoice.import.task
> 一份PDF上传对应一条task，承载完整业务生命周期。

| 字段 | 类型 | 说明 |
|---|---|---|
| name | char | 任务业务编号 |
| source_pdf_attachment_id | many2one(`ir.attachment`) | **原始PDF附件；task与account.move均保留对此附件的引用，生成账单不转移/销毁task侧附件关联** |
| state | selection | 状态机，见下文 |
| selected_provider_config_id | many2one(`wd.ai.provider.config`) | 用户选定AI服务商配置 |
| enter_parsing_datetime | datetime | **本轮task进入parsing状态时间，用于task级别超时判定**，与attempt.started_at语义分离 |
| current_parse_attempt_id | many2one(`vendor.invoice.import.parse.attempt`) | **指向当前正在执行/最新的AI解析attempt；避免遍历查找，领域直接定位当前attempt** |
| parse_attempt_ids | one2many(`vendor.invoice.import.parse.attempt`, `task_id`) | 全部AI解析尝试子实体集合，历史全部保留 |
| human_review_result | jsonb | 值对象：人工复核结果，**账单生成唯一数据源**，修改历史通过audit_log追溯 |
| human_reviewed | boolean | 语义：**当前human_review_result是否完成本轮整体人工复核**；AI重跑后置为`False`，但`human_review_result`旧数据完整保留，数据本身不失效，只是不能直接用来生成账单，需要用户再次确认复核。 |
| review_warnings | jsonb | 结构化警告数组，替代自由文本note；存储校验警告编码+消息；**警告仅UI提示，不阻断账单生成；人工是否修正由复核人员承担业务责任** |
| vendor_bill_id | many2one(`account.move`) | 生成后的草稿供应商账单；**幂等约束：task一旦成功生成bill，不允许二次生成** |
| audit_log_ids | one2many(`vendor.invoice.import.log`, `task_id`) | 审计日志集合 |

#### 全局配置主数据（不属于task聚合）
1. `wd.ai.provider.config`：AI服务商集群配置（接口地址、密钥、模型名、**单次attempt最大内部重试次数**、单次请求超时、启用/禁用）
2. `wd.confidence.threshold`：双级置信度阈值、AI重点关注字段清单
3. `wd.mapping.vendor_alias`：供应商别名映射
4. `wd.mapping.product_keyword`：费用产品关键词映射
5. `wd.mapping.tax_text`：税率文本→account.tax映射
6. `wd.mapping.currency_text`：币种文本→res.currency映射
7. `wd.system.config`：兜底默认产品、cron巡检间隔、task级全局超时、金额容差参数

> 映射配置为全局只读主数据；MappingResult仅输出推荐候选，**映射引擎不会自动改写全局配置**。

### 1.2 子实体：vendor.invoice.import.parse.attempt
> **每一次调用外部AI生成一条attempt；完整保留全部历史AI解析结果，不会被新的解析覆盖。**

| 字段 | 类型 | 说明 |
|---|---|---|
| task_id | many2one(`vendor.invoice.import.task`) | 归属task，聚合内强绑定 |
| sequence | integer | 序号，1、2、3…标记第几次解析尝试 |
| provider_config_id | many2one(`wd.ai.provider.config`) | 本次attempt使用的AI配置 |
| started_at | datetime | **本attempt真正开始执行的时间，worker实际启动时刻**，与task.enter_parsing_datetime分离 |
| finished_at | datetime | 本次解析结束时间；running状态下为null |
| attempt_internal_retry_count | integer | **本次attempt内部自动重试次数（AI请求层级重试）**，仅控制本attempt，不跨attempt累加。 |
| status | selection | `running` / `success` / `failed`；**running状态，表达attempt已经提交worker但尚未得到返回** |
| canonical_result | jsonb | 值对象`CanonicalInvoiceResult`，本次AI标准化输出 |
| mapping_result | jsonb | 值对象`MappingResult`，与本attempt一一绑定，由canonical_result计算生成 |
| is_current_ai_candidate | boolean | UI辅助标记，当前展示的AI候选；业务优先使用`task.current_parse_attempt_id` |
| raw_response_attachment_id | many2one(`ir.attachment`) | AI原始完整响应报文存入附件，用于可追溯，业务逻辑不直接读取此字段 |
| error_message | text | 本次attempt失败原因 |

> 删除字段：`total_task_retry_count`，不再维护；统计需求通过审计日志/attempt集合做查询，**不参与任何状态流转与超时/重试判断**。

### 1.3 值对象 CanonicalInvoiceResult
> AI Adapter输出，**执行JSON Schema校验、字段类型归一化（日期标准化、金额转Decimal、文本清洗）；不执行账单业务校验**。
> 隔离不同大模型输出差异；仅代表AI输出，不等同人工确认业务数据。
> 包含发票头、明细行数组、每个字段/行`confidence`、`is_multi_invoice`标记。

### 1.4 值对象 MappingResult
> 隶属于单个parse_attempt，由该attempt的canonical_result输入映射引擎计算得到；输出各类主数据推荐候选。
> ⚠️**区分两个分数：`AI confidence`（来自AI字段可信度） vs `mapping match_score`（映射规则匹配得分，二者完全隔离，不可混用）**
```json
{
  "supplier_candidates": [{"partner_id":12,"name":"DHL Express NL","match_score":0.96,"match_type":"alias","matched_rule_id":8}],
  "product_candidates": [],
  "tax_candidates": [],
  "currency_candidates": []
}
```
> 规则：匹配0条、多条、错配均属于正常输出，仅用于UI展示，**不会自动写入task业务字段**。

### 1.5 值对象 HumanReviewResult（明确契约）
> UI提交人工修改后的完整发票数据；**是account.move生成的唯一数据源。Invoice Creator禁止从CanonicalInvoiceResult / MappingResult补任何业务字段**。

固定结构契约：
```json
{
  "header":{
    "supplier_id":12,
    "invoice_number":"INV‑2026‑001",
    "invoice_date":"2026‑08‑01",
    "currency_id":3,
    "total_amount":"1200.00",
    "total_tax":"252.00"
  },
  "lines":[
    {
      "product_id":45,
      "description":"Freight",
      "quantity":"1.00",
      "unit_price":"1000.00",
      "subtotal":"1000.00",
      "tax_ids":[22],
      "tax_amount":"210.00",
      "line_total_amount":"1210.00"
    }
  ]
}
```
> ❗无任何`xxx_confirmed`逐字段确认标记；依靠task.human_reviewed布尔值标记**本轮整体复核完成**。

### 1.6 审计日志实体 vendor.invoice.import.log
| 字段 | 说明 |
|---|---|
| task_id | 关联任务 |
| parse_attempt_id | 可选，关联对应的解析attempt |
| action | 动作类型：`ai_parse` / `ai_re_run` / `human_modify` / `bill_create` |
| action_datetime、user_id | 操作时间、操作人 |
| snapshot_delta | **变更摘要，只记录差异，不存储完整大报文** |

> AI原始response放在attempt的raw_response_attachment_id附件，不在日志内重复存储。

## 2 状态机 vendor.invoice.import.task.state
```python
STATE_SELECTION = [
    ("to_parse", "待解析（等待调度worker）"),
    ("parsing", "解析中（worker正在执行AI调用）"),
    ("awaiting_review", "待人工复核"),
    ("bill_generated", "已生成账单"),
    ("error_split_required", "异常‑需拆分【文档输入结构异常：AI识别PDF内含多张独立发票】"),
    ("error_ai_unavailable", "异常‑AI服务不可用【AI基础设施异常】"),
    ("error_timeout", "异常‑超时【执行基础设施异常，worker挂起/失联】")
]
```

### 状态流转
1. `to_parse` →【调用统一入口`start_parse()`】→ `parsing`
2. `parsing`
    - current_attempt.status=`success` && `is_multi_invoice=false` → `awaiting_review`
    - current_attempt.status=`success` && `is_multi_invoice=true` → `error_split_required`
    - current_attempt.status=`failed`（本attempt内部重试耗尽） → `error_ai_unavailable`
    - cron检测task级别超时条件达成 → `error_timeout`
3. `awaiting_review`
    - 用户发起重跑AI → 调用`start_parse()` → `parsing`；**生成全新parse_attempt；task.human_reviewed = False；human_review_result完整保留，数据不删除，仅标记本轮未复核**
    - 用户完成复核+账单生成，完整性校验全部通过 → `bill_generated`
4. `error_split_required` / `error_ai_unavailable` / `error_timeout`
    - 用户手动重跑 → `to_parse`；再经由`start_parse()`进入`parsing`

> 重要：业务匹配类问题、金额不一致，**不改变task.state，始终停留在awaiting_review**；信息写入`review_warnings`结构化数组。
> state的`error_*`区分三类：文档输入结构异常 / AI基础设施异常 / 执行基础设施异常。

## 3 领域服务（Odoo服务层，不直接暴露给前端）
### 3.1 公共统一入口 `start_parse(task_id, provider_config_id)`
> ✅**首次解析、人工重跑、异常恢复重跑全部走本统一入口，消除多套启动逻辑**
执行步骤（短事务，数据库锁只在本阶段，**不阻塞外部AI HTTP调用**）
1. 数据库行锁锁定task，校验当前task状态允许启动解析。
2. 创建全新`parse_attempt`子实体，sequence自增。
3. task.current_parse_attempt_id 指向新建attempt。
4. 赋值attempt.provider_config_id、attempt.started_at = now、attempt.status = `running`。
5. task.state = `parsing`；task.enter_parsing_datetime = now。
6. 提交事务、释放行锁。
7. 调度异步worker，传入task_id、attempt_id。

> 锁仅用于状态变更；**锁绝对不持有到AI网络请求阶段，避免长事务行锁阻塞数据库**。

### 3.2 AI Provider Adapter 防腐层 `wd.ai.provider.service`
> 职责：组装请求、调用外部AI、做schema+类型归一，输出`CanonicalInvoiceResult`。
> ✅只返回值对象；**Adapter禁止直接修改task/attempt，禁止设置task状态；异常向上抛出，由聚合根task处理状态变更**。

```python
def parse_pdf(pdf_attachment, provider_config, attempt_internal_max_retry:int) -> CanonicalInvoiceResult
```
- 内部执行**attempt层级AI请求重试逻辑**（`attempt_internal_retry_count`），到达配置上限抛出业务异常。
- 不做业务映射，不做账单校验。
- SRS约束：**系统不会自动切换AI模型；模型切换只能由用户UI选择传入**。

### 3.3 Worker回写防护（P0 陈旧worker防护）
> 异步worker执行完成（成功/失败），在回写attempt与task之前必须执行守卫判断，**防止陈旧worker实例覆盖新的attempt**。
守卫条件**全部满足**才允许回写：
1. task.state == `parsing`
2. task.current_parse_attempt_id == 当前attempt.id
3. attempt.status == `running`

> 守卫不满足：attempt记录success/failed结果、保存raw_response，但**禁止修改task.state、禁止修改current_parse_attempt_id**，直接丢弃对task的状态变更。旧attempt数据完整留存用于审计。

### 3.4 Mapping Engine `wd.invoice.mapping.service`
```python
def do_mapping(canonical_result) -> MappingResult
```
- 输入：单个attempt的canonical_result；输出MappingResult，绑定回该parse_attempt。
- 只读全局映射配置；**只输出推荐候选，绝不修改task业务数据、绝不自动更新映射配置主数据**。
- 输出携带`match_score`、`match_type`、`matched_rule_id`映射元信息，与AI confidence完全隔离。

### 3.5 Human Review Service `wd.invoice.review.service`
> 聚合根入口；唯一允许写入`human_review_result`的服务。
```python
def submit_review(task_id, human_review_payload) -> None
```
#### submit_review
1. 接收UI提交完整人工payload，写入task.human_review_result（严格遵守HumanReviewResult契约）。
2. 设置`human_reviewed = True`。
3. 清空旧review_warnings，调用`check_amount_balance()`生成最新警告集合。
4. 写入audit_log变更摘要。

> 语义：`human_reviewed=False` 代表**本轮尚未完成复核，旧human_review_result数据保留，但不能直接用于生成账单；用户可以不采纳任何新AI候选，直接确认已有人工结果完成复核**。

> UI行为契约：
> - 多个parse_attempt保存全部AI历史；
> - UI展示「当前人工复核表单（加载human_review_result）」；
> - 新AI候选仅作为备选；提供按钮【应用本次AI候选结果】，点击才把attempt的canonical/mapping数据填充进复核表单；**不会自动覆盖用户已编辑内容**；
> - 不实现两套并行编辑diff界面。

### 3.6 Bill Creation Service `wd.invoice.bill.creator.service`
> Invoice Creator；**生成账单唯一入口；数据源只读取 task.human_review_result，完全不读取任何parse_attempt的AI结果**。

> ⚠️幂等强制约束：
> 1. task行锁；生成前检查`task.vendor_bill_id`不为空则直接拒绝，防止快速重复点击生成多张账单。
> 2. 复用OCA account_invoice_import**底层附件、账单创建基础设施**；❌严格禁止调用OCA原有同步解析入口，不能伪装成OCA导入输入。

执行流程：
1. **Odoo账单技术完整性校验（后端强制，防前端绕过，这是Odoo生成move的技术约束，不属于新增业务规则）**
    - 顶层字段：供应商、发票编号、发票日期、币种、总金额非空
    - **行级：每一条应税明细行必须绑定有效tax_id；免税/零税率明细绑定对应免税税码，满足Odoo account.move.line创建要求**
    - 校验失败抛出异常，阻断账单生成。
2. 执行`check_amount_balance()`：使用**发票币种**，容差取自系统配置，返回警告对象写入`review_warnings`。
    > 业务规则：金额不平衡仅产出结构化警告；**警告不阻断账单生成；人工是否修正属于业务人员的业务责任**。
3. 无明细兜底逻辑：完整性校验全部通过、明细行为空，使用系统配置兜底默认产品生成单行。
4. 复用OCA基座能力生成草稿`account.move`。
5. 原始PDF附件建立与account.move的关联；**task侧附件引用保持不变不丢失**。
6. task.vendor_bill_id赋值；state改为`bill_generated`；写入审计日志。

### 3.7 Cron 超时恢复服务（Retry‑Timeout闭环，P0）
```python
def cron_check_parsing_timeout():
```
> 定位：task级别兜底超时，专门处理worker进程挂死、HTTP永久挂起这类**连内部重试都无法触发的极端场景**。
1. 筛选task.state = `parsing` 的任务。
2. 获取`task.current_parse_attempt_id`对应的attempt，必须满足`attempt.status == running`。
3. 判断条件：`now − task.enter_parsing_datetime > system_config.task_timeout`。
4. 条件达成：task.state置`error_timeout`；attempt标记`failed`；写audit_log；释放锁；允许用户手动重跑。
5. 不干涉attempt内部重试流程；attempt内部重试逻辑完全在worker内部完成。

> 分层模型明确：
> - **AI调用层重试**：attempt内部`attempt_internal_retry_count`，worker内执行；处理HTTP可重试错误。
> - **Task执行层超时（cron）**：仅兜底worker失联、进程挂死；**不干涉attempt内部重试逻辑**。

### 3.8 Validation Service 公共校验服务
```python
def pre_check_integrity(human_review_result) -> None
"""Odoo账单技术完整性校验，不通过抛异常，阻断账单生成"""

def check_amount_balance(human_review_result) -> list[warning_obj]
"""返回结构化警告对象数组，写入task.review_warnings，不抛异常、不阻断"""
```

### 3.9 权限边界定义
> DDD只定义权限边界，具体Odoo security xml分组放到后续技术设计。
1. **AI Invoice User**：创建任务、上传PDF、发起解析/重跑、查看任务与解析结果；**不能修改映射配置，不能执行复核生成账单**。
2. **AI Invoice Reviewer**：拥有User全部权限；可以修改复核数据、执行整体复核、生成草稿账单；**不能修改系统与AI服务商、映射配置**。
3. **AI Invoice Config Manager**：配置AI服务商、四类mapping映射、置信度阈值、系统参数。

> 尽量复用Odoo原有account权限组做组合，避免创建大量孤立新安全组。

### 3.10 并发、锁与幂等总览
1. `start_parse()`使用**短事务行锁**，状态变更完成立刻提交释放，**绝不把锁带到外部AI网络IO**。
2. Worker回写守卫：陈旧attempt禁止修改task状态，仅留存attempt审计记录。
3. Bill Creator：task行锁 + 判断vendor_bill_id非空，保证**一个task最多成功生成一张供应商账单**。
4. 异步job携带task_id+attempt_id，幂等，避免同一个task多次并发AI调用。

## 4 UI层契约（领域对前端输出约束，不写组件实现）
1. UI消费：task + parse_attempt子实体集合 + human_review_result + review_warnings。
2. 置信度数值由attempt.canonical_result提供；UI读取系统阈值配置自行渲染黄色/红色高亮；**后端置信度只作为提示，不作为账单生成阻断条件**。
3. AI重跑产生新attempt，**不覆盖当前复核表单**；提供按钮【应用本次AI候选结果】，人工确认后才将AI候选数据填充至复核表单。
4. UI唯一操作按钮：【确认复核并生成草稿账单】；前端调用`submit_review`再调用bill creator；**后端重新完整执行全套Odoo完整性校验，防御前端绕过**。

## 5 强制架构约束（复制到DDD文档头部，开发必须遵守）
1. **AI Provider：仅做PDF归一解析；不做业务映射、不做账单业务校验、不修改task/attempt、不决定task状态；异常向上抛出，由聚合根处理状态流转。**
2. **Mapping Engine：仅读取全局配置输出推荐候选；绝不直接修改task业务数据，绝不自动更新映射主数据；`mapping match_score`与AI `confidence`严格区分。**
3. **Parse‑Attempt模型：每一次AI调用生成独立子实体；完整留存全部历史AI解析结果，不会被新解析覆盖；MappingResult与attempt一一绑定；增加`running`状态表达未完成的AI调用。**
4. **`start_parse()`为解析统一入口：首次解析、重跑、异常恢复全部复用；短事务锁，锁不持有到外部AI HTTP请求。**
5. **Worker陈旧防护：旧worker回写前校验当前attempt指针；过期attempt仅留存审计，禁止改动task状态。**
6. **人工复核：human_review_result是账单唯一数据源；`human_reviewed`代表**本轮复核完成**；AI重跑后置`human_reviewed=False`，保留旧human_review_result不删除。Invoice Creator禁止从AI/Mapping结果补字段。**
7. **Invoice Creator：只读取human_review_result；复用OCA账单创建底座，禁止调用OCA原有同步解析入口；task幂等，一个task最多生成一张vendor bill；行级税码约束为Odoo move技术完整性约束，非新增业务规则。**
8. **分层重试&超时：attempt内部重试处理AI可重试错误；cron task‑level超时仅兜底worker挂死失联；二者互不干扰。**
9. **重跑AI：生成新parse_attempt，永远不会自动覆盖已有的human_review_result；UI需要用户主动点击“应用AI候选”才填充表单。**
10. **置信度、mapping匹配分数、review警告全部仅UI提示；警告不阻断账单生成；业务正确性最终由人工复核人员负责。**
11. **业务匹配、金额不平仅产生结构化review_warnings，不会切换task异常state；只有文档输入结构、AI/执行基础设施故障才进入error_*状态。**
12. **原始PDF附件：task与account.move均保留引用关系；生成账单不转移、不丢失task侧附件关联。**

---

## 版本变更汇总 v1.1 → v1.2
| P0强制修复 | 处理 |
|---|---|
| attempt缺少running状态，worker挂死导致任务永久parsing | 增加`running`状态；分层区分AI内部重试 / task级别cron兜底超时 |
| 陈旧worker返回覆盖新attempt状态 | 增加worker回写守卫条件，过期attempt仅留存审计，禁止改动task |
| DB行锁长期持有外部AI http请求 | `start_parse()`改为短事务，锁在调度worker前释放 |

| P1优化收口 | 处理 |
|---|---|
| 解析入口不统一，首次/重跑/异常恢复逻辑分散 | 统一`start_parse()`作为唯一启动入口 |
| total_task_retry_count语义模糊无业务作用 | 删除，统计由审计日志查询完成，不参与状态流转 |
| task缺少直接指向当前attempt字段 | 增加`current_parse_attempt_id` |
| HumanReviewResult契约模糊，存在从AI结果补字段风险 | 明确定义完整JSON契约，Invoice Creator强制仅读取该对象 |
| 隐性约束“警告必须人工查看后再确认” | 删除，警告仅提示，不阻断账单生成 |
| mapping候选缺少匹配元信息，与AI confidence混淆 | MappingResult补充match_score、match_type、matched_rule_id；明确与AI confidence隔离 |
| 行级税码约束边界不清，怕产生SRS契约漂移 | 明确：属于Odoo账单创建**技术完整性约束**，不是新增业务需求 |
| enter_parsing_datetime 与 attempt.started_at语义混淆 | DDD文档明确两个字段各自语义，允许时间错位 |

