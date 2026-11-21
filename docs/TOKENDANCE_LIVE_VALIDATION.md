# CompanyAgent v1.4 · TokenDance 受限 Tool Calling 联调手册

> 2026-11-21；状态：**协议适配与合成数据回归已实现，真实 TokenDance API 联调尚未完成**。不能把 MockTransport 测试宣称为真实联调成功。

## 1. 兑换与授权

照片中的 TokenDance 刮刮卡是**额度兑换码，不是 API Key**。兑换操作在本人已登录的 [TokenDance 额度页](https://tokendance.space/credits) 完成（请以网站实际菜单为准），一次性兑换码不要加入 GitHub、Issue、CI 日志、截图或聊天。若已公开传播，应尽快兑换或联系发行方处理。卡片注明在 2026-12-31 前兑换。

兑换成功后，在官方控制台单独创建**仅供联调用、低额度/最小权限**的 API Key，并确认一个支持 **OpenAI Chat Completions + tools / tool_calls** 的模型 ID。TokenDance 官方给出的网关 URL 为：

```text
https://tokendance.space/gateway/v1/chat/completions
```

https://tokendance.space/docs/protocol-openai-chat-completions

**注意：**网页宣称支持 OpenAI 兼容接口，不自动证明账户可用或选定模型支持工具调用；必须以真实响应验收。

## 2. 最小本地配置

在本机服务端环境设置（**不要提交 .env 文件或真正的密钥**）：

```bash
export COMPANYAGENT_MODEL_PROVIDER=tokendance
export TOKENDANCE_MODEL='<在控制台确认的工具调用模型ID>'
read -r -s -p 'TokenDance API Key: ' TOKENDANCE_API_KEY; echo
export TOKENDANCE_API_KEY
```

Provider 和 URL **固定白名单**：`b1x` 与 `tokendance`，不支持模型/客户输入指定自定义 URL。切回 B1X：`COMPANYAGENT_MODEL_PROVIDER=b1x` 且配置 `B1X_API_KEY`。

### Windows 一次性安全启动（推荐）

在自己的 Windows PowerShell 中更新仓库后，从项目根目录执行：

```powershell
python -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File scripts/accept_tokendance.ps1
```

脚本要求手动填写控制台核验的模型 ID、输入大写 `YES` 确认本次合成数据联网请求，再在隐藏输入框中输入**轮换后的新 API Key**。它调用同一个受限验收脚本，按退出码判断是否有真正 `tool_calls`，并在结束时清空本进程的环境变量。**不要把任何密钥复制到 PowerShell 命令行参数中。**

如果旧密钥曾经贴进聊天、工单或截图，先到 TokenDance 控制台撤销旧密钥并创建新的短期低额度密钥。运行成功不意味着正式业务数据已得到授权或生产环境安全门禁通过。

## 3. 验收顺序

先运行离线回归（不会消耗额度）：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q enterprise scripts
node --check enterprise_web/app.js
```

然后使用**纯合成数据**运行真实联网探针（产生模型账单；须本次显式授权）：

```bash
python scripts/verify_tokendance_tool_calling.py --i-authorize-external-call
```

合格标准：真实 HTTPS 请求成功，非 `MockTransport`，模型至少返回一次 `tool_calls`，本地执行工具后能带结果完成第二次对话，输出 `verification_status=tool_calls_executed`。如果只返回文字或超过 4 轮仍没有最终回复，则**不算通过**。此脚本只输出安全摘要，不会打印 Key、兑换码或原始请求。

## 4. CompanyAgent UI 路径

`python server.py` → `http://127.0.0.1:8765/enterprise/` → 登录 → 「客户需求与方案」 → 用**合成库存**生成 Run → 点击「真实受限 Tool Calling」 → 每次明确授权 → 查看实际模型、工具轨迹和最终说明。

- 只向模型提供聚合数量、行业、预算选项；
- 只允许 `inspect_inventory`、`inspect_coverage` 和 `select_budget_scenario`；
- 每轮最多 1 个调用，最多 4 轮；不允许写入、shell、锁位、报价审批、读取凭据；
- 使用冻结 Skill 权限快照，缺权限、请求失败、格式异常、预算越权均拒绝；
- 不调用红豆真实库存 API，不读取企业敏感数据，不构成生产迁移验收。

旧的 `/enterprise/api/runs/{id}/ai-explain` 仍是独立的 B1X 文本解读接口，不能因为 TokenDance Tool Calling 已配置就认为这个旧接口自动切换了服务商。

## 5. 验证记录

| 检查项 | 状态 |
|---|---|
| TokenDance 官方 OpenAI Chat Completions URL | 官方文档已核对 |
| 服务端 TokenDance Provider 适配 | 已实现 |
| 白名单工具协议和脱敏请求 | CI 合成数据测试 |
| GitHub Actions 全套回归 | 以对应提交的实际运行记录为准 |
| 兑换券入账、API Key 生成 | 未核实 |
| 真实模型 Tool Calling | **未完成，须有效密钥与可联网的运行环境** |
| 企业数据访问、真实上刊、内网联通 | 不在本次联调范围内 |

## 6. 真实联调失败时

- 401/403：核对是否已兑换并新建专用 Key；不要把兑换码当 Key。
- 404/400：核对具体模型 ID、协议与 `tools` 支持情况。
- 429：额度、频率或并发限制，需要到服务商控制台核对。
- 200 但 `no_tool_calls`：模型仅回答文字，不满足 Tool Calling 验收。
- 工具非法、参数越权或超 4 轮：必须失败关闭，不允许通过模型自我授权解决。

审计记录只保存最小工具名称、参数和聚合结果；严禁粘贴认证头、原始数据或模型完整请求日志到公开 Issue。
