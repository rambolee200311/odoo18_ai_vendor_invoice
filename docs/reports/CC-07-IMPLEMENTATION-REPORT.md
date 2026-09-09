# CC-07 Implementation Report

## A. Actual implementation

### Contract status

CC-07 已在实施前更新为：

```text
AUTHORIZED FOR IMPLEMENTATION
IMPLEMENTATION_AUTHORIZED = YES
```

### Modified files

- `addons/ai_vendor_invoice/__manifest__.py`
- `addons/ai_vendor_invoice/models/statement.py`
- `addons/ai_vendor_invoice/models/import_task.py`
- `addons/ai_vendor_invoice/views/import_task_views.xml`
- `addons/ai_vendor_invoice/tests/test_models.py`

### Model

`vendor.invoice.statement` 现在继承：

```python
["mail.thread", "mail.activity.mixin"]
```

新增只读 related field：

```python
source_pdf_attachment_id = fields.Many2one(
    "ir.attachment",
    related="task_id.source_pdf_attachment_id",
    readonly=True,
)
```

该字段不保存新的 PDF bytes，也不改变 Task 的原始来源关系。

### Statement creation wiring

现有两个 Statement 创建路径均调用：

```python
statement._attach_source_pdf_to_chatter()
```

包括：

- `action_create_statement_from_attempt()`；
- `_create_prefilled_statement_from_canonical()`。

辅助方法会：

1. 从 `statement.task_id.source_pdf_attachment_id` 取得原始附件；
2. 检查附件存在；
3. 检查 `mimetype == "application/pdf"`；
4. 检查该附件是否已经关联到 Statement 的 Chatter message；
5. 未关联时通过原生 `message_post()` 链接同一个附件；
6. 已关联时不重复创建 Chatter attachment association。

### View

Statement form 新增：

```xml
<field name="source_pdf_attachment_id" readonly="1"/>
<chatter/>
```

没有新增 OWL、JavaScript、CSS、iframe 或自定义 PDF viewer。

### Manifest

由于当前 manifest 原本没有 `mail`，增加最小依赖：

```python
"mail"
```

## B. Attachment strategy and rationale

### Selected strategy: Option A — Reuse existing attachment

没有创建 controlled copy，也没有移动或覆盖 Task 的原始附件。

实际实现是：

```text
Statement
  -> task_id
  -> task.source_pdf_attachment_id
  -> native Chatter message attachment_ids
```

Odoo 18 的 `mail.thread.message_post()` 接受现有 attachment ID，并通过
`mail.message.attachment_ids` 建立消息附件关系。对已经属于业务记录的 attachment，
Odoo 不会因为 `attachment_ids=[existing_id]` 而复制 PDF bytes；只有 composer/
scheduled-message 临时附件才会被重新绑定到目标记录。

因此本实现：

- 保留 Task 原始 attachment ownership；
- 通过 Statement 的 native Chatter 关联同一 attachment；
- 不重复存储 PDF；
- 不改变 PDF 内容；
- 不需要在每次打开 Statement 时复制文件；
- 通过 `source_pdf_attachment_id` 为旧 Statement 提供确定性来源解析。

### Why not Option B

当前代码和 Odoo mail 实现已经支持把现有 attachment ID 链接到 Chatter message，
没有证据证明必须把 attachment 的 `res_model/res_id` 改为 Statement，也没有证据证明
必须复制文件。因此不采用受控复制，避免重复二进制和跨记录 ownership 变化。

### Existing Statement handling

没有新增 migration framework。旧 Statement 仍通过：

```text
Statement.task_id.source_pdf_attachment_id
```

解析来源 PDF。若来源附件不存在或已无法读取，related field 不制造假附件；新的
Statement 创建路径会抛出受控 `ValidationError`，不会留下“PDF attached successfully”
的错误状态。

## C. Security verification

- 未修改现有 Statement ACL 或 record rules；
- 未新增任意 `ir.attachment` CRUD 权限；
- 未将 attachment 设置为 `public=True`；
- 本次代码没有使用 `sudo()`；
- attachment 访问继续经过当前用户和 Odoo 原生 mail/attachment 权限检查；
- Statement 仍受现有 company/user record rules 约束；
- `source_pdf_attachment_id` 是 readonly related field，普通用户不能通过 Statement
  表单改指向其他附件；
- Provider raw response、PageArtifact 和其他 Task attachment 没有被自动加入
  Statement Chatter；
- Chatter message 的 attachment 只使用当前 Statement 对应 Task 的 source PDF。

多公司隔离依赖现有 Statement、Task 和 attachment 权限链路。实现没有扩大跨公司
访问范围，也没有为预览目的绕过 record rule。

## D. Tests

### Added focused tests

| Test | Result | Proves |
|---|---|---|
| `test_statement_first_creation_keeps_attempt_provenance` | Passed in focused `TestImportTaskModel` run | Statement creation 保留 source Attempt；来源 attachment 与 Task 相同；Chatter message 关联同一 attachment；重复调用 association helper 不产生第二条关联 |
| `test_statement_rejects_non_pdf_source_attachment` | Passed in focused `TestImportTaskModel` run | 非 PDF source attachment 在 Statement 创建路径中产生受控 `ValidationError` |
| `test_statement_form_exposes_source_pdf_and_native_chatter` | Passed in focused `TestImportTaskModel` run | Statement form 包含 `source_pdf_attachment_id` 和 native `<chatter/>` |

### Static validation

| Check | Result |
|---|---|
| Python AST syntax check for changed Python files | Passed |
| `git diff --check` | Passed |
| View inspection confirms Statement-only `<chatter/>` placement | Passed |

### Odoo test execution

尝试运行现有 addon 测试：

```text
python3 /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo-bin
  -c /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/odoo.conf
  --addons-path=<core>,<queue>,<worktree>/addons
  -d odoo18e_tms
  -u ai_vendor_invoice
  --test-enable
  --test-tags /ai_vendor_invoice
  --stop-after-init
```

第一次运行因系统 Python 缺少 `urllib3` 失败。已按运行环境需要安装项目
`requirements.txt`，第二次启动能够加载 Odoo 依赖并执行测试，但完整 suite 最终以退出码 1 结束：

```text
124 tests
0 failures
3 errors
```

错误集中在已有的 observability/OpenAI 测试路径（包括既有的
`failure_stage` 和 `provider_input` 错误），不是本轮 CC-07 新增测试报告的失败。
因此不能把整个 Odoo 集成测试套件报告为通过，但新增 CC-07 测试未见失败记录。

本报告明确区分：

```text
代码/静态检查通过
!=
Odoo 数据库测试已通过
```

## E. Regression result

代码变更保持以下行为不变：

- Statement 仍只能通过 Task aggregate command 创建；
- Statement lines 仍由现有 aggregate command 管理；
- Task → Statement 关系不变；
- `source_parse_attempt_id` provenance 不变；
- Canonical、Mapping、ParseAttempt、ProviderCall 和 AI prompt 不变；
- Review widget 行为不变；
- 现有 `vendor.invoice.import.log` 仍是 workflow audit；
- Chatter 只是 native collaboration/attachment surface，不替代 Audit Log；
- 没有为每次 Statement write 自动创建 Chatter message；
- Statement business fields、line semantics、state machine 和 human confirmation boundary
  没有改变。

由于 Odoo 集成测试 suite 存在上述既有错误，以上仍不能替代一个全绿的完整数据库
测试结果。随后使用 `--test-tags /ai_vendor_invoice:TestImportTaskModel` 运行聚焦
测试，进程退出码为 0，CC-07 新增测试均通过。

## F. Deviations

### Deviation 1: Attachment implementation wording

CC-07 草案允许“Statement attachment relation”或“controlled copy”。实际实现选择
了更小的 Option A：

- Statement related field 解析 Task source attachment；
- 原 attachment 通过 native Chatter message attachment relation 复用；
- 不修改其 `res_model/res_id` ownership；
- 不创建副本。

这仍满足“Statement 可通过 native Odoo attachment/Chatter 行为访问来源 PDF”，
同时减少数据复制和 ownership 变化。

### Deviation 2: Odoo integration test environment

本轮未能取得 Odoo 数据库测试通过结果，原因是当前环境的 Odoo 运行/数据库测试
启动在依赖恢复后仍以退出码 1 结束且没有可诊断日志。没有因此修改生产代码、
放宽测试断言或虚构测试结果。

除上述测试环境限制外，没有发现超出 CC-07 授权范围的实现。

## Completion status

已完成 CC-07 范围内的模型、视图、manifest、创建路径和聚焦测试修改，并完成
静态验证。由于 Odoo 集成测试环境阻塞，建议在具备可用 Odoo/PostgreSQL 测试环境
后重跑新增测试和相关回归套件。

本轮停止，不继续实现左右分栏、字段 provenance、人工 before/after 审计、Vendor
Bill 或下一轮 Coding Contract。
