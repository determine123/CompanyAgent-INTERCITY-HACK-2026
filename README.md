# CompanyAgent v1.3 — 客户需求、AI 提案、授权数据与排期变更协同

**INTERCITY HACK 湖州场 · AI+办公赛道 · company Agent**

> **公开评审版**：使用虚构演示数据运行；比赛专用媒体库存、合同、平台账号及密钥不包含在此仓库。  
**技术实现：**FastAPI + SQLite + Web UI + 授权业务工具 + 质量评估与 Skill 策略版本。

> 愿景：企业员工只需要描述要解决的问题，平台就能帮助搭建岗位 Agent/Skill、使用授权数据执行任务，并根据结果反馈持续改进。**先解决问题，再证明改进有效。**

## v1.8 · 公网端到端验收 / 红豆企业私有试点探针

- **已在真实 Railway HTTPS 公网地址完成 25/25 项接口验收**：正确网关密码与应用登录、安全 Cookie、Agent 列表、食品饮料合成需求、方案 Run #3 的生成与读取；错误密码/无会话返回 401、非食品饮料返回 400、旧版 API/导入/用户创建/数据同步/跨行业基准测试返回 403。详见 [2026-11-21 实网验收报告](docs/RAILWAY_REAL_PUBLIC_E2E_2026-11-21.md)。这是实际网络 HTTP API 测试，不是图形浏览器端的手工点击验收。
- **红豆公交/地铁库存只读客户端现已实现**，带精确企业网络出口主机、私有路由、日期与分页、租户授权、Bearer Token、TLS、无重定向、限量响应检查；仅在公司批准的私有环境中由操作员显式执行，不通过公网 Railway、GitHub Actions 或外部模型发起企业数据请求。参见 [私有联调操作手册](docs/HONGDOU_PRIVATE_PILOT_RUNBOOK.md)。
- **当前仍未完成真实红豆 API 联调**：接口说明包含 GET 路径与请求头，但尚无可用授权 Token、已批准的私有运行环境或经过审核的匿名响应字段样例。HTTP 200 也只能作为接口契约探针结果，不能直接当作可售库存。
- Railway 公网演示继续使用食品饮料合成数据，且已新增防护：任何 `HONGDOU_PILOT_*` 变量配置都会使 `cloud_synthetic` 启动拒绝。企业真实数据接入与 OpenClaw 生产迁移门禁不变。

## v1.7 · Railway 两服务公网演示（已部署合成展示）

新增 [Railway 专用部署手册](deploy/railway/README.md)：通过 GitHub 同一仓库创建**一个无公网域名的 CompanyAgent 私有后端**（`companyagent.railway.internal:8765`）及**唯一公网 Caddy 认证网关**（`PORT=8080`，Railway 托管 HTTPS）。仅展示食品饮料合成客户需求/参考方案，不包含真实红豆接口、可视化 API、TokenDance Key 或企业数据。此仓库交付部署配置和安全 CI，**实际 Railway 双服务已部署；公网入口 [在线工作台](https://companyagent-intercity-hack-2026-production.up.railway.app/enterprise/)，只用于合成数据**。

## v1.6 · 公网合成演示入口 / 食品饮料行业 / 红豆企业试点

- **公网演示配置**：新增 [Caddy HTTPS + Basic Auth 网关](deploy/public-demo/README.md) 与 Docker Compose。后端无 host-published `8765`，在 Docker 私有网络以非 root、只读根文件系统运行；仅供合成数据演示，不是生产部署。需自行准备 VPS、真实域名、DNS、两层独立认证及云侧入站规则；**当前仓库没有实际公网访问地址，也未代为开通云主机**。
- **行业固定**：公网 `cloud_synthetic` 模式只允许食品饮料行业；前端锁定选择，后端拒绝其他行业。100/200/500 万预算情景保留，方案不代表库存锁位、正式报价。
- **数据边界**：可视化平台暂无已获授权的 API；红豆公交/地铁库存 GET 说明已收到，但缺企业正式授权、响应字段样例与安全联通证据。公开仓库只提供[脱敏且不可联网的参数契约](enterprise/hongdou_contract.py)，真实接口域名/路径/tenant/Token 不进公开代码。见 [红豆企业试点门禁](docs/HONGDOU_ENTERPRISE_PILOT.md)。
- **验收**：GitHub Actions 通过网关无凭证 401、错误密码 401、旧 API/数据导入 403 负向测试；Python 校验行业和未知响应契约。真实企业数据、AWS VPC 与生产 OpenClaw 切换仍未放行。

## v1.5 · 独立验收 / 受控企业数据接入 / 合成云端部署

本轮新增 **fail-closed 预生产治理包**：

- `COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic` 下阻断旧版未认证 `/api/*`、企业数据上传/来源同步和桥接入口；拒绝模型 Key、企业连接令牌、自动同步和真实数据开关；`production` 模式拒绝启动，**不允许把本地原型当生产系统直接上线**。
- GitHub 云端 Docker 合成沙箱：非 root、只读文件系统、tmpfs 临时状态、宿主端口仅回环绑定，并验证旧 API 和数据导入接口被 403 拒绝。此为 **GitHub Actions 的临时云端容器**，不是已部署 AWS 生产环境。
- 企业数据来源/权限/校验离线预检：`enterprise/ingress_review.py` 只处理授权导出文件的 SHA-256、字段解析和记录数量，不持久化数据或调用外部模型；内网真实数据接入仍须先完成数据所有者与安全审批。
- 迁移证据门禁：`enterprise/migration_gates.py` 将云合成、企业试点与最终生产切换分开；即使全部 JSON 自述项为 verified，也不能据此自动授权生产部署。
- 安全验收计划与回滚矩阵：[v1.5 分阶段交付和门禁说明](docs/V15_CLOUD_DATA_GATES.md)。新镜像使用方式见 [cloud_synthetic README](deploy/cloud-synthetic/README.md)。

**明确状态：企业生产 SSO、租户隔离、KMS、VPC、真实库存、IMDS 真实数据、OpenClaw 最终替换均尚未验收，原生产系统不切流。**

## GitHub Actions 云端 TokenDance 实网验收

新增独立 **TokenDance LIVE Tool Calling (synthetic only)** 工作流，使用 GitHub **Repository Secret `TOKENDANCE_API_KEY`** 安全注入密钥（`workflow_dispatch` 手动选择支持 Tool Calling 的模型）。脚本只使用合成聚合数据，成功时生成 7 天有效的脱敏证据附件。**已在 GitHub 云端使用 TokenDance `glm-5.2` 通过真实 Tool Calling：3 个白名单只读工具调用，脱敏证据已上传**。见 [2026-11-21 实测验收记录](docs/TOKENDANCE_LIVE_VERIFIED_2026-11-21.md)；生产系统和真实企业数据仍未验收。

## v1.4 · TokenDance 受限 Tool Calling（可选，需本人兑换与配置）

- 新增固定地址 `https://tokendance.space/gateway/v1/chat/completions`，只能通过服务端 `COMPANYAGENT_MODEL_PROVIDER=tokendance` 启用；密钥与模型 ID 分别来自 `TOKENDANCE_API_KEY`、`TOKENDANCE_MODEL`，不提供任意自定义 URL。
- 沿用冻结 Skill 权限、三个只读聚合工具、每次外发确认、最多四轮、拒绝越权和零业务写入；模型只返回文字时不当作 Tool Calling 验收成功。
- **实网与离线测试已区分。** `glm-5.2` 在 GitHub Actions 完成 3 次只读 Tool Calling；`deepseek-v3.2` 实网返回 HTTP 403，原因未确认；兑换券是否入账未核实。已暴露的旧 API Key 应轮换。
- 纯合成数据一键验收：`python scripts/verify_tokendance_tool_calling.py --i-authorize-external-call`，须先在本机配置密钥和支持 Tool Calling 的模型 ID。
- 完整步骤与限制见 [TokenDance 联调手册](docs/TOKENDANCE_LIVE_VALIDATION.md)。旧的 B1X 文本解读接口仍独立保留。

## v1.3 新增：给客户的 AI 提案界面与排期变更协同

- **客户需求与方案**：员工从新入口填写品牌、五行业、100/200/500 万预算、2027 档期、商圈和媒体；选择自己的 Agent 后，基于其授权数据生成可追溯的候选方案、证据和风险清单，并导出可交互 HTML。预算变更会重新运行工具，不是单纯改页面数字。
- **排期变更影响**：针对客户改稿、车辆换线、车辆进保、城市管制、外包返工、监拍雨天自动列出车线、排期、制作、施工、监测和客户通知相关的待审核任务。只生成责任清单，不自动修改红豆或向客户发送信息。
- **受限 B1X 入口**：沿用 v1.2 的三种聚合只读工具和逐次外发授权；未设置服务端 `B1X_API_KEY` 时明确标注模型尚未完成真实调用。
- **验证**：71 项 pytest 全通过；Chromium 真实 UI + FastAPI TestClient 桥接通过客户需求、预算重算、变更链和手机端测试。

查看 [v1.3 方案与验证详情](docs/V13_CLIENT_WORKSPACE_AND_CHANGE_IMPACT.md)。

## 一、快速使用

安装 Python 3.11+，在项目根目录：

```bash
python -m pip install -r requirements.txt
python server.py
```

Windows 也可以双击 `run_windows.bat`。浏览器打开：

**http://127.0.0.1:8765/enterprise/**

首次登录：用户名 `admin`；一次性随机密码保存在本机 `runtime/FIRST_LOGIN.txt`。首次成功登录后该文件自动删除，**请尽快修改密码**。程序默认只允许本机访问；不要未经安全加固将它暴露公网。

原有交互广告提案页仍可在 `http://127.0.0.1:8765/` 打开。


## v1.1 新增：可重复执行的 Agent 评估与数据快照

参考 LangGraph 的 Checkpointer、Agno 的 Eval 和 OpenAI Agents SDK 的 Tracing/Guardrails，**原生实现，不依赖或冒充这些框架**：

- **冻结执行清单（Run Manifest）**：每次运行自动保存 Agent/Skill 当时的工具授权、策略版本、数据集 ID、SHA-256 指纹及媒体组合摘要；历史 Skill 修改不会改变这次运行的解释依据。指纹只用于一致性检查，不等于外部可信签名或不可篡改审计。
- **一键可验证重放**：登录后对历史 Run 点击「冻结数据重放校验」，从当时的授权本地数据集重新执行；若数据被修改、删除或结果记录变更，明确返回 `source_drift / result_changed / mismatch`，不会谎称“可重放成功”。重放不调用模型、第三方 API 或任何实际广告锁位工具。
- **规则评估集（Eval Suite）**：自动验证预算、实际选中媒介、三档预算变体、工具轨迹、商圈覆盖证据、来源描述共 6 项；另外有 **五行业 × 三档预算 = 15 个测试场景** 可通过工作台一键运行。
- **权限与人工边界**：任务所有者/管理员才可重放；Skill 当前版本变更不影响历史权限快照；更改后续价格与可售数据不会被静默回填到历史结果。

本地环境通过 **39 项后端测试、Chromium 浏览器端到端（真实 FastAPI 桥接）测试**。GitHub Actions 运行结果以仓库的最新 `main` CI 为准。详细说明见 [v1.1 架构与验证](docs/V11_RELIABILITY_AND_EVALS.md)。

## v1.0 新增：从 Agent 方案到可审计的交付

本版参考 Dify 的 Human-in-the-Loop、Agno 的评估和权限边界，以及 LangGraph 的可追溯执行理念，**自主实现**以下能力（不等于集成了这些框架）：

- **质量门禁**：对所选媒体检测预算上限、明细合计、库存单位数量、目标地标覆盖证据，保留 `blocked / needs_review / demo_ready` 明确状态；只输出可核实的事实，不让 LLM 猜测库存和价格。
- **人工演示审批**：管理员可批准/退回提案。审批绑定结果 SHA-256 快照；数据被改动则原批准自动失效。**审批仅针对比赛演示，绝不表示商业锁位、2027可售确认或正式报价**。
- **冻结数据的三档重算**：一个 Agent Run 持久化 100 / 200 / 500 万元的独立优化结果；用户调整预算，真实更新媒体清单和金额。
- **一键离线 HTML**：运行任务后点击「下载可交互 HTML 提案」；无需服务器，预算切换、数据来源和风险告知保存在单个 HTML 中。**真实数据导出的 HTML 可能包含媒体明细，不应未经授权公开。**

推荐评委路径：`/enterprise/` → 创建个人 Agent/Skill → 运行任务 → 观察质量门禁 → 管理员审批演示 → 导出 HTML → 离线切换预算。公开示例 HTML：`docs/verification_v10/CompanyAgent_v1.0_Offline_Demo.html`（仅虚构数据）。

**测试：**公开版新增 28 项完整后端回归（包含五行业 × 三档预算），本地 Chromium 还验证了离线 HTML 的预算/金额与媒体表格变化、桌面和手机布局；GitHub Actions 跑 Python 测试、Python 编译检查、前端 JS 语法校验。详见 `docs/V10_EVALUATION_AND_SECURITY.md`。

## 二、比赛期间优先演示

1. **从问题创建个人 Agent/Skill：**进入「我的 Agents」，描述具体广告业务问题，点击“一键创建”。生成的 Agent 与 Skill 默认私有，只可调用预定义的安全业务工具。
2. **让 Agent 执行任务：**在「智能任务执行」中选择行业、品牌、预算、2027年档期和商圈；平台使用库存、覆盖与刊例数据形成参考方案。
3. **现场修改预算：**100/200/500万元切换后由确定性算法重算媒体组合，结果不是简单改 UI 数字。
4. **展示自我迭代：**使用管理员默认「广告智能提案 Agent」，选择正大广场 + 500万元，取消「仅推荐有目标地标覆盖证据」。运行后平台检测到缺证据推荐，进入「自我迭代实验室」。
5. **对照、发布与回滚：**点击「运行对照测试」；只有在候选仍有效、预算不过限、缺证据推荐真正减少时，才允许所有者点击「批准发布」。重新执行同一任务验证效果，最后演示「回滚版本」。

在比赛参考资料上，示例对照结果：旧规则13项，缺证据1项，总价500万元；严格覆盖规则12项，缺证据0项，总价494万元。价格为**脱敏区间上沿情景测算**，不代表2027可售、正式报价或商业效果已验证。

## 三、真实完成与尚未完成

| 当前可用 | 明确未实现 |
|---|---|
| 员工与管理员登录；个人/共享 Agent 和 Skill 管理 | 多组织 SaaS、企业级 SSO、生产审计防篡改 |
| 一键从户外媒体业务问题创建 Agent/Skill | 任意行业自动生成可运行代码 |
| 批量读取授权导出的 CSV/XLSX，定时读取白名单HTTPS数据源 | 红豆系统、可视化平台未经确认的内部实时 API |
| 覆盖匹配、历史库存参考、预算约束优化、HTML提案 | 自动确认2027库存、锁位与合同价格 |
| 自动质量诊断、员工反馈、白名单策略 A/B 测试、审批发布、版本回滚 | 自动改写生产代码、自主编程/PR、Pi SDK 自主规划 |
| 可选 B1X 文字解读（需要外部授权模型密钥） | 模型工具调用经真实 B1X API 全链路验收 |

**重要限制：**当前执行器是固定的、可审计的工具编排，并非已经接入 Pi Runtime 的自主多步规划。当前“自我迭代”仅支持通过白名单发布**严格商圈覆盖证据**这一项策略。其他反馈进入记录和人工改进队列，不会冒充已自动修复。

## 四、数据及知识产权边界

- **队内参赛版**：包含组织者提供的历史公交台账、脱敏刊例及用户授权导出的正大广场、上海南站、新天地覆盖数据，供赛事范围内使用。
- **公开源码版**：不含 `data/contest_private/`，只使用 `data/demo_inventory.csv` 虚构样例。**不要把队内版 ZIP 推送到公开 GitHub**。
- 所有模型 API Key 和系统凭证仅保存在服务端环境变量中；示例代码不包含比赛账号密码，不会自动绕过第三方登录或验证码。
- 目前的企业身份认证仅保护 `/enterprise/api/*` 路由；旧版 `/api/*` 尚未统一加固，因此**项目仍是本地原型，不适合直接承载企业生产数据或公开部署**。

## 五、自动数据同步

方式 A：由管理员将授权导出放进 `runtime/imports/`，命名为 `inventory_*.csv`、`coverage_*.csv` 或 `pricing_*.xlsx`。设置 `COMPANYAGENT_AUTO_SYNC=true` 才会自动轮询目录。也可以在数据源中心手动扫描。

方式 B：管理员配置经批准的 HTTPS 数据接口，按环境变量 `COMPANYAGENT_ALLOWED_DATA_HOSTS` 配置精确允许主机。**不能把普通网页登录地址当作 CSV 接口。**

## 六、测试与开发

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

此前队内完整赛事开发目录报告 **75 项后端测试通过**；**当前公开源码仓库新增了 28 项可复现的业务/权限/质量门禁测试**。迭代页面通过 **16 项 Chromium 浏览器交互测试**，包括员工自定义、对照实验、策略发布与回滚、手机布局。浏览器测试需要 `playwright` 和可用 Chromium，开发时可运行：

```bash
python tests/browser_iteration_v09.py
```

公开版 CI 不依赖赛事参考文件，包含完整合成数据回归；真实 2027 库存仍待企业授权核验。参赛队内版才适合复现商圈 13→12 项的具体对照数字。

相关设计与局限：`docs/V09_PRODUCT_AND_SECURITY.md`。赛事实用一页纸：`docs/V09_ONE_PAGER.md`。

**部署及赛事提交状态：**本仓库只提供本地运行代码；是否已部署到公网或提交 B1X，请以对应平台实际状态为准。完整商务方案仍需要使用授权红豆系统查询目标 2027 档期的空车数，并经企业确认价格与施工资源。

## v1.2 — 受限 B1X Tool Calling、授权数据桥、故障驱动 Skill 实验

- **B1X 真正的 Chat Completions 工具协议**：只开放三个白名单聚合型只读函数，四轮以内，参数严格校验，员工逐次明确同意外发。服务器设置 `B1X_API_KEY` 后才可调用；**无密钥时只会明确报错，不会伪装模型调用成功**。
- **红豆 × 新云授权数据关联**：Data Hub 选定授权 CSV/XLSX 库存和覆盖，严格对齐公交编号/名称，保留证据、来源 checksum 和日期限制。历史库存及空间覆盖**不等于 2027 可售、已锁位或正式报价**。
- **执行失败驱动 Skill 迭代**：缺工具/数据/模型时登记诊断；可修复的缺失覆盖工具在同一冻结输入上先做 before/after 测试，人工审批后才会变更 Skill，随时可回滚。不可通过模型擅自扩权或执行代码。

详细接口、权限边界、实际数据验证与已知限制参见 [v1.2 交付文档](docs/V12_MODEL_DATA_ITERATION.md)。
