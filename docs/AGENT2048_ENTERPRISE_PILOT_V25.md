# CompanyAgent v2.5 · AGENT2048 启发的企业试点门禁和评估

> B1X 作品在 2026-11-22 10:23 已提交。本次只改 GitHub 代码和合成演示服务，不碰 B1X 表单。**下文不是已经上线生产或已成功调用真实红豆的证明。**

## 外部优秀项目如何借鉴（不复制非授权源码）

- AGENT2048 的 **01Agent**：围绕用户意图组织多阶段任务与协作。借鉴“Brief → 数据/工具 → 可审核方案 → 角色交接”，不是只生成文案。来源：https://agent2048.com/zh/projects/f758ojdwbqwc
- AGENT2048 的 **ValidFlow**：强调假设-测试-反馈的实验。借鉴**成组配对实测**，但不复用其宣传性百分比作为本项目实测结果。来源：https://agent2048.com/zh/projects/3ta44cf00ljq
- 2048 AI 社区的生产级 Agent 工程实践：最小权限、工具网关、观察性、Evals、人审门禁。借鉴原则，不宣称现阶段拥有 SSO/KMS/生产级系统。来源：https://2048ai.net/69a8fd4254b52172bc5f21f0.html

## 1. 红豆库存：安全联调已就绪到什么程度

现有 \`enterprise/hongdou_private_readonly.py\` 已支持：
- 企业模式隔离的**单次 HTTPS GET**、bus/metro 路由白名单、tenant-id 和单一 Bearer、超时与响应上限；
- 两个批准工单/租户/有效期等结构检查，以及每次请求**外部 PDP 独立判定**；
- 未确认 schema/可售业务含义之前只返回字段**元信息**，不能给出真实“可售”“已锁位”结论。

**本轮新加** \`enterprise/supplier_schema_review.py\`：在企业内网离线检查获准脱敏响应样例的字段形态；要求映射 \`resource_id/media_name/reported_units/stock_status\`，识别 0..50000 的形式数量，但**永远不输出真实库存数量或媒体行，也不标为可售**。任何未知/缺字段/重复映射直接拒绝。

要做到真实联调，还缺的数据所有者批准、独立 PDP/VPN/VPC/出口策略、脱敏完整响应 schema（包含留单/已占用/锁位/未来日期）、正式可售字典、指定日期查询可回放结果、403/429 等错误语义。用户/企业授权人员须在**公司自有系统**管理短期 Token，不要向聊天、GitHub、Railway 传账号、密码、验证码、Authorization 或 Cookie。

> 现阶段绝不能把 \`supplier_schema_review\` 的通过理解成供应商对可售字段的正式确认；也不能把它拼接进公开演示或原始库存导入通道。

## 2. 实测降本比例：从单案例自报升级为成组配对

\`enterprise/evidence_benchmark.py\` 提供 \`evaluate_cohort(trials)\`。每条案例包含：
- \`case_id\`：无 PII 的唯一编号；
- 同复杂度 **manual_minutes** 及 **generation_minutes/review_minutes/rework_minutes**；
- 同任务边界的 \`comparable_scope=true\`；
- 原人工及 Agent 路径审计原件各自的 SHA256（须在企业受控存储中对账，**仅哈希不证明真实存在**）；
- 人工错误数和 Agent 错误数、\`reviewer_ref\`（仅责任人标识，**不是外部真实性证明**）。

验证算法拒绝重复 ID、NaN/负数、超限、不对等工作范围、缺证据哈希等。**10 个配对样本及以上**计算总人工时间减去总辅助时间的观测变化百分比，以及固定随机种子的 bootstrap 95% 分位区间（描述性统计；不自动证明因果效应）。若不到 10 个，仅报告点估计，缺置信区间。

结果不含原始样本，不留存原件，不输出客户信息。无论算法输出何值，\`commercial_claim_permitted=false\`、\`independent_evidence_verified=false\`、\`monetary_roi_verified=false\`，必须由企业独立评审后才可发布经过验证的对外降本结论。

**管理员受控入口**：
- \`GET /enterprise/api/pilot/readiness\`：九项硬阻断，不接受自称 ready；
- \`POST /enterprise/api/pilot/paired-evaluation\`：仅 \`COMPANYAGENT_DEPLOYMENT_MODE=local\` + 管理员会话 + CSRF 使用，公开 Railway 403；不会写入真实案例数据到 DB（仅记录无敏感数量级审计）。
- CLI 脚本 \`python -m scripts.evaluate_enterprise_pilot /path/to/private/pseudonymous-trials.json
# Or: python scripts/evaluate_enterprise_pilot.py /path/to/private/pseudonymous-trials.json\` 在企业内网解析匿名化 JSON，再输出汇总。不要把真实案例发往公开云端。

## 3. 生产化门禁

九项必须独立落实：授权红豆语义；VPC/VPN/PDP；Vault/KMS；SSO 与租户隔离；PostgreSQL 持久化及恢复演练；防篡改审计；覆盖导出数据授权；独立人工对照证据；影子模式与回滚/安全评审。

**当前生产部署阻断**。仓库保持 \`deployment_policy.py\` 的 local/cloud_synthetic 唯一运行模式，绝不因设置 \`PRODUCTION=true\` 就允许服务接触企业 API。正式接入公司内网必须重新设计运行身份、授权、安全审计和数据隔离，并完成书面验收。

依照 OWASP 最小权限与人工审批原则，工具权限不应被 Agent 自身扩大：https://owasp.github.io/DevSecOpsGuideline/2-Process/2-2-Develop/2-2-5-AI-Agent-and-MCP-Security/ 。PostgreSQL 生产部署建议启用 RLS 默认拒绝，并验证多租户对抗测试：https://www.postgresql.org/docs/18/ddl-rowsecurity.html 。

## 4. 可执行验收

\`\`\`bash
python -m pytest -q tests/test_supplier_schema_v25.py tests/test_evidence_cohort_v25.py
python -m pytest -q
\`\`\`

验收结果分级：**unit/synthetic ✅** 与 **real_API ⛔ 未授权** 与 **production ⛔ 未验收** 与 **verified_ROI ⛔ 无真实数据**。新功能使后面三个目标有了规范化验证路径，但目前并未完成它们。
