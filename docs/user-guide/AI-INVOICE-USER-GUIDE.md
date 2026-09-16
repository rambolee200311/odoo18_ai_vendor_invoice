# AI Invoice 用户操作手册

**版本**：User Guide v1.2
**更新日期**：2026-09-16

## 修订记录

- v1.1：改为 Statement-first 流程，新增 Statement 内 AI / Task 页面；
  Run AI 成功后自动将结果填充到 Statement；新增批量导入的批次级 Supplier
  选择和 Profile 说明。
- v1.2：新增 Confirmed Statement 创建 Draft Vendor Bill、幂等重建和税务事实
  边界说明；明确 AI 不直接生成 Odoo 税码。
- v1.0：原始 AI Invoice 操作说明。

## 1. 进入 AI Invoice

登录 Odoo 后，从应用菜单进入 **AI Invoice**。

主要菜单：

- **Imports**：查看技术导入任务；
- **Statements**：创建和审核供应商发票 Statement；
- **Configuration**：维护 Provider 等配置。

正常业务流程从 **Statements** 开始，不需要先创建 Import Task。

## 2. 创建 Statement

1. 打开 **Statements**。
2. 点击 **New**。
3. 在 Statement 的 **AI / Task** 页面上传供应商发票 PDF。
4. 保存 Statement。

保存前不能运行 AI。上传后，页面应保留用户选择的原始 PDF 文件名。

识别前确认：

- PDF 内容清晰且未加密；
- 文件确实是供应商发票；
- 当前用户可以使用所选 Provider；
- 没有重复导入同一 PDF。

## 3. 配置并运行 AI

在 Statement 的 **AI / Task** 页面：

1. 选择 **AI Provider**；
2. 选择执行模式：
   - **Asynchronous**：默认，提交后台队列处理；
   - **Synchronous**：等待当前请求完成，适合测试或小文件；
3. 点击 **Run AI**。

Run AI 后仍停留在当前 Statement 页面，不会自动跳转到独立 Task 页面。
页面会显示 Task、AI State、AI Status、当前 Attempt 和用户可读错误。

解析成功后，AI 结果会自动填充当前 Draft Statement，包括供应商、发票号、
日期、币种、金额和明细。正常流程不需要再点击 Apply AI Candidate。

## 4. 核对解析结果

解析完成后，在 Statement 页面核对：

### 基本信息

- Supplier；
- Invoice Number；
- Invoice Date；
- Currency；
- Subtotal；
- Total Tax；
- Total Amount；
- Overall Tax Rate。

### 明细

逐行检查：

- Description；
- Quantity；
- Price Unit；
- Tax Rate；
- Tax Amount；
- Amount；
- Total Amount；
- Reconciliation Clue。

AI 只是辅助录入。原始 PDF 是最终核对依据，用户必须人工检查和修正
供应商、金额、税额及每一条明细。

Tax Rate 和 Tax Amount 是发票税务事实，不是 Odoo 税码。AI 不直接创建
`account.tax` 或填写税码 ID；税码选择或受控创建发生在后续 Vendor Bill
生成阶段。

## 5. 确认和创建 Vendor Bill

完成核对后：

1. 确认所有明细正确；
2. 按页面要求完成 Check；
3. 点击 **Confirm**；
4. 点击 **Create Bill** 创建 Vendor Bill。

创建的 Vendor Bill 必须保持 Draft。系统根据已 Confirmed Statement 的税务
事实选择或受控创建 Purchase Tax；系统不会从 Provider response 或原始 AI
结果绕过 Statement 直接生成会计行。

重复点击 **Create Bill** 不会创建第二张 active Vendor Bill，而是复用当前
Statement 已关联的 Draft Vendor Bill。若当前 Vendor Bill 已取消，Statement
仍保持 Confirmed，并允许重新创建一张新的 Draft Vendor Bill；旧 Bill 作为
历史记录保留。

Confirmed Statement 不能取消。只有 Draft Statement 可以点击 **Cancel**；
取消后不再进入确认和建单流程。

## 6. 批量导入供应商发票

需要一次处理多张同一供应商发票时：

1. 打开 **Start Batch Import**；
2. 选择 **Supplier**；
3. 选择 **AI Provider**；
4. 上传一张或多张 PDF；
5. 点击 **Start Batch**。

例如批量处理 UPS 发票时选择：

```text
Supplier: United Parcel Service Nederland B.V.
```

系统会把该供应商作为批次级可信输入，并为批次内每个 Statement/Task
使用对应的 Extraction Profile。UPS 使用 `ups_transport`；不选择 Supplier
时使用 Generic Profile。

一个 Batch 应只包含同一供应商的发票。UPS、DHL 等不同供应商请拆分为不同
Batch，不能依赖当前 AI Attempt 自己识别的供应商来切换同一次解析的 Profile。

## 7. 常见状态

### Statement 状态

- **Draft**：草稿，可以上传、运行 AI、编辑和取消；
- **Confirmed**：已完成人工确认；
- **Bill Created**：已创建 Vendor Bill；
- **Cancelled**：已取消。

### AI 状态

- **To Parse**：等待执行；
- **Parsing**：正在解析；
- **Parsed / Completed**：解析成功，结果已自动填充 Statement；
- **Error**：解析失败，需要查看错误摘要；
- **Cancelled**：AI Task 已取消。

Draft Statement 的 Task 如果处于 `Error` 或已经 `Parsed`，仍可从
**AI / Task** 页面重新点击 **Run AI**。重跑会保留同一个 Task 并创建新的
ParseAttempt；已确认、已建单或已取消的 Statement 不应重新运行 AI。

## 8. 文件和技术信息

Statement 的 AI / Task 页面显示：

- 当前 Source PDF；
- 用户上传的原始 File Name；
- Provider；
- Execution Mode；
- AI 状态和错误摘要。

重复保存同一 PDF 不会创建第二个源附件，也不会因为 Run AI 改写原始文件名。

**Technical Details** 是可选的高级诊断入口。普通用户不需要进入独立
Import Task 页面完成正常发票流程。

## 9. 问题处理

- 如果 Run AI 按钮不可用，请先保存 Statement、上传 PDF 并选择 Provider；
- 如果状态为 Error，先查看页面上的错误摘要；
- 不要反复提交相同 PDF；
- 不要修改原始 PDF 来绕过重复检查；
- 如果 AI 结果不正确，请在 Statement 中人工修正后再 Confirm；
- 如果发现队列或 Provider 技术问题，再请管理员查看 Technical Details。
