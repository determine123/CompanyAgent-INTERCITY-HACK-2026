/* CompanyAgent hackathon MVP — deterministic budgets, honest data provenance. */
'use strict';
const $ = (id) => document.getElementById(id);
const state = {records: [], plan: null, demo: true, sourceName: 'DEMO-SYNTHETIC', warnings: [], lastAi: '', briefAnalysis: null, executionReview: null, requestId:0, coverageRows:[], coverageSummary:null, preflight:null};
const labels = {bus:'公交车身', metro:'地铁出入口'};
const areaPos = {
  '黄浦区':[49,50], '静安区':[41,34], '徐汇区':[33,64], '浦东新区':[72,47],
  '长宁区':[23,48], '普陀区':[29,24], '杨浦区':[71,22], '闵行区':[37,82],
  '宝山区':[51,12], '虹口区':[62,35], '松江区':[12,79]
};
const fitCopy = {
  '食品饮料':'建议以商圈消费场景与通勤场景协同触达，并根据门店位置对重点区域进行人工复核。',
  '银行保险':'建议关注商务中心区和通勤节点，突出品牌可信度与金融服务触达场景。',
  '保健品':'建议围绕日常生活圈和健康消费场景规划投放，并严格审核广告合规措辞。',
  '私立医院':'建议结合医院实际地址、目标服务半径和通勤线路筛选点位，并严格审核医疗广告合规。',
  '乐园（主题公园）':'建议关注周末出行与交通枢纽相关区域，结合乐园所在地与投放档期优化组合。'
};
let autoTimer, toastTimer;
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function money(v){return Number(v||0).toLocaleString('zh-CN',{minimumFractionDigits:0,maximumFractionDigits:2})+' 万';}
function num(v){return Number(v||0).toLocaleString('zh-CN');}
function toast(message){$('toast').textContent=message;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),3600);}
async function fetchJson(url, opts={}){
  const res=await fetch(url,opts);let body;
  try{body=await res.json()}catch{throw new Error('服务响应格式异常')}
  if(!res.ok) throw new Error(body.detail||'请求失败');
  return body;
}
function basePayload(){return {industry:$('industry').value, brand:$('brand').value.trim()||'未指定品牌',budget_wan:Number($('budgetRange').value),start_date:$('startDate').value,weeks:Number($('weeks').value),medium:document.querySelector('[data-medium].selected')?.dataset.medium||'both',focus_district:$('focusDistrict').value,focus_landmark:$('focusLandmark').value.trim(),coverage_only:$('coverageOnly').checked,records:state.records};}
function nav(tab){
  for(const el of document.querySelectorAll('.tab-panel'))el.classList.toggle('visible',el.id==='tab-'+tab);
  for(const el of document.querySelectorAll('.side-link'))el.classList.toggle('active',el.dataset.tab===tab);
  $('pageLabel').textContent=({studio:'智能提案工作台',data:'媒体库存与价格',proposal:'提案预览与导出',workflow:'Agent 工作流程'})[tab];
  if(tab==='proposal')renderProposal();
  if(tab==='data')renderData();
  window.scrollTo({top:0,behavior:'smooth'});
}
async function loadDemo(){
  try{
    const obj=await fetchJson('/api/demo');
    state.records=obj.records;state.coverageRows=[];state.coverageSummary=null;state.demo=true;state.sourceName='DEMO-SYNTHETIC';state.warnings=['已加载虚构的演示资源，所有线路和价格均不是真实红豆系统数据。'];
    renderData(); await recalc();toast('已加载模拟数据，可以直接切换预算和生成提案');
  }catch(e){toast('演示数据加载失败：'+e.message);}
}
async function loadContest(){
  try{
    const obj=await fetchJson('/api/contest');
    state.records=obj.records;state.coverageRows=[];state.coverageSummary=null;state.demo=false;
    state.sourceName='赛事附件01公交台账（2026-11-13快照）+ 附件07（脱敏价格）';
    state.warnings=obj.warnings||[];
    try{
      const cov=await fetchJson('/api/contest/coverage');
      if(cov.usable){
        state.coverageRows=cov.records;
        await refreshCoverageJoin();
        state.warnings.push('已加载三个地标的'+cov.usable+'条平台原始CSV汇总分析记录；不代表2027可售。');
        if(cov.warnings)state.warnings.push(...cov.warnings);
      }
    }catch(e){state.warnings.push('覆盖分析可选加载未成功：'+e.message);}
    renderData();await recalc();
    toast(state.coverageRows.length ? '已载入431条公交历史记录和三地标覆盖CSV；仍需核验2027档期' : '已加载431条赛事公交参考记录；注意这不是2027年的可售库存');
  }catch(e){toast('赛事数据未安装：'+e.message);await loadDemo();}
}
function setBudget(v,run=true){
  const n=Math.max(100,Math.min(500,Math.round(Number(v)/10)*10));
  $('budgetRange').value=n;$('budgetLabel').textContent=n;
  for(const b of document.querySelectorAll('[data-budget]'))b.classList.toggle('selected',Number(b.dataset.budget)===n);
  if(run)scheduleRecalc();
}
function scheduleRecalc(){clearTimeout(autoTimer);autoTimer=setTimeout(()=>recalc(),140);}
async function recalc(){
  const req=++state.requestId; const b=basePayload();
  $('generateBtn').disabled=true;$('generateBtn').innerHTML='正在优化提案…';
  try{
    const p=await fetchJson('/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
    if(req!==state.requestId)return;
    state.plan=p;state.lastAi='';
    try{state.executionReview=await fetchJson('/api/execution/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:p})});}
    catch{state.executionReview=null;}
    try{state.preflight=await fetchJson('/api/preflight',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:p})});}
    catch{state.preflight=null;}
    if(req!==state.requestId)return;renderAll();
  }catch(e){if(req===state.requestId)toast(e.message);}
  finally{if(req===state.requestId){$('generateBtn').disabled=false;$('generateBtn').innerHTML='<span>✦</span> 生成 / 重新优化提案 <span>→</span>';}}
}
function renderAll(){const p=state.plan;if(!p)return;
  $('budgetLabel').textContent=p.budget_wan;$('kpiBudget').innerHTML=`¥ ${num(p.budget_wan)} <small>万</small>`;
  $('kpiPriceTitle').textContent=p.is_reference_estimate?'含制作费的上沿测算':'参考报价合计';$('kpiSpent').textContent=money(p.spent_wan);$('kpiRatio').textContent='预算利用率 '+p.utilization_pct+'%';
  $('kpiUnits').textContent=num(p.unit_count);$('kpiMedia').textContent=p.item_count+' 类资源项组合';
  $('kpiDistricts').textContent=num(p.district_count);$('budgetUsageSmall').textContent='已分配 '+p.utilization_pct+'%';
  $('listCount').textContent=p.item_count+' 条组合项';$('candidatesValue').textContent=p.candidate_count+' 条';
  $('periodValue').textContent=p.start_date+' 至 '+p.end_date;
  $('busTotal').textContent=money(p.type_totals_wan.bus||0);$('metroTotal').textContent=money(p.type_totals_wan.metro||0);
  $('remainingTotal').textContent=money(p.remaining_wan);$('donutPct').textContent=p.utilization_pct+'%';
  let busPct=(p.type_totals_wan.bus||0)/p.budget_wan*100,metroPct=(p.type_totals_wan.metro||0)/p.budget_wan*100;
  $('donut').style.background=`conic-gradient(#2468e8 0% ${busPct}%, #18b8ba ${busPct}% ${busPct+metroPct}%, #e8eef6 ${busPct+metroPct}% 100%)`;
  $('datasetBanner').innerHTML=state.demo?'<span class="notice-icon">ⓘ</span><div><strong>当前为模拟演示数据</strong><span>线路、库存和价格均为虚构。可切换预算测试功能，但不可作为对客报价或真实可售证明。</span></div><button id="goData" class="link-btn">导入数据 →</button>':'<span class="notice-icon">ⓘ</span><div><strong>已导入授权数据：'+esc(state.sourceName)+'</strong><span>赛事参考资料：库存是2026-11-13单日历史快照；刊例为脱敏价格区间，上沿情景测算含公交制作费。无2027实时占用及可售锁位；覆盖来源按已导入文件单独核验；地铁库存需另外导入。</span></div><button id="goData" class="link-btn">查看数据 →</button>';
  $('goData').addEventListener('click',()=>nav('data'));
  let rows=p.selected.slice(0,12).map(r=>`<tr><td>${esc(r.media_name)}<span class="td-sub">${esc(r.id)} · ${esc(r.format||'')}</span>${r.coverage_match_count?'<span class="coverage-pill">已关联覆盖来源 · '+esc((r.coverage_landmarks||[]).join('、'))+'</span>':''}</td><td>${esc(r.district)}</td><td><span class="type-pill ${r.media_type==='metro'?'metro':''}">${esc(labels[r.media_type])}</span></td><td>${r.quantity}</td><td>${money(r.unit_price_wan)}</td><td><strong>${money(r.line_total_wan)}</strong></td><td><span class="state-pill">待复核</span></td></tr>`).join('');
  $('mediaRows').innerHTML=rows||'<tr><td class="empty" colspan="7">没有满足筛选条件的有价候选资源，请更改日期或导入含价格的数据。</td></tr>';
  $('tableFooter').textContent=`显示前 ${Math.min(p.selected.length,12)} / ${p.selected.length} 条组合项 · ${p.schedule_state} · ${p.is_reference_estimate?"价格上沿情景测算，非正式报价":"输入参考刊例价"}`;
  renderMap(p);renderAiTemplate();renderProposal();renderExecution();renderPreflight();
}
function renderMap(p){
  const groups={};for(const r of p.selected){const k=r.district+'|'+r.media_type;(groups[k]??={district:r.district,type:r.media_type,quantity:0}).quantity+=r.quantity;}
  let out='';for(const v of Object.values(groups)){
    const pos=areaPos[v.district];if(!pos)continue;
    const offset=v.type==='metro'?7:-7;
    out+=`<div class="map-point ${v.type==='metro'?'metro-point':''}" style="left:calc(${pos[0]}% + ${offset}px);top:calc(${pos[1]}% + ${offset*0.7}px)" title="${esc(v.district+' '+labels[v.type]+'：'+v.quantity+'个资源单元')}"><i></i>${esc(v.district)} ${v.quantity}</div>`;
  }
  if(!out && p.is_reference_estimate){
    out='<div class="map-data-warning"><b>暂无可核验的地理位置</b><span>台账只有公交线路与等级，没有轨迹、坐标或门店覆盖。请在赛事可视化平台导出覆盖结果后再展示地图。</span></div>';
  }
  $('mapDots').innerHTML=out;
}
function renderAiTemplate(){
  const p=state.plan;if(!p)return;
  $('aiBadge').textContent='本地规则版';
  const main=p.type_counts.bus&&p.type_counts.metro?'公交车身与地铁出入口混合投放':p.type_counts.bus?'公交车身投放':p.type_counts.metro?'地铁出入口投放':'暂无可报价的媒体组合';
  $('aiOutput').textContent=`【品牌策略】${p.brand}（${p.industry}）。${fitCopy[p.industry]||'建议根据客户场景匹配投放媒介。'}\n【媒体组合】当前按${money(p.budget_wan)}预算、${p.weeks}周周期，形成${p.item_count}条候选资源组合（${p.unit_count}个单元），以${main}为主。参考合计${money(p.spent_wan)}，未使用${money(p.remaining_wan)}。\n【待确认】实际库存与2027档期占用、合同折扣、最终价格及覆盖分析须回系统核验。${state.demo?'当前仅为虚构数据演示。':''}`;
}
function renderData(){const rs=state.records||[];
  $('dataSourceName').textContent=state.demo?'DEMO-SYNTHETIC：80条虚构演示资源':state.sourceName+'（历史快照+脱敏区间价，非正式报价）';
  $('dataLoaded').textContent=num(rs.length);$('dataBus').textContent=num(rs.filter(r=>r.media_type==='bus').length);$('dataMetro').textContent=num(rs.filter(r=>r.media_type==='metro').length);$('dataUnpriced').textContent=num(rs.filter(r=>r.unit_price_wan===null||r.unit_price_wan===undefined||r.unit_price_wan==='').length);
  $('dataWarnings').textContent=(state.warnings||[]).join(' · ')||'尚无导入警告。';
  renderCoverageStats();
  $('dataRows').innerHTML=rs.slice(0,16).map(r=>`<tr><td>${esc(r.id)}</td><td>${esc(r.media_name)}</td><td>${esc(r.district)}</td><td>${num(r.available_count)}</td><td>${r.unit_price_wan==null?'缺失':money(r.unit_price_wan)}</td><td>${esc(r.source)}</td></tr>`).join('')||'<tr><td colspan="6">暂无资源</td></tr>';
}
async function importStockFiles(files){
  if(!files||!files.length)return;
  const all=[], warnings=[], found=new Set();
  for(const file of files){
    const fd=new FormData();fd.append('file',file);
    let json;
    try{json=await fetchJson('/api/import',{method:'POST',body:fd});}
    catch(e){toast('导入 '+file.name+' 失败：'+e.message);return;}
    warnings.push(...(json.warnings||[]).map(w=>file.name+'：'+w));
    for(const r of json.records){
      const key=r.media_type+':'+r.id;
      if(found.has(key)){warnings.push('重复媒体 ID '+key+' 已跳过（避免重复计算）');continue;}
      found.add(key);all.push(r);
    }
  }
  if(!all.length)return toast('没有识别出有效媒体记录，请检查媒体类型与名称');
  state.records=all;await refreshCoverageJoin();state.demo=false;state.sourceName=files.map(f=>f.name).join(' + ');
  state.warnings=warnings.slice(0,30);
  renderData();await recalc();toast('已合并导入 '+all.length+' 条媒体记录');
}
async function importFile(file,kind){
  if(!file)return;
  const fd=new FormData();fd.append('file',file);
  try{
    const json=await fetchJson(kind==='inventory'?'/api/import':'/api/import-prices',{method:'POST',body:fd});
    if(kind==='inventory'){
      if(!json.records.length)throw new Error('没有识别出可用的公交/地铁记录，检查媒体类型与名称列。');
      state.records=json.records;await refreshCoverageJoin();state.demo=false;state.sourceName=file.name;state.warnings=json.warnings||[];
      toast('已导入 '+json.records.length+' 条媒体记录');
    } else {
      let count=0,missing=0;
      for(const r of state.records){
        if(r.unit_price_wan!=null)continue;
        const matches=json.prices.filter(p=>p.media_type===r.media_type&&((p.grade&&p.grade===r.grade)||(p.format&&p.format===r.format)));
        if(matches.length===1){
          const pm=matches[0];r.unit_price_wan=pm.unit_price_wan;r.price_min_wan=pm.price_min_wan??null;
          r.price_max_wan=pm.price_max_wan??null;r.price_period=pm.price_period||'';
          r.price_basis=pm.price_basis||'';r.production_fee_min_wan=pm.production_fee_min_wan||0;
          r.production_fee_upper_wan=pm.production_fee_upper_wan||0;
          count++;
        }else missing++;
      }
      state.warnings.push(`价格导入 ${file.name}：等级或形式匹配参考价格 ${count} 条；仍缺价 ${missing} 条。区间价使用上沿做情景估算；具体媒体形式价差待确认。`);
      toast('已补齐 '+count+' 条明确匹配价格');
    }
    renderData();await recalc();
  }catch(e){toast('导入失败：'+e.message);}
}
async function refreshCoverageJoin(){
  if(!state.coverageRows.length){state.coverageSummary=null;return;}
  const result=await fetchJson('/api/coverage/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({records:state.records,coverage:state.coverageRows})});
  state.records=result.records;state.coverageSummary=result;
}
async function importCoverageFiles(files){
  if(!files||!files.length)return;
  const all=[...state.coverageRows], warnings=[];
  for(const file of files){
    try{
      const fd=new FormData();fd.append('file',file);
      const res=await fetchJson('/api/coverage/import',{method:'POST',body:fd});
      if(!res.usable)throw new Error('没有识别到媒体名称或ID');
      all.push(...res.records);
      warnings.push(file.name+'：识别'+res.usable+'行（'+(res.source_kind||'模板')+'）');
    }catch(e){warnings.push(file.name+' 导入失败：'+e.message)}
  }
  // Prevent user accidentally counting the same source file twice. Preserve same-name
  // records with different station evidence for audit; inventory is matched separately.
  const seen=new Set();
  state.coverageRows=all.filter(x=>{
    const k=[x.source,x.media_type,x.media_name,x.landmark,x.nearest_station,x.distance_m,x.station_distance_m].join('|');
    if(seen.has(k))return false;seen.add(k);return true;
  });
  await refreshCoverageJoin();
  state.warnings.push(...warnings);renderData();await recalc();
  toast('已有'+state.coverageRows.length+'条覆盖来源，严格关联'+(state.coverageSummary?.matched_inventory_count||0)+'个库存媒体');
}
function renderCoverageStats(){
  if(!state.coverageRows.length){
    $('coverageStats').textContent='尚未导入空间覆盖CSV。';$('coverageWarnings').textContent='';$('coverageBreakdown').innerHTML='';return;
  }
  const s=state.coverageSummary||{};
  const groups={};
  for(const x of state.coverageRows){
    const key=x.landmark||'未注明地标';
    const g=groups[key]??={total:0,bus:0,metro:0,names:new Set()};
    g.total++;g[x.media_type]=(g[x.media_type]||0)+1;g.names.add(x.media_type+'|'+x.media_name);
  }
  const locs=Object.keys(groups);
  $('coverageStats').textContent='授权导出覆盖记录 '+state.coverageRows.length+' 行；与历史公交台账严格匹配 '+(s.matched_inventory_count||0)+' 个不同资源，未匹配 '+(s.unmatched_coverage_rows||0)+' 行。覆盖分析为线路/地铁点位的空间匹配证据，不代表在售。';
  $('coverageBreakdown').innerHTML=locs.map(k=>{const g=groups[k];return '<div class="coverage-spot"><strong>'+esc(k)+'</strong><small>记录 '+g.total+' · 公交 '+g.bus+' / 地铁 '+g.metro+'</small><small>不同媒体 '+g.names.size+' 个 · 半径 500m</small></div>'}).join('');
  $('coverageWarnings').textContent='平台导出含“汇总分析”和“明细分析”，仅汇总区计数；轨迹点距离不等于站点距离。历史公交数据为2026-11-13快照，2027年可售及地铁刊例仍待核验。';
}
function renderPreflight(){
  const r=state.preflight;
  if(!r){$('preflightSummary').textContent='未完成检查';$('preflightRows').innerHTML='';return;}
  $('preflightBadge').textContent=r.demo_operational?'可演示 · 未核实商务':'需补媒体数据';
  $('preflightSummary').textContent=r.summary+'；所选资源匹配覆盖导出 '+r.coverage_matched_selected+' 条。';
  const status={passed:'功能验证',needs_review:'待人工复核',missing:'未提供',evidence_partial:'部分来源',external:'外部操作',blocked:'阻断'};
  $('preflightRows').innerHTML=r.requirements.map(x=>`<div class="preflight-item"><b>${esc(x.label)}</b><small>${esc(x.detail)}</small><em class="${x.status==='passed'?'ok':''}">${status[x.status]||'待确认'}</em></div>`).join('');
}
function csvValue(v){return '"'+String(v??'').replace(/"/g,'""')+'"';}
function download(name,content,type='text/plain;charset=utf-8'){
 const url=URL.createObjectURL(new Blob([content],{type}));const a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),3000);
}
function exportCSV(){
  const p=state.plan;if(!p)return toast('请先生成提案');
  const head=['媒体ID','媒体名称','类型','运营公司','线路等级','广告形式','数量','历史快照日期','历史空位数','价格区间下界(万元/月)','价格区间上界(万元/月)','单车本期发布费上沿(万)','单车制作费上沿(万)','单车本期参考上沿(万)','组合小计上沿(万)','拟投放开始','拟投放结束','源文件','覆盖匹配来源','覆盖地标','复核状态'];
  const values=p.selected.map(r=>[r.id,r.media_name,labels[r.media_type],r.operator,r.grade,r.format,r.quantity,r.stock_asof,r.available_count,r.price_min_wan,r.price_max_wan,Number(r.publication_upper_wan||0)/Math.max(1,r.quantity),Number(r.production_upper_wan||0)/Math.max(1,r.quantity),r.unit_price_wan,r.line_total_wan,p.start_date,p.end_date,r.source,(r.coverage_source||[]).join('、'),(r.coverage_landmarks||[]).join('、'),'候选排期，未锁位／须核验2027档期']);
  const text='\uFEFF'+[head,...values].map(row=>row.map(csvValue).join(',')).join('\r\n');download('CompanyAgent_参考媒介组合_'+p.budget_wan+'万.csv',text,'text/csv;charset=utf-8');
}
async function analyzeBrief(){
  const text=$('brief').value.trim();if(!text)return toast('请先粘贴或导入客户 Brief');
  try{
    const a=await fetchJson('/api/brief/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})});
    state.briefAnalysis=a;
    const fields=`<p><strong>识别媒体：</strong>${esc(a.media_requested.join('、')||'未识别')}<br><strong>日期：</strong>${esc(a.mentioned_dates.join('、')||'待确认')}<br><strong>目标地标：</strong>${esc(a.mentioned_places.join('、')||'待确认')}</p>`;
    const issues=a.needs_review.map(x=>`<li>${esc(x)}</li>`).join('');
    $('briefReview').innerHTML=`<b>客户需求结构化提取 · 规则版</b>${fields}<strong>冲突及核验事项</strong><ul>${issues}</ul><small>${esc(a.sample_warning)}</small>`;
    toast('Brief 解析完成，已标记赛事范围冲突');
  }catch(e){toast('解析失败：'+e.message)}
}
async function loadBriefSample(){
  try{const r=await fetchJson('/api/brief/sample');$('brief').value=r.text;await analyzeBrief();}
  catch(e){toast('示例加载失败：'+e.message)}
}
async function importBriefFile(file){
  if(!file)return;const fd=new FormData();fd.append('file',file);
  try{const r=await fetchJson('/api/brief/import',{method:'POST',body:fd});$('brief').value=r.text;await analyzeBrief();toast('Brief 本地导入成功');}
  catch(e){toast('导入失败：'+e.message)}
}
function renderExecution(){
  const r=state.executionReview;
  if(!r){$('executionReview').textContent='暂无核验清单，请先生成提案';return;}
  $('executionReview').innerHTML=`<div class="execution-flag">${esc(r.readiness_label)} · 候选数量：${r.units_to_schedule}</div>`+
  `<div class="execution-list">${r.gates.map(g=>`<div><strong>${esc(g.stage)}</strong><span>${esc(g.action)}</span><em>待确认</em></div>`).join('')}</div>`+
  `<ul class="execution-warning">${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`;
}
function proposalMarkup(p){if(!p)return '<p>请先在工作台生成提案。</p>';
  const rows=p.selected.map(r=>`<tr><td>${esc(r.media_name)}</td><td>${esc(r.district)}</td><td>${esc(labels[r.media_type])}</td><td>${r.quantity}</td><td>${money(r.unit_price_wan)}</td><td>${money(r.line_total_wan)}</td><td>待复核</td></tr>`).join('');
  return `<div class="proposal-topline">CompanyAgent / AI MEDIA PROPOSAL</div><h2>${esc(p.brand)} · 2027 上海户外媒体投放提案</h2><p>行业：${esc(p.industry)} ｜ 投放日期：${p.start_date} — ${p.end_date} ｜ 版本：动态候选方案 / 非正式报价</p><div class="mini-grid"><div><small>客户预算</small><strong>${money(p.budget_wan)}</strong></div><div><small>刊例价参考合计</small><strong>${money(p.spent_wan)}</strong></div><div><small>候选媒体单元</small><strong>${p.unit_count} 个</strong></div><div><small>覆盖区域数（非人流）</small><strong>${p.district_count} 个</strong></div></div><h3>01 / Campaign 策略</h3><p>${esc(fitCopy[p.industry]||'根据客户门店和受众需求选择投放场景。')}</p><p>基于可导入的媒体库存和刊例数据，以区域偏好、预算和媒体类型进行候选组合优化。所选组合涉及 ${p.item_count} 条不同媒体资源。</p><h3>02 / 媒介组合与报价（区间上沿情景）</h3><div class="table-wrap"><table><thead><tr><th>媒体资源</th><th>区域</th><th>类型</th><th>数量</th><th>本周期单价</th><th>小计（万）</th><th>核验</th></tr></thead><tbody>${rows||'<tr><td colspan="7">当前无可用且已定价的候选媒体</td></tr>'}</tbody></table></div><h3>03 / 重点地标与覆盖来源</h3><p>已关联覆盖导出：${p.coverage_matched_selected||0} 条入选媒体；来源地标：${esc((p.coverage_landmarks||[]).join("、")||"未提供")}。仅作为媒体圈选证据，不代表真实客流、到店效果、ROI 或2027可售性。</p><h3>04 / 排期与校验</h3><p>${esc(p.schedule_state)}。预算利用率 ${p.utilization_pct}%；剩余参考预算 ${money(p.remaining_wan)}。发布费上沿参考合计${money(p.estimated_publication_upper_wan)}，制作费上沿参考合计${money(p.estimated_production_upper_wan)}；历史单日快照不证明2027实际可售。所有正式合同、锁位、折扣和投放效果必须重新确认。</p><div class="review-note">${p.is_demo?'⚠ 当前方案采用虚构演示数据，所有资源及价格均不代表新云传媒真实可售库存。':'⚠ 参考组合根据2026-11-13单日历史快照及脱敏刊例区间测算，并非2027实时可售证明或正式报价。当前仍缺真实地铁库存；覆盖来源关联数量请见上节，不能直接当成完整覆盖证明。'} 不提供未经验证的实际人流、投放覆盖人数、ROI 或销量承诺。</div><h3>05 / 计算规则与限制</h3><ul>${p.assumptions.map(x=>'<li>'+esc(x)+'</li>').join('')}</ul><h3>06 / 施工与交付承诺</h3><p>素材设计、客户定稿、内容审批、制作、夜间安装、上刊监拍、下刊和结案均需要双方逐项确认；单晚施工上限和天气缓冲不能从本数据推出。详细验收清单见下方。</p>`;
}
function renderProposal(){$('proposalPreview').innerHTML=proposalMarkup(state.plan);}
function safeJSON(v){return JSON.stringify(v).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');}
async function exportStandalone(){
  const p=state.plan;if(!p)return toast('请先生成提案');
  toast('正在构建三档预算的独立 HTML 报告…');
  try{
    const base=basePayload();
    const plans={};
    for(const b of [100,200,500]){
      plans[b]=await fetchJson('/api/plan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...base,budget_wan:b})});
      plans[b].execution_review=await fetchJson('/api/execution/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan:plans[b]})});
    }
    const initial=String(p.budget_wan);
    const html=`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CompanyAgent | ${esc(p.brand)}投放提案</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f3f7fc;color:#1a2e4b;font:14px/1.6 system-ui,"Microsoft Yahei",sans-serif}.wrap{max-width:1080px;margin:40px auto;padding:0 15px}.mast{background:linear-gradient(115deg,#0a2755,#236cce);border-radius:18px;color:white;padding:34px 40px}.ey{font-size:11px;letter-spacing:2px;color:#98dafa}.mast h1{font-size:28px;line-height:1.3;margin:12px 0}.mast p{color:#bad4f1}.panel{background:white;border:1px solid #dfe8f4;border-radius:16px;margin-top:18px;padding:30px}.selector{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.selector button{border:1px solid #cde0f7;color:#32649d;background:white;padding:9px 20px;border-radius:9px;cursor:pointer;font-weight:700}.selector button.on{background:#216be4;color:white;border-color:#216be4}.panel h2{font-size:23px;margin:0 0 10px}.panel h3{font-size:17px;margin:26px 0 12px}.panel p,.panel li{color:#62758e}.mini-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:19px 0}.mini-grid>div{padding:19px;background:#f1f7ff;border-radius:10px}.mini-grid small{display:block;font-size:11px;color:#8298b4}.mini-grid strong{display:block;font-size:20px;margin-top:8px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;min-width:680px}th,td{border-bottom:1px solid #e7eef7;text-align:left;padding:10px 12px;font-size:12px}th{background:#f4f7fc;color:#627b9b}.review-note{padding:15px;background:#fff6e5;border-left:3px solid #e5a240;color:#976a25;margin-top:20px}.footer{padding:20px;text-align:center;color:#9bafc4;font-size:11px}@media(max-width:700px){.mini-grid{grid-template-columns:repeat(2,1fr)}.mast{padding:24px}.panel{padding:18px}.mast h1{font-size:23px}}@media print{.selector{display:none}.wrap{margin:0;max-width:none}.panel{border:0;padding:12px}.mast{color:white;print-color-adjust:exact;-webkit-print-color-adjust:exact}}
    </style></head><body><div class="wrap"><div class="mast"><div class="ey">COMPANYAGENT / INTERCITY HACK · AI+办公</div><h1>AI 户外媒体智能提案</h1><p>可交互 HTML · 100 / 200 / 500 万预算即时切换 · 2027档期候选媒体</p></div><div class="panel"><div class="selector"><strong>评委现场调整预算：</strong><button data-b="100">100 万</button><button data-b="200">200 万</button><button data-b="500">500 万</button></div></div><div id="report" class="panel"></div><div class="footer">由 CompanyAgent 自动整理 · 真正可售档期需红豆系统核验 · 不构成商业承诺</div></div>
    <script>const plans=${safeJSON(plans)};const labels=${safeJSON(labels)};const copy=${safeJSON(fitCopy)};
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const money=x=>Number(x||0).toLocaleString('zh-CN',{maximumFractionDigits:2})+' 万';
    function render(b){const p=plans[b];document.querySelectorAll('[data-b]').forEach(x=>x.classList.toggle('on',x.dataset.b==b));
    const rows=p.selected.map(r=>'<tr><td>'+esc(r.media_name)+'</td><td>'+esc(r.district)+'</td><td>'+esc(labels[r.media_type])+'</td><td>'+r.quantity+'</td><td>'+money(r.unit_price_wan)+'</td><td>'+money(r.line_total_wan)+'</td><td>待复核</td></tr>').join('');
    document.getElementById('report').innerHTML='<h2>'+esc(p.brand)+' · 2027 上海户外媒体投放提案</h2><p>行业：'+esc(p.industry)+' ｜ 日期：'+p.start_date+'—'+p.end_date+' ｜ 非正式报价</p><div class="mini-grid"><div><small>投放预算</small><strong>'+money(p.budget_wan)+'</strong></div><div><small>参考合计</small><strong>'+money(p.spent_wan)+'</strong></div><div><small>推荐资源单元</small><strong>'+p.unit_count+' 个</strong></div><div><small>区域数量</small><strong>'+p.district_count+' 个</strong></div></div><h3>01 / 品牌策略</h3><p>'+esc(copy[p.industry]||'根据客户需求进行商圈圈选。')+'</p><h3>02 / 媒介清单与报价</h3><div class="table-wrap"><table><thead><tr><th>媒体名称</th><th>区域</th><th>类型</th><th>数量</th><th>单价</th><th>小计</th><th>库存</th></tr></thead><tbody>'+rows+'</tbody></table></div><h3>03 / 覆盖来源关联</h3><p>严格匹配覆盖分析来源 '+(p.coverage_matched_selected||0)+' 条媒体；地标：'+esc((p.coverage_landmarks||[]).join('、')||'未提供')+'。仅是来源关联，非实测客流或可售证明。</p><h3>04 / 排期与假设</h3><p>'+esc(p.schedule_state)+'</p><div class="review-note">'+(p.is_demo?'本报告使用虚构演示数据，不代表真实库存或报价。':'价格为脱敏区间上沿情景测算；2026年历史库存不证明2027档期可售，制作费及广告形式仍需复核。')+'</div><ul>'+p.assumptions.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><h3>05 / 上下刊与结案核验</h3><p>以下环节来自赛事参考材料，均未被真实证明完成。</p><ul>'+p.execution_review.gates.map(g=>'<li>'+esc(g.stage)+'：'+esc(g.action)+'（待确认）</li>').join('')+'</ul><div class="review-note">'+p.execution_review.warnings.map(esc).join('；')+'</div>';
    }document.querySelectorAll('[data-b]').forEach(x=>x.onclick=()=>render(x.dataset.b));render(${safeJSON([100,200,500].includes(Number(initial))?initial:'200')});<\/script></body></html>`;
    download('CompanyAgent_交互投放提案_'+p.brand.replace(/[\\/:*?"<>|]/g,'_')+'.html',html,'text/html;charset=utf-8');
    toast('HTML 已生成：独立打开后仍可切换三档预算');
  }catch(e){toast('导出失败：'+e.message);}
}
async function askAI(){if(!state.plan)return;
  $('askAiBtn').disabled=true;$('askAiBtn').textContent='Agent 正在生成…';
  try{
    const b=basePayload();const res=await fetchJson('/api/ai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brand:b.brand,industry:b.industry,brief:$('brief').value,summary:state.plan})});
    state.lastAi=res.content;$('aiOutput').textContent=res.content;$('aiBadge').textContent='B1X AI';toast('AI 策略生成成功');
  }catch(e){toast(e.message)}finally{$('askAiBtn').disabled=false;$('askAiBtn').textContent='✦ 使用 B1X AI 解读';}
}
function bind(){
  document.querySelectorAll('[data-tab]').forEach(x=>x.addEventListener('click',()=>nav(x.dataset.tab)));
  $('helpBtn').addEventListener('click',()=>nav('workflow'));$('goData').addEventListener('click',()=>nav('data'));
  $('budgetRange').addEventListener('input',e=>setBudget(e.target.value));
  document.querySelectorAll('[data-budget]').forEach(x=>x.addEventListener('click',()=>setBudget(x.dataset.budget)));
  document.querySelectorAll('[data-medium]').forEach(x=>x.addEventListener('click',()=>{document.querySelectorAll('[data-medium]').forEach(y=>y.classList.toggle('selected',y===x));scheduleRecalc();}));
  for(const id of ['industry','startDate','weeks','focusDistrict','focusLandmark','coverageOnly'])$(id).addEventListener('change',scheduleRecalc);
  $('brand').addEventListener('change',scheduleRecalc);$('generateBtn').addEventListener('click',recalc);
  $('previewQuick').addEventListener('click',()=>nav('proposal'));$('backToStudio').addEventListener('click',()=>nav('studio'));
  $('downloadCsv').addEventListener('click',exportCSV);$('exportPlanCsvBtn').addEventListener('click',exportCSV);
  $('exportHtmlBtn').addEventListener('click',exportStandalone);
  $('askAiBtn').addEventListener('click',askAI);
  $('loadBriefSample').addEventListener('click',loadBriefSample);
  $('analyzeBriefBtn').addEventListener('click',analyzeBrief);
  $('uploadBriefBtn').addEventListener('click',()=>$('briefFile').click());
  $('briefFile').addEventListener('change',e=>importBriefFile(e.target.files[0]));
  $('uploadStockBtn').addEventListener('click',()=>$('stockFile').click());$('uploadPriceBtn').addEventListener('click',()=>$('priceFile').click());
  $('stockFile').addEventListener('change',e=>importStockFiles([...e.target.files]));
  $('priceFile').addEventListener('change',e=>importFile(e.target.files[0],'pricing'));
  $('uploadCoverageBtn').addEventListener('click',()=>$('coverageFile').click());
  $('coverageFile').addEventListener('change',e=>importCoverageFiles([...e.target.files]));
  $('resetDemo').addEventListener('click',loadDemo);$('loadContestBtn').addEventListener('click',loadContest);
}
window.addEventListener('DOMContentLoaded',async()=>{
  bind();await loadContest();
  try{const s=await fetchJson('/api/health');$('aiStatus').textContent=s.ai_enabled?'AI 模型已配置':'离线业务引擎可用';}catch{}
});
