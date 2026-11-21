# CompanyAgent × TokenDance — 2026-11-21 真实云端 Tool Calling 验收

## 结论

**PASS：仅针对合成数据、只读工具和 GitHub Actions 云端模型通道。**

- 服务商：TokenDance（`https://tokendance.space/gateway/v1/chat/completions`）
- 模型：`glm-5.2`
- 运行环境：GitHub-hosted Linux runner / Python 3.11
- 完整运行：[Actions #44896062819](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44896062819)
- 关键结果（来自 Actions job log）：

```text
LIVE_ACCEPTANCE=PASS; provider=tokendance; actual_tool_calls=3
Tools=inspect_coverage,inspect_inventory,select_budget_scenario
```

- GitHub artifact：`tokendance-synthetic-live-evidence`，artifact ID `14703494776`，已成功上传，保留 7 天
- 脱敏证据检查：`transport=live_chat_completions_tool_calling`、`verification_status=tool_calls_executed`、`tool_call_count>=1`、只读工具名单校验通过
- 不涉及公司内部 API、真实广告库存、2027 实际可售、正式报价、商业锁位或任何写操作

## 先前尝试与分析

| GitHub Actions | 模型 | 阶段 | 结果 |
|---|---|---|---|
| [#44895843476](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44895843476) | deepseek-v3.2 | Secret 预检 | BLOCKED，密钥未配置 |
| [#44895874875](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44895874875) | deepseek-v3.2 | 真实 HTTPS 步骤 | FAILED，旧版本未显示精确失败类型 |
| [#44896008697](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44896008697) | deepseek-v3.2 | 诊断版真实 HTTPS | HTTP 403，被服务商拒绝；原因尚不明确 |
| [#44896062819](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44896062819) | glm-5.2 | 真实 HTTPS + tools | **PASS，执行 3 个白名单工具，产生脱敏凭证** |

**不能仅凭 HTTP 403 断定 deepseek-v3.2 不支持工具调用**：它可能是账户权限、模型路由、计费或访问控制问题。当前只证实同一个云端工作流能用 glm-5.2 通过联调。

## 检查实现

1. 脚本 `scripts/verify_tokendance_tool_calling.py` 使用内置合成 JSON，不加载企业 CSV、红豆系统、用户真实 Brief 或任何 IMDS 数据。
2. `enterprise/model_tools.py` 固定 TokenDance HTTPS 地址、三种只读工具和最多四轮调用，限制每轮一个 `tool_calls`，校验参数与权限。
3. 真实云端运行不使用 `MockTransport`；`MODE=live_chat_completions_tool_calling` 仅在使用 `httpx.Client` 与真实 HTTPS 配置时报告。
4. API Key 只注入 Actions 的 Secret 检查与实际 Tool Calling 两个步骤，不出现在源码、流水线输入、缓存、artifact 或公开日志中。
5. 工作流改为 **手动 `workflow_dispatch`**，避免提交代码时自动消耗模型额度。默认模型改为实测通过的 `glm-5.2`。

## 安全与未来工作

- 先前曾在聊天中公开过 TokenDance API Key。**即使本次测试通过，也应撤销已暴露的旧密钥并轮换 GitHub Repository Secret 中的值**，采用额度/访问权限最小化的凭据。
- 当前合成数据验收不代表在 `/enterprise/` 登录、冻结 Run 权限、审计持久化、或带授权真实库存的端到端环境均通过。
- 如需生产迁移，仍须补齐企业权限审批、KMS/Secrets 管理、网络/VPC 隔离、白名单、租户隔离、MCP 认证、人工审阅、失败回滚和真实 IMDS 业务验收。
- 公开仓库只可包含合成数据和匿名化验收日志；真实密钥、实际数据和企业内网地址不上传。

## 状态定义

| 门禁 | 状态 |
|---|---|
| Chat Completions 实网可访问 | PASS (glm-5.2) |
| Tool Calling 返回并执行白名单工具 | PASS (3 calls) |
| 模拟协议/权限单元测试 | PASS（以提交对应 CI 为准） |
| Secret 作用域限制与无凭据日志 | PASS（代码检查） |
| deepseek-v3.2 实网调用 | FAILED / HTTP 403，原因待核验 |
| 企业内部 API、敏感数据、生产迁移 | **未验收 / 不得放行** |
