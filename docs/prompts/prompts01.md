# Codex任务提示词：SPIKE‑OCA‑001 Spike探查
## 任务目标
执行SPIKE‑OCA‑001，范围严格收窄：仅回答OCA `account_invoice_import` 哪些能力可以安全复用，判断是否需要依赖该模块，**不做模块重设计、不开发业务功能**。

## 探查基线固定
- Repository: OCA/edi
- Branch: 18.0
- Module: account_invoice_import
- Manifest版本：18.0.1.2.0
- 务必记录实际Commit SHA，报告中写明本次探查锁定commit
- License: AGPL‑3
- 直接依赖：account、base_iban、base_business_document_import
- **优先以本地已 checkout 的 OCA/edi 代码为唯一事实来源；不得自行切换分支、pull 最新代码、改用远程其他 commit。**

## 需要完成工作项
1. 解析完整依赖树：account_invoice_import → base_business_document_import → 下层依赖，评估为拿到少量能力引入整套模块的代价。
2. 梳理完整账单创建调用链，标注每一段：✅可复用 / ⚠️仅参考不可调用 / ❌禁止调用。
> Upload file → Wizard → parse file → business document import → partner matching → prepare invoice data → create/update account.move → post processing
3. 全量搜索源码中：
`env["account.move"].create`、`invoice_vals`、`move_vals`、`_create_invoice`、`_prepare_invoice`、`_invoice_import_*`、`create_invoice`、`_prepare_create_invoice_vals`、`_post_process_invoice`、`post_create_or_update`、`_match_partner`、`_match_product`、`_match_taxes`、`_match_currency`、`map_tax`、`map_account`。
    - A：寻找无wizard上下文、不依赖文件解析、接收稳定结构化入参的独立helper；
    - B：识别外表可用、实际强依赖wizard上下文/解析schema/OCA mapping的私有方法；
    - C：判断是否不存在合格可直接调用helper。
4. 输出复用矩阵，每一项结论落到 USE / REFERENCE ONLY / DO NOT USE。
| OCA能力 | 本模块需要？ | 可以安全复用？ | 最终决策 |
|---|---|---|---|
| PDF上传 | | | |
| ir.attachment处理 | | | |
| PDF/XML parser | | | |
| invoice2data/template | | | |
| Partner自动匹配 | | | |
| Product匹配 | | | |
| Tax匹配 | | | |
| Currency匹配 | | | |
| invoice vals组装 | | | |
| account.move创建 | | | |
| Import warning机制 | | | |
| 权限 | | | |
| 日志 | | | |
5. 区分能力归属：能力属于`account_invoice_import`还是底层`base_business_document_import`，评估是否仅需要下层模块。
6. 识别所有候选helper副作用，重点检查：是否内部自动执行partner/tax/product/currency匹配、是否触发Fiscal Position重映射；**不得重新覆盖人工已确认的 supplier / currency / product / tax 等业务选择；对 account_id、Fiscal Position 等 Odoo 会计派生行为必须识别并说明副作用。**
7. 最小PoC验证（Odoo18测试环境）
测试数据：Supplier已存在，Invoice号TEST‑001，EUR，1行，Freight产品，21%税，金额100。
- 路径A：候选OCA helper（如果找到）；**如果源码分析已经证明不存在满足条件的独立 helper，路径A允许标记 N/A，不得为了完成PoC强行调用不适合的私有方法。**
校验move_type、partner、currency、invoice_date、ref、行数据、tax_ids；确认不会自动post、不会偷偷跑parser/mapping。
- 路径B：原生`account.move.create()`，同样输入构造bill_vals生成草稿账单。
对比两条路径收益差异。
8. 附件能力核查：确认OCA有无值得复用附件helper；**若无专用附件 helper，验证 Odoo 18 原生 `ir.attachment.copy()` 是否足够；不要为了附件能力单独保留 `account_invoice_import` 依赖。**
9. 原生`account.move.create()`后，**仅验证与本Spike相关的字段和副作用，不扩展为Odoo会计引擎全面研究**：partner/product/account/tax/currency/金额/fiscal position实际运算结果。
10. Fiscal Position风险专项：调用OCA逻辑会不会覆盖人工选择tax，把副作用明确写入报告。

## 三选一最终决策
- A：强复用，保留硬依赖，列出可用方法、禁止调用清单
- B：有限复用，保留依赖，账单创建使用原生`account.move.create()`
- C：不值得硬依赖，移除account_invoice_import依赖，全部走原生Odoo ORM

> **判定原则：若所谓“可复用能力”只是私有 helper、需要构造 OCA `parsed_inv/import_config`、依赖 wizard/context、会再次执行 mapping 或 post‑process，则不得以“减少少量代码”为理由保留硬依赖。**

## Spike输出报告结构（必须严格按此章节输出）
1. 探查基线（repo/branch/commit/module版本/依赖）
2. 代码调用链与标记 ✅ ⚠️ ❌
3. 候选复用点清单：类、方法、入参出参、副作用、稳定性
4. 禁止复用点清单
5. PoC验证结果（OCA路径 / native路径对比）
6. 最终决策 A/B/C
7. TDD回填清单：manifest depends、Bill Creator调用方式、附件实现、禁止调用列表
8. Spike结论 PASS / CHANGE_REQUIRED

## Spike验收必须回答4个核心问题
1. OCA 18是否存在适合直接调用的Vendor Bill创建helper？
2. 调用会不会触发OCA解析/匹配/Fiscal Position逻辑，破坏HumanReviewResult唯一数据源？
3. 不使用OCA helper，直接`account.move.create()`是否足够？
4. `account_invoice_import`是否值得作为wd_ai_vendor_invoice硬依赖？

## 文件输出位置
报告输出文件路径：`mymodules/tk_freight/docs/spike/SPIKE‑OCA‑001.md`
1. 若目录 `mymodules/tk_freight/docs/spike` 不存在，自动创建目录。
2. 完成报告写入后，更新 `docs/context/README.md`，在Spike索引部分登记 SPIKE‑OCA‑001 条目（标题、状态、文件链接）。

## 硬性约束
1. 范围收窄，**不做模块重设计，不开发业务代码**，产出为spike分析报告。
2. 禁止脑补源码行为，全部基于本地OCA/edi 18.0分支真实代码。
3. 不能回避C方案，“不值得依赖”是合法spike结论。
4. Spike执行期间禁止：
    - 修改 OCA/edi 源码；
    - 修改 wd_ai_vendor_invoice 正式代码；
    - 修改 SRS / DDD；
    - 根据 Spike 结论直接修改 TDD；
    - 提交业务实现代码。
  允许：
    - 创建临时测试/PoC代码；
    - 创建 Spike 报告；
    - 如需临时测试文件，必须明确标记为 spike‑only，不进入正式模块实现。
```

