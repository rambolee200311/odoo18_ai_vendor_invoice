# docs/context/design/tdd_wd_ai_vendor_invoice.md
模块名称：wd_ai_vendor_invoice
文档版本：v1.4（Odoo 18 技术收口，P0问题全部修复，SPIKE‑OCA‑001结论落地）
前置依赖：
业务SRS：spec_wd_ai_vendor_invoice.md v1.3.3（业务冻结）
DDD领域设计：ddd_wd_ai_vendor_invoice_v1.2.md（领域模型终审）
说明：本文件为面向Odoo 18的可执行技术详细设计；不再新增业务需求；所有实现服从DDD架构约束。

🔒 技术基线冻结
Odoo版本：18.0
Python版本：Odoo 18 配套版本
数据库：PostgreSQL
ORM：Odoo 18 ORM
前端：Odoo 18 Owl
OCA依赖：
queue‑job：锁定Odoo 18兼容版本
> 修订记录：`account_invoice_import` **移除运行时依赖**。源码探查确认：OCA‑edi 18.0分支存在该模块，但无可独立调用的底层账单创建helper；模块逻辑强耦合文件上传向导，仅可作为阅读参考。
备注：SPIKE‑OCA‑001已完成源码探查，账单vals组装由本模块`bill_creator`自主实现。

## 目录
1. 总体技术栈与依赖说明
2. 模块目录结构（重构，区分domain/service/adapter/schema）
3. ORM数据库模型设计（修正锁、字段、约束、ondelete）
4. JSON‑B值对象Schema（修复Canonical字段结构漂移）
5. 领域服务伪代码（Odoo 18事务/锁/queue‑job语义修正）
6. 异步队列Worker、Cron定时任务（竞态、stale‑worker、重试‑超时闭环）
7. OCA account_invoice_import复用边界 + Spike任务标记（已闭环）
8. AI Adapter外部调用设计（接口、异常分类）
9. UI/视图层设计（Owl视图、wizard、按钮、提示逻辑）
10. 安全与权限设计（access、record‑rule、完整权限矩阵）
11. 错误码、日志、告警策略
12. 附件存储技术决策（ir.attachment关联方案）
13. 部署、前置条件
14. 测试设计（扩充并发、事务回滚、竞态用例）
15. 风险点与防护清单
16. 📜技术不变量表（Coding Contract，用于代码评审门禁）

## 1 总体技术栈与依赖说明
- Odoo 18.0，PostgreSQL；前端Owl组件
- OCA：queue‑job（异步worker，禁止同步阻塞HTTP）
- 第三方库：jsonschema，用于运行时校验JSON‑B值对象
- 外部系统：多模态AI服务商HTTP接口（DeepSeek / Claude等）

🔴架构红线（复制进代码头部注释）
> AI Provider只负责解析；Mapping只负责推荐；人工负责最终确认；Invoice Creator负责生成 Draft Vendor Bill。
> human_review_result是生成account.move唯一数据源，禁止从canonical_result / mapping_result补任何业务字段。
> 数据库排他行锁仅在短事务内；锁绝对不能持有外部AI HTTP网络IO。
> Stale‑worker守卫：过期attempt不允许修改task状态，仅允许写attempt自身记录。
> 一个task最多生成一张vendor bill；禁止产生孤立草稿账单。
> 禁止调用OCA account_invoice_import原有同步文件导入入口。
> 不依赖OCA account_invoice_import运行时；账单vals全部由本模块bill_creator自主组装。

## 2 模块目录结构（重构）
```
wd_ai_vendor_invoice/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── import_task.py          # vendor.invoice.import.task 聚合根
│   ├── import_parse_attempt.py # parse_attempt子实体
│   ├── import_log.py           # audit_log审计日志
│   ├── ai_provider_config.py   # AI服务商配置主数据
│   ├── mapping_*.py            # 4套映射配置主数据
│   ├── conf_threshold.py       # 置信度阈值配置
│   ├── system_config.py        # 系统全局参数
│   └── lock_service.py         # 🔒独立锁工具服务（封装SELECT‑FOR‑UPDATE）
├── services/                   # 领域服务，不直接暴露RPC
│   ├── __init__.py
│   ├── parse_service.py        # start_parse orchestration
│   ├── mapping_service.py
│   ├── review_service.py
│   ├── bill_creator.py
│   ├── validation_service.py
│   └── timeout_service.py      # cron超时业务逻辑
├── adapters/                   # 🤖外部AI适配器，与领域业务解耦
│   ├── __init__.py
│   ├── base.py                 # Abstract AIProviderAdapter
│   ├── deepseek.py
│   └── claude.py
├── schemas/                    # 📄JSON Schema定义，独立存放
│   ├── __init__.py
│   ├── canonical.py
│   ├── mapping.py
│   ├── human_review.py
│   └── warning.py
├── data/
│   ├── ir_cron.xml
│   └── system_config_data.xml
├── security/
│   ├── ir.model.access.csv
│   ├── record_rules.xml
│   └── groups.xml              # 用户组定义
├── views/
│   ├── import_task_views.xml
│   ├── config_views.xml
│   └── wizard/                 # 复核弹窗/owl组件
├── static/
│   └── src/owl/                # 前端高亮、按钮组件
├── tests/
│   ├── __init__.py
│   ├── test_domain_flow.py
│   ├── test_async_worker.py
│   ├── test_bill_creation.py
│   ├── test_mapping_engine.py
│   ├── test_cron_timeout.py
│   ├── test_concurrency.py     # ⚡新增并发/竞态测试
│   └── test_security.py        # 🔐权限测试
└── readme.md
```
约定：领域service/adapter/schema不在model内混杂；service不暴露RPC；所有外部入口通过model‑action/wizard调用。

## 3 ORM数据库模型设计（Odoo 18修正版）
### 3.1 vendor.invoice.import.task（聚合根）

|字段|类型|约束/索引|说明|
|---|---|---|---|
|name|Char|required, copy=False|任务业务编号，序列生成|
|source_pdf_attachment_id|Many2one(ir.attachment)|required, ondelete="restrict"|原始PDF；task与bill分别持有引用；不修改原attachment res_model/res_id|
|state|Selection|required, index|to_parse / parsing / awaiting_review / bill_generated / error_split_required / error_ai_unavailable / error_timeout|
|selected_provider_config_id|Many2one(wd.ai.provider.config)|required|用户选定AI服务商|
|enter_parsing_datetime|Datetime|index|task进入parsing时刻，业务超时判定起点|
|current_parse_attempt_id|Many2one(vendor.invoice.import.parse.attempt)|ondelete="set null", index|当前最新/正在运行attempt；删除 is_current_ai_candidate 冗余标记|
|parse_attempt_ids|One2many(vendor.invoice.import.parse.attempt, task_id)||全部历史AI尝试记录|
|human_review_result|Json|default=lambda self: dict()|HumanReviewResult值对象，账单唯一数据源；Odoo18内部映射PostgreSQL jsonb；禁止直接写原生PostgreSQL JSON操作|
|human_reviewed|Boolean|default=False|本轮是否完成整体人工复核；重跑后置False，旧数据保留|
|review_warnings|Json|default=lambda self: []|结构化警告数组`[{"code":"","message":""}]`|
|vendor_bill_id|Many2one(account.move)|index, ondelete="restrict"|生成的草稿供应商账单；ondelete改为restrict，防止删除bill后task可再次生成账单|
|audit_log_ids|One2many(vendor.invoice.import.log, task_id)||审计日志|

数据库约束：vendor_bill_id非空，业务禁止再次调用bill‑creator；行锁通过lock_service工具获取，禁止模拟recordset.with_for_update()伪写法。

### 3.2 vendor.invoice.import.parse.attempt（子实体，隶属于task聚合）

|字段|类型|约束/索引|说明|
|---|---|---|---|
|task_id|Many2one(vendor.invoice.import.task)|required, ondelete="cascade", index|归属task，级联删除|
|sequence|Integer|required|序号1,2,3|
|provider_config_id|Many2one(wd.ai.provider.config)|required|本次attempt使用AI配置|
|started_at|Datetime|index|worker实际开始执行时间|
|finished_at|Datetime|nullable|结束时间；running状态为null|
|attempt_internal_retry_count|Integer|default=0|本次attempt内部AI请求重试次数；每次重试+1；持久入库，供cron做判断依据|
|status|Selection|required, index|running / success / failed|
|last_activity_at|Datetime|index|⭐新增：worker活性时间，每次AI调用/重试更新，用于cron识别worker是否真正在干活|
|canonical_result|Json|nullable|CanonicalInvoiceResult；Odoo18 json存储|
|mapping_result|Json|nullable|MappingResult，与本attempt一一绑定|
|raw_response_attachment_id|Many2one(ir.attachment)|ondelete="set null"|AI原始完整响应报文附件|
|error_message|Text|nullable|失败详情|

### 3.3 vendor.invoice.import.log（审计日志）

|字段|类型|约束|说明|
|---|---|---|---|
|task_id|Many2one(vendor.invoice.import.task)|required, ondelete="cascade", index||
|parse_attempt_id|Many2one(vendor.invoice.import.parse.attempt)|ondelete="set null"|可选关联attempt|
|action|Selection|required|ai_parse / ai_re_run / human_modify / bill_create|
|action_datetime|Datetime|required||
|user_id|Many2one(res.users)|required|操作人|
|snapshot_delta|Text||变更摘要，只记录差异，不存完整大JSON|

### 3.4 全局配置主数据（简要）
1. wd.ai.provider.config：接口地址、密钥、模型名称、单次attempt最大内部重试、单次HTTP请求超时、启用开关
2. wd.confidence.threshold：全局置信度阈值、关键字段阈值、关键字段清单
3. wd.mapping.vendor_alias：供应商别名映射
4. wd.mapping.product_keyword：产品关键词映射
5. wd.mapping.tax_text：税率文本‑tax映射
6. wd.mapping.currency_text：币种文本‑currency映射
7. wd.system.config：兜底默认产品、cron巡检间隔、task全局业务超时、金额容差

全部mapping配置为只读主数据；mapping_engine只读取，不会自动改写配置表。

🔒 lock_service.py 工具（Odoo18行锁封装）
Odoo18没有ORM层面with_for_update()；封装原生PostgreSQL行锁，避免到处写裸SQL。
```python
def lock_by_id(model_name: str, rec_id: int):
    """获取排他行锁；在当前事务内生效；事务提交/回滚释放锁"""
    env.cr.execute(
        f"SELECT id FROM {env[model_name]._table} WHERE id = %s FOR UPDATE",
        (rec_id,)
    )
    return env[model_name].browse(rec_id)
```

## 4 JSON‑B 值对象Schema定义（修复Canonical字段结构漂移）
使用jsonschema做应用层校验；Odoo Json字段，PostgreSQL底层jsonb；禁止业务代码写PostgreSQL原生JSON操作语句；JSON Schema仅校验结构；业务完整性由validation_service完成。

### 4.1 CanonicalInvoiceResult（AI归一输出，恢复DDD定义的value‑with‑confidence结构）
```json
{
  "$schema":"http://json‑schema.org/draft‑2020‑12/schema",
  "type":"object",
  "properties":{
    "header":{
      "type":"object",
      "properties":{
        "invoice_number":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
        "invoice_date":{"type":"object","properties":{"value":{"type":["string","null"],"format":"date"},"confidence":{"type":"number","minimum":0,"maximum":1}}},
        "supplier_raw_text":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
        "currency_raw_text":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
        "total_amount":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
        "total_tax":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}}
      }
    },
    "lines":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "description":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
          "amount":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}},
          "tax_raw_text":{"type":"object","properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}}
        }
      }
    },
    "is_multi_invoice":{"type":"boolean"}
  },
  "required":["header","lines","is_multi_invoice"]
}
```

### 4.2 MappingResult（映射引擎输出候选）
⚠️区分match_score（映射匹配分）≠ AI confidence
```json
{
  "supplier_candidates":[
    {"partner_id":"integer","name":"string","match_score":"number","match_type":"string","matched_rule_id":"integer|null"}
  ],
  "product_candidates":[],
  "tax_candidates":[],
  "currency_candidates":[]
}
```

### 4.3 HumanReviewResult（账单唯一数据源）
Invoice Creator只读取该对象，禁止从canonical/mapping补任何字段
```json
{
  "header":{
    "supplier_id":{"type":["integer","null"]},
    "invoice_number":{"type":["string","null"]},
    "invoice_date":{"type":["string","null"],"format":"date"},
    "currency_id":{"type":["integer","null"]},
    "total_amount":{"type":["string","null"]},
    "total_tax":{"type":["string","null"]}
  },
  "lines":[
    {
      "product_id":{"type":["integer","null"]},
      "description":{"type":["string","null"]},
      "quantity":{"type":["string","null"]},
      "unit_price":{"type":["string","null"]},
      "subtotal":{"type":["string","null"]},
      "tax_ids":{"type":"array","items":{"type":"integer"}},
      "tax_amount":{"type":["string","null"]},
      "line_total_amount":{"type":["string","null"]}
    }
  ]
}
```

### 4.4 review_warnings数组元素
```json
{"code":"AMOUNT_MISMATCH","message":"文本描述"}
```

## 5 领域服务伪代码（Odoo18事务、queue‑job语义修正）
全部service位于services/，不暴露RPC；由model action/wizard调用。
⚠️OCA queue‑job重要约束：禁止在delayed job内部调用env.cr.commit()。

### 5.1 start_parse(task_id, provider_config_id) — orchestration统一入口
首次解析、重跑、异常恢复全部调用；短事务，拿到锁完成状态变更，提交事务后再调度queue‑job；锁绝不带入worker/HTTP调用。
```python
def start_parse(task_id: int, provider_config_id: int):
    cr = env.cr
    with cr.savepoint():
        # 1.获取排他行锁
        task = lock_service.lock_by_id("vendor.invoice.import.task", task_id)
        # 状态校验：仅允许 to_parse / awaiting_review / error_*
        check_task_allow_start_parse(task)
        # 2.创建全新parse_attempt
        new_attempt = env["vendor.invoice.import.parse.attempt"].create({
            "task_id": task.id,
            "sequence": get_next_sequence(task),
            "provider_config_id": provider_config_id,
            "started_at": fields.Datetime.now(),
            "last_activity_at": fields.Datetime.now(),
            "status": "running",
            "attempt_internal_retry_count": 0,
        })
        # 3.更新task状态
        task.write({
            "current_parse_attempt_id": new_attempt.id,
            "state": "parsing",
            "enter_parsing_datetime": fields.Datetime.now(),
            "human_reviewed": False,
        })
        # ✅ 在此savepoint结束，事务会在外部http请求上下文正常commit；锁释放；**不要在这里发起任何HTTP**
    # 4.事务已经提交释放锁，再调度异步queue‑job
    # 注意：with_delay()仅做调度；真正执行发生在独立worker进程
    parse_service.run_parse_attempt.with_delay(task_id, new_attempt.id)
```

### 5.2 run_parse_attempt(task_id, attempt_id) — queue‑job异步worker
P0：stale‑worker守卫逻辑；不允许过期attempt修改task状态；仅允许修改attempt自身记录。
注意：所有数据库写操作使用worker内部事务；不调用cr.commit()。
```python
def run_parse_attempt(task_id: int, attempt_id:int):
    task = env["vendor.invoice.import.task"].browse(task_id)
    attempt = env["vendor.invoice.import.parse.attempt"].browse(attempt_id)

    # ==========【守卫条件 P0】陈旧worker防护 ==========
    # worker执行时，检查：当前task的current_attempt是否等于本attempt；attempt必须是running
    if not (
        task.state == "parsing"
        and task.current_parse_attempt_id.id == attempt.id
        and attempt.status == "running"
    ):
        # 过期attempt：仅更新attempt自身记录，**禁止修改task任何字段**
        attempt.with_env(env).write({
            "status":"failed",
            "error_message":"Stale worker skip; attempt superseded by newer attempt"
        })
        return

    # ---------- 真正执行AI调用（外部HTTP，无数据库锁持有） ----------
    try:
        canonical_result, raw_bytes = ai_provider.parse_pdf(
            pdf_attachment=task.source_pdf_attachment_id,
            provider_config=attempt.provider_config_id,
            max_attempt_retry=attempt.provider_config_id.max_internal_retry,
            attempt_obj=attempt
        )
    except AIProviderTemporaryError as e:
        # 可重试错误，adapter内部已经完成attempt_internal_retry_count自增并写入attempt
        with env.cr.savepoint():
            att = lock_service.lock_by_id("vendor.invoice.import.parse.attempt", attempt.id)
            att.write({"status":"failed","error_message":str(e)})
            # 注意：**不修改task.state，留给cron或者上层业务处理**
        return
    except AIProviderPermanentError as e:
        with env.cr.savepoint():
            att = lock_service.lock_by_id("vendor.invoice.import.parse.attempt", attempt.id)
            att.write({"status":"failed","error_message":str(e)})
            task = lock_service.lock_by_id("vendor.invoice.import.task", task.id)
            task.write({"state":"error_ai_unavailable"})
        return

    # AI调用成功，执行mapping
    mapping_result = mapping_service.do_mapping(canonical_result)

    # ---------- 回写结果，再次执行守卫 ----------
    with env.cr.savepoint():
        task = lock_service.lock_by_id("vendor.invoice.import.task", task.id)
        att = lock_service.lock_by_id("vendor.invoice.import.parse.attempt", attempt.id)
        # 二次守卫：防止中途task被人为重跑切换current_attempt
        if not (
            task.state == "parsing"
            and task.current_parse_attempt_id.id == att.id
            and att.status == "running"
        ):
            # attempt保存成功结果，但**禁止修改task状态**
            raw_att = store_raw_response_as_attachment(task, raw_bytes)
            att.write({
                "status":"success",
                "canonical_result":canonical_result,
                "mapping_result":mapping_result,
                "raw_response_attachment_id": raw_att.id,
                "finished_at": fields.Datetime.now(),
                "last_activity_at": fields.Datetime.now(),
            })
            return

        # ✅ 守卫全部通过，正常更新attempt + task流转状态
        raw_att = store_raw_response_as_attachment(task, raw_bytes)
        att.write({
            "status":"success",
            "canonical_result":canonical_result,
            "mapping_result":mapping_result,
            "raw_response_attachment_id": raw_att.id,
            "finished_at": fields.Datetime.now(),
            "last_activity_at": fields.Datetime.now(),
        })
        # 判断is_multi_invoice流转task状态
        if canonical_result["is_multi_invoice"]:
            task.write({"state":"error_split_required"})
        else:
            task.write({"state":"awaiting_review"})
```

### 5.3 Cron任务 wd_cron_check_parsing_timeout（修复竞态）
分层：attempt内部重试发生在worker；cron只兜底worker挂死、进程无响应。
判断条件：attempt.status=running，attempt_internal_retry_count已经达到最大，并且last_activity_at超过系统配置超时。
```python
def cron_check_parsing_timeout():
    sys_cfg = env["wd.system.config"].get_config()
    timeout = sys_cfg.task_timeout
    now = fields.Datetime.now()
    candidates = env["vendor.invoice.import.task"].search([
        ("state","=","parsing"),
        ("enter_parsing_datetime","<", now‑timeout)
    ])
    for task in candidates:
        att = task.current_parse_attempt_id
        if not att or att.status != "running":
            continue
        # ⭐双重判断：已经耗尽attempt内部重试，并且超过活性超时
        max_retry = att.provider_config_id.max_internal_retry
        if att.attempt_internal_retry_count >= max_retry and (now - att.last_activity_at) > timeout:
            with env.cr.savepoint():
                t = lock_service.lock_by_id("vendor.invoice.import.task", task.id)
                a = lock_service.lock_by_id("vendor.invoice.import.parse.attempt", att.id)
                a.write({"status":"failed","error_message":"Task cron timeout: worker no activity"})
                t.write({"state":"error_timeout"})
                create_audit_log(t, a, action="cron_timeout")
```

### 5.4 Bill Creator 关键伪代码（事务完整性，防止孤立bill）
⚠️重要：整个账单生成全部在同一个savepoint事务；任意异常全部回滚，禁止遗留孤立account.move；只读取human_review_result。
业务约束：vendor_bill_id ondelete="restrict"；幂等：task有bill_id直接拒绝。
> 修订：SPIKE‑OCA‑001已闭环；不再调用OCA模块helper；`convert_human_result_to_bill_vals`为本模块内部实现。

```python
def create_vendor_bill(task_id):
    with env.cr.savepoint():
        task = lock_service.lock_by_id("vendor.invoice.import.task", task_id)
        # 幂等防护：已经生成账单直接拒绝
        if task.vendor_bill_id:
            raise BusinessException("Bill already generated for this task")

        review_data = task.human_review_result
        # 1.执行pre_check_integrity【Odoo move技术完整性校验，抛异常阻断，事务回滚】
        validation_service.pre_check_integrity(review_data)
        # 2.金额校验，返回警告列表，不抛异常
        warnings = validation_service.check_amount_balance(review_data, task.company_id, sys_config.amount_tolerance)
        task.write({"review_warnings": warnings})
        # 3.无明细兜底逻辑：校验全部通过，lines为空，使用系统默认产品生成单行
        bill_vals = convert_human_result_to_bill_vals(review_data, sys_cfg.default_product_id)

        # 本模块内部组装vals，不调用OCA account_invoice_import代码
        bill = env["account.move"].create(bill_vals)

        # 🔒附件技术决策：不修改原PDF附件的res_model/res_id；复制一份新附件挂载bill；task保留原attachment
        new_att = task.source_pdf_attachment_id.copy({"res_model":"account.move","res_id":bill.id})

        task.write({
            "vendor_bill_id": bill.id,
            "state": "bill_generated"
        })
        create_audit_log(task, action="bill_create")
        return bill
```

附件决策说明：Odoo原生ir.attachment使用res_model/res_id只能绑定一个业务对象；方案选择复制附件：task保留原始attachment；bill获得copy副本，不会破坏task附件引用，实现两边都可查看PDF；不采用中间多对多表，降低模型复杂度。

## 6 OCA account_invoice_import 复用边界（SPIKE‑OCA‑001 已闭环）

|项目|说明|
|---|---|
|Spike编号|SPIKE‑OCA‑001【已完成】|
|探查事实|OCA‑edi 18.0分支存在`account_invoice_import`模块；全部账单构建逻辑耦合在wizard向导内部；**不存在可独立外部调用的账单创建helper函数**|
|✅允许|阅读源码参考`account.move` / `move.line` vals组装思路；复用Odoo Core `ir.attachment`|
|❌严格禁止|manifest增加运行时依赖；调用wizard/do/import_file同步导入入口；invoice2data模板解析；直接复制OCA业务代码|
|最终决策|账单vals转换逻辑`convert_human_result_to_bill_vals`完全在本模块`bill_creator`内部实现，不依赖OCA模块运行。|

## 7 AI Provider Adapter设计
- 协议：HTTPS POST；请求体包含PDF二进制/base64 + Prompt指令
- Prompt Schema固定指令输出is_multi_invoice、字段级value+confidence结构
- 异常分类：
    - AIProviderTemporaryError：可重试网络异常（连接超时、5xx）→ adapter内部循环，每一次重试更新attempt.attempt_internal_retry_count、更新last_activity_at
    - AIProviderPermanentError：4xx、鉴权错误、返回非法JSON →不重试，标记attempt failed
- 原始完整响应报文保存为ir.attachment，业务逻辑不读取该附件，用于排错审计。

## 8 UI / Owl视图设计
1. 主列表视图：vendor.invoice.import.task，过滤状态，操作按钮：上传PDF、重跑AI、打开复核弹窗
2. 复核弹窗（Owl组件）
    - 数据源：task + parse_attempt_ids全部历史attempt
    - 展示当前human_review_result表单
    - 展示全部parse_attempt历史AI候选；按钮【应用本次AI候选结果】：仅把选中attempt的canonical/mapping填充表单，不会自动覆盖用户已经编辑的内容
    - 视觉高亮：读取wd.confidence.threshold配置，普通字段黄色，关键字段红色；仅UI提示，前端不做阻断
    - 唯一按钮：【确认复核并生成草稿账单】
3. 按钮业务逻辑：
    - 点击按钮：前端收集表单payload，调用submit_review；成功后调用bill creator；
    - 后端完整重新执行全套校验，防御前端绕过。
4. 禁止：不做双表单diff并行编辑模式。

## 9 安全与权限设计（增加完整权限矩阵）
DDD定义三类角色，尽量复用Odoo account权限组组合；最小新增安全组。

|Action|AI Invoice User|AI Invoice Reviewer|AI Invoice Config Manager|
|---|---|---|---|
|创建Task|✓|✓|✓|
|上传PDF|✓|✓|✓|
|AI解析/重跑|✓|✓|✓|
|查看AI结果|✓|✓|✓|
|修改Human Review|✗|✓|✓|
|生成Bill|✗|✓|✓|
|查看全部Task|✗|✓|✓|
|修改Provider配置|✗|✗|✓|
|修改Mapping映射|✗|✗|✓|

- security/ir.model.access.csv分配模型读写权限。
- record‑rule：普通User仅查看自己创建的task；Reviewer/Config Manager查看全部task。
- AI服务商配置中的密钥字段：仅Config Manager组可读，普通用户不可见。

## 10 错误码、日志、告警策略
日志分级
- INFO：任务流转、解析启动、账单生成
- WARNING：金额警告、mapping无候选
- ERROR：AI调用失败、cron超时、异常状态流转

告警触发条件（对接Sentry/监控）
1. task大量进入error_ai_unavailable
2. task大量进入error_timeout
3. bill‑creator抛出业务异常

禁止：业务review_warnings警告不上报监控；仅基础设施异常告警。

## 11 部署前置条件
1. Odoo安装模块：queue‑job
> 修订：不再要求部署`account_invoice_import`
2. SPIKE‑OCA‑001技术探查已完成（文档闭环）
3. 配置系统参数：兜底默认费用产品、cron间隔、task超时、金额容差
4. AI服务商配置、四类mapping映射预先维护完成。

## 12 测试设计（扩充并发、事务、竞态用例）
单元测试（tests/）
1. 领域单元：mapping_engine、validation_service校验逻辑、schema校验
2. 状态机全部状态流转；stale‑worker守卫逻辑
3. bill‑creator幂等；重复调用不会生成多张bill
4. cron超时逻辑；模拟hang住的parsing task；区分「内部重试未耗尽」和「真正超时」

集成测试
1. 完整端到端：PDF上传 → AI解析 → 人工复核 → 生成draft bill
2. 多invoice PDF：识别is_multi_invoice流转error_split_required
3. 重跑AI：生成新attempt；不覆盖旧human_review_result
4. 无明细兜底生成单行账单
5. 模拟worker挂死，cron兜底超时
6. 新增P0并发测试
    - 并发start_parse，仅产生一个current_parse_attempt
    - 并发生成bill：一个成功，另一个抛出业务异常，不会生成两张bill
    - stale‑worker：旧attempt返回，禁止修改task状态
    - 事务回滚：account.move创建成功，后续步骤异常，整体回滚，无孤立草稿账单
7. 权限矩阵全覆盖测试

UI测试约定
不做完整浏览器E2E；对关键UI业务行为编写Owl组件契约测试：【应用AI候选】不会覆盖用户已编辑表单；人工测试做视觉与完整交互验收。

## 13 风险点与防护清单

|风险|防护措施|
|---|---|
|数据库行锁持有AI HTTP网络IO|start_parse短事务；提交释放锁之后才调度queue‑job；禁止在with‑for‑update范围内执行外部HTTP调用|
|陈旧worker返回覆盖新attempt|worker执行前守卫判断；过期attempt只能修改自身记录，禁止修改task状态|
|重复生成多张bill|bill‑creator行锁 + vendor_bill_id非空校验；ondelete="restrict"；事务整体回滚|
|开发直接读取canonical_result生成账单|代码评审：bill‑creator只允许读取human_review_result；代码注释红线|
|误用OCA同步文件导入入口|文档+代码注释+评审检查；禁止调用do/import_file；不再依赖OCA模块运行|
|置信度业务阻断|后端：置信度只用于UI渲染，业务不做任何阻断；仅完整性校验阻断账单|
|重跑自动覆盖人工修改结果|重跑生成新attempt；UI需要手动【应用本次AI候选】才填充表单|
|queue‑job内部执行cr.commit()|代码评审禁止；遵循OCA queue‑job规范，worker不调用commit()|
|cron无法区分真正hang worker|attempt增加last_activity_at；cron同时判断retry计数+活性时间|
|删除account.move绕过幂等|vendor_bill_id ondelete="restrict"，禁止删除已经生成bill的关联账单|
|错误引入OCA模块运行时依赖|manifest评审门禁，禁止添加account_invoice_import依赖|

## 📜14 技术不变量表（Coding Contract，评审门禁）

|ID|技术不变量|
|---|---|
|T‑001|Odoo版本固定为18.0|
|T‑002|AI HTTP调用不得持有数据库行锁|
|T‑003|一个task最多存在一个current parse attempt|
|T‑004|stale worker不得修改task状态，仅允许修改自身attempt记录|
|T‑005|一个task最多生成一个vendor bill|
|T‑006|bill creator不得读取canonical_result|
|T‑007|bill creator不得读取mapping_result|
|T‑008|Mapping Engine不得修改mapping主数据|
|T‑009|AI重跑不得覆盖human_review_result|
|T‑010|JSON Schema仅做结构校验；业务完整性校验由validation_service执行|
|T‑011|业务校验不得改变AI异常状态|
|T‑012|OCA同步文件导入入口不得调用|
|T‑013|task事务失败不得留下孤立vendor bill|
|T‑014|queue‑job worker内部禁止调用env.cr.commit()|
|T‑015|task/vendor_bill幂等必须数据库并发安全|
|T‑016|SPIKE‑OCA‑001已完成；**禁止依赖OCA account_invoice_import运行时；账单vals由本模块自主实现**|

> T‑016修订历史：v1.3要求完成spike后才可编码；v1.4已完成源码探查，更新约束内容。

TDD版本：**v1.4**
前置依赖：SRS v1.3.3、DDD v1.2
变更摘要：闭环SPIKE‑OCA‑001；移除`account_invoice_import`运行时依赖；bill_creator改为模块内部自主组装account.move vals；同步更新部署条件、风险清单、技术不变量表T‑016。