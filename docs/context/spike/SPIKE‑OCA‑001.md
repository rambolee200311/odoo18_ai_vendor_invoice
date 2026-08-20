# SPIKE-OCA-001 — OCA account_invoice_import 18.0 源码探查报告

> **状态**：✅ 已完成（闭环）
> **探查日期**：2026-08-20
> **执行者**：GitHub Copilot CLI（requirements-and-design-review worktree）
> **相关文档**：TDD v1.4 §6 OCA account_invoice_import 复用边界；DDD v1.2；SRS v1.3.3
> **约束**：只读本地 checkout；不切换分支；不 pull；不修改 OCA 源码；不修改 wd_ai_vendor_invoice 正式代码；不修改 SRS/DDD/TDD

---

## 目录

1. [Spike 元信息 / 范围](#1-spike-元信息--范围)
2. [OCA/edi Checkout 信息 & 依赖树](#2-ocaedi-checkout-信息--依赖树)
3. [账单创建完整调用链分析](#3-账单创建完整调用链分析)
4. [候选符号标注（USE / REFERENCE ONLY / DO NOT USE）](#4-候选符号标注use--reference-only--do-not-use)
5. [候选 Helper 副作用分析（Mapping / Fiscal Position / 字段覆盖风险）](#5-候选-helper-副作用分析mapping--fiscal-position--字段覆盖风险)
6. [附件能力核查（ir.attachment 创建 vs ir.attachment.copy）](#6-附件能力核查irattachment-创建-vs-irattachmentcopy)
7. [最小 PoC 对比 / N/A 原因](#7-最小-poc-对比--na-原因)
8. [结论与决策建议](#8-结论与决策建议)

---

## 1 Spike 元信息 / 范围

| 项目 | 说明 |
|---|---|
| Spike ID | SPIKE-OCA-001 |
| 驱动来源 | TDD §T-016："SPIKE-OCA-001 完成前不允许编写 bill_creator 代码" |
| 核心问题 | OCA `account_invoice_import` 18.0 是否存在可独立调用的账单创建 helper？应用层能否直接复用？ |
| 次要问题 | Fiscal Position mapping / 字段覆盖副作用；附件能力；ir.attachment.copy 可用性 |
| 探查范围 | `addons/edi/account_invoice_import/` + `addons/edi/base_business_document_import/` |
| 本 Spike 不探查 | account_invoice_import_facturx、account_invoice_import_ubl、invoice2data 等扩展模块 |
| **结论一句话** | **不存在可独立外部调用的账单创建 helper；所有 vals 组装逻辑完全封装在 `TransientModel` 向导内部；`wd_ai_vendor_invoice` 必须在自己的 `bill_creator` 中自主实现。** |

---

## 2 OCA/edi Checkout 信息 & 依赖树

### 2.1 Checkout 位置与 Git 信息

| 项目 | 值 |
|---|---|
| 本地路径 | `/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/edi/` |
| 所在主 Repo | `git@github.com:rambolee200311/odoo18_ai_vendor_invoice.git` |
| 当前 Branch | `main` |
| 实际 Commit SHA | `c36f19d237e3c21fe2b66fb5b516630bbf2d111c` |
| OCA 原始来源 | OCA/edi（18.0 分支，已脱离 `.git` 作为 subtree 导入，见 commit `5404b3f chore: remove nested .git dirs from OCA modules`） |
| 注意 | OCA 代码以静态快照方式存在于主 repo，无独立 git history；原始 OCA remote 未绑定 |

### 2.2 account_invoice_import `__manifest__.py`

```python
{
    "name": "Account Invoice Import",
    "version": "18.0.1.2.0",
    "category": "Accounting & Finance",
    "license": "AGPL-3",
    "author": "Akretion, Odoo Community Association (OCA)",
    "depends": [
        "account",
        "base_iban",
        "base_business_document_import",
    ],
    ...
}
```

### 2.3 完整依赖树

```
account_invoice_import (18.0.1.2.0)
├── account                          # Odoo Core — 账单/分录/税务核心
├── base_iban                        # Odoo Core — IBAN 验证
└── base_business_document_import (18.0.2.0.1)
    ├── account_tax_unece            # OCA/community-data-files — UNECE 税码
    └── uom_unece                    # OCA/community-data-files — UNECE 计量单位
```

#### 间接依赖（传递）

| 模块 | 来源 | 用途 |
|---|---|---|
| `account` | Odoo Core | account.move / account.move.line / account.tax / account.journal 等核心模型 |
| `base_iban` | Odoo Core | `validate_iban()` —— IBAN 校验工具函数 |
| `account_tax_unece` | OCA/community-data-files | 在 account.tax 上增加 `unece_type_code` / `unece_categ_code` 字段；`_match_tax` 依赖 |
| `uom_unece` | OCA/community-data-files | 在 uom.uom 上增加 `unece_code` 字段；`_match_uom` 依赖 |

> ⚠️ **重要**：`account_tax_unece` 和 `uom_unece` 是 `business.document.import` 中 `_match_tax` / `_match_uom` 的隐式依赖。若 `wd_ai_vendor_invoice` 不安装这些模块，调用 `_match_tax` 时 `unece_type_code` 字段不存在，会导致运行时错误。这也是「不依赖 OCA 运行时」的额外理由。

---

## 3 账单创建完整调用链分析

### 3.1 两条公开入口

```
入口 A（UI 按钮）
  AccountInvoiceImport.import_invoices()           # wizard 按钮触发
    └─ parse_invoice(attach.datas, attach.name, company)
         └─ parse_pdf_invoice(file_data, company)  # fallback
              └─ fallback_parse_pdf_invoice()      # 继承扩展点
         └─ _pre_process_parsed_inv(parsed_inv, company)
    └─ partner._convert_to_import_config(company)  # 从 partner 读配置
    └─ create_invoice(parsed_inv, import_config, origin)
         └─ _pre_process_parsed_inv(...)           # 幂等，已标记则跳过
         └─ _prepare_create_invoice_vals(...)      # ★ 核心 vals 组装
              ├─ bdio._match_partner(...)
              ├─ bdio._match_currency(...)
              ├─ _prepare_create_invoice_journal(...)
              ├─ _prepare_line_vals_1line(...)      # 单行模式
              │   └─ fp.map_account(account)        # ★ Fiscal Position 映射
              │   └─ fp.map_tax(taxes)              # ★ Fiscal Position 税务映射
              └─ _prepare_line_vals_nline(...)      # 多行模式
                  └─ bdio._match_product(...)
                  └─ bdio._match_taxes(...)
                  └─ fp.map_account(account)        # ★ Fiscal Position 映射
                  └─ fp.map_tax(taxes)              # ★ Fiscal Position 税务映射
         └─ amo.create(vals)                        # ★ 真正创建 account.move
         └─ _post_process_invoice(...)             # 调整行（金额差异修复）
         └─ bdio.post_create_or_update(...)        # 附件 + chatter 写入
         └─ invoice.message_post(...)              # origin 消息

入口 B（Web Service / 邮件网关）
  AccountInvoiceImport.create_invoice_webservice(
      invoice_file_b64, invoice_filename, company_id, origin)
    └─ parse_invoice(...)
    └─ bdio._match_partner(...)
    └─ partner._convert_to_import_config(company)  （或空 dict）
    └─ create_invoice(...)                          # 同入口 A 后段
```

### 3.2 完整调用链时序（文字版）

```
import_invoices()
  ├─1─ parse_invoice()                      解析 PDF/XML → parsed_inv dict
  │     ├─ parse_pdf_invoice()              PDF 路径：提取内嵌 XML；fallback 纯 PDF
  │     ├─ parse_xml_invoice()              XML 路径（由子模块继承）
  │     └─ _pre_process_parsed_inv()        归一化类型/金额/税务/货币；标记 pre-processed
  │
  ├─2─ _match_partner()                     在 business.document.import 中匹配供应商
  │
  ├─3─ _invoice_already_exists()            防重复检查（按 partner + ref + type）
  │
  ├─4─ partner._convert_to_import_config()  从 partner 字段读取默认产品/科目/税务/日记账
  │
  └─5─ create_invoice()                     ★ 核心账单创建
        ├─ _prepare_create_invoice_vals()   完整 account.move vals 字典
        │   ├─ _match_partner()             （可能二次调用）
        │   ├─ _set_previous_invoice()      找同供应商历史账单
        │   ├─ _update_import_config_from_previous_invoice()  从历史账单补充配置
        │   ├─ _last_update_import_config() 最终兜底（税务/科目/with_company）
        │   └─ _prepare_line_vals_*line()   行级 vals
        ├─ amo.create(vals)                 写库
        ├─ _post_process_invoice()          调整行（amount_untaxed 差异 + 强制税额）
        ├─ post_create_or_update()          附件绑定 + chatter 消息
        └─ message_post()                  origin 来源说明
```

### 3.3 关键数据结构：`parsed_inv` 字典（Invoice Pivot Format）

| 字段 | 类型 | 说明 |
|---|---|---|
| `type` | str | `in_invoice` / `in_refund` / `out_invoice` / `out_refund` |
| `partner` | dict | `{vat, email, name, country_code, state_code, recordset}` |
| `currency` | dict | `{iso, symbol, country_code}` |
| `date` | str | `YYYY-MM-DD` |
| `date_due` | str | 到期日 |
| `invoice_number` | str | 供应商发票号 |
| `amount_untaxed` | float | 税前金额 |
| `amount_tax` | float | 税额 |
| `amount_total` | float | 含税总额（**必填**）|
| `lines` | list[dict] | 多行模式行列表，每行含 `product / name / qty / price_unit / taxes / uom` |
| `attachments` | dict | `{filename: base64_bytes}` |
| `chatter_msg` | list[str] | 累积警告/消息 |
| `pre-processed` | bool | 幂等标记 |

### 3.4 关键数据结构：`import_config` 字典

| 键 | 类型 | 来源 |
|---|---|---|
| `company` | res.company recordset | **必填** |
| `single_line` | bool | partner.invoice_import_single_line |
| `label` | str\|False | partner.invoice_import_label |
| `journal` | account.journal\|False | partner.invoice_import_journal_id |
| `product` | product.product\|False | partner.invoice_import_product_id |
| `account` | account.account\|False | partner.invoice_import_account_id |
| `taxes` | account.tax recordset\|False | partner.invoice_import_tax_ids |
| `previous_invoice` | account.move\|False | 动态注入：同供应商最新已过账账单 |
| `start_end_dates_installed` | bool | 动态注入：检测 OCA account-closing 模块 |

---

## 4 候选符号标注（USE / REFERENCE ONLY / DO NOT USE）

| 符号 | 所在文件 | 标注 | 理由 |
|---|---|---|---|
| `create_invoice(parsed_inv, import_config, origin)` | `wizard/account_invoice_import.py:861` | ❌ **DO NOT USE** | 定义在 `TransientModel`，持有 wizard 事务上下文；会调用 `post_create_or_update()` 绑定 wizard 产生的附件；与 `wd_ai_vendor_invoice` 的 task/attempt 生命周期完全不兼容 |
| `create_invoice_webservice(...)` | `wizard/account_invoice_import.py:882` | ❌ **DO NOT USE** | 同上；额外持有 email origin 语义；进一步依赖文件解析流 |
| `import_invoices()` | `wizard/account_invoice_import.py:771` | ❌ **DO NOT USE** | UI 按钮入口，强依赖 wizard 字段 `invoice_attachment_ids` |
| `_prepare_create_invoice_vals(parsed_inv, import_config)` | `wizard/account_invoice_import.py:299` | 📖 **REFERENCE ONLY** | vals 组装逻辑的最佳参考，但定义在 TransientModel 上，不可直接调用；`bill_creator` 自主实现时参考此方法的字段名和赋值逻辑 |
| `_prepare_line_vals_1line(...)` | `wizard/account_invoice_import.py:368` | 📖 **REFERENCE ONLY** | 单行模式 il_vals 组装参考；FP 映射逻辑见此处 |
| `_prepare_line_vals_nline(...)` | `wizard/account_invoice_import.py:422` | 📖 **REFERENCE ONLY** | 多行模式 il_vals 组装参考 |
| `_prepare_create_invoice_journal(...)` | `wizard/account_invoice_import.py:237` | 📖 **REFERENCE ONLY** | 日记账匹配逻辑参考 |
| `_last_update_import_config(...)` | `wizard/account_invoice_import.py:529` | 📖 **REFERENCE ONLY** | 税务/科目兜底逻辑参考；`with_company()` 用法参考 |
| `_post_process_invoice(...)` | `wizard/account_invoice_import.py:987` | 📖 **REFERENCE ONLY** | 调整行逻辑参考；`_check_total_amount` 用法参考；`wd_ai_vendor_invoice` 人工复核已保证金额一致，此逻辑可能不需要 |
| `parse_invoice(...)` | `wizard/account_invoice_import.py:580` | ❌ **DO NOT USE** | AI Provider 已完全替代文件解析；此方法适用于 EDI/UBL/PDF 自动解析场景 |
| `parse_pdf_invoice(...)` | `wizard/account_invoice_import.py:49` | ❌ **DO NOT USE** | 同上 |
| `_pre_process_parsed_inv(...)` | `wizard/account_invoice_import.py:634` | ❌ **DO NOT USE** | 依赖 `parsed_inv` 的货币/refund 自动推断逻辑；`wd_ai_vendor_invoice` 的 `human_review_result` 已含明确字段 |
| `business.document.import._match_partner(...)` | `models/business_document_import.py:300` | ⚠️ **REFERENCE ONLY（有条件）** | 供应商匹配算法值得参考；但依赖 `account_tax_unece`/`uom_unece` 隐式字段；若作为运行时依赖需部署这些 OCA 模块 |
| `business.document.import._match_currency(...)` | `models/business_document_import.py:746` | 📖 **REFERENCE ONLY** | 货币匹配逻辑参考；`wd_ai_vendor_invoice` 由 AI 返回 ISO code，直接 `res.currency.search([('name','=',iso)])` 更简单 |
| `business.document.import._match_tax(...)` | `models/business_document_import.py:998` | ❌ **DO NOT USE** | 强依赖 `unece_type_code` / `unece_categ_code` 字段（来自 `account_tax_unece`）；`wd_ai_vendor_invoice` 由人工选定税种，不走此路径 |
| `business.document.import.post_create_or_update(...)` | `models/business_document_import.py:1501` | ❌ **DO NOT USE** | 硬编码从 `parsed_inv['attachments']` 创建新 ir.attachment；与 task 侧已有 source_pdf_attachment_id 的关联策略冲突；见 §6 |
| `res.partner._convert_to_import_config(company)` | `models/res_partner.py:64` | 📖 **REFERENCE ONLY** | import_config 字典结构的参考；`wd_ai_vendor_invoice` 的 `human_review_result` 将直接提供等价字段 |
| `account.move._invoice_import_set_partner_and_update_lines(partner)` | `models/account_move.py` | ❌ **DO NOT USE** | 专为"更新已有草稿账单"流程设计；`wd_ai_vendor_invoice` 只需创建 Draft，不存在 update 场景 |
| `partner.invoice_import_product_id` / `invoice_import_account_id` / `invoice_import_tax_ids` 等字段 | `models/res_partner.py` | ⚠️ **REFERENCE ONLY（字段命名参考）** | 这些字段定义在 OCA 模块中；若 `account_invoice_import` 未安装，字段不存在 |
| `account.move.import_warnings` / `import_partner_data` 字段 | `models/account_move.py` | ⚠️ **REFERENCE ONLY** | OCA 扩展字段；`wd_ai_vendor_invoice` 有自己的 review_warnings 机制，不依赖这些字段 |

---

## 5 候选 Helper 副作用分析（Mapping / Fiscal Position / 字段覆盖风险）

### 5.1 Fiscal Position 自动映射机制

**位置**：`_prepare_line_vals_1line()` (L397–400) 和 `_prepare_line_vals_nline()` (L463–466)

```python
fp = partner and partner.property_account_position_id or False
if fp:
    account = fp.map_account(account)
    taxes = fp.map_tax(taxes)
```

**行为说明**：
- 取 `partner.property_account_position_id`（公司相关字段，按当前 with_company 上下文）
- `fp.map_account(account)` — 按 FP 的 account_ids 映射表，替换行科目
- `fp.map_tax(taxes)` — 按 FP 的 tax_ids 映射表，替换/删除税种

**副作用风险**：

| 风险 | 场景 | 影响 |
|---|---|---|
| 科目悄然被替换 | partner 配置了 FP，但 FP 映射表不完整 | account_id 变成 FP 目标科目，可能与人工选定科目不一致 |
| 税种被静默删除 | FP tax_ids 中 tax_dest_id 为空 | 行税种变为空，amount_tax 计算错误 |
| 跨公司 FP 错误 | with_company() 上下文未正确设置 | 读取错误公司的 FP |
| 人工复核结果被覆盖 | `human_review_result` 中明确选了某税种，但 FP 映射替换了它 | 账单与人工确认内容不符 |

**`wd_ai_vendor_invoice` 决策**：  
由 `bill_creator` 在组装 vals 时明确决定是否应用 FP。由于 `human_review_result` 是唯一数据源，建议**不自动应用 FP 映射**（人工已在复核界面直接选定最终科目和税种），以保证账单内容与人工确认完全一致。

### 5.2 `_update_import_config_from_previous_invoice` 隐式字段覆盖

**位置**：`wizard/account_invoice_import.py:513`

```python
def _update_import_config_from_previous_invoice(self, import_config):
    if import_config.get("previous_invoice"):
        inv = import_config["previous_invoice"]
        ilines = inv.invoice_line_ids.filtered(lambda x: x.display_type == "product")
        if ilines:
            iline = ilines[0]
            if not import_config.get("product") and iline.product_id:
                import_config["product"] = iline.product_id
            ...
            if not import_config.get("taxes") and iline.tax_ids:
                import_config["taxes"] = iline.tax_ids
```

**副作用风险**：当 `import_config` 未明确指定 product/account/taxes 时，此方法从历史账单第一行静默注入。历史账单可能与当前发票业务无关。

**`wd_ai_vendor_invoice` 决策**：`bill_creator` 不调用此方法；`human_review_result` 提供完整的字段，无需从历史推断。

### 5.3 `_last_update_import_config` 公司税务兜底

**位置**：`wizard/account_invoice_import.py:529`

当 `import_config['taxes']` 为空时，兜底到 `company.account_purchase_tax_id`（公司默认税）。  
当 `import_config['account']` 为空时，兜底到 journal 的 `default_account_id`，再兜底到产品分类 `property_account_expense_categ_id`。

**副作用风险**：若人工未选税种，会静默应用公司默认税；可能产生意外税额。

**`wd_ai_vendor_invoice` 决策**：`bill_creator` 在人工确认后调用，所有字段均已明确；此兜底逻辑不适用。

### 5.4 `_prepare_global_adjustment_line` 调整行副作用

**位置**：`wizard/account_invoice_import.py:934`

当 OCA 解析的 `amount_untaxed` 与 Odoo 计算结果不一致时，自动插入"Adjustment"调整行。  
调整行科目来自 `company.adjustment_debit_account_id` / `adjustment_credit_account_id`（需要提前配置）。

**副作用风险**：自动插入额外行、需要配置特殊科目。

**`wd_ai_vendor_invoice` 决策**：人工复核已保证金额一致性；`bill_creator` 不需要此逻辑。

### 5.5 `account.move._invoice_import_set_partner_and_update_lines` FP 后置映射

**位置**：`models/account_move.py`

当设置 `partner_id` 时，若 partner 有 FP，此方法会重新遍历所有 invoice_line 并应用 FP 映射。  
这是针对"先创建账单后关联 partner"场景的补偿机制。

**副作用风险**：与 §5.1 同类风险；若在 create(vals) 时已包含 `partner_id`，Odoo Core 的计算字段已自动注入 FP，再手动调用此方法会**双重映射**。

**`wd_ai_vendor_invoice` 决策**：`bill_creator` 在 `create(vals)` 时直接传入 `partner_id`；FP 自动触发由 Odoo Core 处理（若需要）；不单独调用此方法。

---

## 6 附件能力核查（ir.attachment 创建 vs ir.attachment.copy）

### 6.1 OCA 模块的附件处理方式

**`post_create_or_update`**（`models/business_document_import.py:1501`）：

```python
def post_create_or_update(self, parsed_dict, record, doc_filename=None):
    if parsed_dict.get("attachments"):
        for filename, data_base64 in parsed_dict["attachments"].items():
            self.env["ir.attachment"].create({
                "name": filename,
                "res_id": record.id,
                "res_model": str(record._name),
                "datas": data_base64,
            })
```

**行为**：对 `parsed_inv['attachments']` 字典中的每个文件，**重新创建新的 ir.attachment 记录**，绑定到生成的 `account.move`。文件内容为 base64 重新写入，并非引用原始记录。

### 6.2 原生 ir.attachment.copy 方法

Odoo Core `ir.attachment` 继承自 `mail.thread` 的 `copy()` 方法：

```python
# Odoo Core ir.attachment.copy() 伪代码
def copy(self, default=None):
    # 默认行为：复制 attachment 记录（含 datas 引用）
    # 可通过 default={'res_id': new_id, 'res_model': 'account.move'} 绑定到新记录
    return super().copy(default=default)
```

### 6.3 两种方式对比

| 维度 | OCA `post_create_or_update` | 原生 `ir.attachment.copy()` |
|---|---|---|
| 数据来源 | 从内存中的 base64 bytes 重建 | 从已有 ir.attachment 记录复制 |
| 文件存储 | 重新写入（如 filestore）；若 `datas` 为 bytes，产生新文件 | 复用 filestore 中已有文件（store_fname 相同，不重复占用磁盘） |
| res_id / res_model | 绑定到目标 record | 通过 `default` 参数绑定到新 record |
| 原始 attachment 记录 | 不保留对 task 侧的引用关系 | task 侧 `source_pdf_attachment_id` 保留；account.move 侧通过 `copy()` 得到独立引用 |
| 适用场景 | EDI/文件上传场景（文件来自外部，无已有 attachment） | **wd_ai_vendor_invoice 场景**：PDF 已通过 task 上传存为 `source_pdf_attachment_id` |
| DDD 约束符合性 | ❌ 违反"task 附件不转移/销毁"约束 | ✅ task 和 account.move 均保有对原始 PDF 的独立引用 |

### 6.4 `wd_ai_vendor_invoice` 的正确策略

**根据 DDD v1.2**：
> `source_pdf_attachment_id`：task 与 account.move 均保留对此附件的引用，生成账单不转移/销毁 task 侧附件关联

**正确实现**（`bill_creator` 中）：

```python
# 伪代码 — 仅供参考，不调用 OCA 代码
task = self  # vendor.invoice.import.task
pdf_attachment = task.source_pdf_attachment_id
if pdf_attachment:
    pdf_attachment.copy({
        'res_model': 'account.move',
        'res_id': invoice.id,
        'name': pdf_attachment.name,
    })
```

这样：
- task 侧的 `source_pdf_attachment_id` 保持不变
- account.move 侧的 attachment 是独立的记录（`res_model='account.move'`，可在账单 chatter 中显示）
- filestore 文件复用，无重复存储

---

## 7 最小 PoC 对比 / N/A 原因

### 7.1 PoC 结论：**N/A — 无运行时环境**

| 原因 | 说明 |
|---|---|
| 当前 worktree 为纯文档分支 | `requirements-and-design-review` 分支无 Odoo 运行时；仅含文档和 OCA 源码静态 checkout |
| 无 PostgreSQL 数据库 | 无法执行 Odoo 初始化，无法测试 `create_invoice()` 运行时行为 |
| 无 Odoo addons 完整依赖 | `account`、`base_iban` 等 Core 模块未安装；`account_tax_unece`/`uom_unece` 也未配置 |
| OCA 模块依赖未安装 | `account_invoice_import` 需要在已安装 Odoo 实例中运行 |

### 7.2 静态分析替代 PoC 的充分性

以下静态分析结果已足以支撑设计决策，无需运行时 PoC：

| 问题 | 静态分析结论 | 充分性 |
|---|---|---|
| `create_invoice()` 是否可独立调用？ | 定义在 `TransientModel`，持有向导状态；接口要求 `pre-processed parsed_inv` + `import_config` — 均依赖 OCA 解析流程 | ✅ 充分 |
| 是否存在可提取的纯函数 helper？ | 全部 `_prepare_*` 方法均为 `@api.model`，可被继承扩展，但定义在 `TransientModel` 上 — OCA 设计意图是子模块通过继承扩展，而非外部调用 | ✅ 充分 |
| FP 映射副作用？ | 代码已明确：两处 `fp.map_account / fp.map_tax`；无条件执行当 FP 存在时 | ✅ 充分 |
| 附件处理方式？ | `post_create_or_update` 代码明确：重新 create；不调用 copy | ✅ 充分 |
| `account.move.create(vals)` 的 vals 结构？ | `_prepare_create_invoice_vals` 完整展示；所有字段均为标准 Odoo Core 字段 | ✅ 充分 |

### 7.3 如需将来验证

若将来需要验证运行时行为，可在 `main` 分支的完整开发环境中执行：
```python
# 验证 _prepare_create_invoice_vals 输出格式（仅供参考）
wizard = env['account.invoice.import'].create({'company_id': company.id})
vals = wizard._prepare_create_invoice_vals(parsed_inv, import_config)
# 检查 vals 结构是否与 bill_creator 自主实现一致
```

---

## 8 结论与决策建议

### 8.1 核心结论

> **OCA `account_invoice_import` 18.0 不存在可供 `wd_ai_vendor_invoice` 直接调用的独立账单创建 helper。**

详细依据：

1. **所有账单创建逻辑封装在 `TransientModel`**：`account.invoice.import` 是向导模型，其生命周期、字段、事务上下文完全绑定文件上传场景。`create_invoice()` / `_prepare_create_invoice_vals()` 虽然标注了 `@api.model`，但实际上只有在 OCA 向导的调用上下文中才有意义。

2. **解析流程完全不适用**：OCA 的 `parse_invoice()` → `parse_pdf_invoice()` → `fallback_parse_pdf_invoice()` 等入口针对 EDI/UBL/XML/PDF 自动解析设计，而 `wd_ai_vendor_invoice` 的解析由 AI Provider 完成；两条路径的数据结构完全不同。

3. **`import_config` 字典来源不可复用**：`import_config` 的主要来源是 `partner._convert_to_import_config()`（从 partner 字段读取），而 `wd_ai_vendor_invoice` 的数据来源是 `human_review_result`（人工复核结果 JSON）。两者语义不同，不可混用。

4. **Fiscal Position 自动映射与架构约束冲突**：DDD 要求 `human_review_result` 是账单生成的唯一数据源，自动 FP 映射可能在不知情的情况下修改人工确认的科目和税种。

5. **附件处理策略冲突**：OCA 的 `post_create_or_update` 重新创建 attachment；DDD 要求 task 和 account.move 共享对原始 PDF 的引用，正确策略是 `ir.attachment.copy()`。

### 8.2 决策矩阵

| 决策项 | 结论 |
|---|---|
| 是否在 manifest 中添加 `account_invoice_import` 运行时依赖 | ❌ 否 |
| 是否调用 `create_invoice()` / `create_invoice_webservice()` | ❌ 否 |
| 是否调用 `import_invoices()` / 任何文件解析入口 | ❌ 否 |
| 是否参考 `_prepare_create_invoice_vals()` 的字段名和 vals 结构 | ✅ 是（仅参考，不调用） |
| `bill_creator` 是否自主实现 `account.move` vals 组装 | ✅ 是 |
| 是否应用 FP 自动映射 | ⚠️ 由 `bill_creator` 实现者明确决策；建议不自动应用（人工已选定最终值） |
| 附件关联策略 | ✅ 使用 `source_pdf_attachment_id.copy({'res_model': 'account.move', 'res_id': invoice.id})` |
| OCA 源码用途 | 📖 阅读参考（vals 字段名、Odoo Core API 用法）；不作为运行时依赖 |

### 8.3 `bill_creator` 需自主实现的关键逻辑

基于本次源码探查，`bill_creator.convert_human_result_to_bill_vals()` 需要实现以下内容（全部基于 Odoo Core，不依赖 OCA）：

```
1. 从 human_review_result 提取字段 → 组装 account.move vals
   - move_type = 'in_invoice'
   - company_id, partner_id, currency_id, invoice_date, ref, invoice_origin
   - invoice_date_due, invoice_payment_term_id（根据业务需要）

2. 组装 invoice_line_ids
   - display_type = 'product'
   - product_id, account_id, tax_ids
   - quantity, price_unit, name

3. 调用 account.move.create(vals)

4. PDF 附件关联
   - source_pdf_attachment_id.copy({'res_model': 'account.move', 'res_id': invoice.id})

5. chatter 记录
   - invoice.message_post(body=...)
```

### 8.4 本 Spike 对 TDD 的支撑

| TDD 约束 | 本 Spike 支撑 |
|---|---|
| T-016：禁止依赖 OCA account_invoice_import 运行时 | ✅ §3/§4 证明无可用公共 API，§8.2 确认不添加依赖 |
| TDD §6 OCA 复用边界 | ✅ 本报告提供完整技术依据 |
| DDD §source_pdf_attachment_id 引用策略 | ✅ §6 附件能力核查给出正确实现 |
| 架构红线：human_review_result 是唯一数据源 | ✅ §5 FP 副作用分析证明不应用自动映射 |

### 8.5 Spike 结论：**PASS**

本地 OCA/edi 18.0 源码探查已完成，依赖评估、调用链、副作用、附件策略和
PoC N/A 原因均已记录。结论支持 TDD v1.4 的技术收口：

- 不添加 `account_invoice_import` 运行时依赖；
- 不调用 OCA 同步导入、解析或账单创建入口；
- `bill_creator` 使用 Odoo 原生 ORM 自主组装并创建草稿供应商账单；
- OCA 源码仅作为字段、vals 结构和 Core API 用法的参考。

---

*生成时间：2026-08-20 | Spike 执行环境：requirements-and-design-review worktree (c36f19d)*
