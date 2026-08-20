你现在执行 INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md 的 Intent‑1 Foundation。

优先级规则：Coding Contract > TDD‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001 v1.4.2 > 其他上下文文档。
禁止自行新增业务、模型、字段、状态。

当前仅实施 Intent‑1 Foundation，**绝对不要实现 Intent‑2、Intent‑3 的任何内容**：
不要写 AI Provider Adapter，不要写 parse_service/mapping_service，不要写Owl弹窗，不要写bill_creator，不要写复核相关逻辑。

Intent‑1 需要产出：
1. wd_ai_vendor_invoice 模块骨架，odoo18，manifest depends = ["account","contacts","queue_job"]，严禁出现 account_invoice_import
2. 全部ORM模型：
vendor.invoice.import.task
vendor.invoice.import.parse.attempt
vendor.invoice.import.log
wd.ai.provider.config
wd.confidence.threshold
wd.mapping.vendor_alias
wd.mapping.product_keyword
wd.mapping.tax_text
wd.mapping.currency_text
wd.system.config
严格按照TDD v1.4.2字段、索引、ondelete；ParseAttempt必须有数据库唯一约束 (task_id, sequence)。task.company_id 创建后不可写。
3. lock_service：lock_task / lock_attempt，SELECT FOR UPDATE，禁止动态SQL标识符
4. security：groups、ir.model.access、record‑rules xml，落地Coding Contract权限契约
5. schemas：JSON Schema文件，基础schema定义
6. data：cron xml数据文件
7. tests：基础模型层单元测试，只做模型创建、约束校验，不写业务集成测试

目录结构严格遵守TDD约定：
models/ services/ adapters/ schemas/ tests/ views/ security/ data/

完成全部代码输出后，输出Intent‑1自检清单，对照Coding Contract检查：
- manifest校验
- 模型清单是否齐全
- ParseAttempt唯一约束是否存在
- company_id不可写约束
- lock_service实现约束

自检完成，停止工作，不要主动进入Intent‑2。等待我下一步指令。