## DN-004 SPIKE-OCA-001：取消依赖 OCA account_invoice_import，采用原生 account.move.create

### 决策背景
SPIKE-OCA-001 完成对 OCA/edi 18.0（18.0.1.2.0）源码完整探查，目标确认：
是否存在安全、无副作用、可外部复用的 Vendor Bill 创建 Helper，用于 wd_ai_vendor_invoice 的 bill_creator。

### 探查结论
1. OCA `account_invoice_import` **无任何可独立外部调用的公共创建 Helper**
   所有核心组装、创建逻辑全部封闭在 TransientModel 向导内部，强依赖：
   - 文件解析流
   - parsed_inv 结构化解析结果
   - import_config 商户默认配置
   - wizard 上下文状态
   无法独立脱离OCA导入流程运行。

2. OCA 内置逻辑存在多处架构副作用，与本系统 DDD 强冲突：
   - 自动 Fiscal Position 科目/税码覆盖
   - 从历史账单自动回填产品、税、科目
   - 自动生成金额调整行
   会破坏 **HumanReviewResult 唯一可信数据源** 原则。

3. OCA 附件实现与本系统约束冲突
   OCA 采用「重新创建 attachment」，不支持 task 与账单**共享原始PDF引用**，
   本系统必须使用原生 `ir.attachment.copy()`。

4. OCA 存在隐式依赖链
   启用该模块需要额外依赖：`account_tax_unece`、`uom_unece`，
   增加部署成本、模块耦合、运行时风险。

### 最终决策（C方案）
1. **wd_ai_vendor_invoice 永久移除 / 不添加 account_invoice_import 硬依赖**
2. **bill_creator 完全基于 Odoo 原生 ORM：account.move.create()**
3. OCA 代码仅作为静态结构参考，**禁止任何运行时调用**
4. 附件绑定统一使用原生 `ir.attachment.copy()` 策略

### 决策收益
- 彻底消除 OCA 自动映射覆盖人工复核结果的致命风险
- 减少模块依赖、降低部署复杂度
- 完全贴合 DDD 数据源单向收敛架构
- 账单创建逻辑自主可控、无黑盒副作用

### 落地约束
- manifest.py depends **禁止写入 account_invoice_import**
- bill_creator 所有字段组装、税、科目、货币全部由 HumanReviewResult 驱动
- 禁止复用任何 OCA wizard / matcher / post_process 运行时方法

### 关联文档
- SPIKE-OCA-001 完整探查报告：/docs/spike/SPIKE-OCA-001.md
- TDD §T-016
- DDD 1.2 人工复核唯一数据源约束

### 状态
✅ 最终闭环、不可变更