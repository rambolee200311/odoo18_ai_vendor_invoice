# SCRIPT‑INTENT‑AI‑VENDOR‑004
## 目标
修复ENV‑BLOCK‑001（验证基础设施阻塞）：`execution/scripts/verify.py`硬编码指向wd_tlms模块，不能执行ai_vendor_invoice的GATE‑01~GATE‑15门禁校验。

## 现状
1. verify.py文件存在，但硬编码扫描`addons/wd_tlms/models`、`addons/wd_tlms/views`；
2. 未实现ai_vendor_invoice的GATE‑01~GATE‑15自动化门禁校验；
3. Closure流程无法得到可复核自动化验证输出。

## 工作项
1. 将verify.py改造为支持传入模块名参数；解除硬编码wd_tlms路径；
2. 为ai_vendor_invoice完整实现GATE‑01~GATE‑15自动化检查；
3. 脚本输出结构化报告（控制台文本），用于Closure门禁证据；
4. 保留原有wd_tlms兼容；
5. 更新仓库内脚本使用说明文档。

## 不做
1. 不修复业务缺陷；
2. 不写单元/集成测试（TEST‑INTENT负责）；
3. 不修改SRS/DDD文档（DOC‑INTENT负责）。

## 完成门禁
1. 调用`python execution/scripts/verify.py --module ai_vendor_invoice`可完整运行，无FileNotFoundError；
2. 脚本输出GATE‑01‑GATE‑15逐条检查结果；
3. 人为制造gate违规样例，脚本可以正确检出失败；
4. wd_tlms原有调用路径保持兼容；
5. 脚本代码评审完成。