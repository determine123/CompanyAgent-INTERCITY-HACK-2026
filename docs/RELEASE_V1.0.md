# CompanyAgent v1.0 · INTERCITY HACK 发布验收

**发布日期：**2026-11-21（比赛期间）  
**提交目标：**上海新云传媒 · AI+办公赛道  
**运行环境：**本地 Python 3.11+ / FastAPI，默认仅监听 127.0.0.1。

## 新增能力

- 企业员工可自建个人 Agent、Skill 与安全工具组合；保留 v0.9 的反馈、对照实验、人工发布和回滚。
- Agent 提案新增覆盖证据、金额、数量与历史档期校验，标记 `blocked / needs_review / demo_ready`。
- 管理员审批**仅限演示用途**，对结果快照做 SHA-256 绑定；正式商务承诺不在范围内。
- 预算 100/200/500 万分别根据同一数据快照重新计算；可下载单文件、无 CDN 的交互式 HTML。
- 独立 HTML 会写明数据来源、可核验范围、风险告知，不暗示 2027 档期已售或锁位。

## 验收证据

**本地：**`python -m pytest -q` → 28/28 通过，包含 15 组行业×预算参数。  
**静态：**Python compileall、前端 Node JavaScript syntax 检查通过。  
**浏览器：**Chromium 实测 HTML 200→100→500 万切换，金额确实变化；手机交互正常，零 JS 运行错误。  
**GitHub 发布门禁：**[通过的 v1.0 verify/publish 工作流](https://github.com/determine123/CompanyAgent-INTERCITY-HACK-2026/actions/runs/44879549874)。

## 使用

```bash
python -m pip install -r requirements.txt
python server.py
```

打开 `http://127.0.0.1:8765/enterprise/`，首次管理员密码在本机 `runtime/FIRST_LOGIN.txt` 中；登录后更改密码。详细说明参见 [README](../README.md) 和 [验证文档](V10_EVALUATION_AND_SECURITY.md)。

## 边界

公开仓库只包含合成媒体样例；真实赛事库存和覆盖数据、账号密码及密钥均未上传。代码中的 Agent 当前为确定性工具编排，不应声称已集成 Pi Runtime、企业级多租户治理或完成真实 B1X 模型工具调用。对真实 2027 库存和正式报价的核验仍需企业授权。
