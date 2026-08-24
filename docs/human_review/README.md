# Human Review UAT Readiness

本目录存放人工 UAT 启动前的准备材料，不存放 API key、完整敏感 PDF 或未经脱敏的日志。

## 文件说明

- `HUMAN-REVIEW-ENV-CHECKLIST.md`：环境自动检查与人工确认清单；
- `HUMAN-REVIEW-GUIDE.md`：人工 UAT 操作指导；
- `HUMAN-REVIEW-SAMPLE-MANIFEST.md`：样本用途和预期结果；
- `HUMAN-REVIEW-CASE-TEMPLATE.md`：单个 UAT 实例记录模板；
- `HUMAN-REVIEW-SUMMARY-TEMPLATE.md`：Readiness 汇总模板；
- `instances/`：每个实例复制一份 Case Template，禁止覆盖历史记录。

本目录对应 [INTENT-HUMAN-REVIEW-01](../intents/INTENT_HUMAN_REVIEW_01.md)，只判断
`UAT_READY` 或 `UAT_BLOCKED`。真正的人工操作和 `UAT_PASS/UAT_FAIL` 由后续
`INTENT-HUMAN-UAT-01` 负责。
