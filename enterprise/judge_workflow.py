"""Evidence-first change simulation for a single, synthetic media campaign.

This is a read-only, anonymous judge proof of a business workflow, not
a production approval system. No enterprise database, model, network, or
corporate credentials are touched. Every figure comes from the SAME real
deterministic optimizer that powers the authenticated workbench.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .judge_preview import preview
from .change_workflow import analyze_change

_SOURCE = Path(__file__).resolve().parent.parent / "data" / "demo_inventory.csv"
_BUDGETS = (100, 200, 500)
_MEDIA = ("both", "bus", "metro")
_CHANGE_TYPES = ("creative_revision", "vehicle_reassignment", "weather_monitoring")


def _snapshot(result: dict) -> dict:
    """Small client-safe summary; excludes customer/enterprise data."""
    return {
        "budget_wan": result["budget_wan"],
        "medium": result["medium"],
        "spent_wan": result["spent_wan"],
        "remaining_wan": result["remaining_wan"],
        "item_count": result["item_count"],
        "unit_count": result["unit_count"],
    }


def _allocations(result: dict) -> dict[str, dict]:
    allocation = {}
    # Judge preview returns ALL selected fictional entries (never truncated).
    for row in result["selected"]:
        key = row["media_type"] + ":" + row["id"]
        if key in allocation:
            raise ValueError("同一媒体 ID 重复，无法安全计算差异")
        allocation[key] = row
    return allocation


def workflow_preview(budget_wan: int, medium: str, prior_budget_wan: int,
                     prior_medium: str, change_type: str) -> dict:
    """Calculate allocation deltas, review gates and a human-only dependency DAG.

    No free text, arbitrary dates, external URLs, writes, file uploads or data
    from authenticated users are part of this API.
    """
    if type(budget_wan) is not int or budget_wan not in _BUDGETS:
        raise ValueError("当前预算仅支持100、200、500万元")
    if type(prior_budget_wan) is not int or prior_budget_wan not in _BUDGETS:
        raise ValueError("原预算仅支持100、200、500万元")
    if medium not in _MEDIA or prior_medium not in _MEDIA:
        raise ValueError("媒体选项只能为公交、地铁或组合")
    if change_type not in _CHANGE_TYPES:
        raise ValueError("仅开放预定义的合成变更类型")

    previous = preview(prior_budget_wan, prior_medium)
    current = preview(budget_wan, medium)
    before = _allocations(previous)
    after = _allocations(current)
    changes = []
    added_units = removed_units = 0
    for key in sorted(set(before) | set(after)):
        left = before.get(key, {})
        right = after.get(key, {})
        old_qty = int(left.get("quantity") or 0)
        new_qty = int(right.get("quantity") or 0)
        delta_qty = new_qty - old_qty
        if not delta_qty:
            continue
        added_units += max(0, delta_qty)
        removed_units += max(0, -delta_qty)
        changes.append({
            "id": key,
            "media_name": str(right.get("media_name") or left.get("media_name") or ""),
            "district": str(right.get("district") or left.get("district") or ""),
            "before_quantity": old_qty,
            "after_quantity": new_qty,
            "delta_units": delta_qty,
            "before_spent_wan": float(left.get("line_total_wan") or 0),
            "after_spent_wan": float(right.get("line_total_wan") or 0),
        })
    changes.sort(key=lambda item: (-abs(item["delta_units"]), item["id"]))
    delta_spent = round(current["spent_wan"] - previous["spent_wan"], 2)
    # Exact decomposition remains checkable even when the UI shows only top 12 rows.
    assert sum(x["delta_units"] for x in changes) == current["unit_count"] - previous["unit_count"]
    assert round(sum(x["after_spent_wan"] - x["before_spent_wan"] for x in changes), 2) == delta_spent

    hypothetical_result = {
        "plan": {
            "brand": "模拟饮料品牌A",
            "budget_wan": current["budget_wan"],
            "start_date": current["start_date"],
            "focus_landmark": "",
            "selected": current["selected"],
        }
    }
    handoff = analyze_change(
        hypothetical_result, kind=change_type,
        effective_date="2027-05-01", note="公开虚构案例，生成待审批的变更影响清单"
    )
    variants = [preview(amount, medium) for amount in _BUDGETS]
    fingerprint = hashlib.sha256(_SOURCE.read_bytes()).hexdigest()[:16]
    valid_budget = bool(current["item_count"]) and 0 <= current["spent_wan"] <= budget_wan
    variants_valid = all(0 <= row["spent_wan"] <= row["budget_wan"] for row in variants)

    checks = [
        ("industry_scope", "食品饮料单行业", True, "本次比赛只演示食品饮料"),
        ("campaign_brief", "七要素和客户签认", False, "客户真实生意目标、人群、核验 KPI 尚未取得确认"),
        ("source_fingerprint", "输入数据可追溯", bool(fingerprint and current["sample_size"] == 80),
         "只能追溯仓库虚构 CSV；不能代替企业库存核实"),
        ("budget_guard", "金额与数量约束", valid_budget, "根据当前合成库存和预算进行约束选媒"),
        ("scenario_recalculation", "100/200/500 万独立重算", variants_valid,
         "三个方案来自同一个确定性优化器和同一数据版本"),
        ("coverage_evidence", "目标商圈覆盖证据", False, "可视化无开放 API；没有获准的精准覆盖导出"),
        ("future_inventory", "目标日期真实可售", False, "红豆公交/地铁需私有授权核验，未锁位"),
        ("formal_quote", "正式报价和制作费", False, "演示价格未获得销售、财务与供应商确认"),
        ("human_approval", "客户/运营签认", False, "所有变更必须由责任岗位人工审批"),
    ]
    gates = [{"id": key, "label": title,
              "status": "evidence_present" if status else "needs_review",
              "explanation": note}
             for key, title, status, note in checks]

    return {
        "simulation_only": True,
        "production_ready": False,
        "real_api_accessed": False,
        "changed_enterprise_records": False,
        "not_official_rubric": True,
        "previous": _snapshot(previous),
        "current": _snapshot(current),
        "scenario_summary": [_snapshot(item) for item in variants],
        "impact": {
            "spent_delta_wan": delta_spent,
            "net_units": current["unit_count"] - previous["unit_count"],
            "added_units": added_units,
            "removed_units": removed_units,
            "changed_media_count": len(changes),
            "changed_rows": changes[:12],
            "details_truncated": len(changes) > 12,
        },
        "data_lineage": {
            "file": "data/demo_inventory.csv",
            "sha256_prefix": fingerprint,
            "records": current["sample_size"],
            "status": "synthetic_and_unverified",
        },
        "checks": gates,
        "checks_with_evidence": sum(c["status"] == "evidence_present" for c in gates),
        "handoff": {
            "change_type": handoff["change_type"],
            "change_label": handoff["change_label"],
            "dependency_steps": handoff["dependency_steps"],
            "affected_forms": handoff["affected_forms"],
            "evidence_gaps": handoff["evidence_gaps"],
            "customer_notice_draft": handoff["customer_notice_draft"],
            "status": "pending_human_review",
            "customer_notified": False,
            "inventory_reserved": False,
            "real_system_mutated": False,
        },
        "skill_improvement": {
            "name": "商圈覆盖证据核验 Skill",
            "reason": "针对重复出现的商圈覆盖证据缺口，建议补强授权快照匹配能力",
            "status": "suggested_not_installed",
            "human_approval_required": True,
            "tools_allowlisted": ["brief_parse", "load_inventory", "match_coverage", "optimize_budget", "review_risks"],
            "auto_executed": False,
        },
        "caveat": "样例为真实后端代码处理的虚构数据，不证明2027年真实可售、商圈覆盖、正式报价、锁位或实际ROI",
    }
