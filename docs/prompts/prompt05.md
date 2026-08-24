继续执行当前已启动的 `FIX-INTENT-AI-VENDOR-001`。

这是对当前 Intent 的补充执行约束，不新建 Intent，不改变 A-001~A-005 的总体修复目标。

当前仍以以下冻结基线作为唯一真值：
- SRS `spec_wd_ai_vendor_invoice_1.3.3.md`
- DDD `ddd_wd_ai_vendor_invoice_v1.2.md`
- 最终冻结 TDD（以项目磁盘中实际冻结版本为准）
- Coding Contract GATE-01~GATE-15
- `INT-WD-AI-VENDOR-INVOICE-CLOSURE-001.md`
- 当前 `FIX-INTENT-AI-VENDOR-001`

不要根据历史工作报告、聊天描述或自己的推测覆盖冻结文档。
如本 Prompt 与冻结基线存在冲突，必须停止该冲突项的实现并报告，不得自行选择口径。

============================================================
一、首先检查 A-002 契约，不要直接修改
============================================================

当前 FIX Intent 中 A-002 写的是：

`timeout` 判定必须同时满足：
1. 任务超出时间窗口；
2. `attempt_internal_retry_count` 已经耗尽。

但此前技术设计曾对 timeout 语义发生过修订，因此在继续修改 A-002 前，必须直接读取磁盘中的最终冻结 TDD 原文，确认最终契约。

重点核查：
- timeout 判定到底是否依赖 `attempt_internal_retry_count`
- `queued` / `running` 的超时语义
- `enter_parsing_datetime` 与 `last_activity_at` 的职责
- `error_ai_unavailable` 与 `error_timeout` 的边界
- 对应 T-xxx 技术不变量的最终文字

处理规则：

A. 如果最终冻结 TDD 明确要求：
`timeout window AND retry exhausted`
则继续按照当前 A-002 修复。

B. 如果最终冻结 TDD 明确规定：
timeout 仅表示 queue/worker 活性丢失，不依赖 retry_count
则当前 FIX Intent 的 A-002 与冻结 TDD 冲突。

此时：
- 不得按照 FIX Intent 把代码改回旧语义；
- 不得自行修改 TDD；
- 不得自行解释哪个设计更合理；
- 立即把 A-002 标记为 `BASELINE_CONFLICT`；
- 报告冻结 TDD 的文件路径、章节、原文摘要和当前 FIX Intent 冲突点；
- A-002 暂停实施；
- 其他无冲突缺陷继续执行。

如果代码已经对 A-002 做了修改，也先检查修改是否符合最终冻结 TDD；不符合时报告，不要擅自继续扩大修改。

============================================================
二、A-003 增加必要的配套技术实现：PDF → ProviderInput
============================================================

Closure 后进一步确认：

当前解析链直接把 `ir.attachment` PDF 交给 AI Adapter，但实际 Vision Provider API 不一定能够直接消费 PDF 二进制。

同时，A-003 要求 Adapter 契约收口：
- Adapter负责外部Provider协议适配；
- Adapter不能继续耦合上游 `ir.attachment`；
- Adapter输出 CanonicalInvoiceResult 前必须完成归一化和 JSON Schema 校验。

因此，为完成 A-003，必须补齐：

`ir.attachment(PDF) -> ProviderInput -> AI Adapter`

这一转换是 A-003 的配套技术实现，纳入当前 `FIX-INTENT-AI-VENDOR-001`，不单独新建 Intent。

注意：

这不是新增业务需求，不是建设通用文档处理平台，不允许借此扩大 Scope。

============================================================
三、PDF预处理架构边界
============================================================

新增独立技术服务：

`services/pdf_preprocessor.py`

职责仅限：

将当前任务的 PDF attachment 转换成 AI Adapter 可消费的标准技术输入。

禁止把 PDF 解析/渲染逻辑放入：
- ORM `create`
- ORM `write`
- `onchange`
- compute
- constraint
- 其他 model hook

PDF预处理必须发生在异步 worker 中：

`job_run_parse`
    ->
`parse_service.run_parse_attempt`
    ->
`pdf_preprocessor`
    ->
`AI Adapter`
    ->
`External AI Provider`

绝对禁止在 `start_parse()` RPC 阶段执行 PDF 页面渲染或其他重型预处理。

`start_parse()` 仍然只负责现有冻结职责：
- 锁
- 创建 ParseAttempt
- Task 状态转换
- queue-job 入队

不得改变其事务契约。

============================================================
四、ProviderInput 契约
============================================================

当前 Fix 只实现实际需要的 pages 路径。

标准输入结构：

{
    "type": "pages",
    "images": [binary_png_bytes, ...]
}

要求：

1. `images` 按 PDF 原始页面顺序排列；
2. PDF 有 N 页，正常情况下输出 N 个 page image；
3. 页面图片仅存在于当前 worker 内存生命周期；
4. 不向 Task 增加图片字段；
5. 不向 ParseAttempt 增加图片字段；
6. 不把页面 base64 / binary 持久化到业务模型；
7. 不新增缓存 model；
8. 不新增预处理结果 model。

接口设计可以保持未来可扩展性，但当前 Intent：

禁止实现：
- `type=text` 的实际处理路径
- PDF文本提取
- 文本PDF/扫描PDF自动分类
- OCR
- PDF预处理缓存
- 文档分类器
- Strategy/Plugin等没有当前需求支撑的抽象框架

不要为了“以后可能需要”提前实现。

============================================================
五、Adapter职责重新收口
============================================================

AI Adapter 不再直接接收或读取 `ir.attachment`。

Adapter输入改为 ProviderInput。

职责边界：

`pdf_preprocessor`
负责：
PDF attachment
    ->
标准 ProviderInput

AI Adapter
负责：
ProviderInput
    ->
具体 Provider HTTP payload
    ->
调用外部AI
    ->
Provider response
    ->
字段归一化
    ->
Canonical JSON Schema validation
    ->
CanonicalInvoiceResult

Adapter不得承担：
- Odoo attachment读取
- PDF页面解析
- PDF页面渲染
- Task业务状态修改
- Human Review逻辑
- Mapping业务逻辑
- Bill创建逻辑

============================================================
六、Canonical Schema 校验仍然是 A-003 核心修复内容
============================================================

不要因为增加 pdf_preprocessor 而遗漏原 A-003。

A-003 仍然必须完成：

1. 外部Provider response转换为内部Canonical结构；
2. 对CanonicalInvoiceResult执行冻结TDD定义的JSON Schema校验；
3. 不能仅用 `isinstance(result, dict)` 作为合法性判断；
4. 非法Schema必须抛出可区分的Provider/Adapter异常；
5. 不允许非法CanonicalResult进入mapping_service；
6. 合法结果必须完成字段归一化后再交给上层。

Schema定义必须复用项目已有：

`schemas/canonical.py`

或者冻结TDD指定的正式Schema实现。

不要在Adapter里再复制一套Schema定义。

============================================================
七、多页PDF处理语义
============================================================

不要实现“每页AI解析一次，然后业务层合并结果”。

同一个 PDF 的全部页面必须保持为同一个发票解析上下文。

目标语义：

PDF
 ->
page_1 image
page_2 image
...
page_N image
 ->
同一个 Provider 请求上下文
 ->
一次完整 CanonicalInvoiceResult

如果具体Provider API支持单请求多图输入，则一次提交全部页面。

不得新增：
- PageResult业务对象
- 页级CanonicalResult
- 页级MappingResult
- 页级业务结果合并算法

不得自行判断某几页属于同一张发票。

原有：
`is_multi_invoice`
业务语义保持不变。

============================================================
八、PDF异常处理边界
============================================================

pdf_preprocessor 至少需要能够区分：

- 非PDF/无效输入
- 空PDF
- 损坏PDF
- 加密且无法读取PDF
- 页面渲染失败

要求：

1. 使用明确、可测试的预处理异常类型或错误码；
2. 不泄露PDF内容或Provider Secret到异常信息；
3. 不新增Task state；
4. 不修改冻结状态机；
5. 不擅自增加：
   - error_pdf_invalid
   - error_pdf_encrypted
   - error_pdf_render
   等新业务状态。

如果冻结文档没有明确规定某种预处理异常应该映射到哪个现有Task状态：

不要自行创造业务语义。

应：
- 保持底层异常可区分；
- 在报告中标记该状态映射为契约未定义点；
- 仅在现有冻结契约能够明确推导时才修改Task状态。

============================================================
九、配置边界
============================================================

不要因为PDF渲染新增不必要的业务配置。

特别是：
- 不新增用户可见的DPI配置页面；
- 不新增PDF预处理配置模型；
- 不新增Provider预处理策略配置，除非冻结契约已经要求。

如果PDF渲染库必须使用DPI等技术参数：

优先使用内部明确命名的技术默认值/常量。

不要把纯技术实现参数无依据地升级成业务配置项。

============================================================
十、严禁修改现有业务契约
============================================================

本次 A-003 配套修复不得修改：

- `task.company_id` 不可变契约
- Task状态集合
- ParseAttempt状态集合
- current_parse_attempt语义
- stale-worker契约
- queue-job事务契约
- `human_review_result`
- `human_reviewed`
- Mapping契约
- Review契约
- Bill Creator契约
- account.move生成规则
- vendor_bill幂等规则
- Attachment复制到Bill的既有规则

特别注意：

T-025 `task.company_id` 创建后不可修改，现有实现保持不动。

============================================================
十一、A-003新增测试要求
============================================================

在原 FIX Intent A-003 测试基础上增加以下测试。

1. PDF预处理基本测试
- 合法单页PDF -> ProviderInput type=pages
- 合法多页PDF -> images数量等于页数
- 页面顺序保持不变

2. 异常测试
- 空PDF
- 损坏PDF
- 加密无法读取PDF
- 页面渲染失败

确认异常可区分，不产生未定义业务状态。

3. Adapter输入边界测试
确认 Adapter 不再直接读取 `ir.attachment`。

Adapter测试直接传 ProviderInput。

4. Canonical Schema测试
- 合法Provider response -> normalize -> schema PASS
- 缺required字段 -> FAIL
- 字段类型错误 -> FAIL
- confidence越界 -> FAIL
- additionalProperties违反冻结Schema -> FAIL（如正式Schema如此规定）

5. Mapping边界
非法Canonical结果不得进入mapping_service。

6. 多页上下文
确认多页PDF不会在业务层产生N次独立Canonical解析/页级结果合并。

============================================================
十二、原A-001 / A-004 / A-005继续按FIX Intent执行
============================================================

CL-DEF-A-001：
AI重跑只允许：
`human_reviewed = False`

禁止清空：
`human_review_result`

必须补回归测试。

------------------------------------------------------------

CL-DEF-A-004：

严格按照冻结 SRS/TDD 实现人工复核UI：

- 结构化字段展示
- 逐字段编辑
- AI候选查看
- 【应用AI候选】
- 已经被人工编辑的字段不得被候选自动覆盖
- confidence threshold高亮

不要重新设计复核业务流程。

------------------------------------------------------------

CL-DEF-A-005：

`action_save_review` 独立保存路径必须按照冻结DDD契约重新计算 `review_warnings`。

不要借此修改Bill Creator业务规则。

============================================================
十三、仍然不纳入本Intent的内容
============================================================

保持当前 FIX Intent 的明确排除项：

- A-006 非法金额静默转0：不处理
- account_invoice_import文档漂移：不处理
- verify.py问题：不处理
- Closure发现的专项TEST GAP：不在本Intent补齐

特别注意：

A-003新增的测试属于“修复A-003本身必须具备的回归测试”，允许增加。

但不要借此补：
- 全项目并发测试缺口
- 全项目multi-company测试缺口
- 全项目secret专项测试缺口
- Closure其他TEST GAP

============================================================
十四、禁止Scope扩散
============================================================

本次明确禁止自行增加：

- OCR能力
- PDF文本提取优化
- 文本/扫描PDF分类
- PDF缓存
- 通用Document Processing Framework
- 新业务model
- 新Task字段
- 新Attempt字段
- 新业务状态
- 新AI解析业务流程
- 页级AI结果合并
- Provider自动选择
- fallback provider
- 新业务配置界面
- 与本Fix无关的代码重构

发现上述能力“可能以后有用”，只记录为建议，不实现。

============================================================
十五、执行完成后的报告格式
============================================================

完成后不要只说“已完成”。

必须输出：

## 1. Baseline Check

特别报告A-002最终冻结契约核对结果：

- TDD实际文件：
- TDD版本：
- 对应章节/T-编号：
- 冻结规则：
- 是否与当前FIX A-002一致：
- A-002处理结果：
  - IMPLEMENTED
  - BASELINE_CONFLICT
  - NO_CHANGE_REQUIRED

## 2. Defect Resolution Matrix

| Defect | Result | Modified Files | Tests | Notes |
|---|---|---|---|---|
| A-001 | FIXED / BLOCKED | ... | ... | ... |
| A-002 | FIXED / BASELINE_CONFLICT / ... | ... | ... | ... |
| A-003 | FIXED / BLOCKED | ... | ... | ... |
| A-004 | FIXED / BLOCKED | ... | ... | ... |
| A-005 | FIXED / BLOCKED | ... | ... | ... |

A-003必须单独列出：
- canonical normalization/schema validation
- pdf_preprocessor
- ProviderInput
- Adapter contract
- tests

## 3. Test Evidence

列出：
- 新增/修改测试
- 实际执行命令
- PASS/FAIL数量
- 原44项历史测试回归结果

不得只说“测试应该通过”，必须给实际运行结果。

## 4. Scope Check

明确回答：
- 是否新增业务model：YES/NO
- 是否新增Task/Attempt字段：YES/NO
- 是否新增state：YES/NO
- 是否实现OCR：YES/NO
- 是否实现文本提取：YES/NO
- 是否修改human_review/bill契约：YES/NO
- 是否新增cr.commit：YES/NO
- 是否在数据库行锁期间执行AI HTTP：YES/NO

除冻结契约明确授权外，上述预期全部应为NO。

## 5. Remaining Issues

只列仍未解决的问题，不要擅自修复Intent范围外问题。

============================================================
最终执行原则
============================================================

这是 Fix Intent，不是重新架构阶段。

目标是：

“以最小必要修改，使当前实现重新符合冻结契约，并让真实AI Provider输入链路可执行。”

不要把：

“PDF不能直接发送给当前Provider”

扩大成：

“建设通用PDF文档处理平台”。

先核对基线，再实施；
有契约冲突先报告；
只修改本Intent授权范围；
所有修复必须有真实测试证据。