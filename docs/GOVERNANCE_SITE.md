# CompanyAgent · 安全治理与迁云验证站

本目录为与 v1.3 客户提案/变更工作台并行的**脱敏、本地优先治理原型**。它不处理企业真实数据，不是已授权的生产管理平台，也不是已上线的 Google Sites/Wix 网站。

## 使用
安装仓库依赖、运行 `python server.py`，打开 `http://127.0.0.1:8765/governance/`。
原有客户 Brief → Agent 候选方案 → 变更影响功能仍在 `/enterprise/`，登录与授权约束不变。

## 九个栏目
- 迁云方案：AWS Lightsail/EC2 与候选平台成本、区域、网络和内网边界
- CompanyAgent/Hermes 架构：Runtime、Model Broker、KMS、Gateway、PDP/PEP、Shadow Mode
- IAH 与 MCP：工具、scopes、租户隔离、审计和健康状态
- IMDS PoC：仅展示先前记录的合成用例及微基准，真实数据验收为待验证
- 风险与安全边界：SecretRef/密钥/IAM/VPC/代理/白名单与自动风险扫描
- 验证门禁：标准、失败证据与回滚条件
- 迁移进度：公开任务、双轨验证、内部 API 接入审批
- 待确认决策：平台选型、内部连接、切流验收
- 汇报材料：根据记录确定性生成文字、风险与决策对照

## 证据语义和安全边界
每条记录带有“已核实 / 待验证 / 规划能力 / 最终决策”之一。当前种子数据均不是 2026-11-21 当日重新执行的现场验证证据。

**公开任务可先迁移；公司内部 API、密钥、合同和敏感数据在隔离、授权、审计及网络门禁通过前不得接入。** 禁止在表单输入真实 API Key、密码、私钥、内网主机名、客户身份资料；界面含基本令牌模式拒绝与 XSS 安全渲染，但并非完整 DLP。

数据仅存储于当前浏览器 localStorage，支持 JSON 导出/导入。它既不能跨设备自动同步，也不具备企业多用户权限、加密数据库、不可篡改审计或后端鉴权。在未实现内网后端与身份认证前，**禁止用于存储生产敏感治理证据**；示例页面可公开，但实际内部信息应在私有部署中管理。

模型联调状态：仓库 v1.2/v1.3 的受限 Tool Calling 通过 MockTransport 协议测试，但未见授权 B1X 密钥和真实模型实联调证据，故该验收门禁保持待验证。

## 测试
- Node: `node --check governance_site/core.js && node --check governance_site/app.js`
- Node: `node --test governance_site/core.test.js`
- Python 路由检查及原有业务回归：`python -m pytest -q`
- CI: `.github/workflows/governance.yml` 以及已有 `ci.yml`

导出报告仅为建议文本，不构成自动批准。外部价格（如 Lightsail 4 GB 约 USD 24/月）是历史估算，必须复核官网和所选区域。
