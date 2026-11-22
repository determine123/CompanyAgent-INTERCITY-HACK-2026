"""Honest blockers for production enterprise deployment; no config flags self-certify."""
from __future__ import annotations

def production_readiness(*, deployment_mode: str) -> dict:
    checks = [
      ("supplier_contract", "真实红豆响应 schema 与可售语义", False,
       "已有私有 GET 探针；缺企业所有者签字的字段映射、真实只读联调与档期核验"),
      ("approved_network", "企业审批与网络出口授权", False,
       "外部 PDP、指定租户、VPC/VPN 及 egress ACL 未接入本程序"),
      ("secret_management", "企业级短期凭据与轮换", False,
       "必须由公司 KMS/Vault 供应；严禁放入公开 Railway 或仓库"),
      ("sso_and_tenant", "SSO、多客户数据隔离与参数权限", False,
       "当前只支持单组织应用会话及 SQLite；尚未引入生产级身份/租户隔离"),
      ("durable_storage", "PostgreSQL 持久化、备份与恢复演练", False,
       "当前部署使用临时 SQLite；不可宣称完整审计链或可靠企业记忆"),
      ("tamper_evident_audit", "不可篡改审计与追踪", False,
       "现有 SQLite audit 表和 Run 指纹不足以保证防篡改性"),
      ("supplier_coverage", "授权商圈覆盖离线导出及映射", False,
       "可视化无获批 API；未经授权不能猜测媒体覆盖与客流"),
      ("evaluation", "独立验证业务试验", False,
       "已有单案例自报计算和成组统计引擎，但没有独立核验过的真实 A/B 证据"),
      ("release", "影子模式、负向测试、回滚与安全评审", False,
       "需要企业安全/法务/业务负责人正式验收"),
    ]
    return {
        "deployment_mode": deployment_mode,
        "status": "blocked_not_production_ready",
        "production_deployment_permitted": False,
        "real_inventory_verified": False,
        "validated_cost_reduction_claim": False,
        "implemented_components": [
            "synthetic budget planner with deterministic regression tests",
            "separate read-only private supplier probe requiring external approval verification",
            "offline schema-shape inspector that cannot mark availability as bookable",
            "pseudonymous paired-workload benchmarking with reproducible bootstrap intervals",
        ],
        "checks": [{"id": key, "title": title, "passed": ok, "blocker": reason}
                   for key, title, ok, reason in checks],
        "blocking_count": len(checks),
        "migration_note": "Production readiness requires independently checked controls, not environment flags.",
    }
