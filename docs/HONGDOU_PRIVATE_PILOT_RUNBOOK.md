# 红豆公交/地铁库存 · 企业私有只读试点探针

**状态：已完成安全客户端与合成契约回归，尚未获得真实企业联调结果，未在公网演示接入。**

## 根据已提供接口说明，能够确认的部分

- 两个 GET 查询：公交库存分页、地铁出入口库存分页。
- 参数：`pageNo`、`pageSize`、`startDate`、`endDate`；公交可用 `lineName`，地铁可用 `keyword`。
- 认证：`Authorization: Bearer <accessToken>` 与 `tenant-id`（只在受控服务端配置）。
- 未明确：JSON 响应字段、可售/锁定/已预订状态的字段语义、授权日期/线路范围、分页总数、错误码。
- 可视化覆盖**没有可接入的 API**，不能把它冒充实时查询。

## 代码交付

`enterprise/hongdou_private_pilot.py` 提供严格白名单下的只读查询。默认拒绝，**不会被公开 FastAPI 或 Railway 加载成工具**；只有企业私有终端运行 `scripts/probe_hongdou_private.py` 时，才在具备企业数据所有者授权和网络许可的前提下发出**一次** HTTPS GET 请求。真实主机和路径只通过企业私有配置指定，公开仓库不包含企业端点和访问凭据。

防护措施：

- 宿主名与企业网络出口白名单精确相等，禁止 IP、localhost 和占位域名；固定 HTTPS 端口，强制 TLS 验证。
- 路由只允许以 `/bus/page` 或 `/metro/page` 结束的分页只读接口，拒绝跳转、任意路径、恶意参数、超长日期范围、过大分页。
- 只使用 `GET`；不自动重试、不跟随跨域 30x、不继承代理变量。
- 单次数据仅返回**字段名、记录列表长度等结构元信息**，不保存或打印明细、手机号、真实库存价格、账号或 Token，也不发送给外部 LLM。
- 512KiB 响应流上限、8 秒超时、HTTP 401/403/429 等错误只输出状态码，不输出接口返回正文。
- 默认 `quantity_semantics_confirmed=false`、`real_stock_verified=false`、`bookable=false`。即便得到 HTTP 200，也不是库存可售验收。
- `cloud_synthetic` 模式拒绝所有 `HONGDOU_PILOT_*` 环境变量；公网 Railway 演示不能通过环境变量悄然启用该接口。
- 审批工单编号仅是引用，**不能代替企业数据所有者和安全负责人实际签字**。

## 需在企业内部准备的前提

1. 获得红豆系统所有者对**食品饮料行业投放方案试点**的只读数据范围、日期窗口、tenant 与 API 调用来源的书面批准。
2. 企业 IT/网络确认试点主机能在已审计出口访问目标域名及端口；确认 TLS、DNS、网络出口策略与 API 限额。
3. 采用企业 Vault/Secret Manager 注入短期有效 accessToken，**不要**存入 GitHub、公开 Railway、Prompt、对话、截图或 `.env` 的版本库文件。
4. 由授权人员在私有环境配置以下变量（仅列名字；实际值**不得分享**）：

```text
COMPANYAGENT_DEPLOYMENT_MODE=local
HONGDOU_PILOT_HOST=<企业审批的域名>
HONGDOU_PILOT_APPROVED_EGRESS_HOST=<企业网络白名单中同一域名>
HONGDOU_PILOT_BUS_PATH=<审批的公交只读分页路径>
HONGDOU_PILOT_METRO_PATH=<审批的地铁只读分页路径>
HONGDOU_PILOT_TENANT_ID=<获批 tenant ID>
HONGDOU_PILOT_ACCESS_TOKEN=<短期只读 Bearer Token>
HONGDOU_PILOT_APPROVAL_REF=<数据所有者审批工单引用>
```

5. 仅在审批通过、由企业 IT 提供的私有机器上执行，示例：

```bash
python scripts/probe_hongdou_private.py --media bus \
  --start-date 2026-11-21 --end-date 2026-11-21 --line-name "100" \
  --i-confirm-owner-approval --i-confirm-approved-private-network

python scripts/probe_hongdou_private.py --media metro \
  --start-date 2026-11-21 --end-date 2026-11-21 --keyword "上海南站" \
  --i-confirm-owner-approval --i-confirm-approved-private-network
```

两项查询都只请求第一页 **1 条**，不修改库存。操作员的勾选声明不能代替公司审批系统，实际网络出口仍需企业管理员提供并验证。

## 从接口探针到方案工作台真实接入的下一道门槛

在经过审核的私有试点环境中取得**匿名化 JSON 响应样例及数据字段词典**，再开发及测试确定性的库存字段映射（如可售、已锁位、合同占用与排期窗口）。映射测试通过后，才可以让**私有 Tool Gateway** 调用聚合只读数据；业务 Agent 只看许可的聚合结果，并对未知、多个候选、字段冲突标记 `needs_review`。未拿到响应契约前，不能把列表长度当作“可售数量”，更不能宣称完成真实库存联调或自动锁位。

正式接入仍受 `docs/V15_CLOUD_DATA_GATES.md` 中企业数据/SSO/租户/网络/审计/回滚门禁约束。
