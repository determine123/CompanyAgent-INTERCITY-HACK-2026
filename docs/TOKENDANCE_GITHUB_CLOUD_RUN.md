# TokenDance × CompanyAgent · GitHub Actions 云端真实 Tool Calling 验收

> 2026-11-21：云端 workflow 已启动过，但因缺少加密 Secret，被安全预检阻断；**没有向 TokenDance 发送请求，真实 Tool Calling 仍未通过**。

## 云端运行方式

入口：GitHub 项目 → **Settings → Secrets and variables → Actions → Repository secrets → New repository secret**。

1. 在 TokenDance 账户撤销此前曾发送到聊天的旧密钥，并重新生成**低额度、短期有效**的测试专用 API Key。
2. 在 GitHub 创建 Repository secret：**Name = `TOKENDANCE_API_KEY`**，Secret = TokenDance 控制台复制的**新密钥**。不要把它写进仓库文件、Workflow inputs、Issue、PR、评论、聊天或 Actions Variables。
3. 打开 [TokenDance LIVE Tool Calling](../.github/workflows/tokendance-live.yml) 的 Actions 工作流，点击 **Run workflow**，选择 `main`，在 `model` 输入 TokenDance 控制台确认支持 Chat Completions + `tools/tool_calls` 的模型 ID。默认示例 `deepseek-v3.2` 只是候选值，不代表此账号当前可用。
4. 运行会使用云端 Linux GitHub runner，通过官方固定 URL `https://tokendance.space/gateway/v1/chat/completions` 请求。仅发送合成行业、预算和库存覆盖的聚合数据，**不会读取公司真实库存或公司 API**。
5. 成功时 Actions 会产生 `tokendance-synthetic-live-evidence` artifact（7 天自动过期），其中只保存模型名称、已执行工具名称、数量和安全状态，不包含认证头或原始请求。只有 `transport=live_chat_completions_tool_calling`、`verification_status=tool_calls_executed`、`tool_call_count>=1` 时才允许标记 PASS。

## 状态说明

- **BLOCKED**：没有配置 `TOKENDANCE_API_KEY`；不会发起网络请求（预检明确失败）。
- **FAILED**：密钥无效、额度不足、所选模型不支持工具调用、网络不可达、返回字段不符合协议或工具调用超出权限/轮数；不计为成功。
- **PASSED**：真实 Chat Completions HTTPS 请求返回 `tool_calls`，CompanyAgent 执行一个或多个白名单只读工具并将聚合结果送回模型，得到最终响应。GitHub Actions 生成可核查的审计凭证。

## 安全保证与局限

- **只允许三种工具**：`inspect_inventory`、`inspect_coverage`、`select_budget_scenario`，每轮最多一个工具、最多四轮。
- 不允许 Shell、任意网址、云凭据查询、实际库存锁位、报价审批、自动发信。
- GitHub Actions 默认读取仓库中的源代码；使用当前 `main` 的可信版本，不在 Fork PR 中提供密钥，workflow 权限仅 `contents: read`。
- 通过本次云端模型联调**不等于**通过公司 API、IMDS 真实数据、IAH 生产部署、KMS/VPC 与最终 OpenClaw 迁移的企业级安全验收。
- GitHub Secrets 不会自动同步用户在聊天中发出的密钥，必须由有仓库权限的人在 GitHub 设置中录入。
- 联调后建议撤销专用测试密钥或禁用不必要的外部调用权限。

## 已启动的首次云端检查

[首次云端工作流结果](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44895304431)：`Check encrypted Actions secret` failed，后续真实 Tool Calling 步骤全部 skipped。此为缺少凭据的阻塞记录，**不能当作真实调用失败或服务商宕机的证据**。
