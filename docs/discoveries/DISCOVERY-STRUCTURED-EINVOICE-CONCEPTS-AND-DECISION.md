# Discovery: 结构化电子发票概念与当前决策

## 1. 发现目的

本发现文档用于明确以下问题：

> 一张供应商发票到底需要 AI “看懂”，还是本来就包含机器可读的数据，可以直接解析？

这个问题与当前 `ai_vendor_invoice` 的生产架构有关，但本次发现不改变现有架构，也不启动结构化电子发票开发。

当前生产链路保持不变：

```text
Supplier Invoice
  -> AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

## 2. 核心概念

### 2.1 PDF 与 XML 解决不同问题

PDF 主要用于“给人看”，保存页面布局、文字、图片和字体。即使 PDF 中的文字可以复制，系统通常仍然不知道某段文字是发票号码、税额还是订单号。

XML 主要用于“给机器读”，通过标签表达字段含义。例如：

```xml
<Invoice>
  <InvoiceNumber>INV-2026-001</InvoiceNumber>
  <InvoiceDate>2026-09-09</InvoiceDate>
  <Currency>EUR</Currency>
  <TotalAmount>1210.00</TotalAmount>
</Invoice>
```

这只是概念示意，不是 UBL 的正式结构。它表达的是：系统不需要通过版面猜测 `1210.00` 的含义，因为 XML 标签已经说明它是总金额。

因此：

```text
可搜索 PDF != 结构化电子发票
```

普通可搜索 PDF 仍然可能需要 OCR、版面分析或 AI 字段理解。

### 2.2 Factur-X 与 ZUGFeRD

Factur-X 和 ZUGFeRD 是高度相关的混合电子发票方案。典型文件是：

```text
PDF/A-3
  ├── 可视 PDF 页面：给人阅读、打印和审核
  └── 内嵌 XML：给软件读取发票字段
```

用户看到的文件可能仍然只是：

```text
invoice_123.pdf
```

但 PDF 内部可能包含：

```text
factur-x.xml
```

因此，支持该格式的软件可以直接提取 XML，而不是对可视页面进行 OCR。

简化理解：

- ZUGFeRD 起源于德国的混合电子发票标准；
- Factur-X 是法国和德国合作形成的对应方案；
- 现代版本采用高度协调的技术基础；
- 两者都属于“人可读 PDF + 机器可读 XML”的混合发票方案。

它们不是“一个是 PDF、另一个是 XML”，而是都可以把 XML 放入 PDF/A-3 容器中。

### 2.3 UBL

UBL（Universal Business Language）是商业单据的 XML 语法标准，不只表示发票，也可以表示订单等商业文档。

UBL 发票通常可以直接作为 XML 文件发送：

```text
invoice_123.xml
```

也可以与给人阅读的 PDF 一起发送：

```text
invoice_123.xml + invoice_123.pdf
```

UBL 中通常会表达发票编号、日期、币种、供应商、客户、税额和发票行等信息。

UBL 本身不要求必须有 PDF。

### 2.4 EN 16931

EN 16931 不是 PDF 格式，也不是一种单独的 XML 文件。它是欧洲电子发票的语义标准，定义电子发票应该表达哪些业务信息以及这些信息的含义和规则。

可以按层次理解：

| 层次 | 解决的问题 | 示例 |
|---|---|---|
| 语义标准 | 发票数据应该表达什么 | EN 16931 |
| XML 语法 | 数据具体如何写成 XML | UBL、CII |
| 文件包装 | XML 如何交付 | 独立 XML、PDF 内嵌 XML |
| 传输方式 | 文件如何发送 | 邮件、Peppol |

CII（Cross Industry Invoice）是另一种常见的 XML 发票语法。Factur-X/ZUGFeRD 的 XML 通常采用 CII，而 UBL 是另一套常见语法。

因此可以表示为：

```text
EN 16931
  -> 通过 UBL 或 CII 等 XML 语法表达
  -> 作为独立 XML 或 PDF 内嵌 XML 交付
```

### 2.5 Peppol

Peppol 不是 PDF 格式，也不是 OCR 技术。它主要是一套电子商业文档交换网络和相关规范，用于让不同企业的软件交换结构化发票等单据。

可以类比为：

- UBL：信件中的数据格式；
- Peppol：信件通过什么网络发送；
- PDF：给人阅读的打印版。

实际使用中，Peppol 电子发票经常采用符合其规范的 UBL XML。系统收到后通常可以直接解析，不需要先生成 PDF 再 OCR。

## 3. 发票类型与 AI 需求

| 收到的文件 | 文件中主要包含什么 | 发票字段提取是否通常需要 AI |
|---|---|---|
| 普通扫描 PDF | 页面图片 | 通常需要 OCR/视觉识别 |
| 普通可搜索 PDF | 文字、字体和版面布局 | 通常仍需要字段理解 |
| Factur-X PDF | 可视 PDF + 内嵌 XML | XML 可用时通常不需要 |
| ZUGFeRD PDF | 可视 PDF + 内嵌 XML | XML 可用时通常不需要 |
| UBL XML | 结构化发票数据 | 通常不需要 |
| PDF + sidecar XML | PDF + 独立 XML | 通常优先解析 XML |
| Peppol 结构化发票 | 规范化商业 XML | 通常不需要 |

“通常不需要 AI”只表示发票字段提取不必依赖 AI，不表示不需要业务审核。XML 可以表达供应商要求支付的金额，但不能自动证明这笔金额对应的运输订单确实应该支付。

## 4. 对 `ai_vendor_invoice` 的意义

当前普通 PDF 路径是：

```text
普通 PDF
  -> AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business Verification
  -> Vendor Bill
```

如果未来收到结构化电子发票，变化的只是“如何把数据读进系统”：

```text
UBL XML / Factur-X / ZUGFeRD
  -> Structured Data Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business Verification
  -> Vendor Bill
```

核心边界不变：

- 结构化数据不能绕过 Canonical；
- 结构化数据不能绕过 Vendor Invoice Statement；
- 结构化数据不能绕过业务/订单核验；
- 结构化数据不能绕过人工确认策略；
- 结构化数据不能直接创建 Vendor Bill。

因此，结构化电子发票是未来可能增加的输入能力，不是对当前生产流程的替代。

## 5. 当前样本调查发现

对应的详细证据见：

[SPIKE-STRUCTURED-EINVOICE-SURVEY.md](../experiments/SPIKE-STRUCTURED-EINVOICE-SURVEY.md)

当前真实样本结果：

| 项目 | 结果 |
|---|---:|
| PDF 文件路径 | 33 |
| SHA-256 唯一 PDF | 31 |
| 供应商 | Bring、Feelogic、Mainfreight |
| Factur-X | 0 |
| ZUGFeRD | 0 |
| UBL | 0 |
| EN 16931 XML | 0 |
| PDF 内嵌 XML | 0 |
| Sidecar XML | 0 |
| 结构化数据阳性率 | 0% |

样本更像普通业务系统生成的可视 PDF，而不是 PDF/A-3 + XML 的混合电子发票。当前调查没有发现足以支持结构化解析开发的真实使用证据。

## 6. 当前决策

### 决策：暂不开发结构化电子发票解析

当前选择：

> **A. No implementation justified yet**

决策依据：

1. 31 个唯一真实 PDF 中没有发现嵌入 XML；
2. 33 个 PDF 路径中没有发现 Factur-X、ZUGFeRD、UBL 或 EN 16931 XML；
3. 样本目录没有 sidecar XML；
4. 当前供应商样本均未显示结构化电子发票交付模式；
5. 基于本次调查结果，现在增加解析器不会改善当前这批真实发票的处理覆盖率；
6. 直接增加结构化支持会带来维护、验证和依赖成本，但当前没有对应业务收益。

因此当前继续使用 AI Extraction 是合理的：

```text
当前样本
  -> AI Extraction
  -> Canonical
  -> Statement
  -> Business Verification
  -> Human Confirm
  -> Vendor Bill
```

## 7. 未来重新评估条件

以下任一条件出现时，可以重新开展结构化电子发票调查：

- 供应商发送 `.xml` 发票文件；
- 收到 PDF 与 XML 成对的 sidecar 文件；
- 收到可以提取 `/EmbeddedFiles`、`/Filespec` 或 `AFRelationship` 的 PDF；
- 供应商明确说明发送 Factur-X 或 ZUGFeRD；
- 系统接入 Peppol 并实际收到结构化发票；
- 供应商提供 UBL、CII 或 EN 16931 相关样本；
- 当前 AI 识别成本、延迟或错误率成为业务瓶颈，且已确认存在可获取的结构化发票数据。

重新评估时，先收集真实样本并确认：

1. 实际格式属于 UBL、CII、Factur-X、ZUGFeRD 还是供应商私有 XML；
2. XML 是否可以可靠提取；
3. 是否包含供应商、发票号、日期、币种、税额、总额和发票行；
4. XML 数据是否能通过现有业务校验；
5. 样本数量是否足以支持长期维护。

在作出开发决定前，不应仅根据文件扩展名、供应商宣传材料或概念标准假设系统一定会收到结构化发票。

## 8. 一句话结论

**Factur-X/ZUGFeRD 是“PDF 里带 XML”的混合方案；UBL 是 XML 发票语法；EN 16931 规定电子发票数据语义；Peppol 负责电子单据交换。当前真实发票样本没有发现这些结构化数据，因此今天的决策是不开发，未来出现真实样本后再开发。**
