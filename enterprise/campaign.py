"""One-page campaign hypothesis contract for enterprise proposal reviews.

Grounded in INTERCITY HACK / 新云传媒's 7-element hypothesis rubric.
Explicit business claims only: unknown goals/metrics are not inferred or invented.
This is a planning artifact, never proof of customer approval or media availability.
"""
from __future__ import annotations

from typing import Any

OBJECTIVES=("认知","到店","促销","拉新")
PENDING="待客户确认"
LABELS=(
    ("client","① 客户与品牌"),
    ("business_goal","② 生意目标"),
    ("campaign_goal","③ Campaign 主目标"),
    ("audience","④ 目标人群"),
    ("timing_budget","⑤ 档期与预算"),
    ("media","⑥ 媒体范围"),
    ("measurement","⑦ 成功衡量及核验方式"),
)

def _clean(value:Any,limit:int=300)->str:
    if value is None: return ""
    return str(value).strip()[:limit]

def build_hypothesis(req:dict[str,Any],plan:dict[str,Any])->dict[str,Any]:
    """Return an auditable seven-field hypothesis with explicit missing slots."""
    brand=_clean(req.get("brand") or plan.get("brand"),80)
    industry=_clean(req.get("industry") or plan.get("industry"),35)
    business=_clean(req.get("business_goal"))
    goal=_clean(req.get("campaign_goal"),20)
    audience=_clean(req.get("target_audience"))
    kpi=_clean(req.get("success_kpi"))
    method=_clean(req.get("measurement_method"))
    medium=_clean(req.get("medium") or "both")
    medium_label={"both":"公交车身 + 地铁出入口","bus":"公交车身","metro":"地铁出入口"}.get(medium,"")
    start=_clean(plan.get("start_date"))
    end=_clean(plan.get("end_date"))
    budget=plan.get("budget_wan")
    landmark=_clean(req.get("landmark") or plan.get("focus_landmark"),100)
    elements=[
        {"key":"client","label":LABELS[0][1],
         "value":f"{industry} / {brand}" if industry and brand and brand!="客户待确认" else PENDING,
         "complete":bool(industry and brand and brand!="客户待确认")},
        {"key":"business_goal","label":LABELS[1][1],"value":business or PENDING,
         "complete":bool(business)},
        {"key":"campaign_goal","label":LABELS[2][1],"value":goal if goal in OBJECTIVES else PENDING,
         "complete":goal in OBJECTIVES},
        {"key":"audience","label":LABELS[3][1],
         "value":(audience + (f" · 目标区域：{landmark}" if landmark else "")) if audience else PENDING,
         "complete":bool(audience)},
        {"key":"timing_budget","label":LABELS[4][1],
         "value":f"{start} 至 {end} · {budget:g} 万元" if start and end and isinstance(budget,(int,float)) else PENDING,
         "complete":bool(start and end and isinstance(budget,(int,float)))},
        {"key":"media","label":LABELS[5][1],"value":medium_label or PENDING,
         "complete":bool(medium_label)},
        {"key":"measurement","label":LABELS[6][1],
         "value":f"指标：{kpi}；验证：{method}" if kpi and method else PENDING,
         "complete":bool(kpi and method)},
    ]
    missing=[e["label"] for e in elements if not e["complete"]]
    return {
        "elements":elements,
        "completed":len(elements)-len(missing),
        "required":len(elements),
        "complete":not missing,
        "missing":missing,
        "approval_status":"待客户确认，未证明库存可售、正式报价或 KPI 已达成",
        "source":"客户明确输入 + 规则生成的投放时间/预算，不从模型猜测商业目标",
    }

def scenario_changes(variants:dict[str,dict[str,Any]])->list[dict[str,Any]]:
    """Compare verified SAME-RUN scenario choices, never fake financial savings."""
    levels=[str(n) for n in (100,200,500)]
    prev:dict[str,int]|None=None
    output=[]
    for level in levels:
        plan=variants.get(level)
        if not isinstance(plan,dict):continue
        current={}
        for item in plan.get("selected",[]):
            identity=str(item.get("media_type",""))+":"+str(item.get("id",""))
            current[identity]=current.get(identity,0)+int(item.get("quantity",0))
        added=sum(max(0,count-(prev or {}).get(k,0)) for k,count in current.items()) if prev is not None else 0
        removed=sum(max(0,count-current.get(k,0)) for k,count in prev.items()) if prev is not None else 0
        output.append({
            "budget_wan":int(level),
            "spent_wan":plan.get("spent_wan"),
            "remaining_wan":plan.get("remaining_wan"),
            "item_count":plan.get("item_count",0),
            "unit_count":plan.get("unit_count",0),
            "added_vs_prior_units":added if prev is not None else None,
            "removed_vs_prior_units":removed if prev is not None else None,
            "not_real_booking":True,
        })
        prev=current
    return output
