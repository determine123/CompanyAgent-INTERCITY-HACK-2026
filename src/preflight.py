"""Submission and business-evidence preflight for the competition MVP."""
from __future__ import annotations
from typing import Any


def assess(plan: dict[str, Any]) -> dict[str, Any]:
    selected = plan.get("selected") or []
    if not isinstance(selected, list):
        raise ValueError("selected 字段须为列表")
    evidence_matches = sum(1 for r in selected if int(r.get("coverage_match_count") or 0)>0)
    has_metro = any(r.get("media_type")=="metro" for r in selected)
    reference = bool(plan.get("is_reference_estimate"))
    is_demo = bool(plan.get("is_demo"))
    requirements = [
        {"key":"prototype", "label":"可交互原型", "status":"passed" if selected else "blocked", "detail":"已计算候选媒体组合" if selected else "当前无可计价媒体资源"},
        {"key":"budget", "label":"100–500万预算约束", "status":"passed" if float(plan.get("spent_wan",0)) <= float(plan.get("budget_wan",0))+1e-6 else "blocked", "detail":"预算数字由确定性算法产生"},
        {"key":"period", "label":"2027档期占用核验", "status":"needs_review", "detail":"静态库存/日期窗口不是合同锁位，须回红豆系统按完整档期逐项核对"},
        {"key":"price", "label":"对客价格与折扣确认", "status":"needs_review", "detail":"脱敏区间价上沿仅为情景测算" if reference else "导入参考价格非合同确认价"},
        {"key":"coverage", "label":"覆盖分析匹配", "status":"evidence_partial" if evidence_matches else "missing", "detail": f"当前选中 {evidence_matches}/{len(selected)} 条媒体存在严格名称/ID匹配的来源记录；不代表客流测量" if evidence_matches else "未匹配赛事平台的媒体覆盖导出结果"},
        {"key":"metro", "label":"地铁点位数据", "status":"evidence_partial" if has_metro else "missing", "detail":"至少包含一条地铁媒体，仍需核验档期" if has_metro else "当前方案不含已导入且有价格的地铁点位"},
        {"key":"public_source", "label":"公开仓库及 README", "status":"external", "detail":"需要参赛队员上传公开源码并填写仓库 URL；程序无法替你确认外部发布"},
        {"key":"submission", "label":"B1X 官方作品提交", "status":"external", "detail":"需在比赛页面完成正式提交；本地导出不等于官网已提交"},
    ]
    return {
        "demo_operational": bool(selected and requirements[1]["status"] == "passed"),
        "verified_campaign_ready": False,
        "coverage_matched_selected": evidence_matches,
        "has_metro": has_metro,
        "is_demo": is_demo,
        "requirements": requirements,
        "summary": "候选提案可演示，尚非2027档期与报价已核实的商业方案" if selected else "缺少候选媒介，先导入库存及价格",
    }
