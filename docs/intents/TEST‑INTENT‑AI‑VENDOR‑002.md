# TEST-INTENT-AI-VENDOR-002

## 目标

补齐Closure识别的阻塞性测试缺口；只新增测试，不修改业务逻辑代码；所有测试遵循Odoo 18测试框架和最终冻结TDD契约。

## 冻结基线参考文档

- SRS spec_wd_ai_vendor_invoice_1.3.4.md
- DDD ddd_wd_ai_vendor_invoice_v1.2.md
- 最终冻结 TDD（以磁盘实际冻结版本为准）
- Coding Contract GATE-01~GATE-15
- INT-WD-AI-VENDOR-INVOICE-CLOSURE-001.md
- FIX-INTENT-AI-VENDOR-001最终实施结果（仅用于确认代码现状，不替代冻结设计）

## 需要新增测试集合

1. B-001：Bill生成并发幂等测试
   - 使用真实多事务并发；
   - 验证SELECT FOR UPDATE；
   - 最终只能生成1张account.move；
   - 第二个并发请求必须失败且不得留下孤立bill。

2. B-002：Stale-Worker防护测试
   - 模拟旧queue_job晚返回；
   - attempt标记superseded；
   - 禁止修改task状态；
   - superseded不计入AI失败统计。

3. B-003：Multi-Company隔离测试
   - Task.company_id固定；
   - worker使用task.company_id上下文；
   - mapping、tax/product查询和Bill创建不得串公司；
   - 不依赖原RPC env.company。

4. B-004：ACL / Record Rule完整权限矩阵测试
   - User / Reviewer / Config Manager；
   - provider config；
   - task；
   - attempt；
   - human review；
   - raw response attachment；
   - 普通用户不得读取Provider secret。

5. B-005：Provider Secret泄漏专项测试
   - 日志；
   - error_message；
   - RPC/read/fields_get；
   - raw response；
   - 异常链；
   - Secret不得明文泄露。

6. B-006：Adapter异常与重试行为测试
   - TemporaryError；
   - PermanentError；
   - retry计数；
   - retry耗尽最终error_ai_unavailable；
   - superseded保护；
   - 不把retry_count作为timeout判定前置条件。

7. B-007：Parse Pipeline端到端集成测试
   - PDF attachment
   → pdf_preprocessor
   → ProviderInput(pages)
   → mocked Adapter
   → Canonical schema validation
   → MappingResult
   → Human Review
   → Draft Vendor Bill
   - Adapter不得直接读取attachment；
   - 多页PDF保持同一解析上下文；
   - 非法Canonical不得进入Mapping；
   - PDF页面不得持久化到业务模型。

8. B-008：PDF Preprocessor异常测试
   - 空PDF；
   - 损坏/非法PDF；
   - 加密PDF；
   - 页面渲染失败；
   - 异常必须可区分；
   - 不泄露PDF内容或Secret；
   - 在Task状态映射契约未冻结前，不对最终Task state做断言。

## 不做

- 不修复业务bug；
- 不修改SRS/DDD/TDD；
- 不处理文档漂移；
- 不修改verify.py；
- 不自行决定PDF异常映射到哪个Task state。

## 完成门禁

- 本Intent新增全部正式测试PASS；
- 当前仓库全部既有正式测试PASS；
- 并发测试必须真实多事务，不允许顺序调用模拟；
- Odoo运行日志必须作为证据；
- 不允许因为测试需要修改业务代码；
- 若测试暴露实现缺陷，只记录为新的IMPLEMENTATION_DEFECT，不在本Intent修复。