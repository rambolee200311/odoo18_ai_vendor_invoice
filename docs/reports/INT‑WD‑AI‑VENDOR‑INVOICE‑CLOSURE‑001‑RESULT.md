我将按 Closure 文档执行只读验收：先读取冻结基线和 Closure 清单，再从当前 `main` 工作树收集结构证据、运行时测试证据与门禁证据；不会修改正式源码、测试或冻结文档。

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && printf '%s\n' '--- status ---' && git status --short --branch && printf '%s\n' '--- closure doc ---' && sed -n '1,280p' 'docs/intents/INT‑WD‑AI‑VENDOR‑INVOICE‑CLOSURE‑001.md'

Read tool output
Completed with input: {
  "path": "/var/folders/lx/qszgx8zs25q67qyv53bn10sr0000gn/T/1787306275551-copilot-tool-output-33385-15f72604-c954-4c40-8faa-8841777b9cc7.txt",
  "view_range": [
    1,
    120
  ]
}

Read tool output
Completed with input: {
  "path": "/var/folders/lx/qszgx8zs25q67qyv53bn10sr0000gn/T/1787306275551-copilot-tool-output-33385-15f72604-c954-4c40-8faa-8841777b9cc7.txt",
  "view_range": [
    112,
    240
  ]
}

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && find . -maxdepth 5 -type f \( -name 'verify.py' -o -name '*test*.py' \) | sort && printf '\n--- baseline docs ---\n' && find docs/context -maxdepth 2 -type f | sort && printf '\n--- module files ---\n' && find addons/ai_vendor_invoice -type f | sort

Search for `^#{1,4} |T-0[0-2][0-9]|SRS-|Requirement|Invariant|不变量`

Read , lines 1 to 220
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/requirements/spec_wd_ai_vendor_invoice_1.3.3.md",
  "view_range": [
    1,
    220
  ]
}

Read , lines 90 to 220
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/requirements/spec_wd_ai_vendor_invoice_1.3.3.md",
  "view_range": [
    90,
    220
  ]
}

Read , lines 200 to 250
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/requirements/spec_wd_ai_vendor_invoice_1.3.3.md",
  "view_range": [
    200,
    250
  ]
}

Read , lines 1 to 330
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/design/ddd_wd_ai_vendor_invoice_v1.2.md",
  "view_range": [
    1,
    330
  ]
}

Read , lines 102 to 330
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/design/ddd_wd_ai_vendor_invoice_v1.2.md",
  "view_range": [
    102,
    330
  ]
}

Read , lines 233 to 330
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/design/ddd_wd_ai_vendor_invoice_v1.2.md",
  "view_range": [
    233,
    330
  ]
}

Read , lines 700 to 790
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/docs/context/design/tdd_wd_ai_vendor_invoice_v1.4.md",
  "view_range": [
    700,
    790
  ]
}

基线核查发现 Closure 目录中没有 `verify.py`，且必须运行的并发、stale-worker、multi-company、secret 泄漏专项正式测试需要以实际套件结果判定，不能用静态代码替代。现在先执行当前 `main` 的模块升级与完整模块测试，保留原始日志证据。

Ran terminal command: set -eu
cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice
LOG=/tmp/ai_vendor_invoice_closure_odoo.log
rm -f "$LOG"
venv/bin/python3 odoo-bin -c odoo.conf \
  --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons \
  -d odoo18e_tms -u ai_vendor_invoice --test-enable --test-tags /ai_vendor_invoice \
  --stop-after-init --logfile="$LOG" --log-level=info
printf '\n--- closure test summary ---\n'
rg -n 'Module ai_vendor_invoice loaded|0 failed|failed,|error\(s\)|Starting Test|Some modules are not loaded' "$LOG" | tail -80
printf '\n--- test count ---\n'
rg -c 'Starting Test|Starting Test' "$LOG" || true
printf '\nlog=%s\n' "$LOG"

Ran terminal command: LOG=/tmp/ai_vendor_invoice_closure_odoo.log; printf '%s\n' '--- final summary lines ---'; rg -n 'Module ai_vendor_invoice loaded|[0-9]+ failed|[0-9]+ error|At least one test failed|Some modules are not loaded|Starting post tests|post-tests' "$LOG"; printf '%s\n' '--- tests by file ---'; rg 'Starting Test' "$LOG" | awk -F'odoo.addons.ai_vendor_invoice.tests.' '{print $2}' | cut -d: -f1 | sed 's/\.test_.*//' | sort | uniq -c; printf '%s\n' '--- failure/error markers ---'; rg -n 'FAIL:|ERROR: Test|Traceback|AssertionError' "$LOG" || true

Ran terminal command: LOG=/tmp/ai_vendor_invoice_closure_odoo.log; printf '%s\n' '--- executed test names ---'; rg 'Starting Test' "$LOG" | sed -E 's/.*tests\.//; s/ \.+$//' | sed -n '1,100p'; printf '%s\n' '--- relevant formal test symbols ---'; rg -n 'concurr|stale|queue|secret|api_key|company|rollback|permission|AccessError|with_user|bill' addons/ai_vendor_invoice/tests --glob '*.py' || true

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && printf '%s\n' '--- manifest ---'; sed -n '1,80p' addons/ai_vendor_invoice/__manifest__.py; printf '%s\n' '--- security/access ---'; sed -n '1,220p' addons/ai_vendor_invoice/security/ir.model.access.csv; printf '%s\n' '--- record rules ---'; sed -n '1,120p' addons/ai_vendor_invoice/security/record_rules.xml; printf '%s\n' '--- provider secret references ---'; rg -n 'api_key|secret|error_message|logger|_logger|raw_response|public' addons/ai_vendor_invoice --glob '*.py' --glob '*.xml'

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && printf '%s\n' '--- source symbols ---' && rg -n '^class |^def |^    def |_sql_constraints|_name =|depends|assets|group_config_manager|groups=' addons/ai_vendor_invoice --glob '*.py' --glob '*.xml' --glob '*.csv' | sed -n '1,260p'; printf '%s\n' '--- forbidden calls ---' && rg -n 'account_invoice_import|do/import_file|with_delay|cr\.commit|canonical_result|mapping_result|SELECT .*FOR UPDATE|account\.move.*create' addons/ai_vendor_invoice --glob '*.py' --glob '*.xml' --glob '*.csv' || true

Search for `^def |^    def |_sql_constraints|depends|with_delay|cr\.commit|canonical_resu...`

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && venv/bin/python3 odoo-bin shell -c odoo.conf --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons -d odoo18e_tms <<'PY'
print('companies:', env['res.company'].search_count([]))
print('users:', env['res.users'].search_count([]))
print('reviewer group:', env.ref('ai_vendor_invoice.group_reviewer').id)
print('config group:', env.ref('ai_vendor_invoice.group_config_manager').id)
print('cron:', env.ref('ai_vendor_invoice.ir_cron_check_parsing_timeout').active)
print('rules:', env['ir.rule'].search_count([('model_id.model', '=', 'vendor.invoice.import.task')]))
print('verify.py:', 'absent')
PY

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && venv/bin/python3 odoo-bin shell -c odoo.conf --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons -d odoo18e_tms <<'PY'
Provider = env['wd.ai.provider.config'].sudo()
provider = Provider.create({'name': 'closure-secret-probe', 'api_base_url': 'https://example.invalid', 'api_key': 'closure-secret-value', 'model_name': 'probe'})
for user in env['res.users'].search([], order='id'):
    try:
        value = env['wd.ai.provider.config'].with_user(user).browse(provider.id).api_key
        print('user', user.login, 'api_key_visible:', bool(value), 'is_config_manager:', user.has_group('ai_vendor_invoice.group_config_manager'))
    except Exception as error:
        print('user', user.login, 'read_result:', type(error).__name__)
provider.unlink()
PY

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && venv/bin/python3 odoo-bin shell -c odoo.conf --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons -d odoo18e_tms <<'PY'
Provider = env['wd.ai.provider.config'].sudo()
provider = Provider.create({'name': 'closure-secret-probe', 'api_base_url': 'https://example.invalid', 'api_key': 'closure-secret-value', 'model_name': 'probe'})
for user in env['res.users'].search([], order='id'):
    fields = env['wd.ai.provider.config'].with_user(user).fields_get(['api_key'])
    print('user', user.login, 'rpc_field_exposed:', bool(fields), 'is_config_manager:', user.has_group('ai_vendor_invoice.group_config_manager'))
provider.unlink()
PY

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && venv/bin/python3 odoo-bin shell -c odoo.conf --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons -d odoo18e_tms <<'PY'
for name in ('ai_vendor_invoice', 'queue_job', 'account_invoice_import'):
    module = env['ir.module.module'].search([('name', '=', name)], limit=1)
    print(name, module.state if module else 'absent')
PY

Read , lines 1 to 100
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/ai_vendor_invoice/models/system_config.py",
  "view_range": [
    1,
    100
  ]
}

Read , lines 1 to 100
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/ai_vendor_invoice/models/conf_threshold.py",
  "view_range": [
    1,
    100
  ]
}

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && git status --short --branch && printf '\n--- verify files ---\n' && find . -type f -name 'verify.py' -o -name '*closure*test*.py' | sort

Read , lines 1 to 260
Completed with input: {
  "path": "/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/execution/scripts/verify.py",
  "view_range": [
    1,
    260
  ]
}

Ran terminal command: cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice && venv/bin/python3 execution/scripts/verify.py

# INT‑WD‑AI‑VENDOR‑INVOICE‑CLOSURE‑001 核查报告

审计严格基于当前磁盘源码、测试、XML、manifest 和 Odoo 运行输出，没有依赖历史 Sprint 报告。

本次审计没有修改正式业务代码、正式测试代码或冻结文档，也没有创建正式源码树内的临时文件。

---

## 0. 执行环境与证据

### 当前工作树

```text
/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice
```

当前存在的用户未提交变更：

```text
M  .gitignore
A  docs/intents/INT‑WD‑AI‑VENDOR‑INVOICE‑CLOSURE‑001.md
A  docs/prompts/prompt04.md
```

审计未修改这些文件。

### Odoo 模块升级与测试

执行命令：

```bash
venv/bin/python3 odoo-bin \
  -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,addons \
  -d odoo18e_tms \
  -u ai_vendor_invoice \
  --test-enable \
  --test-tags /ai_vendor_invoice \
  --stop-after-init
```

真实结果：

```text
0 failed, 0 error(s) of 44 tests
```

实际执行测试文件：

- `addons/ai_vendor_invoice/tests/test_models.py`：34 项；
- `addons/ai_vendor_invoice/tests/test_intent3_services.py`：10 项。

Odoo 日志证据：

```text
Module ai_vendor_invoice loaded
0 failed, 0 error(s) of 44 tests
```

数据库运行状态：

```text
ai_vendor_invoice: installed
queue_job: installed
account_invoice_import: absent
```

### verify.py

执行：

```bash
venv/bin/python3 execution/scripts/verify.py
```

结果：

```text
Python 编译: PASS
XML 结构: FileNotFoundError
```

失败原因：

```text
FileNotFoundError:
addons/wd_tlms/views
```

当前 `execution/scripts/verify.py` 实际针对 `wd_tlms`，不是 `ai_vendor_invoice`，且无法完成执行。

---

# 1. SRS 逐条反向核查

基线：`spec_wd_ai_vendor_invoice_1.3.3.md`

## 1.1 发票任务管理

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.1.1 上传 PDF、附件永久保存 | `import_task.source_pdf_attachment_id`、任务表单 | PARTIAL | 有附件字段和表单字段，但没有完整上传入口/上传流程测试 |
| SRS-4.1.2 创建任务并记录状态、操作人、时间、模型、重试信息 | `import_task.py`、`import_parse_attempt.py` | PASS | 模型字段存在，基础测试通过 |
| SRS-4.1.3 完整任务状态集合 | `task.state` selection | PASS | 状态集合存在 |
| SRS-4.1.4 支持切换 AI 模型重跑 | `action_rerun_ai`、`start_parse` | PARTIAL | 产生新 attempt，但动作没有独立的 provider 参数，UI 也没有实际模型切换交互 |
| SRS-4.1.5 完整审计日志 | `parse_service.py`、`bill_creator.py` | PARTIAL | 解析、重跑、复核、账单有日志；缺少端到端审计测试 |
| SRS-4.1.6 多页 PDF、多发票识别 | adapter PDF payload、`is_multi_invoice` 状态分支 | PARTIAL | 代码有分支，但无真实 AI 集成测试 |
| SRS-4.1.7 重试优先、cron 超时恢复 | `timeout_service.py` | FAIL | timeout 服务未检查内部 retry 是否耗尽，可能在 retry 尚未耗尽时提前标记 `error_timeout` |
| SRS-4.1.8 单文件上传、不支持批量 | 当前任务模型 | PARTIAL | 未发现批量入口，但缺少 UI 验证测试 |

## 1.2 AI 解析调用

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.2.1 多语种 AI 解析 | DeepSeek/Claude adapter | PARTIAL | 适配器存在，但无真实多语种样本测试 |
| SRS-4.2.2 多套 AI Provider | `deepseek.py`、`claude.py` | PASS | 结构实现存在 |
| SRS-4.2.3 默认模型与任务级模型切换 | `selected_provider_config_id` | PARTIAL | 有任务级 provider，但系统配置没有默认 provider 字段 |
| SRS-4.2.4 provider 地址、密钥、模型、超时、重试配置 | `wd.ai.provider.config` | PASS | 字段存在 |
| SRS-4.2.5 不内置 OCR/模型运算 | adapter HTTP 调用 | PASS | 静态证据通过 |
| SRS-4.2.6 异步任务模型 | `action_enqueue_parse`、`job_run_parse` | PASS | queue-job model method 入口存在 |
| SRS-4.2.7 字段级 confidence 与 `is_multi_invoice` | canonical schema | PARTIAL | Schema 存在，但 adapter 未执行 schema 校验和字段归一化 |

## 1.3 解析预览与人工修正

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.3.1 展示解析结果 | `human_review_result` JSON 视图、Owl dialog | PARTIAL | 有 JSON 展示，未形成完整结构化复核表单 |
| SRS-4.3.2 低置信度黄色/红色高亮 | `wd.confidence.threshold` 字段 | NOT_IMPLEMENTED | 配置字段存在，但没有 Owl 高亮实现 |
| SRS-4.3.3 人工修改全部关键字段 | `review_dialog.xml` | NOT_IMPLEMENTED | 当前主要是 `<pre>` 展示，没有完整编辑控件 |
| SRS-4.3.4 单按钮复核并生成账单 | `action_confirm_review_and_create_bill` | PARTIAL | 后端入口存在，但 UI 没有完整按钮交互测试 |
| SRS-4.3.5 置信度配置 | `conf_threshold.py` | PARTIAL | 模型字段存在，配置视图和 UI 使用缺失 |

## 1.4 Mapping

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.4.1 供应商候选 | `mapping_service.py` | PASS | 代码实现存在 |
| SRS-4.4.2 产品候选 | `mapping_service.do_mapping` | PASS | 代码实现存在 |
| SRS-4.4.3 税码候选 | `mapping_service.do_mapping` | PASS | 代码实现存在 |
| SRS-4.4.4 币种候选 | `mapping_service.do_mapping` | PASS | 代码实现存在 |
| Mapping 只推荐、不修改主数据 | `mapping_service.py` 静态扫描 | PASS | 未发现主数据写入 |

但 Mapping 没有独立正式运行时测试，属于测试缺口。

## 1.5 账单生成

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.5.1 本模块账单创建与 OCA 同步入口边界 | manifest/TDD/Coding Contract/SRS v1.3.4 | PASS | DOC-INTENT-AI-VENDOR-003 选择方案 A；SRS v1.3.4 已明确不依赖 `account_invoice_import` |
| SRS-4.5.2 生成草稿供应商账单 | `account.move.create()` | PASS | Intent-3 测试通过 |
| SRS-4.5.3 原始 PDF 挂载账单 | `source.copy({"res_model": "account.move"})` | PASS | Intent-3 测试通过 |
| SRS-4.5.4 后续过账沿用 account 流程 | 本模块未覆盖 | PASS | 属于边界外流程 |
| SRS-4.5.5 无明细默认产品兜底 | `bill_creator._convert_review_to_move_vals` | PASS | 代码和账单测试覆盖 |

## 1.6 配置管理

| SRS 条目 | 代码/测试证据 | Result | 备注 |
|---|---|---|---|
| SRS-4.6.1 多 Provider 配置 | provider model | PARTIAL | 模型存在，完整配置视图缺失 |
| SRS-4.6.2 默认 AI 模型 | `wd.system.config` | NOT_IMPLEMENTED | 未发现 default provider 字段 |
| SRS-4.6.3 供应商映射配置 | mapping model | PASS | 模型存在 |
| SRS-4.6.4 产品关键词配置 | mapping model | PASS | 模型存在 |
| SRS-4.6.5 税码映射配置 | mapping model | PASS | 模型存在 |
| SRS-4.6.6 币种映射配置 | mapping model | PASS | 模型存在 |
| SRS-4.6.7 双级置信度配置 | `conf_threshold.py` | PARTIAL | 字段存在，UI 消费缺失 |
| SRS-4.6.8 超时和 cron 间隔配置 | `system_config.py`、cron XML | PASS | 字段及 cron 存在 |
| SRS-4.6.9 默认产品配置 | `default_product_id` | PASS | 字段和账单兜底存在 |

## 1.7 业务规则

| SRS 条目 | Result | 证据/备注 |
|---|---|---|
| SRS-5.1 只能生成草稿、不自动过账 | PASS | `move_type=in_invoice`，未调用 post |
| SRS-5.2 供应商无候选进入人工复核 | PARTIAL | mapping 只输出候选，但缺少端到端行为测试 |
| SRS-5.3 产品无候选保留费用行 | PARTIAL | mapping 只推荐，缺少端到端测试 |
| SRS-5.4 账单生成前完整性校验 | PASS | validation service + 测试 |
| SRS-5.5 金额不平只警告 | PASS | `check_amount_balance` 测试通过 |
| SRS-5.6 未人工复核禁止生成 | PASS | bill creator guard 测试通过 |
| SRS-5.7 一个 task 最多一个 bill | PARTIAL | 幂等顺序测试通过，但无并发正式测试 |
| SRS-5.8 模型切换不改 mapping/bill 规则 | PARTIAL | 静态上成立，缺少重跑行为测试 |
| SRS-5.9 全语种使用统一 mapping | PARTIAL | 静态上成立，缺少多语种运行测试 |

## 1.8 SRS 验收标准

| 条目 | Result |
|---|---|
| SRS-9.1 多语种 PDF 解析 | PARTIAL |
| SRS-9.2 多模型配置与手动切换 | PARTIAL |
| SRS-9.3 重跑不覆盖人工结果 | FAIL |
| SRS-9.4 四类 mapping 推荐 | PARTIAL |
| SRS-9.5 confidence 双级 UI 高亮 | NOT_IMPLEMENTED |
| SRS-9.6 多发票进入拆分异常 | PARTIAL |
| SRS-9.7 AI 重试耗尽与 cron 超时 | FAIL |
| SRS-9.8 无明细兜底账单 | PASS |
| SRS-9.9 单 PDF 上传 | PARTIAL |
| SRS-9.10 多页单张发票 | PARTIAL |
| SRS-9.11 单界面查看和修改关键字段 | NOT_IMPLEMENTED |
| SRS-9.12 无候选时人工选择 | PARTIAL |
| SRS-9.13 一次复核界面完成主要操作 | PARTIAL |
| SRS-9.14 单按钮完整校验生成 | PARTIAL |
| SRS-9.15 草稿账单及附件 | PASS |
| SRS-9.16 配置功能完整可用 | PARTIAL |
| SRS-9.17 任务、状态、重跑、审计 | PARTIAL |
| SRS-9.18 独立安装卸载 | PARTIAL |
| SRS-9.19 使用本模块 bill creator 与 Odoo account.move，不调用 OCA 同步入口 | SRS v1.3.4 + manifest | PASS | 文档勘误后与 TDD T-016 / GATE-01 对齐 |

---

# 2. DDD Invariant 逐条核查

基线：`ddd_wd_ai_vendor_invoice_v1.2.md`

| DDD Invariant | Result | 证据 |
|---|---|---|
| 聚合根为 `vendor.invoice.import.task` | PASS | ORM 模型结构 |
| ParseAttempt 隶属于 task | PASS | `task_id` required + cascade |
| HumanReviewResult 是账单唯一数据源 | PARTIAL | bill creator 遵守；缺少静态专门门禁和完整测试 |
| AI Provider 只负责解析 | PARTIAL | adapter 有解析职责，但未做 schema/归一化契约校验 |
| Mapping 只输出候选 | PASS | mapping service 静态扫描 |
| 人工复核最终确认 | PARTIAL | 后端入口存在，UI 编辑/应用候选能力缺失 |
| 重跑保留旧人工结果 | FAIL | `start_parse` 将 `human_review_result` 写成 `{}`，违反 DDD 明确要求保留 |
| ParseAttempt 历史保留 | PASS | One2many + 新 sequence |
| 账单生成只允许统一入口 | PASS | `action_confirm_review_and_create_bill` 存在 |
| 金额不平只产生 warning | PASS | 运行测试通过 |
| task 行锁保证 bill 幂等 | PARTIAL | 静态行锁存在，缺少真实并发 bill 测试 |
| timeout 使用 `enter_parsing_datetime` | PASS | 运行测试覆盖 queued/running |
| timeout 不干扰 retry 层 | FAIL | timeout 未检查 retry 是否耗尽 |
| task.company_id 不可变 | PASS | 运行测试通过 |
| worker 使用 task company | PASS | `with_company(task.company_id)` |
| 原始 PDF task 与 bill 均保留引用 | PASS | 账单附件复制测试通过 |
| Reviewer 可复核并生成 bill | PARTIAL | 后端权限测试存在，UI 完整测试缺失 |
| Config Manager 不隐式继承 Reviewer | PASS | `groups.xml` 静态检查通过 |
| Mapping/AI confidence/warning 分层 | PARTIAL | 数据结构分离，但 UI 使用缺失 |

---

# 3. TDD T‑001 ~ T‑029 核查

基线：`tdd_wd_ai_vendor_invoice_v1.4.md`

| ID | Result | 证据摘要 |
|---|---|---|
| T-001 | PASS | Odoo 18 runtime |
| T-002 | PASS | 外部 HTTP 不在 `lock_task`/`lock_attempt` 范围内 |
| T-003 | PARTIAL | `current_parse_attempt_id` 存在；无并发 `start_parse` 运行测试 |
| T-004 | BLOCKED | stale guard 静态存在，但无正式 stale-worker 测试 |
| T-005 | BLOCKED | bill 行锁/幂等代码存在，无真实并发测试 |
| T-006 | PASS | bill creator 未读取 canonical |
| T-007 | PASS | bill creator 未读取 mapping |
| T-008 | PASS | mapping service 不修改主数据 |
| T-009 | FAIL | `start_parse` 清空 `human_review_result` |
| T-010 | FAIL | adapter 未执行 JSON Schema 验证/归一化 |
| T-011 | PASS | validation service 产生异常/warning，不改 AI error state |
| T-012 | PASS | 未发现 OCA 同步入口调用 |
| T-013 | PASS | 事务回滚测试通过 |
| T-014 | PASS | 未发现 `cr.commit()` |
| T-015 | BLOCKED | 静态行锁存在，缺少并发行为证据 |
| T-016 | PASS | manifest 无 `account_invoice_import`；SRS v1.3.4 已完成对齐 |
| T-017 | BLOCKED | `fields_get` 运行探针显示非配置用户 RPC 字段不可见，但没有正式 secret leakage 测试 |
| T-018 | PASS | SQL unique + 正式测试通过 |
| T-019 | PASS | bill creator 前置状态校验 + 正式测试 |
| T-020 | PARTIAL | start/queue 代码同一请求事务，缺少专门事务测试 |
| T-021 | PASS | timeout/error_ai 状态分支存在 |
| T-022 | BLOCKED | queued/running 代码存在，但无 worker 状态转流正式测试 |
| T-023 | PARTIAL | superseded 状态存在；无失败统计行为测试 |
| T-024 | PASS | `.with_delay()` 只在 model method |
| T-025 | PARTIAL | company immutable 测试通过，缺少 worker 多公司运行测试 |
| T-026 | PASS | queued/running timeout 测试通过 |
| T-027 | PASS | `move_vals["company_id"]` 显式设置 |
| T-028 | PASS | Config Manager 无 implied Reviewer |
| T-029 | PASS | 统一入口存在并使用同一 savepoint/事务 |

---

# 4. Coding Contract GATE‑01 ~ GATE‑15

| Gate | Result | 证据 |
|---|---|---|
| GATE-01 manifest 不包含 `account_invoice_import` | PASS | manifest 静态扫描；SRS v1.3.4 已完成对齐 |
| GATE-02 bill creator 不读 canonical | PASS | `bill_creator.py` 静态扫描 |
| GATE-03 bill creator 不读 mapping | PASS | `bill_creator.py` 静态扫描 |
| GATE-04 worker 无 `cr.commit()` | PASS | 静态扫描 |
| GATE-05 ParseAttempt 唯一约束 | PASS | `_sql_constraints` + 运行测试 |
| GATE-06 账单前置校验 | PASS | `bill_creator.py` + Intent-3 运行测试 |
| GATE-07 stale worker 禁止写 task | BLOCKED | 代码守卫存在，但无正式 stale-worker runtime test |
| GATE-08 provider secret 不进入日志/error/RPC | BLOCKED | `fields_get` 探针通过；缺少正式 secret test |
| GATE-09 company_id 和 with_company | PARTIAL | 静态通过；缺少多公司 worker runtime test |
| GATE-10 并发最终只生成一张 bill | BLOCKED | 没有正式 concurrency test |
| GATE-11 with_delay 只用于 model method | PASS | 静态扫描 |
| GATE-12 使用 account.move.create | PASS | `bill_creator.py:110` |
| GATE-13 company_id 创建后不可写 | PASS | 运行测试通过 |
| GATE-14 统一复核+生成入口 | PASS | model action + service |
| GATE-15 行锁不包裹外部 HTTP | PASS | parse service 执行顺序 + lock service 静态检查 |

---

# 5. Traceability Matrix

| Requirement / Contract ID | Implementation Location | Test / Verification | Result |
|---|---|---|---|
| SRS-4.1 | `models/import_task.py` | `test_models.py` | PARTIAL |
| SRS-4.2 | `adapters/`, `parse_service.py` | 静态扫描；无 adapter 集成测试 | PARTIAL |
| SRS-4.3 | `static/src/owl/`, `import_task_views.xml` | 无 Owl contract test | NOT_IMPLEMENTED/PARTIAL |
| SRS-4.4 | `services/mapping_service.py` | 无 mapping runtime test | PARTIAL |
| SRS-4.5 | `services/bill_creator.py` | `test_intent3_services.py` | PARTIAL/BLOCKED by doc drift |
| SRS-4.6 | `models/*config.py` | 模型测试部分覆盖 | PARTIAL |
| DDD-HR-001 | `bill_creator.py` | 静态扫描 | PASS |
| DDD-RERUN-001 | `parse_service.py` | 无 rerun preservation test | FAIL |
| DDD-TIMEOUT-001 | `timeout_service.py` | `test_timeout_uses_task_entry_time_for_queued_and_running` | FAIL for retry rule |
| DDD-BILL-001 | `bill_creator.py` | rollback/idempotency tests | PARTIAL |
| T-001 | Odoo runtime | `odoo-bin --version` | PASS |
| T-002 | `parse_service.py`/`lock_service.py` | static evidence | PASS |
| T-003 | `start_parse` | no concurrency test | PARTIAL |
| T-004 | `run_parse_attempt` | no stale test | BLOCKED |
| T-005 | `bill_creator.py` | no concurrency test | BLOCKED |
| T-006/T-007 | `bill_creator.py` | static scan | PASS |
| T-008 | `mapping_service.py` | static scan | PASS |
| T-009 | `start_parse` | no preservation test | FAIL |
| T-010 | adapters/schema | no adapter schema test | FAIL |
| T-011 | validation service | Intent-3 tests | PASS |
| T-012 | whole module | forbidden-call scan | PASS |
| T-013 | `test_bill_and_task_roll_back_when_attachment_copy_fails` | Odoo runtime | PASS |
| T-014 | worker source | forbidden-call scan | PASS |
| T-015 | lock service/bill creator | no concurrent runtime test | BLOCKED |
| T-016 | manifest | static scan | PASS under TDD/Contract |
| T-017 | provider config/adapter | `fields_get` diagnostic only | BLOCKED |
| T-018 | ParseAttempt SQL constraint | duplicate insert test | PASS |
| T-019 | bill creator guards | Odoo runtime | PASS |
| T-020 | `start_parse`/enqueue | static only | PARTIAL |
| T-021 | timeout/parse service | static + tests | PASS |
| T-022 | attempt states | model tests only | BLOCKED |
| T-023 | superseded branch | static only | PARTIAL |
| T-024 | `action_enqueue_parse` | delegation test/static | PASS |
| T-025 | company immutable/with_company | partial tests | PARTIAL |
| T-026 | timeout service | queued/running runtime test | PASS |
| T-027 | bill vals | static + bill test | PASS |
| T-028 | groups.xml | static scan | PASS |
| T-029 | model action | source + bill tests | PASS |
| GATE-01~05 | manifest/model source/tests | static + Odoo tests | PASS |
| GATE-06 | bill creator | Odoo test | PASS |
| GATE-07~10 | worker/security/concurrency | formal tests absent | BLOCKED |
| GATE-11~15 | source/model/tests | static + partial runtime | PARTIAL |

---

# 6. 强制运行时测试集合

| 测试类别 | 执行情况 | 结果 |
|---|---|---|
| 模块安装/升级 | `-u ai_vendor_invoice --stop-after-init` | PASS |
| 全部 Unit Tests | 44 项真实执行 | PASS |
| Integration Tests | 没有独立 integration test suite | BLOCKED / TEST_GAP |
| 并发创建 Vendor Bill | 未发现并发测试，未执行正式并发验证 | BLOCKED / TEST_GAP |
| Stale Worker / Queue-Job | 没有正式 stale-worker 测试 | BLOCKED / TEST_GAP |
| Transaction rollback | `test_bill_and_task_roll_back_when_attachment_copy_fails` | PASS |
| ACL / Record Rule | 仅有 non-reviewer 单项测试，无完整矩阵 | BLOCKED / TEST_GAP |
| Multi-company 隔离 | 未发现正式测试 | BLOCKED / TEST_GAP |
| Secret 泄漏 | 临时 `fields_get` 探针显示非配置用户 RPC 字段不可见；无正式测试 | BLOCKED / TEST_GAP |
| Bill Creator 幂等 | 顺序重复调用测试通过 | PASS，真实并发仍未验证 |
| `verify.py` | 执行但因缺少 `addons/wd_tlms/views` 崩溃 | BLOCKED_BY_ENV |

---

# 7. Defect 分类清单

## A. IMPLEMENTATION_DEFECT

### CL-DEF-A-001：AI 重跑清空人工复核结果

- 文件：`parse_service.py`
- 位置：`start_parse`
- 当前行为：

```python
"human_review_result": {},
```

- 基线：DDD 明确要求 AI 重跑后保留旧 `human_review_result`，只将 `human_reviewed=False`。
- 影响：重跑会删除人工已确认的数据，违反 SRS-4.1.4、SRS-9.3、DDD HumanReviewResult 契约、T-009。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`，本 Closure 不修复。

### CL-DEF-A-002：Timeout 未检查 AI 内部重试是否耗尽

- 文件：`timeout_service.py`
- 当前行为：只判断 task 是否超时、attempt 是否 queued/running，没有结合 `attempt_internal_retry_count` 与 provider `max_internal_retry`。
- 基线：SRS-4.1.7a 要求 retry 未耗尽前不触发超时。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`。

### CL-DEF-A-003：Adapter 未执行 Canonical Schema 校验与归一化

- 文件：`base.py`
- 当前行为：`_canonical()` 只判断返回对象是否为 dict。
- 基线：DDD/TDD 要求 adapter 输出前完成 schema 校验、字段类型归一化。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`。

### CL-DEF-A-004：人工复核 UI 不具备完整编辑/应用候选功能

- 文件：`review_dialog.xml`
- 当前行为：主要使用 `<pre>` 展示 JSON，没有完整字段编辑，也没有“应用 AI 候选但不覆盖人工编辑”的交互。
- 基线：SRS-4.3、DDD UI 契约。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`。

### CL-DEF-A-005：复核保存未清理/重新计算 review warnings

- 文件：`import_task.py`
- 当前 `action_save_review` 只写入 `human_review_result` 和 `human_reviewed`，没有按 DDD `submit_review` 契约清空并重算 `review_warnings`。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`。

### CL-DEF-A-006：账单明细非法金额被静默转换为 0

- 文件：`bill_creator.py`
- `_number()` 对非法金额返回默认值，而不是显式阻断。
- 影响：可能生成错误账单数据。
- 分类：`A. IMPLEMENTATION_DEFECT`
- 处理建议：新建独立 `FIX-INTENT`。

## B. TEST_GAP

### CL-DEF-B-001：缺少真实并发 bill 生成测试

- 影响 GATE-10、T-005、T-015。
- 顺序幂等测试不能证明 `SELECT FOR UPDATE` 在两个事务竞争下只产生一个 bill。

### CL-DEF-B-002：缺少 stale-worker runtime 测试

- 影响 GATE-07、T-004。
- 当前只有代码分支，没有真实旧 worker 回写验证。

### CL-DEF-B-003：缺少 multi-company worker 隔离测试

- 影响 GATE-09、T-025、T-027。
- 只有单公司/字段级测试。

### CL-DEF-B-004：缺少完整 ACL / Record Rule 权限矩阵测试

- 当前只测试一个 non-reviewer 场景。
- 未覆盖 User、Reviewer、Config Manager 对全部模型的矩阵。

### CL-DEF-B-005：缺少 provider secret 泄漏正式测试

- 临时 `fields_get` 探针显示普通用户 RPC 字段不可见；
- 但没有正式测试日志、异常、RPC 返回、raw attachment 权限。

### CL-DEF-B-006：缺少 Adapter 异常与 retry 行为测试

- 无正式 DeepSeek/Claude HTTP mock 测试；
- 无临时错误、永久错误、retry count 的正式测试。

### CL-DEF-B-007：缺少 parse_service / mapping_service 集成测试

- 当前 44 项测试没有覆盖完整 AI 成功、失败、superseded、mapping 回写链路。

### CL-DEF-B-008：缺少 Owl contract test

- 未测试人工编辑不被 AI 重跑覆盖；
- 未测试应用候选交互。

### CL-DEF-B-009：缺少独立 Integration Test suite

- 当前测试只有 `test_models.py` 和 `test_intent3_services.py`；
- 没有明确的 integration/concurrency/security 测试文件。

### CL-DEF-B-010：缺少正式 GATE-01~GATE-15 verify 实现

- 当前 `execution/scripts/verify.py` 面向 `wd_tlms`，不是 `ai_vendor_invoice`；
- 不能作为本模块 GATE 关闭依据。

## C. DOCUMENTATION_DRIFT

### CL-DEF-C-001：SRS 与 TDD/Coding Contract 对 OCA 依赖存在冲突

- SRS-3、SRS-4.5.1、SRS-7.5、SRS-9.19 要求或假设 `account_invoice_import`；
- TDD T-016 和 Coding Contract GATE-01 明确禁止运行时依赖；
- 当前 manifest 未依赖 `account_invoice_import`，数据库中该模块也不存在。
- 子分类：`C-AMBIGUOUS`
- 处理：必须人工确认冻结基线优先级或重新冻结文档。
- 后续处理：DOC-INTENT-AI-VENDOR-003 已选择方案 A，输出 SRS v1.3.4；
  本文档中的冲突项已按勘误后的基线更新为 PASS。

## D. NEW_REQUIREMENT

当前没有发现必须归档的新增业务需求。用户要求的 Closure 审计、矩阵和分类本身属于当前 Intent 范围，不计入产品需求。

## E. OPTIMIZATION

### CL-DEF-E-001：配置视图和服务层边界可进一步统一

当前功能性阻塞项解决后，可单独建立 hardening intent 改善：

- 配置视图完整性；
- adapter/provider 注册机制；
- bill creator 数据转换的重复/错误处理；
- 测试 fixture 复用。

---

# 8. Environment Blockers

## ENV-BLOCK-001：verify.py 与当前仓库不匹配

- 执行脚本：`execution/scripts/verify.py`
- 脚本固定扫描：

```text
addons/wd_tlms/models
addons/wd_tlms/views
```

- 当前仓库没有：

```text
addons/wd_tlms/views
```

- 结果：脚本在 XML 检查阶段 `FileNotFoundError`，无法输出 GATE-01~GATE-15。
- 分类：`BLOCKED_BY_ENV`
- 影响：Closure 不能判定为 PASS。

## 非阻塞环境信息

- Odoo、PostgreSQL、queue_job 均可运行；
- `ai_vendor_invoice` 模块升级和 44 项测试均成功；
- `wd_tlms`、`worlddepot` 在数据库加载时有既有警告，但没有阻止本模块测试。

---

# 9. 代码质量审阅清单

以下仅报告，不修改代码。

| File | Issue | Severity | Recommendation |
|---|---|---:|---|
| `services/timeout_service.py` | timeout 未区分 retry 未耗尽状态 | HIGH | 新 Fix Intent 修正超时分层 |
| `services/parse_service.py` | 重跑清空人工复核结果 | HIGH | 新 Fix Intent 保留旧结果 |
| `adapters/base.py` | 未执行 JSON Schema 校验和归一化 | HIGH | 新 Fix Intent 增加 adapter 校验链 |
| `services/bill_creator.py` | 非法金额静默转为 0 | HIGH | 改为显式 ValidationError |
| `static/src/owl/review_dialog.xml` | JSON `<pre>` 展示代替完整编辑表单 | HIGH | 新 UI Fix Intent |
| `models/import_task.py` | `action_save_review` 未重算 review warnings | MED | 统一复核服务逻辑 |
| `services/validation_service.py` | `company` 参数未使用 | LOW | 后续清理或补充币种金额校验 |
| `services/mapping_service.py` | 无独立服务集成测试 | MED | 新 Test Intent |
| `security/` | 未见专门 raw response attachment ACL/rule | HIGH | 新安全 Fix/Test Intent |
| `tests/` | 缺少并发、stale、multi-company、secret、完整权限矩阵 | HIGH | 新 Test Intent |
| `execution/scripts/verify.py` | 验证脚本指向另一模块 | HIGH | 新治理/验证脚本 Intent |
| `tests/test_intent3_services.py` | 主要使用共享数据库 fixture，缺少隔离并发事务 fixture | MED | 新 Test Intent |

---

# 10. 最终 Closure 结论

## `CLOSURE_BLOCKED`

阻塞项：

```text
CL-DEF-A-001  AI 重跑清空 human_review_result
CL-DEF-A-002  timeout 未检查 retry 是否耗尽
CL-DEF-A-003  adapter 未执行 schema 校验/归一化
CL-DEF-A-004  复核 UI 缺少完整编辑及应用候选能力
CL-DEF-A-005  复核保存未重新计算 review_warnings
CL-DEF-A-006  非法金额可能静默转成 0

CL-DEF-B-001  缺少并发 bill 测试
CL-DEF-B-002  缺少 stale-worker 测试
CL-DEF-B-003  缺少 multi-company 测试
CL-DEF-B-004  缺少完整权限矩阵测试
CL-DEF-B-005  缺少 secret leakage 正式测试
CL-DEF-B-006  缺少 adapter 异常/retry 测试
CL-DEF-B-007  缺少 parse/mapping 集成测试
CL-DEF-B-008  缺少 Owl contract test
CL-DEF-B-009  缺少独立 Integration Test suite
CL-DEF-B-010  现有 verify.py 不能验证本模块

CL-DEF-C-001  SRS 与 TDD/Coding Contract 对 account_invoice_import 存在未闭环冲突

ENV-BLOCK-001  verify.py 因缺少 addons/wd_tlms/views 崩溃
```

虽然当前 Odoo 模块升级和 44 项正式测试结果为：

```text
0 failed, 0 error(s)
```

但按照 Closure 的冻结规则：

- 存在 A 类实现缺陷；
- 存在阻塞性正式测试缺口；
- 存在未解决 C-AMBIGUOUS 文档漂移；
- 存在 verify 环境/脚本阻塞；

因此不能输出 `CLOSURE_PASS`。

后续应分别创建独立的：

1. `FIX-INTENT`：修复实现缺陷；
2. `TEST-INTENT`：补齐并发、stale-worker、权限、multi-company、secret、adapter、mapping、Owl 测试；
3. 文档勘误/重新冻结 Intent：解决 `account_invoice_import` 依赖冲突；
4. 验证脚本修复 Intent：使 `verify.py` 针对 `ai_vendor_invoice` 执行 GATE-01~GATE-15。

本 Closure 阶段未自行修复任何问题，符合“只审计、不 Fix、不新增正式测试”的约束。

---

## DOC-INTENT-AI-VENDOR-003 基线更新

DOC-INTENT 已完成方案 A 的文档勘误与重新冻结：

- 新基线：[spec_wd_ai_vendor_invoice_1.3.4.md](../context/requirements/spec_wd_ai_vendor_invoice_1.3.4.md)
- 原 `spec_wd_ai_vendor_invoice_1.3.3.md` 保留为历史冻结版本；
- SRS-4.5.1、SRS-9.19、T-016、GATE-01 已按 v1.3.4 重新对齐；
- `account_invoice_import` 不再是本模块运行时依赖；
- TDD v1.4.2、DDD v1.2、Coding Contract 未修改；
- Closure 原有 A/B 类实现与测试阻塞项不因本次文档勘误自动关闭。