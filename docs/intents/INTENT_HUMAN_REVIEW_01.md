# INTENT-HUMAN-REVIEW-01

## 定位

本 Intent 是 **UAT Readiness（人工 UAT 准备）**，不是人工 UAT 执行。

本 Intent 只负责把人工 UAT 所需的环境、账号、数据、操作说明、样本预期和记录模板准备完整，并输出：

- `UAT_READY`：满足启动正式人工 UAT 的全部前置条件；
- `UAT_BLOCKED`：存在启动阻塞项，并逐项列出。

真正的人工操作和业务体验判断必须由后续独立的 `INTENT-HUMAN-UAT-01` 完成。该后续 Intent 才能输出 `UAT_PASS`、`UAT_FAIL` 或 `UAT_BLOCKED`。

本 Intent 不修改业务代码、正式测试、冻结基线或验证脚本。

---

## 1. 冻结基线

- SRS：`docs/context/requirements/spec_wd_ai_vendor_invoice_1.3.4.md`
- DDD：`docs/context/design/ddd_wd_ai_vendor_invoice_v1.2.md`
- TDD：`docs/context/design/tdd_wd_ai_vendor_invoice_v1.4.md`
- Coding Contract：`docs/intents/INT‑WD‑AI‑VENDOR‑INVOICE‑IMPLEMENTATION‑001.md`
- Closure：`docs/intents/INT‑WD‑AI‑VENDOR‑INVOICE‑CLOSURE‑001.md`

人工 UAT 不得自行改变状态机、账单规则、人工复核规则、Provider 安全规则或公司隔离规则。

---

## 2. 验收准备交付物

本 Intent 必须创建并维护以下目录：

```text
docs/human_review/
├── README.md
├── HUMAN-REVIEW-ENV-CHECKLIST.md
├── HUMAN-REVIEW-GUIDE.md
├── HUMAN-REVIEW-SAMPLE-MANIFEST.md
├── HUMAN-REVIEW-CASE-TEMPLATE.md
├── HUMAN-REVIEW-SUMMARY-TEMPLATE.md
└── instances/
    └── .gitkeep
```

每个实例记录必须复制 [HUMAN-REVIEW-CASE-TEMPLATE.md](../human_review/HUMAN-REVIEW-CASE-TEMPLATE.md)，不得覆盖已有失败记录。

---

## 3. 环境完整性检查

### 3.1 Copilot 自动验证

Copilot 可以验证以下非敏感技术信息，并将实际命令输出或证据路径写入 [HUMAN-REVIEW-ENV-CHECKLIST.md](../human_review/HUMAN-REVIEW-ENV-CHECKLIST.md)：

- Odoo 版本；
- Python 版本和虚拟环境；
- PostgreSQL 连接；
- `account`、`contacts`、`queue_job`、`ai_vendor_invoice` 安装状态；
- manifest 依赖；
- model registry；
- addons path；
- purchase journal；
- fallback product；
- Provider 配置记录是否存在、启用状态及非敏感字段完整性；
- vendor/product/tax/currency mapping 配置记录；
- User、Reviewer、Config Manager 组是否存在；
- `account_invoice_import` 是否未作为运行时依赖。

自动检查结果只能使用：

```text
PASS / FAIL / NOT_CONFIGURED
```

推荐命令：

```bash
cd /Users/lijianqiang/Documents/odoo18_ai_vendor_invoice

venv/bin/python3 odoo-bin --version

venv/bin/python3 odoo-bin shell \
  -c odoo.conf \
  --addons-path=odoo/addons,addons/queue,addons \
  -d odoo18e_tms
```

自动检查不得读取、打印、复制或验证 API key 明文。

### 3.2 必须人工确认

以下内容必须由人工 UAT 执行人员确认，Copilot 不代替确认：

- Web 浏览器可正常登录和操作；
- 验收人员账号已准备；
- 真实或验收专用 Provider API key 有效；
- PDF 样本真实符合业务场景；
- 页面视觉效果、字段可读性和操作体验；
- 截图、日志和记录不包含 API key 或敏感 PDF 内容；
- UAT 开始后代码基线不再变化。

### 3.3 Readiness Blocked

以下问题属于 `READINESS_BLOCKED`，出现时不得启动正式 UAT 实例：

- Odoo 无法启动；
- 数据库不可连接；
- `ai_vendor_invoice` 或 `queue_job` 未安装；
- purchase journal、fallback product 或必要主数据未配置；
- UAT 账号或角色未准备；
- Provider 非敏感配置不完整；
- 样本 Manifest 未完成；
- Git 基线不明确或工作树在 UAT 开始前已变化。

`READINESS_BLOCKED` 必须记录在环境清单，不得创建“10 个 Case 全部 BLOCKED”的无效实例。

---

## 4. Secret 安全边界

- Copilot 只检查 Provider 记录存在、启用状态、URL、模型、timeout 和 retry 等非敏感信息；
- Copilot 不读取 API key 明文；
- API key 是否有效由人工 UAT 执行人员确认；
- API key 不得进入 history、截图、日志、异常、报告或 Git；
- 验收专用 API key 在 UAT 完成后必须清理或轮换。

---

## 5. 样本准备

样本预期统一维护在 [HUMAN-REVIEW-SAMPLE-MANIFEST.md](../human_review/HUMAN-REVIEW-SAMPLE-MANIFEST.md)。

Manifest 必须冻结“样本用来验证什么”，而不是在看到系统结果后反向解释结果。

最低样本集合：

| Sample ID | 类型 | Expected Outcome |
|---|---|---|
| HR-001 | 单页标准 EUR 供应商账单 | `awaiting_review` → `bill_generated` |
| HR-002 | 多页但同一张发票 | 一次 Provider 上下文，单一 Canonical 结果 |
| HR-003 | 两张独立发票合并 PDF | `error_split_required`，不生成账单 |
| HR-004 | 合法无明细账单 | `lines=[]` 且其他前置条件满足，使用 fallback product 生成单行草稿 |
| HR-005 | 金额不一致账单 | 产生 warning；不把金额不平自动当作系统异常 |
| HR-006 | 冻结契约要求税码的应税明细缺税码 | 后端完整性校验阻断 |
| HR-007 | 低 confidence 结果 | 显示提示，人工可以修改 |
| HR-008A | Provider 受控失败 | 人工观察错误提示和 attempt 结果 |
| HR-008B | worker/cron timeout | 引用自动化测试证据，不人工杀 worker 或操纵数据库 |
| HR-009 | AI 重跑 | 新 attempt，不覆盖人工已修改结果 |
| HR-010 | 多公司/多币种 | 账单公司、币种和任务公司一致 |

HR-006 只适用于冻结契约明确要求税码的应税明细；免税/零税率必须按人工选择的有效税务配置验证，不得扩展成新的业务规则。

---

## 6. 人工 UAT 操作指导

完整操作步骤见 [HUMAN-REVIEW-GUIDE.md](../human_review/HUMAN-REVIEW-GUIDE.md)，覆盖：

1. 登录和角色确认；
2. Provider、mapping、阈值和会计基础数据确认；
3. 创建单 PDF 任务；
4. 发起 AI 解析；
5. 查看 attempt 和解析结果；
6. 查看并修改人工复核字段；
7. 应用 AI 候选但不覆盖已编辑字段；
8. 确认金额 warning 和税务完整性；
9. 使用单一按钮生成草稿供应商账单；
10. 检查账单公司、币种、附件和 task 状态；
11. 重复操作的用户层幂等验证；
12. 异常、权限和 secret 可见性观察。

并发事务幂等、stale-worker、retry 计数和 cron 活性丢失属于自动化测试/技术验收，不要求人工 UAT 重复制造。

---

## 7. UAT 实例规则

每个实例必须填写：

```text
Instance ID
Git Commit
Git Dirty
Module Version
Database
Database Snapshot/Identifier
Company
Provider（不得记录 API key）
User Role
Sample IDs
```

规则：

- 实例开始后代码基线不得变化；
- 如果测试过程中修改了代码，当前实例立即结束；
- 修复后必须创建新的实例；
- 每个实例使用独立 task 和样本编号；
- 失败记录不可删除或覆盖；
- `CASE_BLOCKED` 只表示整体环境已 Ready、单个 Case 因外部因素无法执行。

---

## 8. 问题分类

人工 UAT 发现问题只记录，不在本 Intent 修改代码：

- `IMPLEMENTATION_DEFECT`
- `DOCUMENTATION_DRIFT`
- `NEW_REQUIREMENT`
- `ENVIRONMENT`
- `USABILITY`
- `OPTIMIZATION`

问题编号格式：

```text
UAT-DEF-001
UAT-DEF-002
```

不要把所有“界面不好用”直接归类为实现缺陷；先区分冻结需求缺失、实现错误、环境问题和体验优化。

---

## 9. 完成定义

- [ ] 自动环境检查完成并留存证据；
- [ ] 人工环境检查项目形成明确 Checklist；
- [ ] User、Reviewer、Config Manager 三类角色准备完成；
- [ ] Provider 非敏感配置检查完成；
- [ ] 未读取、输出或记录 Provider API key；
- [ ] 会计基础数据准备完成；
- [ ] HR-001 至 HR-010 样本 Manifest 完成；
- [ ] HR-008 已拆分为 Provider 失败观察和 worker/cron 自动化证据；
- [ ] `HUMAN-REVIEW-GUIDE.md` 可由验收人员独立执行；
- [ ] Case Template、Summary Template 和 `instances/` 目录完成；
- [ ] Git Commit、Git Dirty、Module Version、Database 信息可追溯；
- [ ] 未修改业务代码、正式测试或冻结基线；
- [ ] 最终只输出 `UAT_READY` 或 `UAT_BLOCKED`；
- [ ] 本 Intent 不输出 `UAT_PASS` 或 `UAT_FAIL`。

---

## 10. 后续流程

```text
Closure
  ↓
INTENT-HUMAN-REVIEW-01
  ↓
UAT_READY / UAT_BLOCKED
  ↓
INTENT-HUMAN-UAT-01
  ↓
UAT_PASS / UAT_FAIL / UAT_BLOCKED
  ↓
Release
```
