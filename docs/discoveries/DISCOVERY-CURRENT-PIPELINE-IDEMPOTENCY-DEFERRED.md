# Discovery: Current Pipeline Idempotency Deferred

## 1. 当前最终决策

> **Current Pipeline Idempotency：选择 C，证据不足；当前不开发。**

本次不是选择 A“当前完全足够”，也不是宣称“所有风险都已验证通过”。Spike 的结论是：已覆盖的顺序和生命周期路径有明确保护，但仍有边界尚未通过业务或并发证据验证。因此当前先明确最小验证范围，不提前引入幂等框架或修复方案。

当前生产链路保持不变：

```text
PDF
  -> Task
  -> Run AI
  -> ParseAttempt
  -> Canonical
  -> Vendor Invoice Statement
```

## 2. 已确认的保护

以下路径已有代码和现有测试支持：

- 同一 Task 重复 Run AI：queued/running Attempt 会被拒绝；
- ParseAttempt sequence：同一 Task 的 sequence 有唯一约束；
- Provider retry：重复的是技术调用和 ProviderCall 记录，不会按 retry 创建新的 Attempt 或 Statement；
- stale worker：current Attempt 和 Task 状态检查阻止旧 Attempt 覆盖当前结果；
- 顺序重复生成 Statement：Task 级检查与 `unique(task_id)` 约束阻止同一 Task 持久化多个 Statement。

截至本次调查，没有发现已验证的重复 Statement 或旧结果覆盖新结果问题。

## 3. 必须保留的边界

### 3.1 相同 PDF 跨 Task 重复上传

当前 PDF SHA-256 只在 Provider input 准备阶段临时计算，没有保存为 Task 级字段，也没有用于跨 Task 查重。因此相同 PDF 可以形成多个 Task、多个 Attempt 和多个 Statement。

这说明文件级重复保护当前不存在，但尚未确定重复上传在业务上应该：

- 禁止；
- 告警后允许；
- 还是完全允许。

本记录不把“技术上可以重复上传”直接解释为“必须新增去重规则”。

### 3.2 Statement 并发修改

Statement 修改和候选应用的并发行为目前没有专门验证。代码检查显示相关 command 没有统一的 Task row lock，因此不能声称 Statement 已具备完整并发幂等。

当前结论保留为证据不足，而不是已验证的生产缺陷：

- 没有真实并发覆盖案例；
- 没有现有 Statement command 双事务测试；
- 没有为本次 Spike 新增并发验证。

## 4. 当前明确不开发

在真实业务证据出现前，当前不开发：

- Task 或 Attachment 的 checksum 去重；
- 供应商、发票号、金额等业务重复键；
- 通用幂等框架；
- Statement 并发锁或通用并发控制平台；
- 重复 Apply Candidate 的新幂等抽象；
- 任何 Vendor Bill 幂等实现。

特别是，不因为“幂等性重要”就预先增加：

```text
company + supplier + invoice_number
company + supplier + invoice_number + amount
```

这些属于未来业务重复识别策略，不是本次 Discovery 的实施结论。

## 5. 最小重新验证范围

只有出现真实需求、实际问题，或明确的未来并发场景时，才针对具体缺口重新验证：

1. **重复上传需求**：由业务确认相同 PDF 的期望行为是禁止、告警还是允许，并提供真实重复上传案例；
2. **Statement 并发需求**：如果业务明确要求多人同时编辑，或新功能将引入并发写入，则在测试数据库中针对已有 Statement command 做最小双事务验证，只观察 lost update、重复 Statement 或事务异常；
3. **重复 Apply Candidate**：只有出现真实重复操作或覆盖案例时，再验证相同 payload 的最终状态和审计副作用；
4. **Vendor Bill 幂等**：留到实际开发 `Human Confirm → Vendor Bill` 时，作为 Bill 创建的硬性契约和专门测试要求。

上述验证都不应重新调用大量真实 AI，也不应修改生产数据。

## 6. 当前范围收口

当前可以收口的判断是：

> 同一 Task 重复 Run AI、Provider retry、stale worker，以及顺序重复生成 Statement，已有明确保护；没有发现已验证的重复 Statement 或旧结果覆盖新结果问题。

但这不等于所有风险都已验证通过。相同 PDF 跨 Task 重复上传的业务规则仍未确定，Statement 并发修改仍未验证，当前不能声称完整并发幂等。

因此本次最终决策为：

> **C. Evidence insufficient — specify the smallest missing verification**

在没有实际重复上传或并发覆盖问题前，保持现状并停止调查；出现真实问题后，再针对具体缺口处理。不进入 DDD、TDD、Coding Contract，也不提前开发 Vendor Bill 幂等。
