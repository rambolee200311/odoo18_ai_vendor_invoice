# 四种发票 AI 处理方案技术对比

本文对以下四种方案进行对比：

1. 当前项目 `ai_vendor_invoice`
2. `tus_odoo_ocr_ai_expense`
3. `omx_ai_invoice_ocr`
4. `account_invoice_import_llm`

对比重点是：发票从文件进入系统后，如何完成 OCR/LLM 处理、结构化、供应商匹配、人工复核和 Vendor Bill 创建，以及方案在异步、审计、重试和可维护性方面的差异。

> 说明：外部方案的结论基于当前代码快照和其公开配置/说明。实际部署时仍应核对具体版本、供应商 API 契约和依赖许可证。

## 1. 结论摘要

| 方案 | 核心定位 | 适合场景 | 主要短板 |
|---|---|---|---|
| `ai_vendor_invoice` | 面向生产的分阶段发票导入平台 | 需要异步处理、人工确认、可追踪和可重试的企业流程 | 组件较多，部署和运维成本最高 |
| `tus_odoo_ocr_ai_expense` | 通用 OCR 向导和动态字段映射 | 快速把 OCR 结果写入 Expense 或其他配置模型 | 同步调用、代码混淆、持久化审计和失败恢复能力弱 |
| `omx_ai_invoice_ocr` | 独立 OCR 记录到 Vendor Bill | 小规模、单机、同步处理的发票录入 | “AI”提取主要是正则/启发式，且缺少可靠异步链路 |
| `account_invoice_import_llm` | OCA Invoice Import 的 XML/OCR/LLM 扩展 | 已采用 OCA 导入格式，且希望兼容 XML 和多种 LLM | 主要是同步导入，没有 Attempt/ProviderCall 级别的运行审计 |

如果目标是长期运行的企业级 AI 发票入口，推荐以 `ai_vendor_invoice` 为主架构；如果目标是快速接入标准 XML/UBL/Factur-X，`account_invoice_import_llm` 的格式兼容性最有价值。其余两个方案更适合作为局部能力或原型参考，而不是直接作为高可靠主链路。

## 2. 总体架构对比

### 2.1 当前项目：分阶段、可观测的异步链路

```text
上传文件
  -> Invoice Import Task
  -> queue_job
  -> Parse Attempt
  -> Provider Call
  -> 原始响应（持久化）
  -> Canonical 数据
  -> Mapping / 校验
  -> Vendor Invoice Statement
  -> 人工确认
  -> Vendor Bill
```

`Task` 负责业务入口，`Attempt` 记录一次解析尝试，`ProviderCall` 记录外部 Provider 调用和阶段结果。解析、映射、人工确认和建账被拆开，便于重试和定位失败。

### 2.2 `tus_odoo_ocr_ai_expense`：向导直接调用外部 OCR

```text
Expense 列表按钮
  -> import.via.ocr 向导
  -> Fynix OCR API（requests.post）
  -> 动态实体/字段映射
  -> 直接创建目标 Odoo 记录
```

它通过配置动态决定目标模型和字段，支持普通字段、Many2one 和 One2many 等映射。流程简单，但 OCR 调用与业务记录创建处于同一个同步用户操作中。

### 2.3 `omx_ai_invoice_ocr`：独立 OCR 单据同步建账

```text
上传 PDF/图片
  -> ai.invoice.ocr
  -> pdf2image / Tesseract
  -> 规则/正则提取
  -> 创建 account.move
```

该方案有独立 OCR 记录和状态，但处理仍是同步的。缺少 Tesseract 依赖时使用 Mock OCR，这便于开发启动，却可能掩盖生产环境依赖未安装的问题。

### 2.4 `account_invoice_import_llm`：OCA 导入格式优先

```text
XML/UBL/Factur-X
  -> OCA account_invoice_import
  -> XML 失败时 Mistral OCR
  -> Annotation Schema 或 LLM JSON
  -> OCA Invoice Pivot Format
  -> OCA Vendor Bill 创建
```

它优先复用结构化 XML 和 OCA 的 Invoice Pivot Format；非结构化文件再进入 OCR/LLM 路径，因此标准电子发票的准确性和兼容性较好。

## 3. 能力矩阵

| 能力 | `ai_vendor_invoice` | `tus_odoo_ocr_ai_expense` | `omx_ai_invoice_ocr` | `account_invoice_import_llm` |
|---|---|---|---|---|
| 目标 Odoo 版本 | Odoo 18 | 以模块声明和依赖为准 | 目录声明 Odoo 19 | Odoo 18 |
| 主要入口 | Import Task | Expense/OCR 向导 | OCR 单据模型 | Vendor Bill、OCA Import Wizard |
| OCR | Provider 抽象，可扩展 | 外部 Fynix OCR | Tesseract | Mistral OCR |
| LLM | Provider 抽象，可配置 | 未形成独立 LLM 抽象 | 当前主要为规则/正则提取 | OpenAI、Anthropic、Gemini 等 LLM Assistant |
| 结构化层 | Canonical + Mapping | 动态 entities/字段映射 | OCR 字段直接提取 | Annotation Schema 或结构化 JSON，再转 Pivot |
| 供应商匹配 | 独立映射/校验阶段 | 依赖动态字段配置 | 由 Vendor Bill 创建逻辑处理 | 复用 OCA 导入和 partner 逻辑 |
| Vendor Bill | 人工确认后创建 | 取决于目标模型配置 | 同步创建 `account.move` | OCA 导入逻辑创建 |
| 人工审核 | Statement 确认流程 | 主要是向导结果确认 | OCR 记录后再建账，审核能力有限 | Vendor Bill/OCA 导入界面 |
| 状态机 | Task、Attempt、Statement 分层 | 向导生命周期 | OCR 记录状态 | OCA 导入状态加处理结果 |
| 异步队列 | 有，基于 `queue_job` | 无 | 无 | 无 |
| 原始响应持久化 | 有 | 未形成统一审计模型 | 主要保存 OCR 结果 | 保存导入/提取结果，但无统一调用审计 |
| ProviderCall 审计 | 有 | 无 | 无 | 无 |
| 失败阶段 | 明确记录并收敛到 Attempt | 依赖异常/向导错误 | 依赖 OCR/提取状态和异常 | 依赖导入或 AI 处理异常 |
| 重试 | 可针对 Attempt/Provider 设计 | 通常重新执行向导 | 通常重新处理记录 | 通常重新触发导入或 AI 操作 |
| 幂等 | 通过任务、Attempt 和业务校验设计 | 主要依赖附件/配置 | 有一定重复检查，但链路较短 | 依赖 OCA 导入和发票字段 |
| 多公司 | 可在模型和 Provider 配置中隔离 | 有配置隔离风险，需核对规则 | 需核对模型权限和配置 | 依赖 OCA/LLM 配置实现 |
| 权限边界 | 可按任务、Statement、Provider 分层 | 动态模型映射扩大权限风险 | 依赖模型 ACL | 依赖 OCA 模型和 AI 配置 ACL |

## 4. 数据模型与状态管理

### 4.1 `ai_vendor_invoice`

该方案把“上传文件”“一次解析尝试”“外部调用”“规范化数据”“待确认单据”分成不同层次，避免把所有状态塞进一个发票记录：

- **Task**：用户提交的业务任务和输入附件。
- **ParseAttempt**：一次可重试、可审计的解析执行。
- **ProviderCall**：一次 OCR/LLM/映射 Provider 调用，包括阶段、错误和原始响应。
- **Canonical**：与具体 Provider 无关的标准发票数据。
- **Vendor Invoice Statement**：用于人工复核的业务单据。
- **Vendor Bill**：确认后的正式会计单据。

这种拆分适合处理“同一文件多次尝试”“Provider 失败后更换 Provider”“人工修正后再建账”等场景。

### 4.2 其他三个方案

- `tus_odoo_ocr_ai_expense` 以动态配置和向导为核心，目标记录可能是 Expense 或任意模型，灵活但缺少稳定的领域模型和版本化中间结果。
- `omx_ai_invoice_ocr` 有独立的 OCR 记录，可保存文件、OCR 文本、提取字段和处理状态；但 OCR 记录和最终 `account.move` 之间的审计边界较窄。
- `account_invoice_import_llm` 以 OCA Invoice Pivot Format 作为稳定的中间结构，标准导入能力较强；但没有与 Provider 调用一一对应的 Attempt/Call 审计实体。

## 5. 可靠性对比

### 异步与事务

只有 `ai_vendor_invoice` 将耗时 Provider 调用放入队列，并针对异步事务可见性、Attempt 持久化和并发竞争做了收口。这样用户请求不会长时间占用 HTTP worker，也可以由队列系统管理失败任务。

另外三个方案都以同步调用为主。大文件、慢 API、网络抖动或 OCR 超时会直接影响用户操作；在 Odoo worker 超时或用户重复点击时，也更容易产生重复处理。

### 重试与错误定位

`ai_vendor_invoice` 能区分上传、解析、Provider、规范化、映射和建账阶段，适合“只重试失败阶段”。其他方案通常只能重新执行整个向导或整个导入流程，成本更高，也更难判断错误来自外部服务还是业务映射。

### 幂等与重复建账

建议所有方案在最终创建 Vendor Bill 前都使用业务键进行幂等控制，例如：

- 公司 + 供应商 + 发票号码；
- 公司 + 文件哈希；
- 已确认 Statement 与目标 `account.move` 的一对一关联。

不能只依赖文件名或用户是否再次点击按钮。`tus_odoo_ocr_ai_expense` 的动态创建尤其需要在目标模型层补充幂等约束。

## 6. 安全、权限和维护风险

### `tus_odoo_ocr_ai_expense`

该方案的主要风险不是 OCR 本身，而是动态映射和代码可审计性：

- 部分 Python 文件使用 `marshal`、`zlib`、`base64` 和 `exec` 混淆，难以进行常规安全审查和问题定位。
- 动态目标模型/字段映射可能把写权限扩展到不应由 OCR 向导操作的模型。
- Token、公司隔离、附件同名处理和自动创建联系人/产品需要逐项核对。

### `omx_ai_invoice_ocr`

- 目录声明为 Odoo 19，不能未经验证直接安装到 Odoo 18。
- 缺少 Tesseract 等依赖时使用 Mock OCR，生产部署必须显式禁止或监控此 fallback。
- 代码中同步 `env.cr.commit()` 会增加事务边界复杂度，应谨慎处理并发和异常回滚。
- 当前 AI Extraction 更接近启发式解析，不能按通用 LLM 方案评估其覆盖率。

### `account_invoice_import_llm`

- 依赖 OCA `account_invoice_import` 及 LLM/Mistral 相关组件，安装链较长。
- LLM 输出虽有 JSON 约束和 Pivot 转换，但仍需要对供应商、税、币种和产品匹配做业务校验。
- 没有统一 ProviderCall 审计时，外部请求的延迟、成本、原始响应和失败阶段不易集中分析。

### `ai_vendor_invoice`

其复杂度主要来自可靠性设计，而不是隐藏逻辑。应重点维护：

- queue_job、Odoo 和数据库版本兼容性；
- Provider 密钥的公司隔离和访问控制；
- 原始响应的脱敏、保留期限和存储容量；
- 规范化字段与最终会计字段之间的映射契约。

## 7. 方案优缺点

### `ai_vendor_invoice`

**优点**

- 适合大批量和慢 Provider 的异步处理。
- Attempt、ProviderCall 和原始响应提供完整运行审计。
- 人工确认与正式建账分离，降低错误入账风险。
- Provider、Canonical 和 Mapping 分层，便于替换 OCR/LLM。

**缺点**

- 模型和状态较多，初期开发、培训和运维成本较高。
- 需要正确部署 `queue_job`、后台 worker、Provider 配置和监控。
- 规范化模型与 Odoo 会计字段之间需要持续维护映射。

### `tus_odoo_ocr_ai_expense`

**优点**

- 配置驱动，能把 OCR 结果映射到不同业务模型。
- 入口简单，适合快速验证外部 OCR 服务。

**缺点**

- 同步处理，没有可靠的队列、Attempt 和 ProviderCall。
- 动态映射和混淆代码增加安全审查难度。
- 更像通用 OCR 写入工具，而不是完整的发票会计流程。

### `omx_ai_invoice_ocr`

**优点**

- 有独立 OCR 记录，流程比直接向导写入记录更清晰。
- Tesseract 可本地运行，不必把图像发送给外部 OCR 服务。
- 能直接进入 Vendor Bill，使用路径短。

**缺点**

- 版本声明与 Odoo 18 不一致。
- 提取逻辑目前以规则/正则为主，对版式变化和复杂税务场景适应性有限。
- 同步执行，缺少可恢复的异步任务和 Provider 审计。

### `account_invoice_import_llm`

**优点**

- XML/UBL/Factur-X 优先，结构化电子发票不必依赖 OCR。
- 复用 OCA Invoice Pivot Format 和 Vendor Bill 创建逻辑。
- LLM Provider 选择较多，适合已有 OCA 生态的部署。

**缺点**

- 处理链依然主要是同步操作。
- 安全、成本、延迟和原始响应审计不如 `ai_vendor_invoice` 集中。
- 需要理解 OCA 导入模型、Pivot 格式和 LLM Assistant 的组合行为。

## 8. 对当前项目的适配建议

不建议把四个方案完整拼接成一条链路。更稳妥的做法是保留 `ai_vendor_invoice` 的业务骨架，只吸收其他方案中有明确价值的能力：

1. **吸收 OCA 的结构化格式**
   - 将 XML/UBL/Factur-X 解析作为一种高优先级输入 Provider。
   - 将 OCA Invoice Pivot Format 转换为当前 Canonical 格式，而不是直接绕过 Statement。

2. **吸收多 Provider 能力**
   - 参考 `account_invoice_import_llm` 支持多个 LLM Provider。
   - 每次 Provider 调用仍通过 `ProviderCall` 记录模型、版本、耗时、成本、状态和脱敏响应。

3. **保留当前人工确认边界**
   - OCR/LLM 只负责生成候选数据。
   - 供应商、税、币种、金额和发票号码通过 Mapping/校验后进入 Statement。
   - 只有人工确认或明确的自动确认策略才能创建 Vendor Bill。

4. **把本地 Tesseract 作为可选 Provider**
   - `omx_ai_invoice_ocr` 的本地 OCR 可作为无外部 API 场景的 Provider。
   - 不应使用静默 Mock 作为生产 fallback；缺依赖必须让 Attempt 进入明确失败状态。

5. **不要直接引入混淆模块**
   - `tus_odoo_ocr_ai_expense` 的动态映射思路可以参考。
   - 但应以可审计的 Python 实现、白名单模型/字段和明确 ACL 重新实现，不能将混淆代码作为核心依赖。

## 9. 推荐落地路线

### 第一阶段：巩固当前主链路

- 保持 `Task -> Attempt -> ProviderCall -> Canonical -> Statement -> Vendor Bill`。
- 为每个失败阶段补充用户可见错误、管理员日志和可重试入口。
- 增加文件哈希、供应商发票号码和 Statement/Vendor Bill 关联的幂等校验。

### 第二阶段：增加标准电子发票入口

- 增加 XML/UBL/Factur-X Provider。
- 将结构化 XML 映射到 Canonical，跳过不必要的 OCR。
- 对 Schema、币种、税和供应商标识做严格校验。

### 第三阶段：扩展 OCR/LLM Provider

- 接入 Mistral OCR、云端 OCR、本地 Tesseract 或其他 Provider。
- 统一记录 ProviderCall，加入超时、速率限制、成本和脱敏策略。
- 为不同 Provider 建立可比较的准确率和失败率指标。

### 第四阶段：按风险配置自动确认

- 低风险且字段完整的发票可以自动进入确认队列或自动建账。
- 高金额、供应商未知、税额不平衡或置信度不足的发票必须人工复核。
- 自动化规则应记录版本，确保之后可以解释为什么自动确认。

## 10. 最终建议

对于本项目，推荐顺序如下：

1. **主架构：继续使用 `ai_vendor_invoice`**，因为它最完整地覆盖异步、状态机、人工审核、审计和失败恢复。
2. **格式能力：优先借鉴 `account_invoice_import_llm`**，将 OCA 标准导入和电子发票格式作为额外 Provider。
3. **OCR 能力：选择性吸收 `omx_ai_invoice_ocr` 的本地 Tesseract**，但必须纳入 Attempt/ProviderCall，且禁止静默 Mock。
4. **不建议直接采用 `tus_odoo_ocr_ai_expense` 作为核心方案**；可参考其动态字段配置思想，但应重写为白名单、可审计、可测试的实现。

综合来看，四个方案不是同一层面的竞争关系：`ai_vendor_invoice` 是可靠的业务流程平台，`account_invoice_import_llm` 是标准导入和 LLM 适配层，`omx_ai_invoice_ocr` 是同步 OCR 应用，`tus_odoo_ocr_ai_expense` 是动态 OCR 写入工具。将它们按“主流程、输入格式、Provider”三个层次组合，比直接互相替换更合理。
