"""Auditable tool-orchestrated media planning agent (safe default: rule-based)."""
from __future__ import annotations
import json,re
from pathlib import Path
from src.planning import optimize_plan,INDUSTRIES
from src.coverage import join_coverage
from src.brief import analyze_brief
from src.operations import execution_review
from .store import TOOLS, now
from .campaign import build_hypothesis, scenario_changes

LANDMARKS=('正大广场','上海南站','新天地','陆家嘴','徐家汇','人民广场','南京西路')

def canonical_place(value):
    s=str(value or '').strip().replace('「','').replace('」','').replace('“','').replace('”','')
    if s.startswith('上海正大广场'): return '正大广场'
    return s

def choose_params(req):
    brief=(req.get('brief') or '').strip()[:12000]
    parsed=analyze_brief(brief or '客户需要为上海媒体制定投放策略')
    mentions=parsed['budget_mentions_wan']
    budget=req.get('budget_wan')
    if budget is None: budget=mentions[0] if mentions else 200
    if float(budget) not in (100,200,500) and not 100<=float(budget)<=500: raise ValueError('预算需在100至500万元')
    industry=req.get('industry') or next((x for x in INDUSTRIES if x in brief),'食品饮料')
    if industry not in INDUSTRIES: raise ValueError('行业必须为赛题五类之一')
    brand=(req.get('brand') or '').strip()
    if not brand:
        m=re.search(r'给\s*([\u4e00-\u9fa5A-Za-z0-9-]{2,30}?)\s*(?:做|投放|制定)',brief)
        brand=m.group(1) if m else '客户待确认'
    place=canonical_place(req.get('landmark') or next((name for name in LANDMARKS if name in brief),''))
    medium=req.get('medium') or ('bus' if '只投公交' in brief else 'metro' if '只投地铁' in brief else 'both')
    date=req.get('start_date') or next((d for d in parsed['mentioned_dates'] if d.startswith('2027')),'2027-05-01')
    return {"industry":industry,"brand":brand,"budget_wan":float(budget),"start_date":date,
            "weeks":int(req.get('weeks') or 4),"medium":medium,"focus_district":"all",
            "focus_landmark":place,"coverage_only":bool(req.get('coverage_only',bool(place))),"records":[]},parsed

def attach_known_prices(inventory,prices):
    """Fill missing price only on an unambiguous exact grade/type (or exact format/type)."""
    updates=0
    out=[]
    for row in inventory:
        r=dict(row)
        if r.get('unit_price_wan') is None:
            matches=[]
            for price in prices:
                if price.get('media_type')!=r.get('media_type'): continue
                grade=str(r.get('grade') or '').strip()
                fmt=str(r.get('format') or '').strip()
                if price.get('grade') and str(price['grade']).strip()==grade:
                    matches.append(price)
                elif (not price.get('grade')) and price.get('format') and str(price['format']).strip()==fmt:
                    matches.append(price)
            if len(matches)==1:
                p=matches[0]
                for k in ['unit_price_wan','price_min_wan','price_max_wan','production_fee_upper_wan','production_fee_min_wan','price_basis','price_period']:
                    if k in p:r[k]=p[k]
                r['price_reference_source']=p.get('source','')
                updates+=1
        out.append(r)
    return out,updates

def perform(req,agent,skills,inventory,coverage,source_desc,prices=None,policy=None):
    """Execute fixed, approved business tools. Agent/Skill text does NOT execute arbitrary code."""
    policy=policy or {}
    allowed=set()
    for sk in skills: allowed.update(json.loads(sk['tools_json']))
    if not allowed: raise ValueError('Agent 尚未绑定有执行工具的 Skill')
    if any(t not in TOOLS for t in allowed): raise ValueError('Skill 包含未授权工具')
    if 'optimize_budget' not in allowed: raise ValueError('Agent 需要拥有 optimize_budget 工具')
    steps=[]
    def step(tool,detail,status='ok'):
        steps.append({'time':now(),'tool':tool,'status':status,'detail':detail})
    params, parsed=choose_params(req)
    if policy.get('strict_coverage'):
        if 'match_coverage' not in allowed:raise ValueError('严格覆盖策略要求 Skill 授权 match_coverage')
        params['coverage_only']=True
        step('policy_guard','已启用严格覆盖证据策略：不推荐没有匹配证据的媒体')
    if 'brief_parse' in allowed: step('brief_parse', f"识别行业={params['industry']}，预算={params['budget_wan']}万，目标地标={params['focus_landmark'] or '未指定'}")
    if 'load_inventory' in allowed: step('load_inventory',f"读取{len(inventory)}条历史或导入的库存记录，数据来源：{source_desc.get('inventory','待确认')}")
    else: raise ValueError('Agent 需要拥有 load_inventory 工具')
    if prices:
        inventory,updated=attach_known_prices(inventory,prices)
        step('load_inventory',f'按媒体类型和等级/广告形式严格匹配刊例，补全{updated}条缺价库存；报价仍需人工审核')
    if coverage and 'match_coverage' in allowed:
        linked=join_coverage(inventory,coverage)
        inventory=linked['records']
        for item in inventory:
            if item.get('coverage_landmarks'):
                item['coverage_landmarks']=[canonical_place(x) for x in item['coverage_landmarks']]
        step('match_coverage',f"匹配覆盖证据{linked['matched_coverage_rows']}行，关联库存{linked['matched_inventory_count']}条；未匹配{linked['unmatched_coverage_rows']}行")
    else:
        step('match_coverage','未有授权覆盖数据或 Skill 未开放匹配工具，不能推断地标覆盖','needs_review')
        if params['coverage_only'] and not policy.get('strict_coverage'):
            params['coverage_only']=False
            step('match_coverage','因缺少匹配工具/覆盖数据关闭严格过滤，但仍标记数据待核验','needs_review')
        elif policy.get('strict_coverage'):
            step('policy_guard','覆盖证据缺失，保持严格过滤，不能退化成无证据推荐','needs_review')
    params['records']=inventory
    plan=optimize_plan(params)
    budget_variants={}
    # Frozen comparable scenarios using identical data and policy.
    for amount in sorted(set([100,200,500,float(params['budget_wan'])])):
        key=str(int(amount)) if float(amount).is_integer() else str(amount)
        budget_variants[key] = plan if amount==params['budget_wan'] else optimize_plan({**params,'budget_wan':amount})
    step('optimize_budget',f"筛选{plan['candidate_count']}个媒体候选，选中{plan['item_count']}项、{plan['unit_count']}个单元，参考计费{plan['spent_wan']}万")
    unsupported=sum(1 for r in plan['selected'] if not params['focus_landmark'] or params['focus_landmark'] not in (r.get('coverage_landmarks') or []))
    quality={'unsupported_selected':unsupported,'has_schedule_verified':False,'price_is_reference':bool(plan.get('is_reference_estimate')),'within_budget':plan['spent_wan'] <= params['budget_wan'],'has_candidates':plan['item_count']>0,'strict_coverage':bool(policy.get('strict_coverage'))}
    if 'review_risks' in allowed:
        execution=execution_review(plan)
        step('review_risks','排期、广告制作、上下刊与商业条款必须人工核验')
    else: execution=None
    suggestions=[]
    if not coverage:suggestions.append('缺少覆盖分析，推荐仅为库存/等级情景排序，不包含商圈精准证据')
    if not params['focus_landmark']:suggestions.append('应指定门店或地标并使用授权覆盖分析证据')
    if plan['is_reference_estimate']:suggestions.append('金额为脱敏区间上沿情景测算，不是正式报价')
    suggestions.append('当前库存快照或导入数据不能证明目标2027档期的可售性，正式下单前必须回红豆核验占用及锁位')
    if not any(r.get('media_type')=='metro' for r in inventory):suggestions.append('未取得可计价的地铁真实库存，不能编造地铁可售单元')
    if 'explain_plan' in allowed:
        rationale=(f"{params['brand']}的{params['industry']}投放方案：以{params['focus_landmark'] or '上海'}为目标，"
                   f"{params['budget_wan']:g}万元预算、{params['weeks']}周。"
                   f"从有数据依据的候选中选择{plan['item_count']}项媒体，暂按价格区间上沿和制作费计算{plan['spent_wan']}万元。"
                   "调整预算后重新计算组合，不只是改页面数字。")
        step('explain_plan','已生成规则驱动的可解释方案；未调用外部大模型')
    else: rationale='预算及媒体组合由确定性优化器生成；本Agent未授权策略解读工具。'
    return {'plan':plan,'budget_variants':budget_variants,'brief_analysis':parsed,'trace':steps,'rationale':rationale,'alerts':suggestions,
            'agent_policy_notes':[str(agent['instructions'])[:1200]]+[str(s['instructions'])[:1200] for s in skills],
            'execution':execution,'data_sources':source_desc,'mode':'tool_orchestrated_rule_agent',
            'ai_model_used':False,'quality':quality,'finished_at':now()}
