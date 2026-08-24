# DOC‑INTENT‑AI‑VENDOR‑003
## 目标
解决C‑001文档漂移：SRS与TDD/Coding Contract关于`account_invoice_import`依赖冲突；输出勘误版本，完成基线重新冻结。

## 现状事实
1. SRS v1.3.3多处假设/要求`account_invoice_import`；
2. TDD v1.4.2、T‑016、GATE‑01明确禁止运行时依赖`account_invoice_import`，模块自主组装account.move；
3. 当前代码、manifest、数据库环境均遵循TDD实现方向，`account_invoice_import`模块absent。

## 工作项
1. 评估两种方案二选一：
   方案A：修订SRS，删除/改写全部引用`account_invoice_import`的段落，对齐TDD、Coding Contract现有实现边界；
   方案B：修订TDD/Coding Contract，允许依赖OCA account_invoice_import；同时修改manifest与实现；
2. 记录决策理由；
3. 输出勘误后的SRS版本；版本号升级；
4. 更新Closure追踪矩阵受影响条目SRS‑4.5.1 / SRS‑9.19 / T‑016 / GATE‑01；
5. 执行正式基线冻结流程，更新intents引用的文档版本号。

## 风险
- 如果选择方案B，则FIX‑INTENT与TEST‑INTENT部分实现与测试需要回滚重构。

## 不做
- 不修改源码、不修改测试代码。

## 完成门禁
1. 冲突段落全部勘误完毕；
2. 文档版本升级，冻结记录完备；
3. 所有Intent引用基线版本更新；
4. 明确SRS与TDD优先级决策记录。

## 决策结果

- 选择方案 A：修订 SRS，不修改 TDD、DDD 或 Coding Contract。
- 新冻结业务基线为 `spec_wd_ai_vendor_invoice_1.3.4.md`。
- SRS v1.3.4 明确：本模块依赖 Odoo `account`、`contacts` 和 OCA/queue
  `queue_job`，不依赖或调用 `account_invoice_import`。
- 原 v1.3.3 保留为历史版本，不覆盖、不删除。
- 活动 Intent 的 SRS 基线引用已更新为 v1.3.4；历史报告不回写。