# CompanyAgent v1.0 · 可信交付与验证报告

## 设计参考与保留边界

本次增强对照了以下开源企业 Agent 技术体系的能力边界，所有核心代码独立实现：

- **Dify**：Human-in-the-Loop 和显式审核节点；本项目增加 **管理员对演示成果的审核**，而不是让模型决定正式报价。
- **Agno / AgentOS**：执行追踪、评估、工具审批和 RBAC；本项目增加 **质量门禁+审计日志+审批角色检查**。
- **LangGraph**：状态持久化与可重复执行；本项目为每次 Agent Run 保存同数据下的预算变体，提供只读快照和 SHA-256 绑定审核，不引入 LangGraph Runtime。
- **Pi SDK**：可嵌入式 Agent Runtime 设计；本轮**未集成 Pi**，不将规则工具编排冒充自主管理的 LLM Agent。

参考：
- https://www.dify.ai/blog/the-human-input-node-bringing-human-judgment-into-automated-workflows
- https://docs.agno.com/agent-os/introduction
- https://github.com/langchain-ai/langgraph
- https://docs.pi.dev/latest/sdk

## 新增功能

| 模块 | 路径 | 核心约束 |
|---|---|---|
| 质量门禁 | `enterprise/quality.py` | 预算、明细、数量、目标地标证据；未核验不称锁位 |
| 数据冻结 | `enterprise/engine.py` | 三档预算使用一次任务相同库存/覆盖/刊例数据与 Skill 策略 |
| 审批 | `GET/POST /enterprise/api/runs/{id}/quality|review` | 仅管理员；每次审批绑定结果 SHA-256；普通员工不能越权 |
| 交互 HTML | `GET /enterprise/api/runs/{id}/proposal.html` | 认证下载、离线脚本、无 CDN/远程调用、不插入未转义脚本 |
| 浏览器前端 | `enterprise_web/` | 查看质量门禁、演示审核、直接下载离线 HTML |

> **批准范围：**批准的是用于比赛/内部演示的方案呈现，而非库存确认、预订锁位、正式合同、金融结果或企业商用生产部署。

## 验收

- `python -m pytest -q`：28/28 后端测试通过。
- 15 种行业×预算组合：全部确保金额 ≤ 预算，并生成 2027 年期限内的参考方案。
- `node --check enterprise_web/app.js`、`node --check web/app.js`：静态语法检查通过。
- Chromium 真机浏览器：在一个 HTML 文件中点击 200→100→500 万，金额和清单基于同一数据的独立计算结果变化；手机布局验证通过，未发生 JavaScript 运行错误。
- 安全负面测试：员工/经理不能审批他人结果、无 Cookie/CSRF 不能审批、空媒体/虚假总价不能获得批准、审批后篡改数据会标为 stale、注入 `</script>` 不会跳出 JSON 数据块。

截图：`docs/verification_v10/offline-proposal-desktop.png`、`docs/verification_v10/offline-proposal-mobile.png`。

## 尚未实现

- **真实 B1X 模型联网 Tool Calling 测试**：未在本轮执行，B1X 模型仅保留可选解释接口。
- **真实 2027 红豆可售查询**：赛题授权系统未给出经确认的可调用 API；只能加载赛事许可的导出文件，不可绕过验证码或私自抓取。
- **生产治理**：缺少真正多租户、企业 SSO、网关强制执行、不可篡改远程审计与密钥托管；仅本地 M​VP，不可直接公网开放。
- **全局最优算法**：当前为可解释的约束启发式优化，不保证数学全局最优。

## 公开/私有数据

GitHub 公开版仅有**合成库存和模板**。不能将竞赛专用 Excel、红豆登录信息、覆盖 CSV、企业合同或付费模型密钥加入此仓库。

从真实业务数据生成的离线 HTML 也包含线路清单，不应作为公开 GitHub 资源上传。仓库随附的离线 HTML 仅使用虚构合成媒体记录。
