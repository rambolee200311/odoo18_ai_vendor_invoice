你这份文本是纯文本，缺少 Markdown 语法标记（标题#、列表、代码块、表格），所以不是标准 Markdown。

下面修复成完整可直接存为 `INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md` 的版本，适合直接喂给 Codex：

```markdown
# INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md

> Document Type: Coding Contract / Implementation Intent
> Status: Frozen
> Pre‑requisites: SRS‑WD‑AI‑VENDOR‑INVOICE v1.3.3, DDD‑WD‑AI‑VENDOR‑INVOICE v1.2, TDD‑WD‑AI‑VENDOR‑INVOICE v1.4.2
> Purpose: 供 Codex 执行开发；定义必须实现、禁止实现、完成门禁、交付物；不做新架构设计，不新增业务需求。

## 1 Scope 实施范围
模块：`wd_ai_vendor_invoice`，Odoo 18.0。

本契约只落地已经冻结的 TDD 内容，**禁止 Codex 自行扩展业务、新增模型、变更状态机、调整领域规则**。

不在本范围：
- 不开发新业务能力
- 不修改 Odoo core、不修改 OCA queue‑job 源码
- 不引入 `account_invoice_import` 运行时依赖
- 不做 E2E 浏览器自动化测试

### 1.1 模块 manifest 硬性约束
- Odoo 版本：18.0
- depends: `["account","contacts","queue_job"]`
- **禁止** manifest 中加入 `account_invoice_import`

## 2 Must‑Implement 必须实现

### 2.1 ORM 模型集合
必须完整创建下面全部模型，字段、约束、ondelete、索引遵循 TDD v1.4.2：
- `vendor.invoice.import.task` 聚合根
- `vendor.invoice.import.parse.attempt` 子实体
- `vendor.invoice.import.log` 审计日志
- `wd.ai.provider.config` AI 服务商配置
- `wd.confidence.threshold` 置信度阈值配置
- `wd.mapping.vendor_alias`
- `wd.mapping.product_keyword`
- `wd.mapping.tax_text`
- `wd.mapping.currency_text`
- `wd.system.config` 系统全局参数

> 数据库唯一约束：ParseAttempt(task_id, sequence) 唯一。

### 2.2 状态契约 ParseAttempt
状态流转集合：`queued / running / success / failed / superseded`

合法流转：
- 创建 → `queued`
- worker 启动 → `running`
- AI 正常返回 → `success`
- AI 可重试 / 永久异常 → `failed`
- 有更新的 attempt 顶替当前 worker → `superseded`

业务规则：
- `superseded` 不计入 AI 失败统计
- stale worker（attempt 非当前 task.current_parse_attempt_id）只允许修改 attempt 自身记录，**禁止写 task 任何字段**。

### 2.3 Task.state 与 queue‑worker 关系
- `task.state = parsing` 代表业务层面解析中，包含队列排队`queued`以及 worker 执行`running`；
- Task 业务状态不直接同步 ParseAttempt 细粒度技术状态；
- queue‑job 入口只能是 model 方法 `job_run_parse`；service 层禁止直接调用 `.with_delay()`。

### 2.4 company_id 强制契约
- `vendor.invoice.import.task.company_id` 创建时赋值，任务生命周期内不可修改；
- queue‑job 异步 worker 必须执行 `task.with_company(task.company_id)`；
- 创建`account.move`账单时，**显式传入 company_id**，不依赖运行环境 env.company；
- 所有业务读取 attempt 所属公司：从`attempt.task_id.company_id`获取，attempt 模型不冗余存储 company。

### 2.5 AI Provider Adapter 契约
- 抽象基类 `BaseAIProviderAdapter`；实现 DeepSeek、Claude 适配器；
- 区分异常：`AIProviderTemporaryError`（可重试） / `AIProviderPermanentError`（不可重试）；
- 原始 AI 响应报文持久化为`ir.attachment`；业务逻辑不读取该附件，仅用于审计排错；
- API 密钥仅通过`sudo()`读取；禁止 RPC 返回密钥明文。

### 2.6 Mapping Service 契约
Mapping 只做候选推荐，不自动改写 mapping 配置主数据，不自动改写 task/attempt 业务结果；结果写入`ParseAttempt.mapping_result`。

### 2.7 HumanReviewResult 唯一数据源
硬性规则：生成账单只读取 `task.human_review_result`
- bill_creator **禁止读取** `canonical_result`
- bill_creator **禁止读取** `mapping_result`

### 2.8 Bill Creator 契约
- 账单生成底层只允许调用 `account.move.create()`，不允许复用外部模块 helper；

生成前置硬校验：
- `task.state == awaiting_review`
- `human_reviewed == True`
- `human_review_result`非空
- `vendor_bill_id`为空（幂等）

- 复核保存与账单生成使用单一后端入口 `action_confirm_review_and_create_bill`，同一个事务；禁止拆两次 RPC；
- 原始 PDF 复制一份独立`ir.attachment`挂载新建 bill；task 保留原始附件引用；
- `vendor_bill_id` many2one `ondelete="restrict"`。

### 2.9 锁、幂等、stale‑worker 防护
- `lock_task / lock_attempt` 专用行锁函数，使用`SELECT FOR UPDATE`；禁止动态 SQL 标识符；
- AI 外部 HTTP 调用**绝对不能持有数据库行锁**；
- stale worker 守卫：检测 attempt 不再是 task 当前 attempt 时，标记 superseded，不可修改 task；
- 账单创建事务完整闭环，异常回滚，不允许遗留孤立`account.move`。

### 2.10 Secret 安全契约
Provider api_key：
- 仅`group_config_manager`可读；
- 禁止输出到日志、error_message、Sentry、RPC 返回值；
- raw response 附件权限受控，普通业务用户不可访问密钥内容。

### 2.11 Cron 超时巡检
- 超时基准字段：`task.enter_parsing_datetime`，覆盖 `queued` /`running`；
- `last_activity_at`仅本地诊断，不作为跨进程超时判定依据；
- 超时任务置 `task.state = error_timeout`。

## 3 Must‑Not‑Do 禁止项
- ❌ 不引入 `account_invoice_import` manifest 依赖，不调用其向导 / 导入入口；仅允许阅读源码做参考；
- ❌ bill_creator 禁止读取 canonical_result、mapping_result；
- ❌ queue‑job worker 内部禁止调用`env.cr.commit()`；
- ❌ service 对象禁止直接`.with_delay()`；队列入口仅限 model method；
- ❌ stale worker 修改 task 对象状态；
- ❌ API 密钥泄露日志、异常、RPC；
- ❌ Codex 自行新增模型、新增业务流程、扩展状态集合；
- ❌ 复核和生成账单拆分为两次独立 RPC 调用；
- ❌ AI 解析 HTTP 请求期间持有数据库排他行锁。

### 3.1 交付物清单（必须全部产出）
- 模块完整源码目录，遵循 TDD 目录分层 `models/services/adapters/schemas/tests/views/security/data`
- 全部 security：groups、access csv、record‑rules、xml；权限矩阵落地；
- JSON Schema 校验代码；
- queue‑job cron xml 数据；
- 单元测试、集成测试；**必须包含并发测试、权限测试、stale‑worker 测试**；
- 视图 xml + Owl 复核弹窗组件；
- 本 coding contract 文档不修改；

## 4 Gate 机器可检查门禁（verify.py 校验源）
```text
GATE‑01 manifest depends 不包含 account_invoice_import
GATE‑02 bill_creator 源码不得读取 canonical_result
GATE‑03 bill_creator 源码不得读取 mapping_result
GATE‑04 queue‑job worker函数内不存在 cr.commit()
GATE‑05 DB唯一约束 ParseAttempt(task_id, sequence) 存在
GATE‑06 bill_creator执行前校验 awaiting_review + human_reviewed=True
GATE‑07 stale worker分支，禁止写task对象任何字段
GATE‑08 provider secret不出现日志、error_message、RPC返回
GATE‑09 task存在company_id字段；worker执行with_company(task.company_id)
GATE‑10 并发生成账单，最终只产生1条account.move
GATE‑11 queue‑job with_delay调用对象仅为model method，不能是service函数
GATE‑12 bill生成使用account.move.create，不调用第三方模块bill构建helper
GATE‑13 task.company_id 创建完成后不可写
GATE‑14 复核+生成账单使用统一入口action_confirm_review_and_create_bill
GATE‑15 行锁不包裹外部AI HTTP网络IO代码块
```

> verify.py 将以上 GATE 作为门禁；**全部 GATE 通过，才视为开发完成**。

## 5 Sprint Intent 拆分（给 Codex 的实施顺序，不可打乱）

### Intent‑1 Foundation
目标：骨架底座
- ORM 全部模型、字段、索引、SQL 约束、ondelete；
- security 权限组、access、record rule；
- lock_service 行锁工具；
- system /confidence/mapping /provider config 主数据；
- JSON Schema；
- queue‑job 基础骨架、cron 数据；
- 基础单元测试模型层。

### Intent‑2 AI + Review
目标：解析、映射、人工复核链路
- AI Provider Adapter 实现、异常定义；
- parse_service、mapping_service；
- ParseAttempt 完整状态流转；
- task 重跑 AI；
- Owl 复核弹窗 UI 视图；
- 审计日志记录；
- 对应单元、集成测试。

### Intent‑3 Bill Closure
目标：账单闭环、并发、全部门禁落地
- validation_service 校验；
- bill_creator 完整实现；
- 附件复制逻辑；
- 幂等、事务边界；
- cron 超时；
- 并发测试、stale‑worker 测试、权限测试全部落地；
- 跑全部 GATE 门禁，全部通过。

## 6 Definition Of Done 完成定义
- 模块代码完整可安装 Odoo18；无语法错误；
- 所有模型、状态、业务规则符合 TDD v1.4.2；没有私自新增业务；
- 全部单元、集成、并发、权限测试运行通过；
- verify.py 执行，**全部 GATE‑01 ~ GATE‑15 门禁全部 Pass**；
- 人工冒烟：上传 PDF‑AI 解析‑人工复核‑生成草稿账单完整链路跑通；
- 不引入禁止依赖；安全契约全部遵守。

## 7 Post‑Implementation 实施后动作
开发完成后，使用测试、门禁结果反向核验：SRS / DDD / TDD 文档，识别文档‑代码漂移，输出变更记录；本 Coding Contract 本身不随代码实现修改。

> 附录不写在正文；变更记录统一放到项目 `sprint_log.md`。
```

关键改动点：
1. 增加 `#` / `##` / `###` 标题层级；
2. 普通条目改成 Markdown 无序列表 `-`；
3. 代码/标识符用反引号 `` ` ``；
4. GATE 块包裹 ```text```；
5. 块引用使用 `>`；
6. 保留全部业务文字，没有改任何契约逻辑。

保存后，Codex、Cline 可以正确解析标题、列表、代码块结构。