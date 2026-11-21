"""Rules-only demand intelligence over authorized proposal runs.

No raw customer briefs, brand names, login secrets or inventory records are sent to
a model. These analytics summarize recent available runs, NOT a verified ROI claim.
Agent/Skill recommendations are safe, reviewable templates, never generated code.
"""
from __future__ import annotations
import json
from collections import Counter

MAX_RUNS=250
TEMPLATES={
    "campaign_brief":{
        "title":"Campaign 需求补全 Agent",
        "skill":"七要素 Brief 审查 Skill",
        "description":"从已授权客户需求检查生意目标、人群、KPI 与核验缺口，拒绝捏造事实。",
        "tools":["brief_parse","load_inventory","optimize_budget","review_risks","explain_plan"],
        "policy":"先补齐七要素并记录待客户确认项；只读取授权库存，不能捏造客流、销售增长、正式报价与可售。"
    },
    "coverage_evidence":{
        "title":"商圈证据选媒 Agent",
        "skill":"商圈覆盖证据核验 Skill",
        "description":"优先核查媒介商圈证据，不能把地理匹配当成真实档期可售。",
        "tools":["brief_parse","load_inventory","match_coverage","optimize_budget","review_risks","explain_plan"],
        "policy":"需要授权覆盖数据并做精确匹配；无证据时标记未知，不猜测覆盖；不自动锁位。"
    },
    "budget_review":{
        "title":"预算重算与风控 Agent",
        "skill":"预算约束与风险复核 Skill",
        "description":"基于企业授权库存与价格，按预算约束优化并输出执行核验待办。",
        "tools":["brief_parse","load_inventory","optimize_budget","review_risks","explain_plan"],
        "policy":"同份数据快照下执行预算约束和成本校验；变更不自动通知客户、锁位或提交正式报价。"
    }
}

def summarize_runs(rows):
    goals=Counter()
    media=Counter()
    risks=Counter()
    budgets=Counter()
    latest=[]
    for row in rows[:MAX_RUNS]:
        try:
            req=json.loads(row["request_json"])
            res=json.loads(row["result_json"])
        except (ValueError,TypeError,KeyError):
            continue
        goal=req.get("campaign_goal") or "待确认"
        if goal not in ("认知","到店","促销","拉新"):goal="待确认"
        medium=req.get("medium") or "both"
        if medium not in ("bus","metro","both"):medium="other"
        goals[goal]+=1
        media[medium]+=1
        try:
            b=float(req.get("budget_wan",0))
            budget="100万" if b<=100 else "200万" if b<=200 else "500万"
        except (TypeError,ValueError):
            budget="待确认"
        budgets[budget]+=1
        q=res.get("quality_report") or {}
        for warning in (q.get("blockers") or [])+(q.get("warnings") or []):
            code=warning.get("code","")
            if code in ("COVERAGE_GAP","CAMPAIGN_HYPOTHESIS_INCOMPLETE","SCHEDULE_UNVERIFIED",
                        "NO_MEDIA","OVER_BUDGET","MISSING_LANDMARK","TOTAL_MISMATCH"):
                risks[code]+=1
        latest.append({"run_id":int(row["id"]),"created_at":str(row["created_at"]),
                       "campaign_goal":goal,"medium":medium,"budget_band":budget,
                       "quality_status":q.get("status") or "unknown"})
    if risks["CAMPAIGN_HYPOTHESIS_INCOMPLETE"]:
        kind="campaign_brief"
    elif risks["COVERAGE_GAP"] or risks["MISSING_LANDMARK"]:
        kind="coverage_evidence"
    else:
        kind="budget_review"
    return {
        "sample_size":len(latest),"sample_limit":MAX_RUNS,
        "goal_counts":dict(goals),"medium_counts":dict(media),
        "budget_counts":dict(budgets),"risk_counts":dict(risks),
        "recent":latest[:20],
        "suggested_template":kind,
        "suggested_skill":TEMPLATES[kind]["skill"],
        "insight_basis":"最近可访问的 Run 结构化字段与质量错误码；不含品牌或自由文本",
        "limitations":"样本可能有偏、公开演示为合成数据；只是候选策略，不等于模型学习、商业效果验证或生产授权",
    }

def decision_brief(result):
    """Pre-review a frozen run using rules and evidence without scoring a made-up ROI."""
    quality=result.get("quality_report") or {}
    plan=result.get("plan") or {}
    checks={x.get("code"):x.get("message","") for x in
            (quality.get("blockers") or [])+(quality.get("warnings") or [])}
    possibilities=[
        ("NO_MEDIA","预算/限制下无可交付媒体","放宽已确认的约束或申请授权新库存，再进行预算重算"),
        ("CAMPAIGN_HYPOTHESIS_INCOMPLETE","客户 Campaign 要素不完整","明确生意目标、目标人群、KPI 和验证方式，发送客户确认"),
        ("COVERAGE_GAP","目标商圈缺少匹配证据","获取授权覆盖导出，复查媒体与地标对应关系"),
        ("MISSING_LANDMARK","未明确目标商圈","先确认投放区域和覆盖核验口径"),
        ("SCHEDULE_UNVERIFIED","目标档期未得到连续可售证明","使用企业授权只读接口人工核验目标日期的库存状态"),
        ("REFERENCE_PRICE","报价依赖参考价格","交给财务和销售核对合同价、税费、制作与施工成本"),
        ("SYNTHETIC_DATA","方案基于虚构演示数据","在获批私有环境换用有来源的真实授权数据复算"),
        ("NOT_BOOKED","媒体未完成正式锁位","由运营人员确认正式档期、合同与下单流程"),
    ]
    risks=[]
    for code,title,fix in possibilities:
        if code in checks and len(risks)<3:
            risks.append({"code":code,"title":title,"evidence":checks[code],"fix":fix})
    while len(risks)<3:
        risks.append({"code":"HUMAN_GATE","title":"商业交付需要人工复核",
                      "evidence":"没有真实业务人员签署投放合同、质量验收和客户 KPI 基线",
                      "fix":"确认人负责审核，建立反馈和结案证据"})
    return {
        "label":"基于已授权数据库与冻结 Run 的规则预审；不等于商业收益最优",
        "status":quality.get("status","needs_review"),
        "chosen_count":len(plan.get("selected") or []),
        "budget_wan":plan.get("budget_wan"),
        "spent_wan":plan.get("spent_wan"),
        "source_labels":result.get("data_sources",{}),
        "risks":risks[:3],
        "questions":[
            "为什么选这些公交/地铁媒体而不是其他点位？是否有逐项证据？",
            "客户生意目标、唯一主 KPI 和验证数据来源是谁确认的？",
            "100／200／500 万预算改变后，增减的是哪些媒体，为什么？",
            "2027 目标档期是否有授权数据证明可售？谁能正式锁位？",
            "价格、制作、夜间施工、雨天和赔补条款由谁核实？",
            "如果客户临时换稿或车辆进保，哪些部门先行动？",
        ],
        "next_actions":[
            {"priority":"P0","title":"补齐或确认客户七要素","why":"避免从不完整 Brief 推断不存在的客户目标"},
            {"priority":"P1","title":"核验媒体数据来源及目标档期","why":"覆盖、历史库存与报价均不能直接代表可售"},
            {"priority":"P2","title":"人工审核成本与执行交接","why":"审批前需核对制作、施工、运营与监测责任"},
        ],
        "warnings":"不可据此宣称客户已确认、广告已锁位、真实 ROI 已获得；模型不是最终审批者",
    }
