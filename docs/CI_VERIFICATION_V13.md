# CompanyAgent v1.3 · 参赛版本及 GitHub CI 验收记录

**场景：**上海新云传媒，AI+办公，INTERCITY HACK 湖州场。

## v1.3 交付

- 客户需求界面：品牌、五个赛题行业、100/200/500 万元、2027 年档期、媒体、地标、自然语言 Brief。
- Agent 方案：基于当前用户有权读取的库存与覆盖数据，生成候选媒体清单、参考金额、质量门禁和交互式 HTML。
- 变更影响：客户改稿、车辆换线/进保、城市管制、外包返工、监拍雨天 → 责任岗位、车线、排期、制作、施工、监拍、客户确认的有序待办。
- 受限 B1X 接口：最多 4 轮、三个白名单聚合只读工具，单次用户确认，不发送原始客户 Brief、明细库存或企业凭证。
- 错误驱动 Skill 改进实验与审核/回滚沿用 v1.2。

## 可信范围与联调状态

**合成数据回归：**71/71 pytest，包含 6 种变更来源、权限隔离、非法变更、零副作用、CSRF 保护、模型 MockTransport 受限工具协议测试。

**浏览器回归：**Chromium 真实页面 + FastAPI TestClient 桥接，完成客户需求 200→100 万重新执行、车辆换线影响链、HTML 服务端导出、桌面和手机页面，零 JS 异常。图片：`docs/verification_v13/`。

**GitHub 发布门禁：**[v1.3 验证后发布工作流](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44885556285)，在完整测试通过后才提交业务源码。

**尚未完成：**本次环境没有获授权的有效 `B1X_API_KEY`，因此未执行真实线上 Chat Completions Tool Calling。库存桥接仍是授权 CSV/XLSX，不能声称红豆实时 API 已联通、2027 档期已锁定或已经有正式报价。请勿将比赛账号、API 密钥、真实业务资料上传公开仓库。

详见 [版本设计与限制](V13_CLIENT_WORKSPACE_AND_CHANGE_IMPACT.md)。

## 本地启动

```bash
python -m pip install -r requirements.txt
python server.py
```

打开 `http://127.0.0.1:8765/enterprise/`，登录后点击「客户需求与方案」。管理员首次随机密码保存在运行机器的 `runtime/FIRST_LOGIN.txt`，不要截图公开或提交 GitHub。
