# Human Review Environment Checklist

## A. Copilot 自动验证

| 检查项 | 命令/证据 | Result | Evidence |
|---|---|---|---|
| Odoo 版本 | `venv/bin/python3 odoo-bin --version` | PASS | `Odoo Server 18.0+e-20250619` |
| Python 虚拟环境 | `venv/bin/python3 --version` | PASS | `/Users/lijianqiang/Documents/odoo18_ai_vendor_invoice/venv` |
| PostgreSQL 连接 | Odoo shell 启动输出 | PASS | `odoo18e_tms` shell 可连接 |
| addons path | Odoo 启动日志 | PASS | `odoo/addons, addons/queue, addons` |
| `account` | Odoo shell / Apps | PASS | installed |
| `contacts` | Odoo shell / Apps | PASS | installed |
| `queue_job` | Odoo shell / Apps | PASS | installed |
| `ai_vendor_invoice` | Odoo shell / Apps | PASS | installed |
| `account_invoice_import` 运行时依赖 | manifest 静态检查 | PASS | 不在 manifest depends，数据库 absent |
| model registry | Odoo shell | PASS | 9 个模块模型均 registered |
| purchase journal | Odoo shell | PASS | 当前数据库共 1 个 |
| fallback product | Odoo shell | PASS | system config 已配置 |
| Provider 非敏感配置 | Odoo shell | PASS | 4 个 active provider，非敏感字段完整 |
| Mapping 配置 | Odoo shell | NOT_CONFIGURED | 4 类 active mapping 当前均为 0 条 |
| User 组 | Odoo shell | PASS | XML ID 存在 |
| Reviewer 组 | Odoo shell | PASS | XML ID 存在 |
| Config Manager 组 | Odoo shell | PASS | XML ID 存在 |

自动检查不得读取或记录 API key 明文。

## B. 人工确认

| 检查项 | Result | Evidence / Notes |
|---|---|---|
| 浏览器可登录 | PASS | `http://127.0.0.1:8091/web/login` 返回 HTTP 200 |
| 验收人员账号已准备 | NOT_CONFIGURED | 由验收人员确认，不作为本次自动检查阻塞 |
| Provider API key 有效 | NOT_CONFIGURED | 由验收人员确认，不记录明文 |
| PDF 样本已准备 | PASS | `docs/carrier_invoice/bring_26022366.pdf`，5 页 |
| 页面视觉效果可接受 | NOT_CONFIGURED | 后续 UAT 确认 |
| 截图和日志已脱敏 | NOT_CONFIGURED | 由验收人员确认 |
| UAT 开始后代码基线锁定 | FAIL | 当前 Git Dirty，需提交 readiness 基线后确认 |

## 判定

```text
Readiness Result: UAT_BLOCKED
Blocking IDs: READINESS-002, READINESS-004
Reviewed by: Copilot automatic readiness check
Reviewed at: 2026-08-24
```

## Blocking Details

| ID | Type | Description | Evidence |
|---|---|---|---|
| READINESS-002 | NOT_CONFIGURED | Four active mapping tables contain zero records; invoice-specific master data is also absent | Odoo shell output; PDF extraction |
| READINESS-004 | BASELINE | Git worktree is dirty while preparing readiness documents | `git status --porcelain` |

## Invoice Mapping Preparation

Extracted non-sensitive source text from
`docs/carrier_invoice/bring_26022366.pdf`:

| Mapping type | Source text | Required Odoo master data |
|---|---|---|
| Vendor alias | `Bring Cargo B.V.` | Supplier partner |
| Product keyword | `Transportkosten ex Douane` | Freight expense product |
| Product keyword | `Dieselolietoeslag` | Diesel surcharge product |
| Product keyword | `ADR toeslag` | ADR surcharge product |
| Product keyword | `ETS toeslag` | ETS surcharge product |
| Product keyword | `IMO toeslag` | IMO surcharge product |
| Tax text | `21%` | 21% `account.tax` |
| Currency text | `EUR`, `€` | EUR `res.currency` |

The current database has no matching Bring partner, freight products, 21% tax,
EUR currency, or mapping rows. Do not create guessed records; configure the
real master data before creating the mapping rules.
