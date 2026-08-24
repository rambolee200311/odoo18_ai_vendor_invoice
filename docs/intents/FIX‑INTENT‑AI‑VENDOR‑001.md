# FIX‑INTENT‑AI‑VENDOR‑001
## 目标
修复Closure二次审阅确认的A类实现缺陷；不新增业务需求，对齐冻结DDD / TDD / SRS契约。

## 冻结基线参考文档
- SRS spec_wd_ai_vendor_invoice_1.3.4.md
- DDD ddd_wd_ai_vendor_invoice_v1.2.md
- TDD tdd_wd_ai_vendor_invoice_v1.4.md
- Coding Contract GATE‑01~GATE‑15
- INT‑WD‑AI‑VENDOR‑INVOICE‑CLOSURE‑001.md

## 缺陷列表
1. CL‑DEF‑A‑001：AI重跑清空human_review_result
   - 文件：`services/parse_service.py` start_parse
   - 契约：DDD重跑保留旧人工复核结果；仅置`human_reviewed=False`，禁止把`human_review_result`置`{}`
   - 验收：单元测试验证，执行AI重跑，原有human_review_result数据保留。

2. CL‑DEF‑A‑002：timeout_service未读取attempt_internal_retry_count，retry未耗尽就标记timeout错误
   - 文件：`services/timeout_service.py`
   - 契约：SRS‑4.1.7a；超时判定必须同时判断：任务时间窗口 **AND** AI内部重试计数已经耗尽；重试尚未耗尽时不触发timeout失败。
   - 验收：单元测试构造retry未耗尽场景，不会被timeout服务标记error_timeout。

3. CL‑DEF‑A‑003：Adapter缺少canonical schema校验与字段归一化
   - 文件：`adapters/base.py`
   - 契约：DDD Adapter职责、TDD §4；外部AI返回数据返回上层前，必须执行JSON‑Schema校验，执行字段归一化；不能仅判断是否为dict。
   - 验收：单元mock测试：非法schema返回直接抛出可区分异常；合法输出完成归一化。

4. CL‑DEF‑A‑004：人工复核UI review_dialog只有pre JSON展示，无结构化编辑、应用AI候选、置信度高亮
   - 文件：`static/src/owl/review_dialog.xml`、对应owl组件
   - 契约：SRS‑4.3 人工解析预览与修正；TDD UI契约
   - 验收：UI可查看AI候选字段，可逐字段编辑；可“应用AI候选”，不覆盖已修改字段；置信度阈值驱动高亮。

5. CL‑DEF‑A‑005：action_save_review独立保存复核结果，未清空并重算review_warnings（严重度MEDIUM）
   - 文件：`models/import_task.py` action_save_review
   - 契约：DDD submit_review契约；独立保存复核路径必须与“复核并生成账单”路径保持warning重算逻辑一致。
   - 验收：单元测试调用独立保存接口，review_warnings会被清空并重新计算。

## 明确不做
1. A‑006非法金额静默转0：**不纳入本intent**；需要先完成契约确认，后续再单独intent；
2. 不修改文档漂移项account_invoice_import冲突；归DOC‑INTENT；
3. 不修改verify.py验证脚本；归SCRIPT‑INTENT；
4. 不补齐并发、多公司、secret等专项测试；归TEST‑INTENT。

## 完成门禁
- 全部缺陷单元测试PASS；
- 原有44项历史测试全部PASS；
- 不引入新的cr.commit、外部锁内HTTP等契约违规；
- 代码评审通过；本Intent不解决Closure全部阻塞，仅解决实现缺陷子集。