# CompanyAgent · Railway 真实公网端到端验收（2026-11-21）

**结论：PASS，25/25 真实 HTTPS API 检查通过。仅限食品饮料行业合成数据，不能证明企业库存对接或浏览器视觉渲染。**

## 环境与证据

- Railway project：`dynamic-abundance`，environment：`production`（**仅是 Railway 环境名称，不代表 CompanyAgent 已达企业生产标准**）。
- 公开入口：[CompanyAgent 公网演示](https://companyagent-intercity-hack-2026-production.up.railway.app/enterprise/)。
- 私有后端：`companyagent`，没有公网域名；公网网关为 Caddy Basic Auth。
- 通过 Railway 项目内**一次性、无公网域名**的独立验收函数对真实 HTTPS 地址发起调用，凭据使用临时私有环境变量，不进入仓库、输出或业务数据库。
- 验收函数最终部署 ID：`d8a20845-d8dc-4fd0-b118-0b126923d064`。
- 生成的合成需求及方案：**Run #3**，投放行业 `食品饮料`、合成预算 **200 万元**、起始日期 `2027-05-01`；不涉及真实用户、库存锁位、业务审批。
- 该测试会话完成后应删除临时 Railway 函数及其测试凭据。文档仅保存脱敏摘要。

## 真实状态码与功能

| 检查 | 实测 |
|---|---|
| 无 Basic Auth 访问前端 | 401 PASS |
| 错误网关密码 | 401 PASS |
| 正确密码加载工作台 HTML | 200 PASS，正文非空 |
| 应用内 `admin` 登录 | 200 PASS |
| 登录 Cookie | Secure / HttpOnly / SameSite=Strict PASS |
| 已登录查询 `/enterprise/api/status` | 200 PASS |
| 返回演示环境状态 | `deployment_mode=cloud_synthetic` PASS |
| 红豆与可视化 API 状态 | 两者均未接入，PASS |
| 已登录 `/me` 和 Agent 列表 | 200 / 200 PASS |
| 非食品饮料行业请求 | 400 PASS |
| 食品饮料合成需求与方案生成 | 200 PASS，Run #3 |
| 方案行业与查询已保存的 Run | 食品饮料 / 200 PASS |
| `/api/demo` 旧接口 | 403 PASS |
| 企业数据上传 | 403 PASS |
| 用户创建 | 403 PASS |
| 数据来源同步 | 403 PASS |
| 五行业 Benchmark | 403 PASS |
| 未携带会话访问应用接口 | 401 PASS |

上表覆盖了总共 **25 项**检查，其中若干多字段检查被合并展示。首次探测有 4 项在登录前误查受保护状态接口而收到 401；调整测试顺序后重新执行，**25/25 全部通过**。这是验收脚本的测试顺序问题，不是绕过鉴权或后端失败。

## 边界与下一步

- 本次验证为**HTTP API 实际网络调用**，包括正确网关密码、应用会话、CSRF、真实合成需求写入、方案生成和禁用端点；**并非自动化浏览器截图/按钮点击验收**。
- 公网端点仍不能读取任何真实红豆公交/地铁库存。真实数据不能借助公开 GitHub Actions、模型 API 或 Railway 演示服务导入。
- 红豆库存的接口说明已经给出两个只读 GET 路由和 Bearer/tenant-id 认证方式；仍缺独立确认的企业数据所有者批准、有效试点 token、受控网络可达性、返回字段样例和可售/已预订字段语义。私人试点探针见 `enterprise/hongdou_private_pilot.py`。
- Railway 运行环境内合成数据可能随重启消失；Run #3 是这次实例的验收证据，不代表永久归档。
- 此处没有公布用户名、网关密码、应用密码、Cookie、Bearer Token 或任何真实接口响应正文。
