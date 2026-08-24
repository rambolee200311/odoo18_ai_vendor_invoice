# Human Review UAT Guide

## 0. 启动前

1. 填写环境清单并确认 `UAT_READY`；
2. 记录 Git Commit、Git Dirty、Module Version、Database；
3. 确认本实例使用的 Sample ID；
4. 确认截图、日志和记录不包含 API key 或敏感 PDF；
5. 确认代码基线在实例期间不变。

如果环境未 Ready，不创建 UAT 实例，直接记录 `READINESS_BLOCKED`。

## 1. 登录与角色

分别确认：

- AI Invoice User：任务和解析结果查看/发起权限；
- AI Invoice Reviewer：人工复核和生成草稿账单权限；
- AI Invoice Config Manager：Provider、mapping、阈值和系统配置权限。

普通用户不得看到 Provider API key 或 raw AI response。

## 2. 基础配置

使用 Config Manager 确认：

1. Provider name、URL、model、timeout、retry；
2. 供应商别名、产品关键词、税码文本、币种文本 mapping；
3. 普通/关键 confidence threshold；
4. fallback product；
5. task timeout 和 cron interval；
6. 目标公司 purchase journal、供应商、产品、币种和税码。

不要在记录中填写 API key 明文。

## 3. 创建并解析任务

1. 使用 User 或 Reviewer 进入 `Accounting → Invoicing → AI Vendor Invoice Imports`；
2. 新建任务；
3. 每次只上传一个 Manifest 指定的 PDF；
4. 选择 Provider 并保存；
5. 发起解析；
6. 记录 task ID；
7. 观察 task 进入 `parsing`；
8. 观察 ParseAttempt 的 `queued → running → success/failed`；
9. 单张发票应进入 `awaiting_review`；
10. 多张独立发票应进入 `error_split_required`；
11. 检查审计日志、attempt、mapping 候选和 raw response 引用。

PDF 多页场景要确认全部页面属于同一次解析上下文，不把每页当成一张业务发票。

## 4. 人工复核

1. 使用 Reviewer 打开 `awaiting_review` task；
2. 查看供应商、编号、日期、币种、金额和费用行；
3. 查看 confidence 提示和 mapping 候选；
4. 修改至少一个 header 字段和一个明细字段；
5. 点击“应用 AI 候选”；
6. 确认已人工编辑字段没有被覆盖；
7. 对 HR-005 确认金额不平只产生 warning；
8. 对 HR-006 仅验证冻结契约要求税码的应税明细；
9. 保存并确认 `human_modify` 审计记录；
10. 重跑场景确认新 attempt 不覆盖人工结果。

## 5. 生成草稿账单

仅对 HumanReviewResult 完整且人工复核完成的任务执行：

1. 点击“确认复核并生成草稿账单”；
2. 确认只生成一张 `in_invoice` 草稿；
3. 确认账单公司等于 task.company；
4. 确认原始 PDF 已挂载到账单；
5. 确认 task 原附件引用仍存在；
6. 确认 task 进入 `bill_generated`；
7. 确认 `bill_create` 审计日志；
8. 再次执行用户层重复操作，确认被幂等保护拒绝；
9. 确认没有孤立账单。

用户层重复操作不等同于并发事务验证；并发和 stale-worker 由自动化测试负责。

## 6. 异常观察

- HR-008A：使用受控错误 Provider，记录业务可观察错误；
- HR-008B：只引用自动化 timeout 证据，不杀 worker、不改数据库、不操纵时间；
- 未定义的 PDF 异常到 Task state 映射只记录，不自行新增状态或解释。

## 7. 记录与结束

1. 每个实例复制 Case Template；
2. 每个 Case 写实际结果和证据路径；
3. 发现问题只分类，不现场修复；
4. 代码发生变化时关闭当前实例并重新建实例；
5. 使用 Summary Template 输出 `UAT_READY` 或 `UAT_BLOCKED`。
