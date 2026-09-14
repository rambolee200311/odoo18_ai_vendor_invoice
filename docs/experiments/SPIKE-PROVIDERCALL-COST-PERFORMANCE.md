# Spike: ProviderCall Cost & Performance

## 1. Objective

本 Spike 只读调查当前 ProviderCall 及其关联的 Task、ParseAttempt、ProviderConfig、PageArtifact 和审计数据，回答：

> 当前数据是否已经足够支持实际 Provider 成本、耗时、调用次数和失败率分析？如果不足，具体缺少什么？

本次不修改生产代码，不新增 ProviderCall 字段、成本模型、价格表、Dashboard、fallback 或 Provider 选择策略，也不重新调用真实 AI。

## 2. Current ProviderCall data model

### 2.1 数据粒度

当前数据粒度明确区分：

```text
Task
  -> ParseAttempt
      -> ProviderCall 1
      -> ProviderCall 2
      -> ProviderCall 3
```

一次 ParseAttempt 可能包含多个 ProviderCall：

- 多页图片输入可能按页批次产生多个 call；
- Provider timeout 或 retry 会产生新的 ProviderCall；
- 每个 ProviderCall 有独立 `call_sequence` 和 `retry_index`。

因此，调用次数和 Provider 成本必须以 **ProviderCall** 为基础粒度；Attempt 和 Task 只能作为聚合粒度。

### 2.2 ProviderCall 已保存字段

[`models/provider_call.py`](../../addons/ai_vendor_invoice/models/provider_call.py) 当前保存：

- `parse_attempt_id`
- `company_id`（从 Task 关联）
- `page_artifact_id` / `page_artifact_ids`
- `input_page_count`
- `input_mode`
- `input_document_type`
- `rendered_image_count`
- `returned_page_count`
- `failure_page_no`
- `call_sequence`
- `retry_index`
- `provider_snapshot`
- `model_snapshot`
- `effective_prompt_snapshot`
- `request_started_at`
- `response_received_at`
- `http_status`
- `outcome`
- `validation_status`
- `failure_stage`
- `safe_error_summary`
- `raw_response_attachment_id`
- `page_extraction_result`

ProviderCall 的数据库约束包括：

```text
unique(parse_attempt_id, call_sequence)
call_sequence > 0
retry_index >= 0
```

### 2.3 关联数据

ParseAttempt 保存：

- `task_id`
- `sequence`
- `provider_config_id`
- `model_name_snapshot`
- `submitted_at`
- `started_at`
- `completed_at`
- `finished_at`
- `attempt_internal_retry_count`
- `provider_call_ids`
- 状态和失败阶段

ProviderConfig 保存：

- Provider 显示名称；
- API base URL；
- 当前 `model_name`；
- 输入模式；
- retry 上限；
- HTTP timeout。

PageArtifact 保存传给 Provider 的图片页、页号、PNG checksum、字节数和渲染时间。Native PDF 路径保存输入模式为 `native_pdf`，图片路径保存为 `rendered_images`。

## 3. Field availability matrix

状态定义：

- `PERSISTED`：作为稳定的数据库字段或受控 JSON 证据保存；
- `DERIVABLE`：可以由现有持久化字段可靠计算；
- `MISSING`：当前没有可靠数据；
- `NOT APPLICABLE`：当前设计不使用该能力；
- `UNKNOWN`：代码或现有数据不足以确认。

| 分析项 | 当前状态 | 现有证据 | 限定 |
|---|---|---|---|
| Provider 名称 | `PERSISTED` | ProviderCall `provider_snapshot`；Attempt `provider_config_id` | 保存的是调用时名称快照，不受后续配置改名影响 |
| Provider 配置关联 | `PERSISTED` | ProviderCall → ParseAttempt → Task；Attempt → ProviderConfig | 可按公司、Task、Attempt、Provider 聚合 |
| 实际模型名称 | `PERSISTED` | ProviderCall `model_snapshot`；Attempt `model_name_snapshot` | 是调用/Attempt 创建时的模型标识 |
| 独立模型版本 | `MISSING` | 没有独立 `model_version` 或 provider release 字段 | 只能按模型标识分组，不能证明模型内部版本 |
| 请求开始时间 | `PERSISTED` | ProviderCall `request_started_at` | 是开始 ProviderCall 请求的时间点，不是 Task 提交时间 |
| 响应接收时间 | `PERSISTED` | ProviderCall `response_received_at` | 仅在 `response_received=True` 时写入 |
| ProviderCall API 请求耗时 | `DERIVABLE` | `response_received_at - request_started_at` | 失败且未收到响应的 call 可能没有结束时间 |
| 页面批次诊断耗时 | `PERSISTED` | Attempt `provider_diagnostics` 中的 `elapsed_ms` | 是 adapter/page-batch 诊断，不应当冒充完整 ProviderCall duration |
| ParseAttempt 总耗时 | `DERIVABLE` | `started_at` / `completed_at` 或 `finished_at` | 是 Attempt worker 生命周期，不等于 API 请求耗时 |
| Task 端到端耗时 | `DERIVABLE` | Task 创建/状态时间若有完整记录可计算 | 当前没有确认一套专门的 Task timing contract，需避免用 Attempt 时间代替 |
| 输入模式 | `PERSISTED` | ProviderCall `input_mode` | 可区分 `rendered_images` 与 `native_pdf` |
| 输入页数 | `PERSISTED` | `input_page_count` | native PDF 也记录页数；不能直接等同计费 token |
| 渲染图片数量 | `PERSISTED` | `rendered_image_count`、PageArtifact 关系 | Native PDF 通常不是图片计数路径 |
| 输入字节数 | `PERSISTED` / `DERIVABLE` | PageArtifact `byte_size`；native PDF bytes 不在 ProviderCall 字段中 | 图片路径较完整；native PDF 计费输入大小不能由此统一恢复 |
| Provider usage | `MISSING` | ProviderCall 没有 usage JSON 或 token 字段；adapter 未将 usage 写入 Call | 不能可靠获得 Provider 返回的 usage |
| 输入 token | `MISSING` | 无持久化字段 | 不能按 Provider/Model 统计 |
| 输出 token | `MISSING` | 无持久化字段 | 不能按 Provider/Model 统计 |
| Cached/reasoning token | `MISSING` | 无分类字段 | 不能区分不同计费类别 |
| 实际 API 费用 | `MISSING` | 无账单 API、费用字段或调用时价格快照 | 不能声称为真实账单 |
| HTTP 状态码 | `PERSISTED` | ProviderCall `http_status` | 某些 SDK/连接异常没有 HTTP response，状态码可为空 |
| 稳定错误分类 | `PERSISTED`（有限） | `outcome`、`failure_stage`、`safe_error_summary` | 可按系统阶段和粗粒度 outcome 分析；不能替代 Provider 的完整错误码 |
| Retry 次数 | `DERIVABLE` | ProviderCall `retry_index`、`call_sequence`；Attempt retry count | 应以 ProviderCall 数量和 retry index 聚合，不只看 Attempt |
| Timeout 比例 | `DERIVABLE`（有限） | timeout 失败阶段/outcome、HTTP status、diagnostic category | 未收到 HTTP response 的 timeout 依赖错误分类；需明确分母 |
| Fallback Provider | `NOT APPLICABLE` | 当前 Provider 选择没有自动 fallback | 不统计不存在的 fallback 路径 |
| Raw Provider response | `PERSISTED` | ProviderCall raw response attachment；Attempt compatibility attachment | 可用于事后检查，但不等于 usage 已被结构化持久化 |
| PageArtifact | `PERSISTED` | 页号、PNG checksum、字节数、渲染时间 | 可分析图片准备和输入页范围，不能还原全部 Provider 账单 |

## 4. Cost calculation feasibility

### 4.1 单次 ProviderCall 成本

当前无法可靠计算实际成本：

```text
ProviderCall
  -> provider usage: 缺失
  -> input token: 缺失
  -> output token: 缺失
  -> cached/reasoning token: 缺失
  -> call-time price: 缺失
  -> actual invoice charge: 缺失
```

ProviderCall 的页数、图片数量、图片字节数和 native PDF 输入模式只能描述输入规模，不能可靠还原不同 Provider/Model 的 token 计费，更不能还原 PDF、视觉 token、缓存 token 或 reasoning token 的计费规则。

结论：

> **单次 ProviderCall 实际 API 费用：MISSING。**

### 4.2 估算费用

当前也不能形成可审计的 token-based 估算，因为缺少：

- Provider 返回的 input/output usage；
- cached input、reasoning 等 usage 分类；
- 与调用时间匹配的价格表；
- 调用时生效的价格快照；
- 不同输入模式的计费换算规则。

可以从现有数据计算页数或 ProviderCall 数量，但这只能作为工作量代理指标，不应命名为估算费用。

结论：

> **根据 Token usage 和价格表的估算费用：当前不可计算。**

### 4.3 聚合成本

以下成本聚合目前都不可可靠计算：

| 指标 | 结论 | 原因 |
|---|---|---|
| 单个 ParseAttempt 总成本 | 不可计算 | 缺少每个 ProviderCall 的 usage/价格 |
| 单张发票处理成本 | 不可计算 | 缺少 Attempt 级 usage/价格，且 Task 可能有多次 Attempt |
| Provider / Model 累计成本 | 不可计算 | 虽有 Provider/Model snapshot，但没有费用基础 |
| 失败调用产生的费用 | 不可判断 | 失败 ProviderCall 保留 outcome/status，但没有 Provider 账单或 usage |

重试成本的边界是明确的：如果未来有 usage，应累计同一 ParseAttempt 下所有实际 ProviderCall，包括失败但已被 Provider 接收的调用；当前无法完成这个累计。

## 5. Performance calculation feasibility

### 5.1 ProviderCall API duration

对收到响应的调用，可以使用：

```text
response_received_at - request_started_at
```

这能够计算 ProviderCall 级别的近似 API duration。它包括 adapter 发起请求到收到响应的时间点，但不应与完整 Attempt duration 混用。

对没有收到响应的 timeout/connection failure：

- `response_received_at` 可能为空；
- 可以通过 outcome、failure stage 和 timeout 配置统计失败类别；
- 不能对所有失败 call 计算完整 duration。

### 5.2 ParseAttempt duration

可以用 Attempt 的：

```text
completed_at - started_at
```

或 `finished_at - started_at`（按实际写入语义选择）计算 worker Attempt 生命周期。该时间包括 ProviderCall、解析、schema validation、normalization、mapping 和 persistence 等阶段，不能当作 API latency。

### 5.3 Task end-to-end duration

理论上可由 Task 创建时间到最终状态时间计算，但当前没有确认一组专门、统一的 Task end-to-end 时间字段和时间边界契约。不能用：

```text
Attempt started_at -> Attempt completed_at
```

冒充：

```text
Task created -> Statement ready
```

因此 Task 级平均/中位数耗时需要先明确状态边界和历史数据完整性；当前只能进行有限的基于现有时间字段的分析。

### 5.4 失败率、retry 分布和 timeout 比例

这些指标比成本更可行：

- ProviderCall 失败率：按 `outcome` 聚合；
- Provider/Model 失败率：按 `provider_snapshot` / `model_snapshot` 聚合；
- 阶段失败率：按 `failure_stage` 聚合；
- retry 分布：按 `retry_index` 和同一 Attempt 的 ProviderCall 数量聚合；
- HTTP 错误分布：按 `http_status` 聚合；
- timeout 比例：按明确的 timeout outcome/category 与实际 ProviderCall 分母聚合。

但要注意：

1. ProviderCall 失败率和 ParseAttempt 失败率不是同一个指标；
2. 一次 Attempt 可能包含多个成功和失败的 ProviderCall；
3. 一个 Task 可能有多个 Attempt；
4. `safe_error_summary` 适合展示，不应作为稳定分类键；
5. 没有 ProviderCall usage 时，失败调用的实际费用仍未知。

## 6. Accuracy / human correction data limitations

### 6.1 Provider 准确率

当前没有可靠的字段级人工 ground truth，可以稳定比较：

```text
AI extracted value
vs
Human accepted / corrected value
```

ProviderCall 的 `page_extraction_result`、Attempt 的 Canonical 和 Statement 的最终值能表示处理结果，但不自动表示人工是否接受、修改了哪些字段，也没有统一的字段级修正数据集。

因此不能用以下指标替代 Provider 准确率：

- AI confidence；
- 金额平衡通过；
- Canonical schema validation 通过；
- Statement 创建成功；
- ParseAttempt 成功率。

### 6.2 字段修改频率

当前不能可靠测量：

- 字段名；
- 修改前值；
- 修改后值；
- 修改原因；
- 修改是否由 AI、人工或 Mapping 引起。

结论：

> **字段修改频率：NOT CURRENTLY MEASURABLE。**

本 Spike 不因此提出完整 Field Evidence、Canonical provenance 或字段级审计平台。

### 6.3 按供应商统计失败率

Task/Attempt 关联到供应商配置和业务 Task，但 Provider 失败可能发生在供应商尚未从发票中识别之前。因而：

- 有明确 supplier mapping 的成功/后续失败，可以按供应商做有限分析；
- provider request、输入策略、schema validation 等早期失败，供应商可能未知；
- `supplier unknown` 不能直接归因于某个供应商的发票质量。

供应商失败率必须明确分母和“供应商已识别”的条件；当前不能把所有 Attempt 失败按供应商归因。

## 7. Existing data verification

本次采用代码、模型定义和现有测试/观测性样本进行只读核对，没有重新调用真实 AI。

现有测试已验证的 ProviderCall 能力包括：

- native PDF 成功调用保存 `input_mode`、页数和调用记录；
- Provider 失败仍保留 ProviderCall evidence；
- timeout retry 产生 retry index 为 0、1 等独立 Call；
- retry exhaustion 不产生超出配置上限的额外调用；
- 每次真实 retry 保留独立 raw response、outcome 和模型 snapshot；
- PageArtifact 保存实际传入的 PNG checksum、页号和字节数；
- ProviderCall/diagnostic 持久化具有事务隔离和权限边界。

现有测试和代码没有发现以下可用于成本分析的持久化数据：

- Provider usage；
- input/output token；
- cached/reasoning token；
- 调用时价格；
- 实际 Provider 账单；
- 独立模型版本；
- 字段级人工接受/修正 ground truth。

现有 ProviderCall 记录足以做调用次数、Provider/Model 分布、输入模式、retry、HTTP 状态、outcome 和部分耗时分析，但不足以做可靠成本分析或准确率分析。

## 8. Verified gaps

### GAP-01: Token usage 没有结构化持久化

当前 raw response 可能作为 attachment 保存，但 Provider 返回的 usage 没有被抽取到 ProviderCall 字段。仅依赖 raw JSON 做事后猜测不构成稳定成本数据，且不同 Provider response shape 可能不同。

### GAP-02: 没有调用时价格或实际费用

当前没有价格表、调用时价格 snapshot 或账单 API。即使未来可以得到 token usage，也不能把当前价格反推为历史真实费用。

### GAP-03: Task 端到端时间边界未形成统一契约

ProviderCall 和 Attempt 时间字段足以支持部分阶段分析，但不能未经定义就把 API duration、Attempt duration 和 Task end-to-end duration 混为一个耗时指标。

### GAP-04: 字段级人工修正不可测

当前数据不能可靠建立 AI 原值与人工接受/修正值的字段级配对，因此不能从现有数据计算 Provider 字段准确率或修改频率。

## 9. Non-issues

以下不是本次需要修改的缺陷：

1. **一次 Attempt 包含多个 ProviderCall**：这是当前正确的审计粒度，不是重复数据。
2. **Provider retry 产生多个 Call**：这是实际外部调用的记录，成本分析未来应累计这些 Call，而不是只统计 Attempt。
3. **ProviderCall 没有 fallback 字段**：当前设计不使用自动 fallback，属于 `NOT APPLICABLE`。
4. **Raw response 不是结构化 usage**：raw response 用于审计和诊断，不应被误称为已经具备统一 usage 统计。
5. **PageArtifact 记录页数和图片大小**：这些是输入证据，不等于 token 或 API 费用。
6. **AI confidence 不是准确率**：没有人工 ground truth 时，不用 confidence 推导 Provider accuracy。

## 10. Recommendation

### Decision: D. Evidence insufficient — defer

当前不选择 B，也不新增 ProviderCall 字段或成本平台。理由是：

- 调用次数、Provider/Model、输入模式、retry、HTTP 状态、outcome 和部分耗时已经可以从现有数据分析；
- 实际费用和 token-based 估算费用都缺少基础数据；
- Task end-to-end latency 的时间边界尚未统一定义；
- 字段准确率和人工修改频率没有可靠 ground truth；
- 当前没有业务要求证明必须立即建设成本 Dashboard 或通用 AI Observability Platform。

当前决定：

- 不新增 usage/token 字段；
- 不新增价格表或账单 API；
- 不新增费用模型；
- 不新增 Dashboard；
- 不修改 ProviderConfig；
- 不修改 Provider 选择和 retry/fallback 语义；
- 不建立字段级 Evidence 或人工修正平台。

## 11. Smallest re-open trigger

只有出现实际分析需求时，才重新评估最小范围：

1. **成本需求**：Provider 账单或 Provider usage 成为实际对账要求；
2. **性能需求**：业务需要按 Provider/Model 比较延迟，且先明确 API、Attempt、Task 三种时间边界；
3. **容量/失败需求**：实际调用量需要可靠统计 retry、timeout 或 Provider 失败率；
4. **质量需求**：业务提供可关联的人工接受/修正样本，能够定义准确率分母。

重新评估时仍应先验证真实 Provider response 和历史记录，再决定是否做局部字段增强；不预先承诺建立通用 AI Observability Platform。

## 12. Scope closure

最终回答：

> 当前已经能够可靠计算 Provider 的实际调用次数，以及部分 Provider/Model、输入模式、retry、HTTP 状态、失败率和 API/Attempt 层级耗时；不能可靠获得 Provider 返回的 Token usage、实际 API 费用、调用时价格或字段级人工准确率。因此，当前数据不足以支持完整的 Provider 成本与性能报告，选择 D：证据不足，延期。

本 Spike 到此收口，不进入 DDD、TDD、Coding Contract 或生产开发。
