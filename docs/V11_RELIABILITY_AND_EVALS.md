# CompanyAgent v1.1 — Agent Eval、冻结重放与可观测性

**INTERCITY HACK · AI+办公 · 发布候选**

## 国外开源 Agent 项目的参考点（借鉴设计，不是集成其完整框架）

| 参考项目 | 官方原理 | CompanyAgent v1.1 采取的可验证实现 |
|---|---|---|
| [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | checkpoint / 重启恢复 / 人工审核与状态追溯 | 每次执行冻结 Dataset ID、原始记录指纹、Agent + Skill 授权，支持确定性重放；**不具有 LangGraph 的任意中断恢复能力** |
| [Agno Evals](https://docs.agno.com/features/evaluation) | 将输出标准、工具使用等变为可执行测试 | 6 项质量检查与 15 行业预算组合回归；拒绝把“模型看着合理”当成通过 |
| [OpenAI Agents SDK tracing](https://openai.github.io/openai-agents-python/tracing/) | 追踪 Agent 和工具执行步骤 | 原生 `trace` + 历史快照摘要；**不是 OTel 或 OpenAI Traces 后端** |
| [Pydantic AI tool approval](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/) | 结构化约束、审批与可靠运行 | Skill 工具白名单、管理员演示审批、不可静默越权回放；**不是其 Durable Execution 引擎** |
| [Dify human-in-the-loop](https://www.dify.ai/workflows) | 工具流程中的人工审核 | 历史提案 SHA-256 绑定审批、发现变化自动标 stale；**仅批准演示，不表示可售锁位** |

## 新功能 API

- `GET /enterprise/api/runs/{id}/evaluation`：返回 6 项诊断、来源风险与质量门禁。
- `POST /enterprise/api/runs/{id}/replay`：使用**冻结的 Agent、Skill 及策略**执行只读本地重放，检测 `matched`、`source_drift`、`result_changed`、`mismatch` 等状态。
- `POST /enterprise/api/agents/{id}/benchmark`：五行业×三预算，共 15 个只读模拟测试，输出逐案例通过结果及实际花费；不会发送模型请求。

上述接口都经过本地 cookie 登录验证；POST 还要求会话 CSRF Token。普通员工不能读取/重放其他员工的私有运行。重放本身不修改原运行，也没有锁位与合同副作用。

## 关键测试

- **39 项 Python pytest 通过**（2026-11-21，本地 Python 3.13，隔离临时 SQLite；CI 采用 Python 3.11）。
- **真实 Chromium UI**：采用 Playwright 与 *FastAPI TestClient in-process bridge*，规避云端 Chromium 的本机端口访问限制；验证用户登录、Agent 执行、六项评估、冻结重放、15/15 预算矩阵、手机布局，并记录零 JS pageerror。
- **异常注入**：篡改历史库存记录 → `source_drift`；篡改历史输出 → `result_changed`；修改当前 Skill → 历史重放仍匹配；其他员工查看历史 Run → 404；无 CSRF 的 POST → 403；旧版本无 Manifest → 409。
- **源码语法**：Python compileall 与 Node `--check`。

截图：`docs/verification_v11/enterprise-eval-replay-desktop.png`；浏览器脚本：`tests/browser_v11.py`（需要 Playwright + Chromium，CI 不默认安装浏览器）。

## 明确不能宣称完成的事项

1. 它仍是固定安全业务工具编排，未完成 Pi SDK、LangGraph、Agno 或任何模型的自主规划与 Tool Calling 接入。
2. Hash 不是防篡改签名：具有 SQLite 文件管理权限的操作人可同时修改结果及指纹；需要生产审计时应使用外部不可变日志和 KMS 签名。
3. 公开仓库使用**虚构媒体数据**。未接红豆系统授权实时库存 API；不代表 2027 档期可售、锁位、正式报价、真实曝光与 ROI。
4. 这不是企业生产级多租户平台，不应直接公网部署；旧版 `/api/*` 仍未完成统一身份治理。
5. `15/15` 仅表示固定工具在合成数据上的行业×预算约束不出错，**并不验证五个真实品牌的营销效果**。

## 路演建议

1. 员工输入需求并选择岗位 Agent / Skill。
2. 运行 200 万媒体提案，展示路线、预算与数据来源。
3. 点击「冻结数据重放校验」→ 显示 `matched` 和原始指纹摘要。
4. 点击「五行业×三预算评估」→ 显示 `15/15`（使用合成数据）。
5. 展示审批、HTML 离线切换预算、以及修改 Skill 策略后的对照测试和回滚。

**演示解释**：我们不是用大模型生成看似可信的答案，而是在可控工具集和证据边界内先完成问题，再用自动化测试评估 Agent 的可靠性，促进安全自我迭代。
