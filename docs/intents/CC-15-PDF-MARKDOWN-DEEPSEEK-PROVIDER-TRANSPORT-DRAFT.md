# CC-15 — PDF Markdown DeepSeek Provider Transport

**Status：`FROZEN — APPROVED FOR IMPLEMENTATION`**  
**起草日期：2026-09-14**  
**审查对象：** PDF → Markdown → DeepSeek → Canonical JSON

## 1. Contract Goal

增加一条基于 Markdown 的 PDF Provider transport：

```text
Statement source PDF
→ PDF validation
→ PDF → Markdown
→ provider prompt selected by document_input_mode
→ DeepSeek JSON
→ Canonical JSON validation
→ existing mapping / Statement projection
```

本 Contract 只改变 AI 输入 transport 和 DeepSeek 解析适配，不改变：

- Statement 业务 authority；
- Task / ParseAttempt 生命周期；
- Statement-first 入口；
- Batch orchestration；
- Canonical JSON 业务字段语义；
- Candidate projection、人工审核、Confirm 或 Vendor Bill 流程。

## 2. Frozen Decisions

以下决策已冻结并作为实施边界：

1. 保留 `native_pdf`，用于 GPT/OpenAI native PDF 路线；
2. `document_input_mode` 字段继续显示；
3. 只移除 `rendered_images` 的新配置选项；
4. 后端旧的 rendered-images 兼容代码暂时保留；
5. 增加 `markdown` 选项；
6. Markdown 只在内存中传递，不持久化中间文件；
7. Prompt 必须按 `document_input_mode` 匹配，不能仅按 Provider 名称硬编码；
8. 当前实施范围只覆盖用户配置的 GPT/OpenAI 和 DeepSeek；
9. 暂不更新 TDD。

## 3. Scope

### 3.1 Included

- Provider 配置增加 `markdown`；
- Provider 配置不再向用户显示 `rendered_images`；
- 保留 `native_pdf`；
- 增加 PDF → Markdown preprocessor；
- 增加 `ProviderInput(mode="markdown")`；
- 增加 DeepSeek Markdown adapter；
- 使用冻结的 V4 Prompt；
- 对 DeepSeek response 执行 JSON parse、Canonical normalization 和 Schema validation；
- 记录 input mode、Prompt version/checksum、PDF checksum、Markdown checksum；
- 增加 focused tests 和 native PDF regression tests。

### 3.2 Explicitly Excluded

- 不删除现有 rendered-images 后端兼容代码；
- 不修改 Statement、Task、ParseAttempt 状态机；
- 不修改 Canonical Schema；
- 不实现 Provider fallback；
- 不把 Markdown 写回 source PDF；
- 不把 Markdown 结果直接写入 Confirmed Statement；
- 不同时向同一次 DeepSeek 请求发送 PNG 和 Markdown；
- 不重新设计人工审核或 Vendor Bill 创建；
- 不更新 TDD；
- 不实现 Claude Markdown 路线；
- 不实现 OpenAI Markdown 路线。

## 4. Provider Input Mode Contract

### 4.1 New configuration options

`wd.ai.provider.config.document_input_mode` 对新建或编辑配置只显示：

```text
native_pdf
markdown
```

`rendered_images` 不再是新的 Selection/UI 选项。

注意：这不等于立即删除后端兼容能力。已有数据库记录或旧调用可能仍带有
`rendered_images`，ProviderInput、旧 adapter 和旧测试暂时保留兼容处理。

### 4.2 Capability matrix

| Provider | `native_pdf` | `markdown` | `rendered_images` |
|---|---:|---:|---:|
| GPT/OpenAI | Supported | Out of scope | Legacy backend only |
| DeepSeek | Out of scope | Supported | Legacy backend only |
| Claude | Out of scope | Out of scope | Legacy backend only |

如果 Provider adapter 不支持配置的 input mode，必须显式失败，不得静默切换
到另一种 mode。

## 5. Mode-specific Prompt Contract

Prompt 选择必须由 `document_input_mode` 决定：

```text
native_pdf
→ OpenAI native-PDF instructions

markdown
→ DeepSeek V4 Markdown Prompt

rendered_images
→ legacy Vision Prompt，仅供后端兼容路径
```

禁止：

- 根据 Provider 名称无条件覆盖 `document_input_mode`；
- 将 Markdown 拼接到旧 Vision Prompt 后继续发送图片；
- DeepSeek Markdown 路径发送 PNG image payload；
- OpenAI native PDF 路径改用 DeepSeek Prompt。

### 5.1 V4 Prompt invariants

V4 必须保留：

- nested `header` / `line` value-confidence structure；
- transport/business record line semantics；
- 一个独立 transport/business record 对应一个顶层 line；
- nested surcharge 放入 `charge_details`；
- shipment/loading/unloading/cargo/reference preservation；
- 只有明确标注的 invoice number 才能进入 `invoice_number`；
- header totals 必须来自明确标注的 summary area；
- 不计算、不推断、不 reconcile 缺失金额；
- Markdown layout、表格、分页和 OCR artifact 的保守重建；
- `is_multi_invoice`；
- supplier name-only rule。

Supplier rule：

```text
supplier_raw_text must contain only the supplier name.
Do not include address, phone, email, VAT number, or contact information.
If the name and address appear on the same line or block, keep only the name.
```

Prompt 必须保存：

- Prompt version；
- Prompt checksum；
- input mode；
- model name。

## 6. Markdown Preprocessor Contract

输入：

```text
PDF bytes
```

处理：

```text
readable PDF validation
→ encrypted/empty/page-count checks
→ pymupdf4llm conversion
→ ProviderInput(mode="markdown")
```

输出中的 Markdown 只存在于当前 ParseAttempt 的内存调用链中，不创建
Markdown attachment。

### 6.1 Required metadata

至少记录：

- source attachment id；
- source PDF SHA-256；
- page count；
- source MIME type；
- Markdown character count；
- Markdown SHA-256；
- converter version；
- conversion duration。

### 6.2 Error contract

以下错误必须显式失败，并进入现有 ParseAttempt error handling：

- invalid PDF；
- empty PDF；
- encrypted PDF；
- Markdown conversion failure；
- unsupported input mode；
- Provider request failure；
- JSON parse failure；
- Canonical Schema validation failure。

Markdown conversion 失败不得继续调用 Provider。

## 7. ProviderInput Contract

必须支持：

```python
ProviderInput(
    mode="markdown",
    source={
        "attachment_id": 123,
        "page_count": 2,
        "mime_type": "application/pdf",
        "checksum": "...",
        "markdown_checksum": "...",
    },
    markdown_text="...",
)
```

约束：

- `markdown` 必须有非空 `markdown_text`；
- `markdown` 不得同时携带 `images`；
- `markdown` 不得同时携带 `document_bytes`；
- `native_pdf` 继续只携带 `document_bytes`；
- `rendered_images` 后端兼容约束保持不变；
- 非法组合必须在构造阶段显式失败。

## 8. DeepSeek Markdown Adapter Contract

DeepSeek Markdown adapter 必须：

- 只接收 `ProviderInput.mode == "markdown"`；
- 使用 V4 Prompt；
- 使用 `temperature=0`；
- 使用 JSON response mode；
- 将 Markdown 作为 user content；
- 不发送 PNG image payload；
- 不调用 OpenAI native PDF file upload；
- 对返回值执行：

```text
JSON parse
→ provider response shape validation
→ Canonical normalization
→ production Canonical Schema validation
→ existing mapping
```

以下情况必须失败：

- response 不是 JSON；
- response 缺少 required header；
- line shape 不合法；
- 额外字段导致 provider contract invalid；
- 日期、金额或 currency 无法规范化；
- `is_multi_invoice` 类型错误。

## 9. Parse Service Integration

`run_parse_attempt()` 根据配置 mode 分派：

```text
native_pdf
→ prepare native PDF input
→ OpenAI native_pdf adapter

markdown
→ prepare Markdown input
→ DeepSeek Markdown adapter
```

成功后仍使用现有：

- raw response persistence；
- Canonical snapshot persistence；
- mapping；
- Draft Statement projection；
- Task success/error state；
- audit and observability。

`markdown` 和 `native_pdf` 都必须进入现有 Draft Statement projection；
Confirmed 或已创建 Vendor Bill 的业务保护规则保持不变。

## 10. Observability and Security

每个 Markdown ParseAttempt 至少记录：

- `input_mode = markdown`；
- source PDF checksum；
- Markdown checksum；
- Markdown character count；
- page count；
- Provider/model；
- Prompt version/checksum；
- Canonical schema checksum；
- token usage（如果 Provider 返回）；
- latency；
- retry count；
- conversion duration；
- failure stage；
- raw Provider response；
- normalized Canonical result。

不得记录：

- API key；
- authorization header；
- PDF 全文；
- Markdown 全文到生产日志。

## 11. Testing Contract

必须覆盖：

### ProviderInput

- Markdown input 接受；
- Markdown 拒绝 images；
- Markdown 拒绝 document bytes；
- native PDF regression；
- rendered-images legacy compatibility；
- 新配置 Selection 不再包含 rendered-images。

### Preprocessor

- valid PDF 转 Markdown；
- empty PDF；
- invalid PDF；
- encrypted PDF；
- conversion failure；
- checksum、字符数和 page count 正确；
- 不创建 attachment。

### DeepSeek adapter

- V4 Prompt 被发送；
- Prompt 根据 mode 选择；
- JSON response mode；
- temperature 为 0；
- 不发送 image payload；
- malformed JSON 失败；
- Canonical validation failure 失败；
- successful response 进入现有 mapping。

### Integration

- Markdown ParseAttempt 成功；
- raw/canonical evidence 持久化；
- Draft Statement projection 成功；
- native PDF 路径不回归；
- unsupported mode 显式失败；
- Confirmed/Bill Created Statement 不被覆盖。

## 12. Acceptance Criteria

CC-15 只有同时满足以下条件才算完成：

- `document_input_mode` 字段仍可见；
- 新配置不再显示 `rendered_images`；
- rendered-images 后端兼容代码仍可运行；
- `markdown` mode 可从 source PDF 生成；
- Markdown 中间数据不持久化为 attachment；
- DeepSeek Markdown route 可执行；
- OpenAI `native_pdf` baseline 未被破坏；
- Prompt 由 `document_input_mode` 匹配；
- V4 Prompt version/checksum 可审计；
- ParseAttempt、mapping、Statement projection 规则保持不变；
- focused tests 全部通过；
- 既有模块回归测试全部通过。

## 13. Non-goals

以下事项不在本 Contract 授权范围内：

- 生产 Provider fallback；
- 自动切换 GPT 与 DeepSeek；
- Claude Markdown adapter；
- OpenAI Markdown adapter；
- Prompt tuning beyond V4；
- 修改 TDD；
- 提升或承诺新的业务准确率门槛；
- 提交、合并或推送代码。

## 14. Decision

当前状态：

> **FROZEN — APPROVED FOR IMPLEMENTATION**

已确认的实施边界：

1. 移除 `rendered_images` 的新配置选项；
2. 保留 rendered-images 后端兼容代码；
3. 实施 PDF → Markdown → DeepSeek 路线；
4. Markdown 只在内存中传递，不持久化 attachment；
5. 当前实施 Provider 仅为 GPT/OpenAI 与 DeepSeek；
6. 暂不更新 TDD。

本 Contract 授权进入 CC-15 实施。它不授权提交、合并、推送或生产切换。
