执行 INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md 的 Intent‑3 Bill Closure。
优先级：Coding Contract > TDD‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001 v1.4.2 > 其余上下文。
前置：Intent‑1、Intent‑2代码完整可用。

产出范围：
1. validation_service：费用校验逻辑
2. bill_creator完整实现
- 硬性前置校验：task.state==awaiting_review，human_reviewed==True，human_review_result非空，vendor_bill_id为空
- bill_creator只读取task.human_review_result；严禁读取canonical_result、mapping_result
- 只能调用account.move.create()，禁止第三方模块helper
- 统一入口action_confirm_review_and_create_bill，单事务，禁止拆两次RPC
- 原始PDF复制独立ir.attachment挂载新建account.move；task保留原附件
- vendor_bill_id ondelete=restrict
- 事务闭环，异常完整回滚，禁止孤立account.move

3. cron超时巡检实现
- 使用task.enter_parsing_datetime做超时基准，覆盖queued/running
- last_activity_at仅诊断，不作为超时判定；超时置task.state=error_timeout

4. 补全tests：
‑ bill_creator幂等测试
‑ 并发生成账单测试，断言最终仅生成1条account.move
‑ 权限测试
‑ 事务回滚场景测试

必须遵守门禁约束：
‑ queue‑job worker内部无cr.commit()
‑ stale worker规则不变
‑ provider secret安全规则不变
‑ task.company_id不可写，worker使用with_company(task.company_id)

全部代码完成后输出Intent‑3完整自检清单，逐条核对全部GATE‑01~GATE‑15。
自检完成后，输出模块安装冒烟测试步骤。
停止工作，等待人工执行verify.py门禁与冒烟验证。