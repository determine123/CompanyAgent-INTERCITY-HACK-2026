/* Public, stateless judge experience: only allowlisted selectors go to synthetic APIs.
 * Brand, business goal, audience, KPI and proof method stay entirely client-side.
 * No tokens, private inventory, analytics events, cookies or enterprise writes.
 */
const $=id=>document.getElementById(id);
const state={budget:200,lastPlan:null,lastWorkflow:null};
const escapeText=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const mediumLabels={both:'公交车身 + 地铁出入口',bus:'公交车身',metro:'地铁出入口'};
const text=id=>$(id).value.trim().slice(0,100);

document.querySelectorAll('#budgetOptions button').forEach(b=>b.addEventListener('click',()=>{
  state.budget=Number(b.dataset.budget);
  document.querySelectorAll('#budgetOptions button').forEach(x=>x.classList.toggle('active',x===b));
  state.lastPlan=null;state.lastWorkflow=null;
  $('status').textContent='参数已变更 · 需重新计算';
  $('workflowLoading').textContent='预算已修改；请重新点击上方 Agent 生成候选方案。';
  $('workflowResult').hidden=true;$('handoffResult').hidden=true;$('handoffEmpty').hidden=false;
  renderBrief();
}));
const briefInputs=['brand','goal','businessGoal','audience','kpi','measurement','medium'];
briefInputs.forEach(id=>$(id).addEventListener('input',renderBrief));
briefInputs.forEach(id=>$(id).addEventListener('change',()=>{
  renderBrief();
  if(id==='medium'){state.lastPlan=null;state.lastWorkflow=null;$('status').textContent='媒体范围已改变 · 需重算';$('workflowResult').hidden=true;$('handoffResult').hidden=true;$('handoffEmpty').hidden=false;}
}));

function briefElements(){
 return [
   ['客户与品牌',text('brand')?'食品饮料 · '+text('brand'):'待确认',Boolean(text('brand'))],
   ['生意目标',text('businessGoal')||'待确认',Boolean(text('businessGoal'))],
   ['唯一 Campaign 目标',$('goal').value,Boolean($('goal').value)],
   ['目标受众',text('audience')||'待确认',Boolean(text('audience'))],
   ['档期与预算','2027-05-01 起 4 周 · '+state.budget+' 万（虚构档期）',true],
   ['媒体范围',mediumLabels[$('medium').value]||'待确认',Boolean(mediumLabels[$('medium').value])],
   ['KPI 与核验方式',text('kpi')&&text('measurement')?text('kpi')+' / '+text('measurement'):'待客户确认',Boolean(text('kpi')&&text('measurement'))],
 ];
}
function renderBrief(){
 const elements=briefElements(),complete=elements.filter(x=>x[2]).length;
 $('briefCheck').textContent='Campaign 七要素字段 '+complete+'/7 · '+(complete===7?'样例填写完整，仍待客户确认':'缺少 '+(7-complete)+' 项，请补齐')+'。本页自由文本不会发送给服务器。';
 $('briefCheck').dataset.ready=complete===7?'yes':'no';
}

async function readDemo(url){
 const res=await fetch(url,{method:'GET',credentials:'omit',cache:'no-store'});
 const data=await res.json();
 if(!res.ok)throw new Error(data.detail||'HTTP '+res.status);
 return data;
}

async function generate(){
 const b=$('generate');b.disabled=true;
 $('status').textContent='计算中';
 $('loading').hidden=false;$('loading').textContent='正在调用安全的虚构库存优化 API…';
 $('result').hidden=true;
 $('workflowResult').hidden=true;$('handoffResult').hidden=true;
 $('handoffEmpty').hidden=false;
 try{
   const params=new URLSearchParams({budget_wan:String(state.budget),medium:$('medium').value});
   const data=await readDemo('/judge/api/plan?'+params.toString());
   if(data.synthetic_only!==true||data.real_hongdou_connected!==false)throw new Error('演示安全状态异常，拒绝展示');
   state.lastPlan=data;
   $('planTitle').textContent=(text('brand')||'模拟饮料品牌')+' · '+$('goal').value+'目标参考方案';
   $('outBudget').textContent=data.budget_wan+' 万';
   $('outSpent').textContent=data.spent_wan+' 万';
   $('outCount').textContent=data.item_count+' 项 / '+data.unit_count+' 单元';
   $('source').textContent='数据：'+data.source_file+'（'+data.sample_size+' 条虚构记录） · 同一确定性优化器 · 不接入红豆/可视化 API';
   $('mediaRows').innerHTML=(data.selected||[]).slice(0,30).map(x=>'<tr><td>'+escapeText(x.media_name)+'</td><td>'+escapeText(x.district)+'</td><td>'+x.quantity+'</td><td>'+x.line_total_wan+'</td></tr>').join('')||'<tr><td colspan="4">没有匹配媒体，请调整约束。</td></tr>';
   $('risks').innerHTML=(data.risk_questions||[]).map((x,i)=>'<p><b>风险 '+(i+1)+'：</b>'+escapeText(x)+'</p>').join('');
   $('actions').innerHTML=(data.actions||[]).map((x,i)=>'<p><b>P'+(i+1)+'：</b>'+escapeText(x)+'</p>').join('');
   $('status').textContent='参考方案已生成';
   $('loading').hidden=true;$('result').hidden=false;
   await analyzeChange();
 }catch(err){
   $('status').textContent='暂不可用';
   $('loading').textContent='本次未能完成：'+err.message+'。可以查看 GitHub 或现场演示。';
 }finally{b.disabled=false}
}
function displaySigned(value,suffix){
 return (value>0?'+':'')+value+suffix;
}
async function analyzeChange(){
 if(!state.lastPlan){$('workflowLoading').textContent='请先生成本次预算方案';return;}
 const button=$('analyzeChange');button.disabled=true;
 $('workflowLoading').textContent='正在重跑原方案、计算媒体差异并生成部门交接…';
 try{
  const params=new URLSearchParams({
    budget_wan:String(state.budget),medium:$('medium').value,
    prior_budget_wan:$('priorBudget').value,prior_medium:$('priorMedium').value,
    change_type:$('changeType').value
  });
  const x=await readDemo('/judge/api/workflow?'+params.toString());
  if(x.simulation_only!==true||x.real_api_accessed!==false||x.changed_enterprise_records!==false)throw new Error('仿真状态未通过安全校验');
  state.lastWorkflow=x;
  const i=x.impact;
  $('impactSpend').textContent=displaySigned(i.spent_delta_wan,' 万');
  $('impactAdd').textContent='+'+i.added_units+' 单元';
  $('impactRemove').textContent='−'+i.removed_units+' 单元';
  $('diffProvenance').textContent='原方案 '+x.previous.budget_wan+' 万（'+mediumLabels[x.previous.medium]+'）→ 新方案 '+x.current.budget_wan+' 万（'+mediumLabels[x.current.medium]+'） · 同源虚构 CSV SHA256 前缀 '+x.data_lineage.sha256_prefix+' · '+x.data_lineage.records+' 条';
  $('variantSummary').innerHTML=x.scenario_summary.map(s=>'<div><b>'+s.budget_wan+' 万</b><span>参考使用 '+s.spent_wan+' 万 · '+s.item_count+' 项 / '+s.unit_count+' 单元</span></div>').join('');
  $('diffRows').innerHTML=i.changed_rows.map(r=>'<tr><td>'+escapeText(r.media_name)+'</td><td>'+r.before_quantity+'</td><td>'+r.after_quantity+'</td><td>'+displaySigned(r.delta_units,'')+'</td></tr>').join('')||'<tr><td colspan="4">前后媒体组合相同（业务事件仍需人工复核）</td></tr>';
  $('diffCoverage').textContent='变动媒体 '+i.changed_media_count+' 项；净增减 '+displaySigned(i.net_units,' 个单元')+(i.details_truncated?'；仅展示差异最大的前 12 项':'')+'。参考金额不是成交价。';
  $('workflowResult').hidden=false;
  $('workflowLoading').textContent='差异计算完成，未执行预订或变更';
  $('qualityStatus').textContent='内部证据自查 '+x.checks_with_evidence+'/'+x.checks.length+' 项具备基本证据 · 非主办方评分 · 正式报价/锁位/合同仍待审核';
  $('qualityChecks').innerHTML=x.checks.map(c=>'<div class="'+(c.status==='evidence_present'?'ready':'pending')+'"><b>'+(c.status==='evidence_present'?'✓':'⚑')+' '+escapeText(c.label)+'</b><small>'+escapeText(c.explanation)+'</small></div>').join('');
  $('handoffSteps').innerHTML=x.handoff.dependency_steps.map(step=>'<div class="handoff-step"><span>'+step.order+'</span><div><b>'+escapeText(step.title)+'</b><small>'+escapeText(step.owner)+' · 待人工确认</small><p>'+escapeText(step.detail)+'</p></div></div>').join('');
  $('skillPreview').innerHTML='<b>建议：'+escapeText(x.skill_improvement.name)+'</b><p>'+escapeText(x.skill_improvement.reason)+'</p><small>状态：仅为候选建议，必须经员工审批；不自动安装或调用企业工具。</small>';
  $('noticeDraft').textContent=x.handoff.customer_notice_draft+'（虚构通知草稿，绝未发送）';
  $('handoffEmpty').hidden=true;$('handoffResult').hidden=false;
 }catch(err){
  $('workflowLoading').textContent='变更计算不可用：'+err.message;
  $('workflowResult').hidden=true;$('handoffResult').hidden=true;$('handoffEmpty').hidden=false;
 }finally{button.disabled=false}
}

$('generate').addEventListener('click',generate);
$('analyzeChange').addEventListener('click',analyzeChange);
$('copyHandoff').addEventListener('click',async()=>{
 if(!state.lastWorkflow){return;}
 const x=state.lastWorkflow;
 const brief=briefElements().map(e=>e[0]+'：'+e[1]).join('\n');
 const tasks=x.handoff.dependency_steps.map(s=>s.order+'. '+s.title+'｜责任人：'+s.owner+'｜未执行').join('\n');
 const value='CompanyAgent｜虚构数据人工复核摘要\n\n'+brief+
  '\n\n基于虚构库存的前后方案：'+x.previous.budget_wan+' → '+x.current.budget_wan+' 万\n'+
  '参考金额变化：'+displaySigned(x.impact.spent_delta_wan,' 万')+
  '；新增单元 '+x.impact.added_units+'；减少单元 '+x.impact.removed_units+
  '\n源文件 SHA256 前缀：'+x.data_lineage.sha256_prefix+
  '\n\n待人工审批工作：\n'+tasks+
  '\n\n重要：模拟数据，不构成真实可售、正式报价、通知、锁位或广告收益保证。';
 try{
  await navigator.clipboard.writeText(value);
  $('copyHandoff').textContent='✓ 已复制 · 请人工审核后使用';
 }catch(e){$('copyHandoff').textContent='浏览器未授权复制，请改用现场展示';}
});
renderBrief();
