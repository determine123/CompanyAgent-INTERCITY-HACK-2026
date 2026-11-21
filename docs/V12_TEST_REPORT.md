# CompanyAgent v1.2 交付验收记录

| 项目 | 当前状态 |
|---|---|
| 本地 Python pytest | 58/58 通过 |
| Python 编译 | 通过 |
| Node JS 语法检查 | 通过 |
| FastAPI 登录、前端资源、CSRF 和业务接口 | 通过自动测试 |
| B1X Chat Completions 工具协议 | 使用 mock transport 通过多轮、异常和越权测试 |
| B1X 线上模型真实 token/API 调用 | **未执行**，没有可用密钥，不得声称成功 |
| 431 行历史库存 + 44 条三商圈真实授权覆盖导出 | 私有本地脚本解析/匹配完成，匹配 32 个不同媒体；未提交数据到公开仓库 |
| 2027 红豆日历档期与锁位 | **未验证**，不代表正式商业可售 |
| 浏览器 Chromium E2E | 未通过环境可访问性门禁，浏览器本地 URL 被管理策略屏蔽；静态 JS 和 FastAPI 接口已验证 |

## 本地重测

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q server.py enterprise src
node --check enterprise_web/app.js
node --check web/app.js
```

## 授权与隔离

公共源码包只包含虚构演示 CSV、模板、源码、测试、设计文档。**不包含**红豆账号、私有 XLSX、三份商圈原始 CSV、比赛密码、模型密钥或开发机 SQLite。日志只记录有限聚合/状态，不记录模型认证令牌。
