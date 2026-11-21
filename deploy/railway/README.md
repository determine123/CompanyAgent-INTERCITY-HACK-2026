# Railway 两服务公网演示部署 · CompanyAgent v1.7

> **仅限合成数据展示，不是企业内网试点或生产环境。**
> 当前状态：Railway 配置与 CI 已提交；尚需连接 Railway 账户、创建服务、生成真正的公网网址后才算上线。

## 目标架构

```text
访客浏览器 HTTPS
     │  Railway edge 自动 TLS (*.up.railway.app)
     ▼
companyagent-gateway [唯一公网服务，Caddy :8080，Basic Auth]
     │  Railway project private network
     ▼
companyagent [无 Public Domain，:8765，第二层应用登录]
     │
     └─ cloud_synthetic：食品饮料 · 合成库存 · 内存/临时 SQLite
        ├─ /api/* 拒绝访问
        ├─ 企业数据导入、同步、用户创建与五行业基准测试均拒绝
        ├─ 无 TokenDance/B1X/红豆真实 API Key
        └─ 不具备生产 SSO、持久化审计、企业数据隔离
```

Railway 官方提供 GitHub 构建 Dockerfile、私网 `<service>.railway.internal`、自动 HTTPS 和 `.up.railway.app` 域名：

- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/networking/private-networking
- https://docs.railway.com/networking/public-networking

## 1. 创建项目和后端私有服务

在 https://railway.com/dashboard 登录，**New Project** → **Deploy from GitHub repo** → 选择：

```text
determine123/CompanyAgent-INTERCITY-HACK-2026
```

使用已合并并通过 CI 的 `main` 分支。将该服务明确命名为 **companyagent**，切勿添加 Public Domain 或 TCP Proxy。

在服务 **Variables** 设置：

```dotenv
RAILWAY_DOCKERFILE_PATH=deploy/railway/backend.Dockerfile
PORT=8765
HOST=0.0.0.0
COMPANYAGENT_DEPLOYMENT_MODE=cloud_synthetic
COMPANYAGENT_RAILWAY_PRIVATE_BACKEND=true
COMPANYAGENT_COOKIE_SECURE=true
COMPANYAGENT_AUTO_SYNC=false
COMPANYAGENT_REAL_DATA_ENABLED=false
COMPANYAGENT_ALLOWED_DATA_HOSTS=
COMPANYAGENT_RUNTIME_DIR=/app/runtime
COMPANYAGENT_ADMIN_PASSWORD=<在 Railway 私密变量中输入独立的 20 字符以上强密码>
```

`backend.Dockerfile` 本身也固定 cloud_synthetic 运行模式；启动时会拒绝弱密码、不安全 Cookie、企业 API Key、源同步、生产标记及错误端口配置。

**不要**将密码写入 GitHub、PR、聊天或共享截图。此服务必须是**私有服务**：`companyagent.railway.internal:8765` 仅在同一项目、同一环境的 Railway 私网内解析。应用为单进程、单实例演示，不能设置多个副本或将临时 SQLite 当持久数据库。

## 2. 新建唯一公网网关服务

在**同一个 Railway Project 和 Environment** 内，选择 **+ New → GitHub Repo** 再次使用上述仓库，命名服务为 **companyagent-gateway**。

设置 **Variables**：

```dotenv
RAILWAY_DOCKERFILE_PATH=deploy/railway/gateway.Dockerfile
PORT=8080
RAILWAY_DEMO_USER=reviewer
RAILWAY_DEMO_BCRYPT_HASH=<Caddy bcrypt 哈希，不是明文密码>
```

在可信本机或私有终端生成 bcrypt 哈希（这里是交互式输入，不传到命令历史）：

```bash
docker run --rm -it caddy:2.10.2-alpine caddy hash-password
```

按提示输入单独的网关密码，并将输出的 **完整 bcrypt 哈希**保存到 Railway 的 `RAILWAY_DEMO_BCRYPT_HASH` 私密变量中。它必须与后端的 `COMPANYAGENT_ADMIN_PASSWORD` 不同。不要设置 `PUBLIC_DEMO_DOMAIN`，这里使用 Railway Edge 管理 TLS。

在 **companyagent-gateway → Settings → Networking → Public Networking → Generate Domain** 生成 `https://<真实随机名>.up.railway.app`。**只为网关生成域名，后端不生成**。网关的配置仅代理到固定的 `companyagent.railway.internal:8765`，任何服务名称变动都要同时修改网关文件并重新测试。

## 3. Railway 运行与访问检查

部署先后顺序：后端 READY → 网关 READY → 生成公网域名。用户只在公网端访问：

- `https://<生成的域名>/enterprise/`：客户需求与 Agent 参考方案工作台
- `https://<生成的域名>/governance/`：CompanyAgent 治理与迁移台

第一次 HTTP Basic Auth 输入网关用户名/密码，网页内的企业工作台登录输入用户名 `admin` 和**另一把**后端应用密码。所有数据均是合成演示，只有**食品饮料**行业；真实红豆公交/地铁库存与可视化 API 均未接入。

验证清单：

```bash
# 1. 不带密码应返回 401
curl -s -o /dev/null -w '%{http_code}\n' https://<DOMAIN>/healthz
# 2. 正确 Basic Auth 的 /healthz 应返回 cloud_synthetic / production_ready=false
#    建议在浏览器完成登录，不把密码放在 shell 参数和历史中
# 3. 经过 Basic Auth 的 /api/demo 返回 403
# 4. 经过 Basic Auth 的 /enterprise/api/datasets/upload POST 返回 403
# 5. 浏览器开发者工具确认应用 Cookie 标记 Secure、HttpOnly、SameSite=Strict
# 6. Railway Settings 确认 companyagent 没有 Public Domain / TCP Proxy
```

如果出现 Caddy `502`，首先核对 **两个服务处于同一环境**、后端服务名称严格为 `companyagent`、`PORT=8765`、后端部署日志无失败。若得到 503/504，检查 Railway 健康与两服务资源状态。不要为了修复 502 给后端生成公网域名。

**注意**：网关所有路径都受 Basic Auth 保护，Railway 若配置自动 Healthcheck `/healthz`，未经凭据会返回 401；这不能代表服务故障。可不配置 Railway 对网关的 HTTP Healthcheck，而在人工授权情况下测试端到端健康。

## 4. 安全、费用与回滚

Railway 属于面向公网的第三方云平台。本项目**不部署**红豆真实 API、公司内网地址、IMDS 真实数据、TokenDance 密钥或企业用户权限信息。Railway 普通容器文件系统可能因重启/重新部署丢失数据：所有业务数据必须被视为临时合成数据，不能当作长期留存或真实库存。

请在 Railway 设置预算/费用通知、单副本、最小资源配置；**服务部署可能产生费用**，账单以 Railway 实际账户与计划为准。

紧急停用：先在 Railway 删除 **companyagent-gateway** 的 Public Domain，或停止该服务，阻断全部公网访问；后端始终没有公网域名。如发现认证失败、越权、泄露或异常流量，应关闭网关、轮换两层密码并检查 Railway 日志。不应通过关闭鉴权或开放端口 8765 来恢复访问。

## 5. 正式企业试点仍被阻断

公司的公交/地铁库存接口和可视化资料不在 Railway 公网演示范围。企业内部试点须取得数据所有者审批、VPN/VPC 受控网络、租户权限、KMS/企业 Secret Manager、真实响应 JSON 契约、审计和回滚验收。**不允许用 Railway 公网演示代替企业审批或最终 OpenClaw 生产迁移**。

## 6. CI 验证

`scripts/railway_synthetic_smoke.sh` 在 GitHub Runner 以本地 Docker 模拟 Railway 两服务拓扑，测试 Basic Auth 401、旧 API/企业导入/用户创建 403、Secure Cookie、后端无公网端口；它没有访问 Railway 账户或部署真实域名。工作流 `.github/workflows/railway-synthetic.yml`。

实际部署与公网域名状态只能以 Railway 运行日志和外部 HTTPS 验证为准，不能用本地 CI PASS 代替。
