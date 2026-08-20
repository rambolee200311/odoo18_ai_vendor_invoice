# docs/context/design/tdd_wd_ai_vendor_invoice.md
模块名称：**wd_ai_vendor_invoice**
文档版本：**v1.4.2（Odoo 18 queue‑job语义生产勘误冻结版，SPIKE‑OCA‑001结论落地）**

前置依赖：
- 业务SRS：`spec_wd_ai_vendor_invoice.md` v1.3.3（业务冻结）
- DDD领域设计：`ddd_wd_ai_vendor_invoice_v1.2.md`（领域模型终审）

说明：本文件为面向Odoo 18的可执行技术详细设计；不再新增业务需求；所有实现服从DDD架构约束。

## 🔒 技术基线冻结
- Odoo版本：18.0
- Python版本：Odoo 18 配套版本
- 数据库：PostgreSQL
- ORM：Odoo 18 ORM
- 前端：Odoo 18 Owl
- OCA依赖：`queue‑job`：锁定Odoo 18兼容版本

> 修订记录：account_invoice_import 移除运行时依赖。源码探查确认：OCA‑edi 18.0分支存在该模块，但无可独立调用的底层账单创建helper；模块逻辑强耦合文件上传向导，仅可作为阅读参考。
> 备注：SPIKE‑OCA‑001已完成源码探查，账单vals组装由本模块bill_creator自主实现。

## 目录
1. [总体技术栈与依赖说明](#1-总体技术栈与依赖说明)
2. [模块目录结构（重构，区分domain/service/adapter/schema）](#2-模块目录结构重构区分domainserviceadapterschema)
3. [ORM数据库模型设计（修正锁、字段、约束、ondelete）](#3-orm数据库模型设计odoo18修正版)
4. [JSON‑B值对象Schema（修复Canonical字段结构漂移）](#4-json‑b值对象schema定义修复canonical字段结构漂移)
5. [领域服务伪代码（Odoo 18事务/锁/queue‑job语义修正）](#5-领域服务伪代码odoo18事务锁queue‑job语义修正)
6. [异步队列Worker、Cron定时任务（竞态、stale‑worker、重试‑超时闭环）](#5-领域服务伪代码odoo18事务锁queue‑job语义修正)
7. [OCA account_invoice_import复用边界 + Spike任务标记（已闭环）](#6-oca-account_invoice_import复用边界spike‑oca‑001-已闭环)
8. [AI Adapter外部调用设计（接口、异常分类）](#7-ai-provider-adapter设计)
9. [UI/视图层设计（Owl视图、wizard、按钮、提示逻辑）](#8-ui--owl视图设计)
10. [安全与权限设计（access、record‑rule、完整权限矩阵）](#9-安全与权限设计增加完整权限矩阵)
11. [错误码、日志、告警策略](#10-错误码日志告警策略)
12. [附件存储技术决策（ir.attachment关联方案）](#bill-creator-关键伪代码事务完整性防止孤立bill)
13. [部署、前置条件](#11-部署前置条件)
14. [测试设计（扩充并发、事务回滚、竞态用例）](#12-测试设计扩充并发事务竞态用例)
15. [风险点与防护清单](#13-风险点与防护清单)
16. [📜技术不变量表（Coding Contract，用于代码评审门禁）](#14-技术不变量表coding-contract评审门禁)

## 1 总体技术栈与依赖说明
Odoo 18.0，PostgreSQL；前端Owl组件

- OCA：`queue‑job`（异步worker，禁止同步阻塞HTTP）
- 第三方库：`jsonschema`，用于运行时校验JSON‑B值对象
- 外部系统：多模态AI服务商HTTP接口（DeepSeek / Claude等）

### 🔴架构红线（复制进代码头部注释）
> AI Provider只负责解析；Mapping只负责推荐；人工负责最终确认；Invoice Creator负责生成 Draft Vendor Bill。
> `human_review_result`是生成`account.move`唯一数据源，禁止从`canonical_result` / `mapping_result`补任何业务字段。
> 数据库排他行锁仅在短事务内；锁绝对不能持有外部AI HTTP网络IO。
> Stale‑worker守卫：过期attempt不允许修改task状态，仅允许写attempt自身记录。
> 一个task最多生成一张vendor bill；禁止产生孤立草稿账单。
> 禁止调用OCA `account_invoice_import`原有同步文件导入入口。
> 不依赖OCA `account_invoice_import`运行时；账单vals全部由本模块`bill_creator`自主组装。

## 2 模块目录结构（重构）
```text
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

约定：领域`service`/`adapter`/`schema`不在model内混杂；service不暴露RPC；所有外部入口通过model‑action/wizard调用。

## 3 ORM数据库模型设计（Odoo 18修正版）
### 3.1 vendor.invoice.import.task（聚合根）

|字段|类型|约束/索引|说明|
|---|---|---|---|
|name|Char|required, copy=False|任务业务编号，序列生成|
|source_pdf_attachment_id|Many2one(ir.attachment)|required, ondelete="restrict"|原始PDF；task与bill分别持有引用；不修改原attachment res_model/res_id|
|company_id|Many2one(res.company)|required, index, default=lambda self: self.env.company|任务所属会计公司；task创建后不可修改；异步worker不依赖env.company获取公司|
|state|Selection|required, index|to_parse / parsing / awaiting_review / bill_generated / error_split_required / error_ai_unavailable / error_timeout|
|selected_provider_config_id|Many2one(wd.ai.provider.config)|required|用户选定AI服务商|
|enter_parsing_datetime|Datetime|index|task进入parsing时刻，业务超时判定起点|
|current_parse_attempt_id|Many2one(vendor.invoice.import.parse.attempt)|ondelete="set null", index|当前业务有效的AI Attempt。解析期间指当前执行Attempt；解析成功后继续指向当前提供给人工复核的最新AI候选Attempt。|
|parse_attempt_ids|One2many(vendor.invoice.import.parse.attempt, task_id)| |全部历史AI尝试记录|
|human_review_result|Json|default=lambda self: dict()|HumanReviewResult值对象，账单唯一数据源；Odoo18内部映射PostgreSQL jsonb；禁止直接写原生PostgreSQL JSON操作|
|human_reviewed|Boolean|default=False|本轮是否完成整体人工复核；重跑后置False，旧数据保留|
|review_warnings|Json|default=lambda self: []|结构化警告数组`[{"code":"","message":""}]`|
|vendor_bill_id|Many2one(account.move)|index, ondelete="restrict"|生成的草稿供应商账单；ondelete改为restrict，防止删除bill后task可再次生成账单|
|audit_log_ids|One2many(vendor.invoice.import.log, task_id)| |审计日志|

数据库约束：`vendor_bill_id`非空，业务禁止再次调用bill‑creator；行锁通过`lock_service`工具获取，禁止模拟`recordset.with_for_update()`伪写法。

### 3.2 vendor.invoice.import.parse.attempt（子实体，隶属于task聚合）

|字段|类型|约束/索引|说明|
|---|---|---|---|
|task_id|Many2one(vendor.invoice.import.task)|required, ondelete="cascade", index|归属task，级联删除|
|sequence|Integer|required|序号1,2,3|
|provider_config_id|Many2one(wd.ai.provider.config)|required|本次attempt使用AI配置|
|started_at|Datetime|index|worker实际开始执行时间；queued状态为空|
|finished_at|Datetime|nullable|结束时间；running/queued状态为null|
|attempt_internal_retry_count|Integer|default=0|本次attempt内部AI请求重试次数；每次重试+1；持久入库，供cron做判断依据|
|status|Selection|required, index|queued / running / success / failed / superseded|
|last_activity_at|Datetime|index|worker活性时间，queued状态为空；每次AI调用/重试更新，仅用于worker本地诊断；禁止作为cron跨事务心跳判定依据|
|canonical_result|Json|nullable|CanonicalInvoiceResult；Odoo18 json存储|
|mapping_result|Json|nullable|MappingResult，与本attempt一一绑定|
|raw_response_attachment_id|Many2one(ir.attachment)|ondelete="set null"|AI原始完整响应报文附件；仅限Reviewer/Config Manager/指定技术管理员访问，禁止public|
|error_message|Text|nullable|失败详情|

> SQL唯一约束：
```python
_sql_constraints = [
    (
        "task_sequence_unique",
        "unique(task_id, sequence)",
        "Parse attempt sequence must be unique per task.",
    )
]
```

> ParseAttempt不冗余存储company；业务读取来源：`attempt.task_id.company_id`。
> Model层queue‑job入口方法：
```python
def job_run_parse(self):
    """queue_job延迟任务入口；ORM model method，禁止业务service直接with_delay"""
    self.ensure_one()
    return parse_service.run_parse_attempt(self.task_id.id, self.id)
```

### 3.3 vendor.invoice.import.log（审计日志）

|字段|类型|约束|说明|
|---|---|---|---|
|task_id|Many2one(vendor.invoice.import.task)|required, ondelete="cascade", index| |
|parse_attempt_id|Many2one(vendor.invoice.import.parse.attempt)|ondelete="set null"|可选关联attempt|
|action|Selection|required|ai_parse / ai_re_run / human_modify / bill_create|
|action_datetime|Datetime|required| |
|user_id|Many2one(res.users)|required|操作人|
|snapshot_delta|Text| |变更摘要，只记录差异，不存完整大JSON|

### 3.4 全局配置主数据（简要）
- `wd.ai.provider.config`：接口地址、密钥、模型名称、单次attempt最大内部重试、单次HTTP请求超时、启用开关；**API密钥仅服务端受控sudo路径读取；禁止输出RPC、日志、error_message、raw response、Sentry**
  - api_key字段权限约束：`groups="wd_ai_vendor_invoice.group_config_manager"`，普通业务用户仅可引用provider ID，不可读取密钥明文。Adapter内部使用`sudo()`读取密钥。
- `wd.confidence.threshold`：全局置信度阈值、关键字段阈值、关键字段清单
- `wd.mapping.vendor_alias`：供应商别名映射
- `wd.mapping.product_keyword`：产品关键词映射
- `wd.mapping.tax_text`：税率文本‑tax映射
- `wd.mapping.currency_text`：币种文本‑currency映射
- `wd.system.config`：兜底默认产品、cron巡检间隔、task全局业务超时、金额容差

全部mapping配置为只读主数据；mapping_engine只读取，不会自动改写配置表。

#### 🔒 lock_service.py 工具（Odoo18行锁封装）
> 变更：移除泛化lock_by_id；改为两个专用函数，杜绝动态SQL标识符风险
```python
def lock_task(task_id: int):
    """获取task排他行锁；在当前事务内生效；事务提交/回滚释放锁"""
    env.cr.execute(
        "SELECT id FROM vendor_invoice_import_task WHERE id = %s FOR UPDATE",
        (task_id,)
    )
    return env["vendor.invoice.import.task"].browse(task_id)

def lock_attempt(attempt_id: int):
    """获取parse attempt排他行锁；在当前事务内生效；事务提交/回滚释放锁"""
    env.cr.execute(
        "SELECT id FROM vendor_invoice_import_parse_attempt WHERE id = %s FOR UPDATE",
        (attempt_id,)
    )
    return env["vendor.invoice.import.parse_attempt"].browse(attempt_id)
```

## 4 JSON‑B 值对象Schema定义（修复Canonical字段结构漂移）
使用`jsonschema`做应用层校验；Odoo Json字段，PostgreSQL底层jsonb；禁止业务代码写PostgreSQL原生JSON操作语句；JSON Schema仅校验结构；业务完整性由`validation_service`完成。

### 4.1 CanonicalInvoiceResult（AI归一输出，恢复DDD定义的value‑with‑confidence结构）
```json
{
  "$schema":"http://json‑schema.org/draft‑2020‑12/schema",
  "type":"object",
  "required":["header","lines","is_multi_invoice"],
  "additionalProperties": false,
  "properties":{
    "header":{
      "type":"object",
      "required":["invoice_number","invoice_date","supplier_raw_text","currency_raw_text","total_amount","total_tax"],
      "additionalProperties": false,
      "properties":{
        "invoice_number":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
        },
        "invoice_date":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"],"format":"date"},"confidence":{"type":"number","minimum":0,"maximum":1}}
        },
        "supplier_raw_text":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
        },
        "currency_raw_text":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
        },
        "total_amount":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
        },
        "total_tax":{
          "type":"object",
          "required":["value","confidence"],
          "additionalProperties": false,
          "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
        }
      }
    },
    "lines":{
      "type":"array",
      "items":{
        "type":"object",
        "required":["description","amount","tax_raw_text"],
        "additionalProperties": false,
        "properties":{
          "description":{
            "type":"object",
            "required":["value","confidence"],
            "additionalProperties": false,
            "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
          },
          "amount":{
            "type":"object",
            "required":["value","confidence"],
            "additionalProperties": false,
            "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
          },
          "tax_raw_text":{
            "type":"object",
            "required":["value","confidence"],
            "additionalProperties": false,
            "properties":{"value":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1}}
          }
        }
      }
    },
    "is_multi_invoice":{"type":"boolean"}
  }
}
```

### 4.2 MappingResult（映射引擎输出候选）
> 说明：以下仅结构示意，正式可执行JSON Schema以 `schemas/*.py` 为准。
```json
{
  "type":"object",
  "properties":{
    "supplier_candidates":{
      "type":"array",
      "items":{
        "type":"object",
        "properties":{
          "partner_id":{"type":["integer","null"]},
          "name":{"type":"string"},
          "match_score":{"type":"number"},
          "match_type":{"type":"string"},
          "matched_rule_id":{"type":["integer","null"]}
        }
      }
    },
    "product_candidates":{"type":"array"},
    "tax_candidates":{"type":"array"},
    "currency_candidates":{"type":"array"}
  }
}
```

### 4.3 HumanReviewResult（账单唯一数据源）
> Invoice Creator只读取该对象，禁止从canonical/mapping补任何字段
> 说明：以下仅结构示意，正式可执行JSON Schema以 `schemas/*.py` 为准。
```json
{
  "type":"object",
  "properties":{
    "header":{
      "type":"object",
      "properties":{
        "supplier_id":{"type":["integer","null"]},
        "invoice_number":{"type":["string","null"]},
        "invoice_date":{"type":["string","null"],"format":"date"},
        "currency_id":{"type":["integer","null"]},
        "total_amount":{"type":["string","null"]},
        "total_tax":{"type":["string","null"]}
      }
    },
    "lines":[
      {
        "type":"object",
        "properties":{
          "product_id":{"type":["integer","null"]},
          "description":{"type":["string","null"]},
          "quantity":{"type":["string","null"]},
          "unit_price":{"type":["string","null"]},
          "subtotal":{"type":["string","null"]},
          "tax_ids":{"type":"array","items":{"type":"integer"}},
          "tax_amount":{"type":["string","null"]},
          "line_total_amount":{"type":["string","null"]}
        }
      }
    ]
  }
}
```

### 4.4 review_warnings数组元素
> 说明：以下仅结构示意，正式可执行JSON Schema以 `schemas/*.py` 为准。
```json
{"code":"AMOUNT_MISMATCH","message":"文本描述"}
```

## 5 领域服务伪代码（Odoo18事务、queue‑job语义修正）
全部service位于`services/`，不暴露RPC；由model action/wizard调用。
⚠️OCA queue‑job重要约束：禁止在delayed job内部调用`env.cr.commit()`。

### 5.1 start_parse(task_id, provider_config_id) — orchestration统一入口
> 契约：`start_parse()` **不主动执行commit**。Task状态变更、ParseAttempt创建以及queue‑job入队处于同一个Odoo业务事务；由Odoo请求生命周期统一提交或回滚。`SELECT FOR UPDATE`锁在该事务结束后释放。异步worker在独立事务中运行，因此AI HTTP调用期间不会持有Task行锁。
> `with cr.savepoint()` 仅子事务回滚点，不等于commit，不会释放FOR UPDATE行锁。

```python
def start_parse(task_id: int, provider_config_id: int):
    cr = env.cr
    with cr.savepoint():
        # 1.获取排他行锁
        task = lock_task(task_id)
        # 状态校验：仅允许 to_parse / awaiting_review / error_*
        check_task_allow_start_parse(task)
        # 2.创建全新parse_attempt：状态=queued，尚未进入worker执行
        new_attempt = env["vendor.invoice.import.parse.attempt"].create({
            "task_id": task.id,
            "sequence": get_next_sequence(task),
            "provider_config_id": provider_config_id,
            "started_at": False,
            "last_activity_at": False,
            "status": "queued",
            "attempt_internal_retry_count": 0,
        })
        # 3.更新task状态
        task.write({
            "current_parse_attempt_id": new_attempt.id,
            "state": "parsing",
            "enter_parsing_datetime": fields.Datetime.now(),
            "human_reviewed": False,
        })
    # 4. queue‑job入队；与上面task/attempt写操作属于同一个外层RPC事务；请求结束才统一commit
    # 不允许直接对service做with_delay；调用model层ORM包装入口
    new_attempt.with_delay(
        description=f"AI Vendor Invoice Parse #{new_attempt.sequence}",
    ).job_run_parse()
```

### 5.2 run_parse_attempt(task_id, attempt_id) — queue‑job异步worker
P0：stale‑worker守卫逻辑；不允许过期attempt修改task状态；仅允许修改attempt自身记录。
注意：所有数据库写操作使用worker内部事务；不调用`cr.commit()`。
```python
def run_parse_attempt(task_id: int, attempt_id:int):
    task = env["vendor.invoice.import.task"].browse(task_id)
    attempt = env["vendor.invoice.import.parse.attempt"].browse(attempt_id)

    # queue‑job不保留原始RPC context；强制使用task携带的company_id
    task = task.with_company(task.company_id)

    # ==========【守卫条件 P0】陈旧worker防护 ==========
    # worker执行时，检查：当前task的current_attempt是否等于本attempt；attempt必须是queued/running
    if not (
        task.state == "parsing"
        and task.current_parse_attempt_id.id == attempt.id
        and attempt.status in ("queued","running")
    ):
        # 过期attempt：标记 superseded，仅更新attempt自身记录，**禁止修改task任何字段**
        attempt.with_env(env).write({
            "status":"superseded",
            "error_message":"Stale worker skip; attempt superseded by newer attempt"
        })
        return

    # 切换为running，填充执行时间戳
    att = lock_attempt(attempt.id)
    att.write({
        "status":"running",
        "started_at": fields.Datetime.now(),
        "last_activity_at": fields.Datetime.now(),
    })

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
            att = lock_attempt(attempt.id)
            att.write({
                "status":"failed",
                "finished_at": fields.Datetime.now(),
                "error_message":str(e)
            })
            task = lock_task(task.id)
            task.write({"state":"error_ai_unavailable"})
        return
    except AIProviderPermanentError as e:
        with env.cr.savepoint():
            att = lock_attempt(attempt.id)
            att.write({
                "status":"failed",
                "finished_at": fields.Datetime.now(),
                "error_message":str(e)
            })
            task = lock_task(task.id)
            task.write({"state":"error_ai_unavailable"})
        return

    # AI调用成功，执行mapping
    mapping_result = mapping_service.do_mapping(canonical_result)

    # ---------- 回写结果，再次执行守卫 ----------
    with env.cr.savepoint():
        task = lock_task(task.id)
        att = lock_attempt(attempt.id)
        # 二次守卫：防止中途task被人为重跑切换current_attempt
        if not (
            task.state == "parsing"
            and task.current_parse_attempt_id.id == att.id
            and att.status == "running"
        ):
            # attempt保存成功结果，状态superseded；**禁止修改task状态**
            raw_att = store_raw_response_as_attachment(task, raw_bytes)
            att.write({
                "status":"superseded",
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
> 异常语义：
> - `error_ai_unavailable`：worker正常走完错误处理流程，AI服务最终不可用
> - `error_timeout`：worker进程挂死、进程丢失活性，cron兜底超时

> 业务超时基准使用task.enter_parsing_datetime；覆盖queued / running两种状态；不再依靠`last_activity_at`做跨进程活性判断；该字段仅本地诊断。
> Task.parsing是业务级“解析处理中”，包含queue排队queued以及worker执行running；具体技术状态以ParseAttempt.status、关联queue.job为准。
```python
def cron_check_parsing_timeout():
    sys_cfg = env["wd.system.config"].get_config()
    timeout = sys_cfg.task_timeout
    now = fields.Datetime.now()
    candidates = env["vendor.invoice.import.task"].search([
        ("state","=","parsing"),
    ])
    for task in candidates:
        att = task.current_parse_attempt_id
        if not att:
            continue
        if (now - task.enter_parsing_datetime) > timeout:
            with env.cr.savepoint():
                t = lock_task(task.id)
                a = lock_attempt(att.id)
                a.write({"status":"failed","error_message":"Task cron timeout: parsing lifecycle exceed system timeout"})
                t.write({"state":"error_timeout"})
                create_audit_log(t, a, action="cron_timeout")
```

### 5.4 Bill Creator 关键伪代码（事务完整性，防止孤立bill）
> ⚠️重要：账单生成步骤处于同一个Odoo业务事务；内部可以使用savepoint作为局部回滚边界；任意异常全部回滚，禁止遗留孤立`account.move`；只读取`human_review_result`。
业务约束：`vendor_bill_id ondelete="restrict"`；幂等：task有bill_id直接拒绝。

> 修订：SPIKE‑OCA‑001已闭环；不再调用OCA模块helper；`convert_human_result_to_bill_vals`为本模块内部实现。
> 新增服务端硬校验：task状态必须awaiting_review，human_reviewed=True，存在human_review_result。

```python
def create_vendor_bill(task_id):
    with env.cr.savepoint():
        task = lock_task(task_id)
        task = task.with_company(task.company_id)

        # ============服务端硬校验，不依赖UI============
        if task.state != "awaiting_review":
            raise BusinessException("Task state must be awaiting_review before generate bill")
        if not task.human_reviewed:
            raise BusinessException("Task must be human reviewed before generate bill")
        if not task.human_review_result:
            raise BusinessException("Missing human review result")
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
        bill_vals["company_id"] = task.company_id.id

        # 本模块内部组装vals，不调用OCA account_invoice_import代码
        bill = env["account.move"].create(bill_vals)

        # 🔒附件技术决策：Task保留原始PDF attachment；生成Bill时复制一条独立attachment记录挂载至Bill，两条attachment对应同一原始PDF内容。
        new_att = task.source_pdf_attachment_id.copy({"res_model":"account.move","res_id":bill.id})

        task.write({
            "vendor_bill_id": bill.id,
            "state": "bill_generated"
        })
        create_audit_log(task, action="bill_create")
        return bill
```

```python
def action_confirm_review_and_create_bill(self, review_payload):
    """UI唯一后端入口：复核保存 + 生成账单，同一个业务事务"""
    lock_task(self.id)
    review_service.save(self, review_payload)
    self.human_reviewed = True
    return bill_creator.create_vendor_bill(self.id)
```

> UI业务约束：前端按钮【确认复核并生成草稿账单】不拆成两次RPC；后端提供单一入口`action_confirm_review_and_create_bill`，复核保存+生成账单在同一个事务，失败完整rollback。

## 6 OCA account_invoice_import 复用边界（SPIKE‑OCA‑001 已闭环）

|项目|说明|
|---|---|
|Spike编号|SPIKE‑OCA‑001【已完成】|
|探查事实|OCA‑edi 18.0分支存在`account_invoice_import`模块；全部账单构建逻辑耦合在wizard向导内部；不存在可独立外部调用的账单创建helper函数|
|✅允许|阅读源码参考`account.move` / `move.line` vals组装思路；复用Odoo Core `ir.attachment`|
|❌严格禁止|manifest增加运行时依赖；调用wizard/do/import_file同步导入入口；invoice2data模板解析；直接复制OCA业务代码|
|最终决策|账单vals转换逻辑`convert_human_result_to_bill_vals`完全在本模块`bill_creator`内部实现，不依赖OCA模块运行。|

## 7 AI Provider Adapter设计
协议：HTTPS POST；请求体包含PDF二进制/base64 + Prompt指令
Prompt Schema固定指令输出`is_multi_invoice`、字段级`value+confidence`结构

异常分类：
- `AIProviderTemporaryError`：可重试网络异常（连接超时、5xx）→ adapter内部循环，每一次重试更新`attempt.attempt_internal_retry_count`、更新`last_activity_at`
- `AIProviderPermanentError`：4xx、鉴权错误、返回非法JSON →不重试，标记attempt failed

原始完整响应报文保存为`ir.attachment`，业务逻辑不读取该附件，用于排错审计。

## 8 UI / Owl视图设计
- 主列表视图：`vendor.invoice.import.task`，过滤状态，操作按钮：上传PDF、重跑AI、打开复核弹窗
- 复核弹窗（Owl组件）
  - 数据源：task + `parse_attempt_ids`全部历史attempt
  - 展示当前`human_review_result`表单
  - 展示全部parse_attempt历史AI候选；按钮【应用本次AI候选结果】：仅把选中attempt的canonical/mapping填充表单，不会自动覆盖用户已经编辑的内容
  - 视觉高亮：读取`wd.confidence.threshold`配置，普通字段黄色，关键字段红色；仅UI提示，前端不做阻断
  - 唯一按钮：【确认复核并生成草稿账单】

> 变更：不拆分为 submit_review + create_vendor_bill 两次RPC；调用后端统一入口 `action_confirm_review_and_create_bill`。

禁止：不做双表单diff并行编辑模式。

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

- `security/ir.model.access.csv`分配模型读写权限。
- `record‑rule`：普通User仅查看自己创建的task；Reviewer/Config Manager查看全部task。
- AI服务商配置中的密钥字段：仅Config Manager组可读，普通用户不可见。
- raw_response_attachment_id：权限继承task；仅Reviewer / Config Manager / 指定技术管理员可读，禁止public。

> 开发security.xml注意：`group_config_manager`不要通过`implied_ids`隐式继承Reviewer财务复核权限；权限采用组合模式。

## 10 错误码、日志、告警策略
日志分级
- INFO：任务流转、解析启动、账单生成
- WARNING：金额警告、mapping无候选
- ERROR：AI调用失败、cron超时、异常状态流转

告警触发条件（对接Sentry/监控）
- task大量进入`error_ai_unavailable`
- task大量进入`error_timeout`
- bill‑creator抛出业务异常

> 不变量：Provider API Secret禁止写入普通日志、audit日志、error_message、raw response、Sentry breadcrumbs。

禁止：业务`review_warnings`警告不上报监控；仅基础设施异常告警。

## 11 部署前置条件
- Odoo安装模块：`queue‑job`
- manifest depends：`["account","contacts","queue_job"]`
- 修订：不再要求部署`account_invoice_import`
- SPIKE‑OCA‑001技术探查已完成（文档闭环）
- 配置系统参数：兜底默认费用产品、cron间隔、task超时、金额容差
- AI服务商配置、四类mapping映射预先维护完成。

## 12 测试设计（扩充并发、事务回滚、竞态用例）
单元测试（`tests/`）
- 领域单元：mapping_engine、validation_service校验逻辑、schema校验
- 状态机全部状态流转；stale‑worker守卫逻辑；queued→running流转；superseded不计入AI失败统计
- bill‑creator幂等；重复调用不会生成多张bill；校验awaiting_review+human_reviewed硬约束
- cron超时逻辑；模拟hang住的parsing task；业务超时基于task.enter_parsing_datetime，覆盖queued、running

集成测试
- 完整端到端：PDF上传 → AI解析 → 人工复核 → 生成draft bill
- 多invoice PDF：识别`is_multi_invoice`流转`error_split_required`
- 重跑AI：生成新attempt；旧attempt标记superseded；不覆盖旧`human_review_result`
- 无明细兜底生成单行账单
- 模拟worker挂死，cron兜底超时

新增P0并发测试
- 并发`start_parse`，仅产生一个current_parse_attempt；数据库unique(task_id,sequence)约束生效
- 并发生成bill：一个成功，另一个抛出业务异常，不会生成两张bill
- stale‑worker：旧attempt返回，标记superseded，禁止修改task状态
- 事务回滚：account.move创建成功，后续步骤异常，整体回滚，无孤立草稿账单
- 权限矩阵全覆盖测试
- API密钥不泄露日志/RPC/异常返回
- queue‑job仅使用model method作为延迟入口；service不可直接with_delay
- 异步job公司上下文隔离；account.move写入正确company_id

UI测试约定：不做完整浏览器E2E；对关键UI业务行为编写Owl组件契约测试：【应用AI候选】不会覆盖用户已编辑表单；人工测试做视觉与完整交互验收。

## 13 风险点与防护清单

|风险|防护措施|
|---|---|
|数据库行锁持有AI HTTP网络IO|`start_parse`短事务；task/attempt写与queue‑job入队属于同一RPC事务；请求结束统一commit释放锁之后worker才会执行；禁止在with‑for‑update范围内执行外部HTTP调用|
|陈旧worker返回覆盖新attempt|worker执行前守卫判断；过期attempt标记superseded，只能修改自身记录，禁止修改task状态；superseded不计入AI失败统计|
|重复生成多张bill|bill‑creator行锁 + `vendor_bill_id`非空校验；`ondelete="restrict"`；事务整体回滚；服务端硬校验awaiting_review+human_reviewed|
|开发直接读取canonical_result生成账单|代码评审：bill‑creator只允许读取`human_review_result`；代码注释红线|
|误用OCA同步文件导入入口|文档+代码注释+评审检查；禁止调用do/import_file；不再依赖OCA模块运行|
|置信度业务阻断|后端：置信度只用于UI渲染，业务不做任何阻断；仅完整性校验阻断账单|
|重跑自动覆盖人工修改结果|重跑生成新attempt；UI需要手动【应用本次AI候选】才填充表单；旧attempt superseded|
|queue‑job内部执行cr.commit()|代码评审禁止；遵循OCA queue‑job规范，worker不调用commit()|
|cron无法识别queued永久卡死任务|业务超时基准采用task.enter_parsing_datetime，覆盖queued/running；last_activity_at仅用于本地诊断，不作为跨事务判定条件|
|删除account.move绕过幂等|`vendor_bill_id ondelete="restrict"`，禁止删除已经生成bill的关联账单|
|错误引入OCA模块运行时依赖|manifest评审门禁，禁止添加`account_invoice_import`依赖|
|动态SQL标识符注入风险|lock_service移除泛化lock_by_id；使用lock_task / lock_attempt专用函数，不接收外部model_name入参|
|API密钥泄露|密钥受控sudo读取；禁止出现在RPC、日志、error_message、raw附件、Sentry；字段配置groups权限隔离|
|raw_response附件越权访问|ACL约束，仅Reviewer/Config Manager/指定技术管理员可读，权限继承task，禁止public|
|queue‑job丢失原始RPC公司上下文|task持久化company_id；异步任务强制with_company切换；account.move显式传入company_id|
|直接对service执行with_delay触发队列异常|queue‑job仅允许model method作为延迟任务入口，禁止service实例with_delay|

## 📜14 技术不变量表（Coding Contract，评审门禁）

|ID|技术不变量|
|---|---|
|T‑001|Odoo版本固定为18.0|
|T‑002|AI HTTP调用不得持有数据库行锁|
|T‑003|一个task最多存在一个current parse attempt|
|T‑004|stale worker不得修改task状态，仅允许修改自身attempt记录；状态标记为superseded，不计入AI失败统计|
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
|T‑016|SPIKE‑OCA‑001已完成；禁止依赖OCA account_invoice_import运行时；账单vals由本模块自主实现|
|T‑017|Provider API Secret禁止通过RPC、日志、审计、异常信息暴露。|
|T‑018|ParseAttempt(task_id, sequence)必须数据库唯一。|
|T‑019|Bill Creator仅允许awaiting_review且human_reviewed=True的Task执行。|
|T‑020|Task/Attempt状态修改与queue‑job入队属于同一Odoo事务。|
|T‑021|error_ai_unavailable表示AI正常错误流程最终失败；error_timeout表示worker活性丢失导致超时。|
|T‑022|Attempt在queue中为queued，worker真正开始后才进入running。|
|T‑023|superseded attempt不得计入AI失败统计。|
|T‑024|queue_job只以Odoo Model method作为延迟任务入口；普通service不得直接作为with_delay调用对象。|
|T‑025|task.company_id任务创建后不可变更；异步worker不依赖env.company获取会计公司上下文。|
|T‑026|cron解析超时判定基准使用task.enter_parsing_datetime，同时覆盖queued、running状态；last_activity_at仅用于本地诊断，不参与跨事务超时判定。|
|T‑027|account.move创建必须显式传入company_id，不依赖环境上下文。|
|T‑028|security.xml中group_config_manager禁止implied_ids隐式继承Reviewer权限，权限采用组合模式。|
|T‑029|复核保存与账单生成必须使用同一个后端事务入口action_confirm_review_and_create_bill，禁止拆分为两次RPC。|

---

TDD版本：**v1.4.2**
前置依赖：SRS v1.3.3、DDD v1.2
变更摘要：
1. v1.4.1全部变更继承；
2. P0修复：last_activity_at跨事务心跳失效；queue_job不允许service直接with_delay；queue_job丢失RPC‑context导致company上下文丢失；cron无法捕获queued永久卡死；
3. P1收口：task持久化company_id；bill创建显式携带company_id；savepoint措辞修正；provider api_key字段groups权限；security权限继承约束；新增UI统一事务入口；补充对应并发测试；风险清单同步扩充；
4. 新增技术不变量T‑024 ~ T‑029。

## 附录：v1.4.1 → v1.4.2 修改备查（不参与业务阅读，仅变更追溯）
1. 文档头部版本升级 v1.4.1 → v1.4.2
2. ORM task模型新增`company_id`字段，task创建后不可修改。
3. parse_attempt补充model层queue‑job入口`job_run_parse`；禁止service直接with_delay；调整start_parse入队调用。
4. run_parse_attempt函数内部增加task公司上下文切换`task.with_company(task.company_id)`。
5. 修正cron超时逻辑：放弃last_activity_at跨事务判定，改用task.enter_parsing_datetime，覆盖queued/running。
6. bill_creator增加task公司上下文切换，bill_vals显式注入`company_id`；补充`action_confirm_review_and_create_bill`伪代码。
7. 修正Bill Creator章节savepoint描述措辞。
8. ai_provider_config api_key增加groups权限约束。
9. 安全章节补充：group_config_manager禁止implied_ids隐式继承Reviewer权限。
10. 测试用例增加queue‑job入口约束、异步公司上下文隔离、account.move公司正确性测试。
11. 风险清单补充queue‑job入口风险、异步上下文丢失风险。
12. 技术不变量表追加T‑024 ~ T‑029。
13. 文档末尾变更摘要更新；增加本附录用于变更追溯。