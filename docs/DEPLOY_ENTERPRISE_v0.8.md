# CompanyAgent v0.8 · Windows/云电脑本地部署

## 推荐环境
- Python 3.11–3.13，Windows 10/11、Linux 或 WSL；本机或可信云桌面；至少 2 GB 内存。
- 浏览器 Chrome / Edge，建议 1366×768 以上，移动端也做了响应式验证。
- **禁止将此演示原型的 8765 端口直接暴露公网。** 默认只监听 127.0.0.1。

## 方法 A：Windows
1. 解压完整私有 ZIP 到无中文路径，例如 `D:\CompanyAgent`。
2. 双击 `run_windows.bat`，或在 PowerShell 执行：

```powershell
py -m pip install -r requirements.txt
py server.py
```

3. 浏览器打开 **http://127.0.0.1:8765/enterprise/**。
4. 首次启动会生成随机管理员密码，打开 `runtime/FIRST_LOGIN.txt` 查看；用户名 `admin`。第一次登录后请修改密码，并妥善删除或保管初始密码文件。**不要向聊天、截图或仓库公开凭证。**
5. 第一个界面为员工 Agent 工作台；旧版广告提案页面仍在 `/`。

## 方法 B：Linux / Docker Compose

```bash
# 首次使用需安装 Docker Engine 与 Compose V2
docker compose up --build -d
# 获取容器日志、查看运行状态
docker compose logs --tail=40
```

浏览器打开 `http://127.0.0.1:8765/enterprise/`。管理员初始登录凭证同样写入挂载后的 `runtime/FIRST_LOGIN.txt`。Compose 将宿主端口仅绑定到回环地址，不对外公开。

## 启用本地文件夹自动采集

1. 在项目根目录找到 `runtime/imports/`（不存在时手动创建）。
2. 将**已经授权导出的**文件放进去，名字以 `inventory_`（库存）、`coverage_`（覆盖）或 `pricing_`（刊例）开头，扩展名 `.csv/.xlsx`。
3. 设置 `COMPANYAGENT_AUTO_SYNC=true` 后重启服务。后台每 60 秒扫描，SHA256 去重；也可在“数据源中心”点击立即扫描。
4. 把源数据文件留在该目录时会重复检查但不会新增相同哈希的数据集；建议及时归档到受控目录。

## 配置企业正式 HTTPS 数据接口

需业务方明确提供**已授权、返回 CSV 或 XLSX 的直接 HTTPS 文件地址**。没有 API 就不要通过页面隐藏接口或绕过验证码抓取。

```powershell
$env:COMPANYAGENT_ALLOWED_DATA_HOSTS="approved-data.company.example"
$env:COMPANYAGENT_SOURCE_A_TOKEN="服务器专用的授权令牌"
$env:COMPANYAGENT_AUTO_SYNC="true"
py server.py
```

管理员在“数据源中心”登记该主机的导出 URL、同步间隔和凭证环境变量名称 `COMPANYAGENT_SOURCE_A_TOKEN`，然后点击立即同步，验证数据。凭证不写入数据库或前端。出于 SSRF 防护，程序拒绝没有白名单、重定向、私网目标、非 HTTPS 443、带查询参数的地址。

## B1X 模型（可选）

```powershell
$env:B1X_API_KEY="仅在你的本地电脑环境中设置的比赛密钥"
py server.py
```

Agent 完成后点击“B1X AI 补充解读”，只有用户再次确认时才向 B1X 发送聚合摘要。浏览器不会收到完整密钥；不要把密钥写入 `.env` 并推送至 GitHub。比赛专用额度在 2026-11-22 23:00 到期，之后应换正式授权模型服务。

## 自测

```powershell
py -m pytest -q tests/test_planning.py tests/test_brief_workflow.py tests/test_coverage_preflight.py
```

新增企业权限测试在隔离目录运行，使用专用测试密码（**不要使用正式业务密码**）。详细见测试报告。

## 当前安全边界与升级路线

- 只支持**单组织本地测试**；密码哈希和 Session 并不等于完善企业身份管理。
- 旧版比赛 `/api/*` 接口仍缺少统一身份验证，严禁直接对公网开放。
- 上生产前必须增加 OIDC/SSO、租户级数据隔离、KMS/密钥轮换、审计长期留存、权限穿透测试、批处理和任务队列、TLS 终止与网络白名单。
