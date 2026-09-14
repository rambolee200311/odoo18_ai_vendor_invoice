# Spike: Real Invoice Structured E-Invoice Survey

## 1. Objective

本 spike 只调查现有真实供应商发票 PDF 是否已经包含可直接利用的结构化电子发票数据。

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

本次不修改生产模块代码，不实现 Provider，不修改 Canonical、Statement 或 Vendor Bill，也不新增生产依赖。

## 2. Sample corpus

调查对象是工作区中的真实发票样本目录：

```text
docs/carrier_invoice/
```

### 2.1 Corpus counts

| 项目 | 数量 |
|---|---:|
| PDF 文件路径 | 33 |
| SHA-256 唯一 PDF 二进制 | 31 |
| 重复路径造成的重复二进制 | 2 |
| 供应商 | 3 |
| Sidecar XML 文件 | 0 |

33 个路径中有 2 个是同一 PDF 内容的重复副本，因此结果同时按“文件路径”和“唯一二进制”统计。两种统计口径的结构化数据阳性结果相同。

### 2.2 Supplier distribution

| Supplier | PDF paths | Unique binaries | Total pages | PDF versions | Producer evidence |
|---|---:|---:|---:|---|---|
| Bring | 11 | 11 | 33 | 1.4 | BluJay Solutions |
| Feelogic | 11 | 10 | 11 | 1.3 | PyPDF2 |
| Mainfreight | 11 | 10 | 27 | 1.4 | BluJay Solutions |
| **Total** | **33** | **31** | **71** | **1.3 / 1.4** | — |

另有 1 个位于目录根部的 `bring_26022366.pdf`，已计入 Bring；1 个 `feelogic_35318.pdf`，已计入 Feelogic；1 个 `mainfreight_1727001370.pdf`，已计入 Mainfreight。因此完整样本总数为 33 个路径。

代表性文件包括：

| Supplier | Representative files | Observed PDF characteristics |
|---|---|---|
| Bring | `bring_26022366.pdf`、`卡车发票/Bring/factuur_26026130.pdf`、`factuur_26027170.pdf` | PDF 1.4；Producer 为 BluJay Solutions；包含字体对象和图像对象 |
| Feelogic | `feelogic_35318.pdf`、`卡车发票/Feelogic/35138.pdf`、`invoice 37829.pdf` | PDF 1.3；Producer 为 PyPDF2；包含图像对象 |
| Mainfreight | `mainfreight_1727001370.pdf`、`卡车发票/Mainfreight/1727001370_555.pdf`、`1727003687.pdf` | PDF 1.4；Producer 为 BluJay Solutions；包含字体对象和图像对象 |

国家信息不能仅从当前目录名和 PDF 元数据可靠推断，因此本 spike 不把国家作为确定字段。文件名和供应商名称足以支持供应商分层抽样，但不足以作为税务管辖区结论。

## 3. Detection method

本次采用只读、证据导向的本地检查：

1. 递归枚举 `docs/carrier_invoice/` 下的 PDF。
2. 使用 `file` 检查 PDF 版本和页数。
3. 使用 SHA-256 识别重复二进制，避免重复副本放大样本结果。
4. 使用二进制安全文本扫描检查 PDF 对象和元数据标识：
   - `/EmbeddedFiles`
   - `/EmbeddedFile`
   - `/Filespec`
   - `/EF`
   - `/AF`
   - `/AFRelationship`
   - `Factur-X`
   - `ZUGFeRD`
   - UBL namespace/标识
   - `EN 16931`、`urn:cen.eu:en16931`
   - `pdfaid`、XMP/PDF/A 标识
5. 检查样本目录中是否存在与 PDF 对应的 sidecar `.xml` 文件。
6. 检查常见 PDF 结构特征（页面、字体、图像、ToUnicode、压缩流）以区分普通可视 PDF 与“包含结构化附件”的 PDF。

本环境没有安装 `qpdf`、`pdfinfo` 或 Python PDF 解析库，因此没有将新的解析依赖安装到项目中。该限制不影响本次对嵌入文件字典、标准名称和 sidecar 文件的否定性调查，但意味着本报告不是 XML schema 验证报告。

## 4. Results table

### 4.1 Detection result

| 样本口径 | Sample count | Embedded structured data | Positive count | Positive percentage |
|---|---:|---:|---:|---:|
| PDF 路径 | 33 | 未发现 | 0 | 0% |
| 唯一 PDF 二进制 | 31 | 未发现 | 0 | 0% |

### 4.2 Format distribution

| Format / evidence | PDF paths | Unique binaries | Result |
|---|---:|---:|---|
| Factur-X | 0 | 0 | 未发现标识或嵌入 XML |
| ZUGFeRD | 0 | 0 | 未发现标识或嵌入 XML |
| UBL | 0 | 0 | 未发现 UBL namespace 或 XML |
| EN 16931 compatible XML | 0 | 0 | 未发现 namespace/profile 标识 |
| Generic embedded XML attachment | 0 | 0 | 未发现 `/EmbeddedFiles`、`/Filespec` 或 `/EmbeddedFile` |
| Sidecar XML | 0 | 0 | 样本目录无 `.xml` sidecar 文件 |
| PDF/A metadata | 0 | 0 | 未发现 `pdfaid` 或明确 PDF/A 标识 |
| Other identifiable structured invoice format | 0 | 0 | 未发现可分类的结构化发票格式 |

### 4.3 Exact negative evidence

对全部 33 个 PDF 路径进行扫描的结果如下：

| Marker | Matching PDF paths |
|---|---:|
| `/EmbeddedFiles` | 0 |
| `/EmbeddedFile` | 0 |
| `/Filespec` | 0 |
| `/AF` | 0 |
| `/AFRelationship` | 0 |
| `Factur-X` / `factur-x` | 0 |
| `ZUGFeRD` / `zugferd` | 0 |
| UBL namespace/identifier | 0 |
| `urn:cen.eu:en16931` / `EN16931` | 0 |
| `pdfaid` | 0 |

有一个 Bring PDF 出现孤立的 `/EF` 文本匹配，但同一文件没有 `/Filespec`、`/EmbeddedFile`、`/EmbeddedFiles`、`/AF` 或 `/AFRelationship`。该匹配不构成嵌入文件证据，因此不计为阳性。

两个 Mainfreight PDF 出现 `16931` 字符串，但其位置是 PDF 交叉引用偏移量（例如 `0000316931 00000 n`），不是 EN 16931 namespace、profile 或 XML 内容，因此不计为阳性。

## 5. Formats found

本样本集没有发现以下任何格式：

- Factur-X；
- ZUGFeRD；
- UBL；
- 可识别为 EN 16931 的 XML；
- PDF 内嵌 XML；
- 与 PDF 配套的 sidecar XML；
- 其他可识别的结构化电子发票格式。

样本更接近由业务系统生成的普通 PDF 发票，而不是 PDF/A-3 + XML 的混合发票。Bring 和 Mainfreight 样本的 Producer 标识为 BluJay Solutions，Feelogic 样本的 Producer 标识为 PyPDF2；这些 Producer 标识描述 PDF 生成工具，不代表存在电子发票 XML。

## 6. Positive sample details

没有阳性样本，因此不存在可进一步提取和核对的结构化 XML。

作为边界观察：

- Bring 和 Mainfreight 样本包含字体、页面和图像相关的 PDF 对象，表明 PDF 中存在可视内容或文本布局对象；
- Feelogic 样本包含图像对象，但未发现结构化附件标识；
- 可视文本、字体对象、OCR 可读文本和结构化电子发票 XML 是不同层次的数据，不能因为 PDF 可搜索或包含字体对象就将其归类为 UBL/Factur-X。

## 7. Fields available from structured data

由于阳性样本数为 0，本次没有从结构化数据直接获取任何字段：

| Field | Structured samples available | Direct extraction result |
|---|---:|---|
| Supplier name | 0 | 无 |
| Supplier VAT number | 0 | 无 |
| Invoice number | 0 | 无 |
| Invoice date | 0 | 无 |
| Due date | 0 | 无 |
| Currency | 0 | 无 |
| Subtotal | 0 | 无 |
| Tax total | 0 | 无 |
| Total amount | 0 | 无 |
| Invoice lines | 0 | 无 |
| PO/reference/order reference | 0 | 无 |

因此本次没有运行 XML 字段解析，也没有为了对比而重新发起昂贵的 AI 调用。

## 8. Reliability observations

### 8.1 What can be concluded reliably

在当前本地样本库中，可以较有把握地得出：

1. 没有发现 PDF 内置文件附件结构；
2. 没有发现 Factur-X/ZUGFeRD 的标准标识；
3. 没有发现 UBL 或 EN 16931 XML；
4. 没有发现 sidecar XML；
5. 对现有样本增加结构化 XML 优先路径不会立即命中任何已知样本。

### 8.2 What cannot be concluded

本次结果不能证明：

- 所有未来供应商都不会发送 Factur-X 或 ZUGFeRD；
- 供应商后台系统永远不提供单独 XML；
- 当前 PDF 的可视内容质量或 OCR 识别准确率；
- PDF 中是否存在某种非标准、压缩后无法通过普通标识扫描识别的私有数据；
- 任何 XML 是否满足完整 EN 16931 业务规则。

换言之，这是“当前真实样本中没有证据”的结论，不是对所有供应商格式的永久否定。

## 9. Gaps / unsupported cases

当前样本调查的主要缺口是：

1. 样本只覆盖 Bring、Feelogic 和 Mainfreight 三个供应商；
2. 没有拿到供应商原始 XML、Peppol/网络传输附件或发票发送邮件的 MIME 原文；
3. 没有安装专用 PDF 容器检查工具进行第二解析器交叉验证；
4. 没有对 PDF 可视文本与现有 AI extraction 结果做字段级准确率比较，因为本 spike 的阳性样本数为零；
5. 目录中的重复副本会增加路径数，但没有增加格式多样性，因此报告同时给出路径数和唯一二进制数。

如果未来业务收到新的电子发票格式，应把该文件加入样本库后重新执行同样的证据检查，而不是根据文件扩展名直接假设其包含结构化数据。

## 10. Recommendation

### Decision: A. No implementation justified yet

当前没有足够的真实使用证据支持在生产模块中优先实现结构化电子发票解析。

### Exact evidence

- 33 个真实 PDF 路径中，0 个发现嵌入结构化发票数据；
- 去重后的 31 个唯一 PDF 二进制中，0 个发现嵌入结构化发票数据；
- 0/33（0%）发现 Factur-X、ZUGFeRD、UBL、EN 16931 XML 或其他可识别结构化格式；
- 0/31（0%）唯一二进制发现上述格式；
- sidecar XML 数量为 0；
- 样本覆盖三家真实供应商，且不同 PDF 版本、页数和 Producer 均未出现阳性格式。

因此，当前生产链路继续使用：

```text
Supplier Invoice
  -> AI Extraction
  -> Canonical
  -> Vendor Invoice Statement
  -> Business / Order Verification
  -> Human Confirm
  -> Vendor Bill
```

本 spike 不建议新增结构化解析实现、Provider、Canonical 字段或生产依赖。只有当后续收到实际 Factur-X/ZUGFeRD/UBL 文件，或供应商明确承诺提供 XML 并能提供样本时，才有必要重新开展针对该格式的验证。
