# Human Review Sample Manifest

该 Manifest 冻结每个样本的用途和预期结果。样本文件本身不提交到仓库；只记录非敏感描述、校验目标和脱敏证据位置。

| Sample ID | 非敏感描述 | Expected Outcome | Sensitivity | Ready | Evidence |
|---|---|---|---|---|---|
| HR-001 | 单页标准 EUR 供应商账单 | `awaiting_review → bill_generated` | Internal | NOT_CONFIGURED |  |
| HR-002 | 多页同一张发票 | 单一 Provider 上下文、单一 Canonical 结果 | Internal | NOT_CONFIGURED |  |
| HR-003 | 两张独立发票合并 PDF | `error_split_required`，不生成账单 | Internal | NOT_CONFIGURED |  |
| HR-004 | 合法无明细账单 | `lines=[]` 且前置条件满足，fallback product 单行草稿 | Internal | NOT_CONFIGURED |  |
| HR-005 | 金额不一致 | warning，不自动切换异常状态 | Internal | NOT_CONFIGURED |  |
| HR-006 | 冻结契约要求税码的应税明细缺税码 | 后端完整性校验阻断 | Internal | NOT_CONFIGURED |  |
| HR-007 | 低 confidence 结果 | UI 提示，允许人工修改 | Internal | NOT_CONFIGURED |  |
| HR-008A | Provider 受控业务失败 | 记录可观察错误和 attempt 结果 | Internal | NOT_CONFIGURED |  |
| HR-008B | worker/cron timeout | 引用自动化测试证据，不人工破坏 worker | Technical | NOT_CONFIGURED |  |
| HR-009 | AI 重跑 | 新 attempt，不覆盖人工修改 | Internal | NOT_CONFIGURED |  |
| HR-010 | 多公司/多币种 | task、bill company 和 currency 一致 | Internal | NOT_CONFIGURED |  |

## Manifest 签核

```text
Prepared by:
Reviewed by:
Prepared at:
Version:
```
