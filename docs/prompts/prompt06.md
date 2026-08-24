继续执行 TEST-INTENT-AI-VENDOR-002，但本轮属于 TEST-INTENT-002 的补充执行 / 测试收口，不重新扩大测试范围。

项目目录：
/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice

模块：
addons/ai_vendor_invoice

冻结基线：
- SRS spec_wd_ai_vendor_invoice_1.3.3.md
- DDD ddd_wd_ai_vendor_invoice_v1.2.md
- TDD tdd_wd_ai_vendor_invoice_v1.4.md
- Coding Contract GATE-01~GATE-15
- INT-WD-AI-VENDOR-INVOICE-CLOSURE-001.md
- TEST-INTENT-AI-VENDOR-002

============================================================
一、本轮目标
============================================================

TEST-INTENT-AI-VENDOR-002 首轮执行已经完成大部分测试，但当前仍有两个阻塞性 TEST_GAP 没有取得有效运行时证据：

B-001：
bill生成真实并发幂等测试没有成功建立并发场景。

当前结果：
1 test
1 failure

失败信息：
first transaction did not start within 10 seconds

这不能判定产品代码PASS，也不能直接归类为Environment Blocker。
当前只能判定：
B-001 = TEST_GAP / BLOCKED

B-003：
multi-company测试因为目标公司缺少purchase journal而被skip。

当前结果：
Task company has no purchase journal.

这同样不能判定PASS。
自动化测试不能依赖当前业务数据库“恰好已经存在”完整的第二公司会计基础数据。

当前只能判定：
B-003 = TEST_GAP / BLOCKED

另外，首轮测试已经发现：

CL-DEF-A-006：
wd.ai.provider.config.api_key字段权限配置存在实现缺陷。

现象：
- 普通User不可见；
- Reviewer不可见；
- Config Manager同样无法通过正常RPC fields_get看到api_key；
- 与冻结权限契约不一致。

该问题属于：
A. IMPLEMENTATION_DEFECT

本TEST Intent严禁修复该业务实现缺陷。
只保留失败测试和缺陷记录。
后续由独立FIX-INTENT修复。

============================================================
二、本轮唯一允许修改范围
============================================================

只允许修改：

addons/ai_vendor_invoice/tests/**
以及必要的测试辅助代码 / 测试fixture。

允许更新：
docs/context/history/sprint_log.md

用于记录本轮TEST Intent执行结果。

禁止修改：

addons/ai_vendor_invoice/models/**
addons/ai_vendor_invoice/services/**
addons/ai_vendor_invoice/adapters/**
addons/ai_vendor_invoice/schemas/**
addons/ai_vendor_invoice/security/**
addons/ai_vendor_invoice/views/**
addons/ai_vendor_invoice/static/**
addons/ai_vendor_invoice/data/**
addons/ai_vendor_invoice/__manifest__.py

禁止修改冻结：
SRS / DDD / TDD / Coding Contract / Closure Intent。

禁止修改verify.py。

如果测试暴露新的产品实现缺陷：
只记录。
不得修复。

============================================================
三、任务1：修正 B-001 真实并发测试
============================================================

目标：

必须取得真正的多数据库事务并发运行时证据，验证：

同一个 vendor.invoice.import.task 被两个独立事务并发请求生成 Vendor Bill 时：

1. 两个执行路径必须使用独立数据库transaction/cursor；
2. 必须真正触发 task SELECT FOR UPDATE 竞争；
3. 第二事务必须等待第一事务释放task锁；
4. 第一事务成功生成bill并写入vendor_bill_id；
5. 第一事务commit后，第二事务获得锁；
6. 第二事务重新读取task后看到vendor_bill_id已经存在；
7. 第二事务必须拒绝重复生成；
8. 最终数据库中该task只关联一张account.move；
9. 不允许产生孤立account.move；
10. 不允许使用“两个顺序调用”伪装成并发测试。

目标并发时序：

TX-A                         TX-B
 |                            |
 acquire task FOR UPDATE      |
 |                            |
 create vendor bill           |
 |                         attempt same task
 |                         wait FOR UPDATE
 |                            |
 commit                       |
                              |
                           acquire lock
                              |
                           reload task
                              |
                        vendor_bill_id exists
                              |
                       reject duplicate create

最终：

task.vendor_bill_id = bill_A

并且：

针对本次测试task生成的account.move数量 = 1

注意：

不要简单通过增加sleep或者把10秒timeout改成60秒掩盖fixture问题。

首先分析为什么当前：

"first transaction did not start within 10 seconds"

重点检查：

- Odoo TransactionCase / SavepointCase 外层事务是否持有测试数据锁；
- 子线程的新cursor是否正在等待主测试事务中尚未commit的数据；
- 测试task是否是在主测试事务创建，因此独立cursor根本看不到；
- registry cursor使用方式是否正确；
- Environment创建方式是否正确；
- threading synchronization是否正确；
- Event / Barrier是否在正确位置；
- 第一事务究竟卡在cursor创建、browse、FOR UPDATE还是account.move创建；
- 是否应该把并发fixture数据放到独立已提交事务中创建，而不是依赖外层TransactionCase未提交数据。

必须找出真实原因后修测试fixture。

如果Odoo测试框架的外层事务导致线程无法看到fixture数据：

允许在“测试代码范围内”重新设计并发测试harness。

可以使用：
- 独立registry cursor；
- 独立Environment；
- threading.Event；
- threading.Barrier；
- PostgreSQL独立事务；
- 专门为并发测试创建并提交fixture数据的测试辅助方法；

但不得修改产品代码。

特别注意测试清理：
测试创建并commit的数据必须有可靠cleanup策略，不能污染后续测试。

完成后必须能够明确证明：

B-001 PASS

而不是：
“代码看起来正确”。

如果经过合理修正后仍然无法在当前Odoo测试框架运行，必须输出具体数据库等待点 / 锁等待证据，而不能只写“Environment Blocker”。

============================================================
四、任务2：修正 B-003 Multi-Company Fixture
============================================================

当前测试：

Task company has no purchase journal.

因此被skip。

禁止继续依赖现有数据库第二公司的会计配置。

测试必须自行创建最小可运行multi-company fixture。

测试至少建立：

Company A
Company B

其中Company B必须具备生成Vendor Bill所需的最低会计基础数据。

根据当前Odoo18 account.move实际要求创建最小必要fixture，例如：

- company
- currency
- account
- purchase journal
- supplier partner
- 必要的product/account配置
- 如测试使用tax，则创建公司B自己的tax
- 其他account.move.create真正要求的最低数据

不要为了测试创建大量无关会计配置。

目标验证：

1. task.company_id = Company B；
2. worker执行时使用task.company_id上下文；
3. attempt公司来源仍然通过attempt.task_id.company_id，不给attempt新增company_id；
4. AI / parse / mapping执行不得错误使用env.company = Company A的数据；
5. bill创建必须属于Company B；
6. account.move.company_id == task.company_id；
7. Company A用户/上下文不得导致bill错误落入Company A；
8. Company A / Company B相关数据访问遵守现有record rule；
9. 不允许因为缺少purchase journal而skip。

如果产品代码本身导致multi-company测试失败：

不要修改业务代码。

记录新的：

CL-DEF-A-XXX
Category: IMPLEMENTATION_DEFECT

并保留失败测试。

如果只是fixture不足：
继续修fixture直到测试真实执行。

B-003只有在真实运行完整路径后才能PASS。

============================================================
五、CL-DEF-A-006处理规则
============================================================

当前已经确认：

CL-DEF-A-006
Category: IMPLEMENTATION_DEFECT

Description:
wd.ai.provider.config.api_key字段权限配置与冻结权限契约不一致，
导致Config Manager无法通过正常RPC字段元数据访问该配置字段。

本轮：

禁止修改provider业务模型；
禁止修改security XML；
禁止修改groups；
禁止修改api_key字段定义。

必须保留对应测试。

测试应该继续真实反映当前产品行为。

因此，在A-006尚未由独立FIX Intent修复前：

全套测试存在这一项产品失败是允许的，
但报告必须明确：

“TEST infrastructure本身已完成；当前失败来自已确认的产品实现缺陷A-006。”

不要为了让suite全绿：
- skip该测试；
- xfail该测试；
- 降低assert；
- 删除assert；
- 修改期望值；
- 绕过fields_get；
- 通过sudo伪造Config Manager正常权限。

该失败必须保留作为回归测试。

============================================================
六、已有通过测试不得破坏
============================================================

保留并继续运行已有：

B-002 stale worker
B-004 ACL / Record Rule
B-005 secret leakage
B-006 Adapter temporary/permanent error + retry
B-007 parse + mapping pipeline
B-008 PDF异常测试

以及原有历史测试。

不得为了修B-001/B-003破坏其他测试。

============================================================
七、测试执行要求
============================================================

修改完成后，先执行静态检查：

python3 -m compileall -q addons/ai_vendor_invoice

然后执行完整模块测试：

venv/bin/python3 odoo-bin \
  -c odoo.conf \
  --addons-path=/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo/addons,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons/queue,/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/addons \
  -u ai_vendor_invoice \
  --test-enable \
  --test-tags /ai_vendor_invoice \
  --stop-after-init \
  --log-level=info

如果当前odoo.conf已经定义数据库，不要擅自更换生产/正式数据库。

并发测试如果有独立tag，再单独执行：

--test-tags closure_concurrency

必须记录：

- 实际执行命令；
- tests总数；
- failures；
- errors；
- skipped；
- B-001结果；
- B-003结果；
- A-006预期产品失败结果。

============================================================
八、禁止为了“测试通过”修改测试语义
============================================================

严禁：

1. 把真实并发改成顺序调用；
2. 删除SELECT FOR UPDATE竞争验证；
3. 用mock替代数据库事务并发；
4. 因测试难运行直接skip B-001；
5. 因缺purchase journal继续skip B-003；
6. 修改业务代码让测试通过；
7. 修改冻结契约；
8. 修改A-006测试期望；
9. 将A-006标记为测试问题；
10. 使用sudo绕过本应验证的ACL/Record Rule；
11. 捕获AssertionError后仍让测试PASS；
12. 用try/except吞掉产品异常；
13. 为追求0 failure而降低断言；
14. 删除首轮已经发现问题的测试。

测试的目标是证明产品行为，不是制造绿色测试报告。

============================================================
九、新缺陷处理
============================================================

如果B-001或B-003真实运行后发现业务代码不符合冻结契约：

立即停止对该问题的进一步产品修复。

记录：

ID: CL-DEF-A-XXX
Category: A.IMPLEMENTATION_DEFECT
Description:
Baseline-ref:
Runtime Evidence:
Implementation Location:
Recommended Fix Intent:

继续完成其他不依赖该缺陷的测试。

不得在TEST Intent中修改产品代码。

如果发现的是测试自身问题：
允许继续修测试。

判断标准：

“产品行为错误” → A类实现缺陷，停止修改产品。

“测试没有正确构造冻结契约要求的场景” → 测试fixture问题，继续修测试。

============================================================
十、Git / 工作树约束
============================================================

开始前执行：

git status --short --branch

记录当前已有修改。

不要：
- reset其他Intent文件；
- checkout覆盖已有工作；
- clean未跟踪文件；
- revert其他人的修改；
- 自动commit；
- 自动push；
- 自动merge。

只修改本Intent授权的测试文件和sprint_log。

结束时再次执行：

git status --short --branch

明确列出本轮实际修改文件。

============================================================
十一、完成标准
============================================================

本轮TEST-INTENT-002补充执行完成的最低条件：

B-001：
必须真实多事务并发运行完成，不再因为fixture/thread启动问题失败。

B-003：
必须真实multi-company运行完成，不再因为缺purchase journal等fixture原因skip。

B-002/B-004/B-005/B-006/B-007/B-008：
不得出现新的测试基础设施失败。

A-006：
允许继续FAIL，因为这是已经确认的产品实现缺陷；
必须保留失败测试，等待独立FIX Intent修复。

因此本轮理想结果不是通过篡改测试得到“0 failure”，而是：

- 所有TEST_GAP已经获得有效运行证据；
- B-001/B-003真实执行；
- 测试基础设施自身没有阻塞；
- 剩余失败全部能够明确映射到已登记的产品实现缺陷。

============================================================
十二、最终工作报告格式
============================================================

完成后只输出工作报告，不要输出大段源码。

报告必须包含：

# TEST-INTENT-AI-VENDOR-002 Supplemental Execution Report

## 1. Scope
说明本轮只处理B-001/B-003测试基础设施，不修改业务代码。

## 2. Changed Files
逐个列出实际修改的测试/history文件。

## 3. B-001 Concurrency
- 原失败原因
- 根因
- fixture如何修正
- 实际并发事务结构
- SELECT FOR UPDATE运行证据
- 最终account.move数量
- PASS / FAIL

## 4. B-003 Multi-Company
- 原skip原因
- 新建了哪些最小fixture
- task.company_id
- worker company context
- bill.company_id
- 隔离验证
- PASS / FAIL

## 5. Existing Tests
分别报告：
B-002
B-004
B-005
B-006
B-007
B-008

## 6. Known Product Defects
至少保留：

CL-DEF-A-006
Category: IMPLEMENTATION_DEFECT
Status: NOT FIXED BY TEST INTENT

并列出运行时失败证据。

如果发现新的A类缺陷，也在这里登记。

## 7. Runtime Test Evidence
列出：
- compileall
- full Odoo test suite
- concurrency suite
- test count
- failure
- error
- skipped

## 8. Git Diff Scope
证明没有修改：
models/services/adapters/security/views等产品实现代码。

## 9. Final Result

只能使用：

TEST_INTENT_PASS
或
TEST_INTENT_BLOCKED

判断规则：

TEST_INTENT_PASS：
B-001/B-003等测试基础设施缺口全部解决，所有要求场景都有真实运行时证据。
允许因为已登记A类产品缺陷导致对应回归测试FAIL，但必须明确说明TEST Intent本身已经完成。

TEST_INTENT_BLOCKED：
仍有要求的测试场景因为fixture、并发harness、环境构造等原因没有真正执行。

最后明确写：

是否可以结束TEST-INTENT-AI-VENDOR-002，
以及下一步需要进入哪些独立FIX Intent。

============================================================
十三、执行原则
============================================================

先读取现有测试和失败日志，理解首轮为什么失败，再修改。

不要重新设计业务架构。
不要扩大Intent。
不要修改产品实现。
不要追求表面全绿。

本轮核心目标只有一句话：

“把B-001和B-003从‘测试没有真正跑起来’变成‘测试真实执行并产生可信证据’；如果真实执行证明产品有bug，就记录A类缺陷，而不是在TEST Intent里修。”