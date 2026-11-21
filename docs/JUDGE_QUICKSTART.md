# CompanyAgent — B1X 评委快速启动指南

这是 INTERCITY HACK 湖州场 AI+办公赛道的 **CompanyAgent v2.3 公开评审版**。

## 评委零门槛体验（无需网关或企业账号）

https://companyagent-intercity-hack-2026-production.up.railway.app/judge/

仅加载版本仓库自带的 80 条虚构媒体数据，并调用相同的确定性优化器。支持切换预算和公交/地铁，展示三项风险与人工核验工作。该路径不访问企业数据库、不自动发邮件或锁位。

B1X 提交字段、演讲词见 `docs/B1X_SUBMISSION_V23.md`。


## 运行与演示

```bash
python -m pip install -r requirements.txt
python server.py
```

浏览器打开 `http://127.0.0.1:8765/enterprise/`，在本机查看 `runtime/FIRST_LOGIN.txt` 获取首次管理员密码。不要将该文件上传到代码仓库。普通广告投放方案页位于 `http://127.0.0.1:8765/`。

评委可以依次体验：输入广告业务问题创建 Agent/Skill → 选择行业、预算、商圈执行提案 → 将预算从 200 万元改为 100 万元 → 查看执行轨迹 → 反馈问题 → 在自我迭代实验室进行对照、人工发布和回滚。

## 可验证的技术边界

- 本公开仓库只含 **虚构样例数据**；赛事专用库存/覆盖 CSV、合同、账号和密码不在公开仓库中。
- 预算优化是可解释的约束启发式算法，不保证全局最优。
- Agent 当前采用确定性工具编排，**尚未集成 Pi SDK 自主规划**。
- 2027 年真实可售库存、正式商务报价和外部实时系统接口尚待授权核验。
- 只建议本地或隔离演示，**不应未经安全加固直接公网部署**。

## 自动测试

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions 的 `Public source smoke test` 工作流在 Python 3.11 下运行上述测试。当前源码主分支的测试结果请以 GitHub Actions 的实际运行记录为准。
