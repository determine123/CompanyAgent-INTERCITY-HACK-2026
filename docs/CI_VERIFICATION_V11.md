# CompanyAgent v1.1 发布验证记录

此文档记录 INTERCITY HACK 的公开版 **v1.1**，不含比赛私有数据。

- 先在隔离本地 Python 环境完成 `39/39 pytest`、Python compileall、前端 Node JS 语法校验及 Chromium + FastAPI 桥接浏览器验收。
- 正式发布前，GitHub Actions 对 SHA-256 为 `ca4b3468e12b13e0f6a0201cf1d4af5dcc6fdc64857dcc38439e07cd63bf12fd` 的 58 文件源码 ZIP 重做这些可自动复现的编译与 pytest 校验，**全部成功后**提交源码至 main。
- [受控发布工作流 · Success](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44880392674)
- 公开版仍是规则驱动 Agent，不代表 Pi / Agno / LangGraph runtime 已集成。
- 没有真实 2027 红豆可售 API 访问与锁位授权；`15/15` 行业预算评估仅代表模拟数据下的技术回归。

后续对主分支的每次业务代码更新应继续坚持测试通过后发布。
