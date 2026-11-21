"""Portable offline HTML proposal. Entire payload is a frozen run snapshot.

No third-party scripts, remote calls, arbitrary HTML injection, or live booking claims.
"""
from __future__ import annotations
import html
import json


def render_proposal(run_id: int, req: dict, result: dict, quality: dict, review: dict) -> str:
    plan=result['plan']
    variants=result.get('budget_variants',{})
    if not variants:
        variants={str(int(plan.get('budget_wan',200))):plan}
    values={str(key):{
        'spent_wan':p['spent_wan'], 'remaining_wan':p['remaining_wan'],
        'budget_wan':p['budget_wan'], 'unit_count':p['unit_count'],
        'item_count':p['item_count'], 'selected':[{k:row.get(k) for k in
            ('id','media_name','media_type','quantity','line_total_wan','coverage_landmarks','source')}
            for row in p['selected']]
    } for key,p in variants.items()}
    payload={'variants':values,'brand':plan.get('brand',''),'landmark':plan.get('focus_landmark',''),
             'industry':plan.get('industry',''),'start_date':plan.get('start_date',''),
             'end_date':plan.get('end_date',''),'quality':quality,
             'sources':result.get('data_sources',{}),'review':review,
             'generated_from_run':run_id,
             'campaign_hypothesis':result.get('campaign_hypothesis') or {},
             'scenario_changes':result.get('scenario_changes') or []}
    # Only data, not markup. JS uses textContent for all untrusted fields.
    data_json=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    title=html.escape(str(plan.get('brand') or '客户'))
    actual_budget=float(plan.get('budget_wan',200))
    default_key=str(int(actual_budget)) if actual_budget.is_integer() else str(actual_budget)
    review_text='管理员已批准用于演示' if review.get('status')=='approved' else '未获演示审批 · 参考方案'
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CompanyAgent · {title} · 交互式投放提案</title>
<style>
:root{{--ink:#172d45;--blue:#2369cc;--mint:#0c8069;--line:#dfe8f3;--muted:#60758b}}
*{{box-sizing:border-box}}body{{margin:0;background:#f5f8fc;color:var(--ink);font:15px/1.55 system-ui,'Microsoft YaHei',sans-serif}}
header{{background:linear-gradient(120deg,#122a51,#2369cc);color:white;padding:45px max(22px,calc((100vw - 1100px)/2))}}
.eyebrow{{font-size:12px;letter-spacing:.12em;opacity:.8}}h1{{font-size:clamp(25px,4vw,40px);margin:8px 0 12px}}
.sub{{opacity:.89}}main{{max-width:1100px;margin:24px auto;padding:0 18px}}.notice{{background:#fff7e8;border:1px solid #e8c98f;padding:14px;border-radius:10px;margin-bottom:18px}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.card{{background:white;border:1px solid var(--line);border-radius:15px;padding:18px;box-shadow:0 3px 15px #1b3b5810}}
.card small{{color:var(--muted)}}.big{{font-size:28px;font-weight:800;margin-top:4px}}.section{{margin-top:18px}}h2{{font-size:20px;margin:2px 0 14px}}
.controls{{display:flex;gap:10px;flex-wrap:wrap}}button{{border:1px solid #c4d5e7;background:white;border-radius:9px;color:var(--ink);padding:9px 18px;font-weight:700;cursor:pointer}}
button.selected{{background:var(--blue);color:white;border-color:var(--blue)}}.tablewrap{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px;min-width:600px}}
th,td{{padding:11px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted);font-weight:600;background:#f7faff}}.foot{{color:var(--muted);font-size:12px;margin:25px auto}}
.tag{{display:inline-block;border:1px solid #bad6cd;background:#e8f6f0;padding:3px 8px;border-radius:6px;color:#13664e}}ul{{padding-left:22px}}li{{margin-bottom:5px;word-break:break-word}}
@media(max-width:650px){{.grid{{grid-template-columns:1fr}}header{{padding:30px 20px}}.big{{font-size:24px}}}}
@media print{{button{{display:none}}header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
</style></head><body><header><div class="eyebrow">COMPANYAGENT · INTERCITY HACK 2026 · RUN #{run_id}</div>
<h1>{title} · 户外媒体智能投放方案</h1><div class="sub">离线交互提案 · 2027 年投放候选 · {html.escape(review_text)}</div></header>
<main><div class="notice"><b>重要边界：</b>此方案为参考/比赛演示用途。覆盖命中不代表 2027 年可售或锁位；历史库存、脱敏价格与正式合同不等价。正式报价与媒体预订必须由红豆系统和人工复核。</div>
<div class="card"><h2>预算即时切换</h2><div class="controls" id="budgetButtons"></div><p style="color:var(--muted);font-size:13px">预算切换展示原始同一份授权数据上的独立计算结果，不是按比例修改报价。仅显示比赛三档预算。</p></div>
<div class="grid section"><div class="card"><small>当前预算</small><div class="big" id="budget">—</div></div><div class="card"><small>参考测算总额</small><div class="big" id="spent">—</div></div><div class="card"><small>媒体资源 / 单元</small><div class="big" id="units">—</div></div></div>
<div class="card section"><h2>客户 Campaign 假设书 · 七要素</h2><p id="hypothesisStatus"></p><div class="tablewrap"><table><thead><tr><th>必备要素</th><th>客户明确输入 / 待确认事项</th><th>状态</th></tr></thead><tbody id="hypothesisRows"></tbody></table></div><p class="foot">这是一页待客户签字确认的假设书；填写完整不等于 KPI 已实现或商业报价已确认。</p></div>
<div class="card section"><h2>预算 100 / 200 / 500 万元的增减方案</h2><div class="tablewrap"><table><thead><tr><th>预算</th><th>参考投入</th><th>媒体数 / 单元数</th><th>较上一档新增 / 减少单元</th></tr></thead><tbody id="scenarioRows"></tbody></table></div><p class="foot">所有档位使用同一份冻结数据分别运行预算优化；没有可比的真实人工工时基线，不能声称已实现成本节省。</p></div>
<div class="card section"><h2>投放范围与证据状态</h2><div id="meta"></div><div id="review"></div><ul id="warnings"></ul></div>
<div class="card section"><h2>可追溯媒体清单</h2><div class="tablewrap"><table><thead><tr><th>媒体 / 线路</th><th>类型</th><th>数量</th><th>参考金额（万元）</th><th>覆盖地标</th></tr></thead><tbody id="rows"></tbody></table></div></div>
<div class="card section"><h2>数据来源</h2><ul id="sources"></ul></div><p class="foot">生成自 CompanyAgent Run #{run_id} 的冻结结果快照。独立 HTML 不包含 API 密钥，不请求远程接口；因其包含所选媒体明细，请仅向获授权的评委/客户分享。</p>
</main><script type="application/json" id="payload">{data_json}</script><script>
'use strict';const data=JSON.parse(document.getElementById('payload').textContent);const $=id=>document.getElementById(id);
const text=(node,value)=>{{node.textContent=String(value??'');return node}};
const appendLi=(parent,v)=>{{const li=document.createElement('li');text(li,v);parent.appendChild(li)}};
text($('meta'),'行业：'+data.industry+' ｜ 目标地标：'+(data.landmark||'待确认')+' ｜ 档期：'+data.start_date+' 至 '+data.end_date);
text($('review'),'质量门禁：'+data.quality.status+' ｜ 覆盖证据：'+data.quality.evidence.matched_items+'/'+data.quality.evidence.total_items+'项 ｜ 演示审核：'+data.review.status);
data.quality.warnings.forEach(x=>appendLi($('warnings'),x.message));data.quality.blockers.forEach(x=>appendLi($('warnings'),'【阻断】'+x.message));
Object.entries(data.sources).forEach(([k,v])=>appendLi($('sources'),k+'：'+v));
const campaign=data.campaign_hypothesis||{{}};
text($('hypothesisStatus'),(campaign.completed||0)+' / '+(campaign.required||7)+' 已填写；'+(campaign.complete?'待客户业务核验':'未填写要素需要客户确认'));
for(const e of (campaign.elements||[])){{const row=document.createElement('tr');for(const val of [e.label,e.value,e.complete?'已填写 / 未核验':'待确认']){{text(row.appendChild(document.createElement('td')),val)}}$('hypothesisRows').appendChild(row)}}
for(const e of (data.scenario_changes||[])){{const row=document.createElement('tr');const delta=e.added_vs_prior_units===null?'基准预算':('+'+e.added_vs_prior_units+' / -'+e.removed_vs_prior_units);for(const val of [e.budget_wan+' 万元',e.spent_wan+' 万元',e.item_count+'项 / '+e.unit_count+'单元',delta]){{text(row.appendChild(document.createElement('td')),val)}}$('scenarioRows').appendChild(row)}}
function render(key){{const p=data.variants[key];if(!p)return;document.querySelectorAll('[data-budget]').forEach(b=>b.classList.toggle('selected',b.dataset.budget===key));text($('budget'),key+' 万元');text($('spent'),p.spent_wan+' 万元');text($('units'),p.item_count+'项 / '+p.unit_count+'单元');$('rows').replaceChildren();for(const r of p.selected){{const tr=document.createElement('tr');for(const v of [r.media_name||r.id,r.media_type==='bus'?'公交车身':'地铁出入口',r.quantity,r.line_total_wan,(r.coverage_landmarks||[]).join('、')||'待核验']){{text(tr.appendChild(document.createElement('td')),v)}}$('rows').appendChild(tr)}}}}
const keys=Object.keys(data.variants).sort((a,b)=>Number(a)-Number(b));for(const k of keys){{const b=document.createElement('button');b.dataset.budget=k;text(b,k+' 万元');b.addEventListener('click',()=>render(k));$('budgetButtons').appendChild(b)}}render(keys.includes({json.dumps(default_key)})?{json.dumps(default_key)}:keys[0]);
</script></body></html>'''
