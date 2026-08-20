执行 INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md 的 Intent‑2 AI + Review。
优先级：Coding Contract > TDD‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001 v1.4.2 > 其余上下文。

前置条件：Intent‑1 Foundation 已经完整落地。
严禁实现 Intent‑3 的任何能力：不写validation_service、不写bill_creator、不做account.move账单创建、不做账单附件复制。

需要完成产出：
1. AI Provider Adapter
- 抽象基类 BaseAIProviderAdapter
- DeepSeek、Claude 两个具体适配器实现
- 定义异常类：AIProviderTemporaryError、AIProviderPermanentError
- AI返回原始报文存入ir.attachment；业务代码不读取该原始报文；
- api_key仅通过sudo读取，禁止RPC输出密钥明文

2. Service层
- parse_service：完整ParseAttempt状态流转，queued/running/success/failed/superseded
- mapping_service：仅做候选推荐，禁止改写mapping主数据、禁止改写task/attempt业务结果，结果写入ParseAttempt.mapping_result
- 严格遵守stale worker规则：非当前attempt只修改attempt自身，禁止写task任何字段
- queue‑job入口只能是model方法job_run_parse，service禁止直接调用.with_delay()

3. 业务动作
- task重跑AI的action逻辑，生成新ParseAttempt

4. 审计日志 vendor.invoice.import.log
- 记录解析、重跑、变更关键操作

5. UI层
- 视图xml、Owl复核弹窗组件；完成任务查看、解析结果查看、费用复核界面；不触发生成发票/账单。

6. tests单元&集成测试
- ParseAttempt状态流转测试
- stale worker防护测试
- adapter异常分支测试
- mapping服务测试
- 重跑AI业务流程测试

约束规则：
1. 禁止bill_creator、账单生成相关代码；
2. 禁止cr.commit()出现在queue‑job worker内部；
3. AI外部HTTP调用不能持有数据库行锁；
4. 所有company处理沿用Intent‑1契约，worker必须执行task.with_company(task.company_id)。

完成全部代码后输出Intent‑2自检清单，对照Coding Contract校验：
‑ adapter抽象、异常类完整
‑ ParseAttempt全部状态流转完整，superseded不计失败
‑ stale worker没有写task字段
‑ mapping仅输出候选，不修改主数据
‑ worker不存在cr.commit()
‑ 没有混入Intent‑3账单相关代码

自检完毕立刻停止，不要进入Intent‑3，等待我下发指令。