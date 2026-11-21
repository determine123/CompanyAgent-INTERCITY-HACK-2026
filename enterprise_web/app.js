/* CompanyAgent staff workbench — only approved fixed tools; no arbitrary code execution. */
const $=id=>document.getElementById(id);
const E=value=>String(value??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const state={csrf:'',user:null,agents:[],skills:[],datasets:[],sources:[],lastRun:null,budget:100,page:'client',publicSynthetic:false};
function enforceIndustry(){if(!state.publicSynthetic)return;for(const id of ['clientIndustry','taskIndustry']){const select=$(id);if(select){select.value='食品饮料';select.disabled=true;select.title='公网演示只支持食品饮料，其他行业需独立审批';}}for(const id of ['clientCoverage','taskStrict']){const input=$(id);if(input){input.checked=false;input.disabled=true;input.title='公网演示没有授权的商圈覆盖数据；仅生成无覆盖证明的参考候选方案';}}const bench=$('benchmarkAgent');if(bench){bench.disabled=true;bench.title='公网单行业演示不开放五行业测试';}const status=$('parseStatus');if(status)status.textContent='演示范围：食品饮料 · 虚构库存 · 未取得商圈覆盖证据 · 红豆真实接口未接入';}
const TOOLTITLES={brief_parse:'Brief 结构化解析',load_inventory:'加载授权库存',match_coverage:'覆盖证据精确匹配',optimize_budget:'预算确定性优化',review_risks:'人工核验风险清单',explain_plan:'生成可解释方案'};
function toast(message){const el=$('toast');el.textContent=message;el.classList.remove('hidden');clearTimeout(toast.t);toast.t=setTimeout(()=>el.classList.add('hidden'),3400)}
async function api(path,method='GET',data){const headers={};if(method!=='GET')headers['X-CSRF-Token']=state.csrf;if(data!==undefined&&!(data instanceof FormData)){headers['Content-Type']='application/json';data=JSON.stringify(data)}let r;try{r=await fetch('/enterprise/api'+path,{method,headers,body:method==='GET'?undefined:data,credentials:'same-origin'})}catch(e){throw new Error('无法连接本地服务：'+e.message)}const content=await r.json().catch(()=>({}));if(!r.ok)throw new Error(typeof content.detail==='string'?content.detail:'服务器操作失败 '+r.status);return content}
function show(page){state.page=page;document.querySelectorAll('.screen').forEach(x=>x.classList.toggle('active',x.id==='page-'+page));document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));$('crumb').textContent=({studio:'智能任务执行',agents:'我的 Agents',skills:'我的 Skills',datasets:'数据源中心',audit:'执行与审计',iteration:'自我迭代实验室',client:'客户需求与方案',insights:'企业需求资产库'})[page];if(page==='audit')refreshAudit();if(page==='datasets')refreshData();if(page==='iteration'){refreshImprovements();loadFailureCases()}if(page==='insights')refreshDemandInsights();window.scrollTo({top:0,behavior:'smooth'})}
function renderAsset(asset,type){const isOwner=asset.owner_id===state.user.id||state.user.role==='admin';const ident=type==='agent'?asset.skill_ids:asset.tools;let meta=type==='agent'?`已绑定 ${ident.length} 项 Skill`:`工具：${ident.map(t=>TOOLTITLES[t]||t).join('、')}`;return `<article class="asset"><h3>${E(asset.name)}</h3><p>${E(asset.description||'暂无业务说明')}</p><div class="asset-meta"><span>${asset.visibility==='team'?'企业共享':'仅个人'} · ${E(meta)}</span>${isOwner?`<button class="tiny-btn" data-edit-${type}="${asset.id}">编辑</button>`:''}</div></article>`}
async function refreshAssets(){const [a,s]=await Promise.all([api('/agents'),api('/skills')]);state.agents=a.items;state.skills=s.items;$('agentList').innerHTML=a.items.map(x=>renderAsset(x,'agent')).join('')||'<p class="micro">暂无 Agent，左侧新建</p>';$('skillList').innerHTML=s.items.map(x=>renderAsset(x,'skill')).join('')||'<p class="micro">暂无 Skill，左侧新建</p>';$('agentCount').textContent=a.items.length+' 个';$('skillCount').textContent=s.items.length+' 个';$('taskAgent').innerHTML=a.items.map(x=>`<option value="${x.id}">${E(x.name)}</option>`).join('');$('clientAgent').innerHTML=a.items.map(x=>`<option value="${x.id}">${E(x.name)}</option>`).join('');$('agentSkillOptions').innerHTML=s.items.map(x=>`<label><input type="checkbox" value="${x.id}" class="select-agent-skill"><span>${E(x.name)}</span></label>`).join('');$('skillTools').innerHTML=s.supported_tools.map(x=>`<label><input type="checkbox" value="${E(x)}" class="select-skill-tool"><span>${E(TOOLTITLES[x]||x)}</span></label>`).join('')}
function resetAgent(){for(let id of ['agentEdit','agentName','agentDesc','agentInstructions'])$(id).value='';$('agentVisibility').value='private';document.querySelectorAll('.select-agent-skill').forEach(x=>x.checked=false)}
function resetSkill(){for(let id of ['skillEdit','skillName','skillDesc','skillInstructions'])$(id).value='';$('skillVisibility').value='private';document.querySelectorAll('.select-skill-tool').forEach(x=>x.checked=false)}
function collect(type){const isA=type==='agent';return {name:$(isA?'agentName':'skillName').value.trim(),description:$(isA?'agentDesc':'skillDesc').value.trim(),instructions:$(isA?'agentInstructions':'skillInstructions').value,visibility:$(isA?'agentVisibility':'skillVisibility').value,skill_ids:[...document.querySelectorAll('.select-agent-skill:checked')].map(x=>Number(x.value)),tools:[...document.querySelectorAll('.select-skill-tool:checked')].map(x=>x.value)}}
async function saveAsset(type){try{const isA=type==='agent',name=isA?'agents':'skills',id=$(isA?'agentEdit':'skillEdit').value,payload=collect(type);if(!payload.name)throw new Error('请输入名称');await api('/'+name+(id?'/'+id:''),id?'PUT':'POST',payload);toast((isA?'Agent':'Skill')+' 已保存');await refreshAssets();isA?resetAgent():resetSkill()}catch(e){toast(e.message)}}
function editAsset(type,id){let isA=type==='agent',item=(isA?state.agents:state.skills).find(x=>x.id===id);if(!item)return;show(isA?'agents':'skills');$(isA?'agentEdit':'skillEdit').value=item.id;$(isA?'agentName':'skillName').value=item.name;$(isA?'agentDesc':'skillDesc').value=item.description;$(isA?'agentInstructions':'skillInstructions').value=item.instructions;$(isA?'agentVisibility':'skillVisibility').value=item.visibility;document.querySelectorAll(isA?'.select-agent-skill':'.select-skill-tool').forEach(x=>x.checked=(isA?item.skill_ids:item.tools).includes(isA?Number(x.value):x.value));window.scrollTo({top:150,behavior:'smooth'})}
function setBudget(v){state.budget=Number(v);document.querySelectorAll('.budget').forEach(b=>b.classList.toggle('active',Number(b.dataset.budget)===state.budget))}
function runHtml(result){let p=result.plan;$('emptyResult').classList.add('hidden');$('runResult').classList.remove('hidden');$('runState').textContent='已完成 · Run #'+result.run_id;$('resTitle').textContent=`${p.brand} · ${p.focus_landmark||'上海'}广告方案`;$('resRationale').textContent=result.rationale;$('resSpent').textContent=p.spent_wan.toLocaleString('zh-CN')+' 万';$('resUnits').textContent=p.unit_count;$('resItems').textContent=p.item_count;
 $('trace').innerHTML=result.trace.map(x=>`<div class="trace-item ${x.status==='ok'?'':'warn'}"><b>${E(TOOLTITLES[x.tool]||x.tool)}</b><small>${E(x.detail)}</small></div>`).join('');$('resultRows').innerHTML=p.selected.slice(0,30).map(r=>`<tr><td>${E(r.media_name||r.id)}</td><td>${E(r.quantity)}</td><td>${E(r.line_total_wan)}</td><td>${E((r.coverage_landmarks||[]).join('、')||'未验证')}</td></tr>`).join('')||'<tr><td colspan="4">没有符合预算、库存价格和覆盖限制的媒体</td></tr>';$('resultWarnings').innerHTML=result.alerts.map(x=>`<p>⚑ ${E(x)}</p>`).join('');$('modelInsight').classList.add('hidden');$('qualityInfo').textContent=result.quality_report?`质量门禁：${result.quality_report.status} · ${result.quality_report.evidence.matched_items}/${result.quality_report.evidence.total_items}项有商圈覆盖证据 · ${result.quality_report.blockers.length}项阻断 · ${result.quality_report.warnings.length}项待核验`:'质量信号待收集';$('evaluationInfo').textContent=result.evaluation_report?`质量评估：${result.evaluation_report.passed}/${result.evaluation_report.total} 项检查通过（不代表商业效果）`:'旧版运行未生成评估结果';
 $('replayInfo').textContent='冻结数据重放：点击按钮验证当时的工具权限、数据来源与结果';
 $('benchmarkInfo').textContent='15 场景评估：点击按钮运行五行业 × 三档预算测试';
 $('iterationHint').textContent=result.improvement_hint||'任务完成后可提交反馈，试验新的 Skill 策略。';$('feedbackRunId').textContent='Run #'+result.run_id;refreshProposalReview();}
async function parseNaturalBrief(){
 const brief=$('taskBrief').value.trim();if(!brief)throw new Error('请先填写需求文本');
 const r=await api('/brief/parse','POST',{text:brief});const f=r.fields;
 if(f.brand&&f.brand!=='客户待确认')$('taskBrand').value=f.brand;
 if(f.industry)$('taskIndustry').value=state.publicSynthetic?'食品饮料':f.industry;
 if(f.focus_landmark&&[...$('taskPlace').options].some(x=>x.value===f.focus_landmark))$('taskPlace').value=f.focus_landmark;
 if(f.start_date)$('taskDate').value=f.start_date;
 if(f.budget_wan){const rounded=[100,200,500].includes(f.budget_wan)?f.budget_wan:200;setBudget(rounded);}
 $('parseStatus').textContent=`已提取：${f.industry} · ${f.budget_wan}万 · ${f.focus_landmark||'地标待指定'}`;
 return r;
}
async function runTask(){try{const agentId=Number($('taskAgent').value);if(!agentId)throw new Error('请先创建一个有业务 Skill 的 Agent');const payload={agent_id:agentId,brief:$('taskBrief').value,industry:$('taskIndustry').value,brand:$('taskBrand').value,budget_wan:state.budget,start_date:$('taskDate').value,weeks:Number($('taskWeeks').value),landmark:$('taskPlace').value,medium:$('taskMedium').value,coverage_only:$('taskStrict').checked};$('runBtn').disabled=true;$('runBtn').textContent='Agent 正在执行工具…';$('runState').textContent='正在执行';const submittedAt=performance.now();
  const r=await api('/runs','POST',payload);
  state.lastClientDurationMs=Math.max(0,performance.now()-submittedAt);state.lastRun=r;runHtml(r);refreshStatus();toast('任务完成，已记录执行轨迹')}catch(e){$('runState').textContent='执行失败';toast(e.message)}finally{$('runBtn').disabled=false;$('runBtn').innerHTML='✦ 让 Agent 执行任务 <span>→</span>'}}
function copyResult(){if(!state.lastRun)return;const r=state.lastRun,p=r.plan,text=[`${p.brand} · ${p.budget_wan}万元投放方案`,r.rationale,`参考合计${p.spent_wan}万元；候选${p.item_count}项；需要2027库存确认。`,...r.alerts].join('\n');navigator.clipboard?.writeText(text).then(()=>toast('已复制方案摘要')).catch(()=>toast('复制失败，请使用浏览器复制'))}
async function refreshData(){try{const d=await api('/datasets');state.datasets=d.items;
 for(const [id,kind] of [['bridgeInventory','inventory'],['bridgeCoverage','coverage']]){
  const el=$(id),old=el.value,rows=d.items.filter(t=>t.kind===kind);
  el.innerHTML=rows.map(x=>`<option value="${x.id}">${E(x.name)} · ${x.count} 行</option>`).join('');
  if(rows.some(x=>String(x.id)===old))el.value=old;
 }
 $('datasetCount').textContent=d.items.length+' 个';$('datasetList').innerHTML=d.items.map(x=>`<article class="asset"><h3>${E(x.name)}</h3><p>${x.kind==='inventory'?'媒体库存':x.kind==='pricing'?'价格表':'覆盖分析'} · ${x.count} 行 · ${E(x.origin)}<br>${E(x.notes||'')}</p><div class="asset-meta"><span>${E(x.imported_at)} · ${E(x.visibility)}</span><span>#${x.id}</span></div></article>`).join('')||'<p class="micro">未导入数据</p>';const stat=await api('/status');$('autoInfo').textContent='监听目录：'+stat.import_folder+'；自动同步：'+(stat.automated_sync?'已开启':'默认关闭')+'；HTTPS 白名单：'+(stat.allowed_hosts||'未设置');const src=await api('/sources');state.sources=src.items;$('sourceCount').textContent=src.items.length+' 个';$('sourceList').innerHTML=src.items.map(s=>`<article class="asset"><h3>${E(s.name)}</h3><p>${E(s.kind)} · 每${s.interval_minutes}分钟<br>${E(s.url)}</p><div class="asset-meta"><span>${E(s.last_status||'未执行')} · ${E(s.last_sync||'无同步记录')}</span><button class="tiny-btn" data-sync-source="${s.id}">立即同步</button></div>${s.last_error?`<p style="color:#c66d50">${E(s.last_error)}</p>`:''}</article>`).join('')||'<p class="micro">未创建 HTTPS 连接器（仅管理员可见）</p>';$('pollFolder').disabled=state.user.role!=='admin';$('saveSource').disabled=state.user.role!=='admin'}catch(e){toast(e.message)}}
async function uploadDataset(){try{const f=$('datasetFile').files[0];if(!f)throw new Error('请先选择CSV/XLSX');const form=new FormData();form.set('file',f);const r=await api(`/datasets/upload?kind=${encodeURIComponent($('datasetKind').value)}&visibility=${encodeURIComponent($('datasetVisibility').value)}`,'POST',form);$('uploadStatus').textContent=`完成：${r.record_count}条记录；${r.duplicate?'已有相同文件，已去重':'新数据集 #'+r.dataset_id}`;toast('数据已导入');await refreshData();await refreshStatus()}catch(e){$('uploadStatus').textContent=e.message;toast(e.message)}}
async function createSource(){try{const data={name:$('sourceName').value,kind:$('sourceKind').value,url:$('sourceUrl').value,token_env:$('sourceTokenEnv').value,interval_minutes:Number($('sourceInterval').value)};await api('/sources','POST',data);toast('HTTPS 连接器已添加');refreshData()}catch(e){toast(e.message)}}
async function refreshAudit(){try{const [r,a,u]=await Promise.all([api('/runs'),api('/audit'),api('/users')]);$('runHistory').innerHTML=r.items.map(x=>`<article class="asset"><h3>Run #${x.id} · ${E(x.brand||'客户')}</h3><p>参考${x.spent_wan}万 · 选中${x.item_count}项 · ${E(x.created_at)}</p><button class="tiny-btn" data-open-run="${x.id}">查看执行记录</button></article>`).join('')||'<p class="micro">尚无任务执行历史</p>';$('auditList').innerHTML=a.items.map(x=>`<article class="asset"><h3>${E(x.action)}</h3><p>${E(x.detail)} · ${E(x.created_at)}</p></article>`).join('')||'<p class="micro">暂无审计记录</p>';$('adminPanel').classList.toggle('hidden',state.user.role!=='admin');$('userList').innerHTML=u.items.map(x=>`<article class="asset"><h3>${E(x.display)} · ${E(x.username)}</h3><p>${E(x.role)} · ${E(x.created_at)}</p></article>`).join('')}catch(e){toast(e.message)}}
async function createUser(){try{const r=await api('/users','POST',{username:$('newUser').value.trim(),display:$('newDisplay').value.trim(),role:$('newRole').value});$('newUserCred').classList.remove('hidden');$('newUserCred').textContent=`新账号：${r.username}；一次性初始密码：${r.initial_password}。请安全转交员工，立即更改。此处不再重复显示。`;await refreshAudit();toast('已创建员工账号')}catch(e){toast(e.message)}}
async function refreshStatus(){try{const s=await api('/status');for(let field of ['agents','skills','datasets','runs'])$('stat'+field[0].toUpperCase()+field.slice(1)).textContent=s.counts[field]}catch(e){}}
async function bootstrap(){try{const me=await api('/me');state.csrf=me.csrf;state.user=me.user;$('loginCover').classList.add('hidden');$('userLabel').textContent=me.user.display;$('roleLabel').textContent=me.user.role;$('avatar').textContent=me.user.display.slice(0,1);await Promise.all([refreshAssets(),refreshStatus(),loadClientDatasetChoices()]);setBudget(200);try{const cfg=await api('/status');state.publicSynthetic=cfg.deployment_mode==='cloud_synthetic';enforceIndustry();$('clientModelStatus').textContent=cfg.tool_model_configured?('服务端已配置 '+cfg.tool_model_provider+' 受限 Tool Calling；仍须真实调用才能判定联调成功'):'尚未配置 '+cfg.tool_model_provider+' 受限模型密钥或模型 ID；确定性方案功能仍可用';}catch(e){}}catch(e){$('loginCover').classList.remove('hidden')}}
$('loginForm').addEventListener('submit',async e=>{e.preventDefault();try{const r=await api('/auth/login','POST',{username:$('loginUser').value.trim(),password:$('loginPassword').value});state.csrf=r.csrf;await bootstrap();toast('欢迎进入企业 Agent 工作台')}catch(err){$('loginError').textContent=err.message}});
async function refreshProposalReview(){
 if(!state.lastRun?.run_id)return;
 const a=$('approveDemo'),r=$('rejectDemo');a.classList.add('hidden');r.classList.add('hidden');
 try{const d=await api('/runs/'+state.lastRun.run_id+'/quality');
  const q=d.quality,review=d.review;
  $('reviewStatus').textContent='演示审批：'+({pending:'待审核',approved:'已批准',rejected:'已退回',stale:'快照变更，审批失效'}[review.status]||review.status)+
   ' · 质量状态：'+q.status+' · 覆盖证据 '+q.evidence.coverage_pct+'% · 注：批准仅限比赛演示，不代表已售/锁位';
  if(state.user?.role==='admin') {a.classList.remove('hidden');r.classList.remove('hidden');a.disabled=!q.demo_approvable;}
 }catch(err){$('reviewStatus').textContent='审批状态读取失败：'+err.message}
}
$('exportProposal').onclick=()=>{if(!state.lastRun?.run_id){toast('请先运行一次任务');return}
 window.location.href='/enterprise/api/runs/'+state.lastRun.run_id+'/proposal.html';
 toast('正在导出冻结快照 HTML 提案');};
async function decideDemo(decision){if(!state.lastRun?.run_id)return;
 if(!confirm(decision==='approve'?'仅批准该结果用于比赛演示，不代表锁位或正式报价。确认？':'确认退回这份演示提案？'))return;
 try{await api('/runs/'+state.lastRun.run_id+'/review','POST',{decision,comment:decision==='approve'?'人工审核通过比赛演示（非商业承诺）':'退回修改并核对数据'});
 toast(decision==='approve'?'演示审核已记录':'已退回');await refreshProposalReview();}catch(e){toast(e.message)}
}
$('replayRun').onclick=async()=>{
 if(!state.lastRun?.run_id){toast('请先运行一次业务任务');return}
 try{
  $('replayInfo').textContent='正在使用冻结数据与原 Skill 权限重放…';
  const out=await api('/runs/'+state.lastRun.run_id+'/replay','POST',{});
  $('replayInfo').textContent=out.verified?
   '重放通过：冻结的媒体、预算与质量门禁结果完全一致 · '+out.original_fingerprint.slice(0,12):
   '重放未通过：'+out.status+' · '+(out.issues||[]).join('、');
  toast(out.verified?'任务可重复验证':'检测到数据/结果漂移，需要人工复核');
 }catch(err){$('replayInfo').textContent='重放失败：'+err.message;toast(err.message)}
};
$('benchmarkAgent').onclick=async()=>{
 const agentId=Number($('taskAgent').value);
 if(!agentId){toast('请先选择 Agent');return}
 try{
  $('benchmarkInfo').textContent='正在运行 5 行业 × 3 预算安全工具回归…';
  const report=await api('/agents/'+agentId+'/benchmark','POST',{
   landmark:$('taskPlace').value,start_date:$('taskDate').value,
   weeks:Number($('taskWeeks').value),medium:$('taskMedium').value,
   coverage_only:$('taskStrict').checked});
  const failures=report.tests.filter(x=>!x.passed).map(x=>x.industry+'/'+x.budget_wan+'万');
  $('benchmarkInfo').textContent='Agent 回归：'+report.passed+'/'+report.total+' 场景通过'+
   (failures.length?'；未通过：'+failures.join('、'):'；全部通过（仍需真实档期核验）');
  toast('场景回归完成');
 }catch(err){$('benchmarkInfo').textContent='回归异常：'+err.message;toast(err.message)}
};
$('approveDemo').onclick=()=>decideDemo('approve');$('rejectDemo').onclick=()=>decideDemo('reject');
$('modelToolCall').onclick=async()=>{
 if(!state.lastRun?.run_id){toast('请先完成一条媒体任务');return}
 const providerInfo=await api('/status').catch(()=>null);
 if(!providerInfo?.tool_model_configured){toast('受限模型尚未配置密钥与模型 ID');return}
 const providerLabel=providerInfo.tool_model_provider==='tokendance'?'TokenDance':'B1X';
 if(!confirm('将行业、预算范围、覆盖/库存数量等汇总信息发送给 '+providerLabel+' 模型。不会发送媒体明细、原始 CSV、客户 Brief、地标名称和登录信息。确定授权本次调用吗？'))return;
 const b=$('modelToolCall');b.disabled=true;$('toolCallInfo').textContent='模型工具调用中（限制 4 轮、只读工具）…';
 try{const x=await api('/runs/'+state.lastRun.run_id+'/model-tools','POST',{external_consent:true,max_steps:4});
  const calls=x.executed_tools||[];
  $('toolCallInfo').textContent=`${x.provider} 模型 ${x.model} · 实际返回 ${calls.length} 次只读工具调用：${calls.map(c=>c.tool).join(' → ')||'未选择工具'}。选择参考方案：${x.selected_scenario?.budget_wan||'未选择'} 万；${x.summary||'模型未生成额外解释'}。正式报价与 2027 库存仍需核验。`;
  toast('受限模型调用完成；请检查执行轨迹');
 }catch(e){$('toolCallInfo').textContent='模型任务没有成功：'+e.message+'。已保留确定性原始提案；到自我迭代实验室查看诊断。';toast(e.message)}
 finally{b.disabled=false}
};
$('bridgeCheck').onclick=async()=>{
 const a=Number($('bridgeInventory').value),b=Number($('bridgeCoverage').value);
 if(!a||!b){toast('请先分别导入库存与覆盖文件');return}
 $('bridgeResult').textContent='正在严格匹配并核对数据出处…';
 try{const v=await api('/data/bridge/reconcile','POST', {inventory_dataset_id:a,coverage_dataset_id:b,landmark:$('bridgeLandmark').value});
  const x=v.summary; $('bridgeResult').textContent=`授权关联完成：${x.coverage_rows} 行覆盖记录、${x.inventory_rows} 行库存快照；匹配库存 ${x.matched_inventory_rows} 条，当前商圈 ${x.filtered_matched_items} 条（公交 ${x.bus_matched} / 地铁 ${x.metro_matched}）；不唯一 ${x.ambiguous_coverage_rows} 行。2027 可售：未确认；状态：未锁位。`;toast('数据桥关联成功');
 }catch(e){$('bridgeResult').textContent='关联未成功：'+e.message;toast(e.message)}
};
async function loadFailureCases(){
 try{const r=await api('/failures');const e=$('failureCases');e.innerHTML=r.items.map(x=>`<article class="improvement-card"><div class="asset-meta"><span>故障 #${x.id} · ${E(x.code)}</span><span class="pill">${E(x.status)}</span></div><p>${E(x.reason)}</p><p class="micro">${E(x.proposal.next_step||'')}</p><p class="micro">${E(x.evaluation.reason||'')}</p><div class="form-actions">${['proposed','rejected','evaluated'].includes(x.status)&&x.proposal.tool?`<button class="secondary" data-failure-eval="${x.id}">相同数据对照测试</button>`:''}${x.status==='evaluated'&&x.evaluation.passed?`<button class="primary" data-failure-publish="${x.id}">审批发布 Skill</button>`:''}${x.status==='published'?`<button class="secondary" data-failure-rollback="${x.id}">回滚工具权限</button>`:''}</div></article>`).join('')||'<p class="micro">目前没有故障；模型调用失败或缺少覆盖工具时会自动记录诊断。</p>'}
 catch(e){$('failureCases').textContent='读取故障记录失败：'+e.message}
}
document.addEventListener('click',async e=>{const b=e.target.closest('[data-failure-eval],[data-failure-publish],[data-failure-rollback]');if(!b)return;
 const action=b.dataset.failureEval?'evaluate':b.dataset.failurePublish?'publish':'rollback'; const id=b.dataset.failureEval||b.dataset.failurePublish||b.dataset.failureRollback;
 if(action!=='evaluate'&&!confirm('这会更新您拥有的 Skill 授权工具。该更新可回滚，确认？'))return;
 try{const r=await api('/failures/'+id+'/'+action,'POST',{}); toast(action==='evaluate'?(r.passed?'实验证明净改进':'实验未通过，禁止发布'):action==='publish'?'Skill 工具已审批发布':'已回滚');loadFailureCases();if(action!=='evaluate')refreshAssets()}
 catch(err){toast(err.message)}
});
$('aiExplain').onclick=async()=>{if(!state.lastRun)return; if(!confirm('这会将品牌、预算和媒体数量等汇总信息发送到 B1X 模型；不会发送完整库存文件。是否继续？'))return;
 try{$('aiExplain').disabled=true;const r=await api('/runs/'+state.lastRun.run_id+'/ai-explain','POST',{});$('modelInsight').classList.remove('hidden');$('modelInsight').textContent='✦ '+r.model+'：'+r.content;toast('AI 解读已完成');}catch(e){toast(e.message)}finally{$('aiExplain').disabled=false}};
$('logout').onclick=async()=>{try{await api('/auth/logout','POST')}catch(e){}location.reload()};document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>show(b.dataset.page));document.querySelectorAll('.budget').forEach(b=>b.onclick=()=>setBudget(b.dataset.budget));$('parseBriefBtn').onclick=()=>parseNaturalBrief().then(()=>toast('已识别文字需求，仍可手动调整')).catch(e=>toast(e.message));$('runBtn').onclick=runTask;$('saveAgent').onclick=()=>saveAsset('agent');$('saveSkill').onclick=()=>saveAsset('skill');$('resetAgent').onclick=resetAgent;$('resetSkill').onclick=resetSkill;$('uploadDataset').onclick=uploadDataset;$('saveSource').onclick=createSource;$('copyResult').onclick=copyResult;$('openHistory').onclick=()=>show('audit');$('openIteration').onclick=()=>show('iteration');$('pollFolder').onclick=async()=>{try{const r=await api('/sources/poll-folder','POST',{});toast('已扫描'+r.items.length+'个候选文件');refreshData()}catch(e){toast(e.message)}};$('createUser').onclick=createUser;
document.addEventListener('click',async e=>{const b=e.target.closest('[data-edit-agent],[data-edit-skill],[data-open-run],[data-sync-source]');if(!b)return;if(b.dataset.editAgent){editAsset('agent',Number(b.dataset.editAgent))}else if(b.dataset.editSkill){editAsset('skill',Number(b.dataset.editSkill))}else if(b.dataset.openRun){try{const r=await api('/runs/'+b.dataset.openRun);state.lastRun={...r.result,run_id:r.id};show('studio');runHtml(state.lastRun)}catch(err){toast(err.message)}}else if(b.dataset.syncSource){try{await api('/sources/'+b.dataset.syncSource+'/sync','POST',{});toast('同步完成');refreshData()}catch(err){toast(err.message)}}});

async function refreshImprovements(){
 try{
   const [a,b]=await Promise.all([api('/improvements'),api('/feedback')]);
   $('statFeedback').textContent=b.items.length;$('statImprovements').textContent=a.items.length;
   $('statPublished').textContent=a.items.filter(i=>i.status==='published').length;
   $('statRollbacks').textContent=a.items.filter(i=>i.status==='rolled_back').length;
   $('improvementsCount').textContent=a.items.length+' 条';
   const statusMap={proposed:'待实验',evaluated:'测试通过，待批准',rejected:'实验未通过',published:'已发布',rolled_back:'已回滚'};
   $('improvementsList').innerHTML=a.items.map(p=>{
     const ev=p.eval||{},hasEval=ev.before&&ev.after;
     return `<article class="improvement-card"><div class="asset-meta"><span>建议 #${p.id} · Run #${p.run_id}</span><span class="pill">${E(statusMap[p.status]||p.status)}</span></div><h3>覆盖证据质量门禁</h3><p>${E(p.reason)}</p>${hasEval?`<div class="compare"><span>改进前<br><b>${ev.before.unsupported_selected}</b> 项缺证据<br>${ev.before.selected} 项候选</span><span>→</span><span>改进后<br><b>${ev.after.unsupported_selected}</b> 项缺证据<br>${ev.after.selected} 项候选</span></div><p class="micro">${E(ev.explanation||'')}</p>`:''}<div class="form-actions">${['proposed','evaluated','rejected'].includes(p.status)?`<button class="secondary" data-improvement-eval="${p.id}">运行对照测试</button>`:''}${p.status==='evaluated'&&ev.passed?`<button class="primary" data-improvement-publish="${p.id}">批准发布</button>`:''}${p.status==='published'?`<button class="secondary" data-improvement-rollback="${p.id}">回滚版本</button>`:''}</div></article>`
   }).join('')||'<p class="micro">暂无建议。运行一个任务后取消「仅推荐有覆盖证据」，检查是否生成改善候选，或提交手工反馈。</p>';
 }catch(e){toast(e.message)}
}
async function submitFeedback(){try{const runId=state.lastRun?.run_id;if(!runId)throw new Error('请先运行一条业务任务');const r=await api('/feedback','POST',{run_id:runId,score:Number($('feedbackScore').value),category:$('feedbackCategory').value,comment:$('feedbackComment').value});$('feedbackStatus').textContent=r.next_step;await refreshImprovements();toast('反馈已记录')}catch(e){toast(e.message)}}
$('submitFeedback').onclick=submitFeedback;
$('bootstrapAgent').onclick=async()=>{try{const problem=$('bootstrapProblem').value.trim();if(problem.length<10)throw new Error('请描述至少10个字的具体问题');const r=await api('/agents/from-problem','POST',{problem});$('bootstrapMessage').textContent='已创建 Agent #'+r.agent_id+'，Skill #'+r.skill_id+'（个人私有）';await refreshAssets();$('taskAgent').value=String(r.agent_id);$('taskBrief').value=problem;toast('专属 Agent 与 Skill 已建立，可直接前往任务工作台运行')}catch(e){$('bootstrapMessage').textContent=e.message;toast(e.message)}};
document.addEventListener('click',async ev=>{const b=ev.target.closest('[data-improvement-eval],[data-improvement-publish],[data-improvement-rollback]');if(!b)return;
 try{let id,action;if(b.dataset.improvementEval){id=b.dataset.improvementEval;action='evaluate'}else if(b.dataset.improvementPublish){id=b.dataset.improvementPublish;action='publish'}else{id=b.dataset.improvementRollback;action='rollback'}
 if(action==='publish'&&!confirm('对照实验已通过。确认将这条白名单覆盖策略发布到对应 Skill 吗？'))return;
 if(action==='rollback'&&!confirm('确定回滚到发布前的策略吗？'))return;
 b.disabled=true;const r=await api('/improvements/'+id+'/'+action,'POST',{});toast(action==='evaluate'?(r.passed?'对照实验通过':'实验未通过，不可发布'):action==='publish'?'策略已发布':'已回滚');await refreshImprovements();
 }catch(e){toast(e.message)}finally{b.disabled=false}
});
bootstrap();


// Competition customer-facing workflow: reuses the audited enterprise Agent Run.
function clientImpactInputs(){
 const read=id=>$(id).value.trim();
 const baseline=read('clientManualBaseline'),review=read('clientReviewMinutes'),rework=read('clientReworkMinutes');
 if(!baseline||!review||!rework)throw new Error('填写人工基线、AI 人工复核和返工耗时；没有返工请填 0');
 const nums=[baseline,review,rework].map(Number);
 if(nums.some(x=>!Number.isFinite(x)||x<0||x>1440)||nums[0]<=0)throw new Error('工时必须为 0–1440 分钟；人工基线须大于零');
 const m=read('clientManualErrors'),a=read('clientAiErrors');
 if(Boolean(m)!==Boolean(a))throw new Error('错误数需要两边都填，或都不填');
 if([m,a].some(x=>x&&!/^(0|[1-9][0-9]*)$/.test(x)))throw new Error('错误数须为 0–100 的整数');
 if([m,a].some(x=>x&&Number(x)>100))throw new Error('错误数不能超过 100');
 return {
   manual_minutes:nums[0],generation_minutes:state.lastClientDurationMs/60000,
   review_minutes:nums[1],rework_minutes:nums[2],
   manual_errors:m===''?null:Number(m),assistant_errors:a===''?null:Number(a),
   comparable_scope:$('clientComparable').checked,
   evidence_attested:$('clientEvidenceAttested').checked
 };
}
function renderEfficiency(){
 const duration=state.lastClientDurationMs;
 if(duration===undefined)return;
 $('clientLatency').textContent='本次客户提案从提交到返回：'+(duration/1000).toFixed(2)+' 秒（含网络，不含复核/返工）';
 try{
   const x=clientImpactInputs(), total=x.generation_minutes+x.review_minutes+x.rework_minutes;
   const delta=x.manual_minutes-total;
   $('clientEfficiency').textContent='本案例自报对照：AI+人工总计 '+total.toFixed(2)+' 分钟（生成+复核+返工），'+(delta>=0?'较人工少 ':'较人工多 ')+Math.abs(delta).toFixed(2)+' 分钟。'+
    (x.comparable_scope&&x.evidence_attested?'已勾选同范围与自报证据；仍需企业独立审核。':'范围/证据未核对，不可比较，更不能声称 ROI。');
 }catch(e){$('clientEfficiency').textContent=e.message+'。未完成数据不能推断真实节省。'}
}
async function saveClientImpact(){
 const rid=state.lastRun?.run_id;
 if(!rid||state.lastClientDurationMs===undefined){toast('先在本页面生成一份客户提案');return}
 const button=$('clientImpactSave');
 try{
   const data=clientImpactInputs();
   button.disabled=true;
   const result=await api('/runs/'+rid+'/impact-measurement','POST',data);
   const report=result.report;
   $('clientImpactSaved').textContent='Run #'+rid+' 已记录自报数据 · '+report.status+' · 时间差 '+report.delta_minutes+' 分钟 · 错误差 '+(report.error_delta??'未提供')+'；不构成企业总体 ROI 证明。';
   toast('已保存单案例自报数据，审计可追踪');
 }catch(e){toast(e.message)}finally{button.disabled=false}
}
async function generateClientProposal(){
 const b=$('clientGenerate');b.disabled=true;b.textContent='正在分析授权数据和预算约束…';
 $('clientRunState').textContent='执行中';
 try{
  const payload={agent_id:Number($('clientAgent').value),
   brief:$('clientBrief').value.trim(),brand:$('clientBrand').value.trim(),
   industry:$('clientIndustry').value,budget_wan:Number($('clientBudget').value),
   start_date:$('clientDate').value,weeks:Number($('clientWeeks').value),
   landmark:$('clientPlace').value,medium:$('clientMedium').value,
   coverage_only:$('clientCoverage').checked,
   inventory_dataset_id:Number($('clientInventorySource').value)||null,
   coverage_dataset_id:Number($('clientCoverageSource').value)||null,
   pricing_dataset_id:Number($('clientPricingSource').value)||null,
   business_goal:$('clientBusinessGoal').value.trim(),
   campaign_goal:$('clientCampaignGoal').value,
   target_audience:$('clientAudience').value.trim(),
   success_kpi:$('clientKpi').value.trim(),
   measurement_method:$('clientMeasurement').value.trim()};
  if(!payload.agent_id)throw new Error('请先选择有权使用的 Agent');
  if(!payload.brand)throw new Error('请填写目标品牌');
  if(!payload.brief)throw new Error('请填写客户 Brief');
  if(!payload.start_date.startsWith('2027-'))throw new Error('投放档期必须为2027年');
   for(const [field,label] of [['business_goal','客户生意目标'],['target_audience','目标人群'],['success_kpi','成功衡量 KPI'],['measurement_method','KPI 核验方式']]){
     if(!payload[field])throw new Error('Campaign 假设书缺少：'+label);
   }
  const submittedAt=performance.now();
  const r=await api('/runs','POST',payload);
  state.lastClientDurationMs=Math.max(0,performance.now()-submittedAt);
  state.lastRun=r;
  $('clientImpactSaved').textContent='新 Run #'+r.run_id+' 尚未保存效率证据；需要重新核对该案例。';
  runHtml(r); // Same verified result is also visible in original task studio.
  renderClientProposal(r);
  renderEfficiency();
  refreshStatus();
  await Promise.all([loadClientPreReview(r.run_id),loadClientWorkshopReadiness(r.run_id)]);
  toast('客户方案已生成：可查看质量、数据来源及待审核门禁');
 }catch(err){$('clientRunState').textContent='执行未成功';toast(err.message)}
 finally{b.disabled=false;b.innerHTML='✦ 开始分析客户需求，给出最优候选 <span>→</span>'}
}
function renderClientProposal(r){
 const p=r.plan||{},q=r.quality_report||{},rows=p.selected||[];
 $('clientEmpty').classList.add('hidden');$('clientProposal').classList.remove('hidden');
 $('clientRunState').textContent='Run #'+r.run_id+' · '+(q.status||'需复核');
 $('clientTitle').textContent=(p.brand||'客户')+' · '+(p.focus_landmark||'上海')+'媒体投放提案';
 $('clientIntro').textContent=r.rationale||'基于当前授权数据和规则给出参考候选';
 const hypo=r.campaign_hypothesis||{};
 $('clientHypothesisStatus').textContent='赛题七要素 '+(hypo.completed??0)+' / '+(hypo.required??7)+'；'+(hypo.complete?'已填写，仍需客户确认':'缺失要素必须补齐');
 $('clientHypothesisRows').innerHTML=(hypo.elements||[]).map(e=>'<p>'+ (e.complete?'✓ ':'⚑ ')+'<b>'+E(e.label)+'</b>：'+E(e.value)+'</p>').join('');
 $('clientScenarioRows').innerHTML=(r.scenario_changes||[]).map(e=>'<p><b>'+E(e.budget_wan)+' 万</b> → 参考 '+E(e.spent_wan)+' 万；'+E(e.item_count)+' 项 / '+E(e.unit_count)+' 单元；'+(e.added_vs_prior_units===null?'基准方案':'较前一档新增 '+E(e.added_vs_prior_units)+' 单元，减少 '+E(e.removed_vs_prior_units)+' 单元')+'</p>').join('');
 $('clientSpent').textContent=(p.spent_wan??0)+' 万 / '+p.budget_wan+' 万';
 $('clientCount').textContent=rows.length+' 项';
 $('clientEvidence').textContent=(q.evidence?.coverage_pct??0)+'%';
 $('clientRows').innerHTML=rows.slice(0,30).map(x=>`<tr><td>${E(x.media_name||x.id)}</td><td>${E(x.quantity)}</td><td>${E(x.line_total_wan)}</td><td>${E((x.coverage_landmarks||[]).join('、')||'待核验')}</td></tr>`).join('')||'<tr><td colspan="4">没有符合条件的媒体；请检查数据或筛选条件</td></tr>';
 const warns=[...(q.blockers||[]),...(q.warnings||[])].map(x=>x.message);
 $('clientWarnings').innerHTML=warns.map(x=>`<p>⚑ ${E(x)}</p>`).join('')||'<p>质量规则未发现问题；仍需人工确认商业条件。</p>';
 $('clientDbProof').textContent='本次建议来自企业授权数据集：'+Object.entries(r.data_sources||{}).map(([name,source])=>name+'：'+source).join('；')+'。预算规则选出约束内组合，并不证明真实档期可售或投放效果最优。';
 $('clientModelOutput').classList.add('hidden');
}
async function analyzeClientChange(){
 const run=state.lastRun?.run_id;if(!run){toast('先生成一份方案才能分析变更影响');return}
 const b=$('changeAnalyze');b.disabled=true;
 try{
  const x=await api('/runs/'+run+'/change-impact','POST',{
   change_type:$('changeType').value,effective_date:$('changeDate').value,note:$('changeNote').value.trim()});
  $('changeResult').classList.remove('hidden');
  $('changeTitle').textContent='变更来源：'+x.change_label+' · '+x.effective_date;
  $('changeAffected').textContent='需重算或复核：'+x.affected_forms.join('、');
  $('changeSteps').innerHTML=x.dependency_steps.map(t=>`<div class="change-step"><span class="change-index">${t.order}</span><div><b>${E(t.title)}</b><p>${E(t.detail)}</p><small>责任岗位：${E(t.owner)} · 待人工确认</small></div></div>`).join('');
  $('changeWarnings').innerHTML=x.evidence_gaps.map(w=>`<p>⚑ ${E(w)}</p>`).join('');
  $('changeNotice').textContent=x.customer_notice_draft+'\n'+x.limitations;
  toast('影响分析已生成，未更改任何真实业务系统');
 }catch(e){toast(e.message)}finally{b.disabled=false}
}
// Customer-facing evidence review, grounded in the same authenticated frozen Run.
// Workshop data selection: same authenticated snapshot that the Agent will read.
// Only safe metadata comes back; no token, URL, inventory rows or client details.
async function loadClientDatasetChoices(){
 const mapping=[['inventory','clientInventorySource'],['coverage','clientCoverageSource'],['pricing','clientPricingSource']];
 try{
   const x=await api('/workshop/data-readiness');
   const data=x.available_snapshots||[];
   for(const [kind,id] of mapping){
     const select=$(id),prev=select.value;
     const choices=data.filter(d=>d.kind===kind);
     const leading=kind==='inventory'?'': '<option value="">不选择（标记相应证据待核验）</option>';
     select.innerHTML=leading+choices.map(d=>
       '<option value="'+d.dataset_id+'">#'+d.dataset_id+' · '+E(d.class)+
       ' · '+d.record_count+' 条 · '+E(d.checksum_short||'无指纹')+'</option>').join('');
     if(prev&&choices.some(d=>String(d.dataset_id)===prev))select.value=prev;
     select.disabled=!choices.length;
   }
   $('clientSourceState').textContent='仅显示当前账号有权限的数据集。红豆公交/地铁：需企业审批后私有只读联调；可视化：暂无 API，仅经授权离线导出。'+
     (data.some(d=>d.class==='synthetic_demo')?' 当前有虚构合成数据，不能用于正式报价。':'');
 }catch(e){$('clientSourceState').textContent='数据快照查询失败：'+e.message+'。不可假设真实库存已连接。'}
}
async function loadClientWorkshopReadiness(runId){
 const status=$('clientWorkshopStatus'),container=$('clientWorkshopChecks');
 status.textContent='正在读取方案快照并检查 workshop 规则…';container.textContent='';
 try{
   const x=await api('/runs/'+runId+'/workshop-readiness');
   status.textContent='内部证据检查 '+x.passed_checks+'/'+x.total_checks+
     ' · '+(x.status==='blocked'?'存在阻断':'仍需人工复核')+
     ' · 正式标准原文未提供；本报告不是官方打分。';
   container.innerHTML=x.checks.map(c=>
     '<div class="review-card"><b>'+({evidence_present:'✓ 已有证据',needs_review:'⚑ 待核验',blocked:'✕ 阻断'}[c.status]||'待核验')+
     ' · '+E(c.label)+'</b><p>'+E(c.explanation)+'</p></div>').join('');
 }catch(e){status.textContent='证据审查未完成：'+e.message}
}
async function loadClientPreReview(runId){
 const risks=$('clientReviewRisks'),questions=$('clientReviewQuestions'),actions=$('clientReviewActions');
 risks.textContent='正在检查数据缺口…';questions.textContent='正在生成业务追问…';actions.textContent='正在组织人工待办…';
 try{
   const d=await api('/runs/'+runId+'/decision-brief');
   risks.innerHTML=d.risks.map((x,i)=>'<div class="review-card"><b>风险 '+(i+1)+' · '+E(x.title)+'</b><p>证据：'+E(x.evidence)+'</p><small>修复建议：'+E(x.fix)+'</small></div>').join('');
   questions.innerHTML=d.questions.map((x,i)=>'<div class="review-card"><b>Q'+(i+1)+'</b><span> '+E(x)+'</span></div>').join('');
   actions.innerHTML=d.next_actions.map(x=>'<div class="review-card"><b>'+E(x.priority)+' · '+E(x.title)+'</b><p>'+E(x.why)+'</p></div>').join('');
 }catch(e){risks.textContent='预审未完成：'+e.message;questions.textContent='请检查执行记录';actions.textContent='请人工核验目标和数据来源'}
}
async function refreshDemandInsights(){
 try{
  const [x,d]=await Promise.all([api('/insights'),api('/insights/drafts')]);
  $('insightTotal').textContent=x.sample_size;
  const biggest=entries=>Object.entries(entries||{}).sort((a,b)=>b[1]-a[1])[0];
  $('insightGoal').textContent=biggest(x.goal_counts)?.[0]||'待采样';
  $('insightRisk').textContent=biggest(x.risk_counts)?.[0]||'未发现';
  const line=(name,values)=>'<div class="review-card"><b>'+name+'</b><p>'+Object.entries(values||{}).map(([k,v])=>E(k)+'：'+v).join(' · ')+'</p></div>';
  $('insightSummary').innerHTML=line('Campaign 目标',x.goal_counts)+line('预算分布',x.budget_counts)+line('媒介偏好',x.medium_counts)+line('质量缺口（只含编码）',x.risk_counts);
  $('insightRecent').innerHTML=(x.recent||[]).map(r=>'<article class="asset"><h3>Run #'+r.run_id+' · '+E(r.campaign_goal)+'</h3><p>'+E(r.budget_band)+' · '+E(r.medium)+' · '+E(r.quality_status)+' · '+E(r.created_at)+'</p></article>').join('')||'<p class="micro">没有历史需求；先去客户界面运行方案。</p>';
  $('insightRecommendation').textContent=x.sample_size+' 条结构化需求中，建议优先：'+x.suggested_skill+'。样本来自 '+x.scope+'；不证明商业效果或模型自动学习。';
  $('insightCreateDraft').disabled=x.sample_size<1;
  $('insightDrafts').innerHTML=(d.items||[]).map(r=>'<article class="asset"><h3>候选 #'+r.id+' · '+E(r.kind)+'</h3><p>'+E(r.status)+' · 样本 '+r.sample_size+' · '+E(r.created_at)+'</p></article>').join('')||'<p class="micro">尚无 Skill 候选。</p>';
 }catch(e){$('insightRecommendation').textContent='需求分析失败：'+e.message}
}
$('insightCreateDraft').onclick=async()=>{
 const b=$('insightCreateDraft');b.disabled=true;
 try{
  const r=await api('/insights/drafts','POST',{});
  state.currentDemandDraft=r.draft_id;
  $('insightDraftPreview').innerHTML='<div class="review-card"><b>'+E(r.template.title)+'</b><p>'+E(r.template.description)+'</p><small>待人工审批：'+r.template.tools.map(E).join('、')+'；样本 '+r.sample_size+'。不会自动扩权或发布。</small></div>';
  $('insightApproveDraft').classList.remove('hidden');
  await refreshDemandInsights();
  toast('候选已生成，尚未授予工具权限');
 }catch(e){toast(e.message)}finally{b.disabled=false}
};
$('insightApproveDraft').onclick=async()=>{
 const id=state.currentDemandDraft;if(!id){toast('请先生成候选');return}
 if(!confirm('明确批准：根据所示白名单创建仅自己可见的 Agent 与 Skill。不会自动部署、锁位或对外发送信息。继续？'))return;
 const b=$('insightApproveDraft');b.disabled=true;
 try{
  const r=await api('/insights/drafts/'+id+'/adopt','POST',{});
  state.currentDemandDraft=null;
  b.classList.add('hidden');
  $('insightDraftPreview').textContent='已创建私有 Agent #'+r.agent_id+' 与 Skill #'+r.skill_id+'。请在后台审查工具、权限及业务规则后再执行。';
  await Promise.all([refreshAssets(),refreshDemandInsights(),refreshStatus()]);
  toast('Agent/Skill 已创建（默认私有）');
 }catch(e){toast(e.message);b.disabled=false}
};
$('clientGenerate').onclick=generateClientProposal;
$('clientManualBaseline').oninput=renderEfficiency;
$('clientReviewMinutes').oninput=renderEfficiency;
$('clientReworkMinutes').oninput=renderEfficiency;
$('clientManualErrors').oninput=renderEfficiency;
$('clientAiErrors').oninput=renderEfficiency;
$('clientComparable').onchange=renderEfficiency;
$('clientEvidenceAttested').onchange=renderEfficiency;
$('clientImpactSave').onclick=saveClientImpact;
$('changeAnalyze').onclick=analyzeClientChange;
$('clientExport').onclick=()=>{
 if(!state.lastRun?.run_id){toast('请先生成方案');return}
 window.location.href='/enterprise/api/runs/'+state.lastRun.run_id+'/proposal.html';
};
$('clientGoStudio').onclick=()=>show('studio');
$('clientModel').onclick=async()=>{
 if(!state.lastRun?.run_id){toast('请先生成一份方案');return}
 const providerInfo=await api('/status').catch(()=>null);
 if(!providerInfo?.tool_model_configured){toast('模型密钥或模型 ID 尚未配置');return}
 const providerLabel=providerInfo.tool_model_provider==='tokendance'?'TokenDance':'B1X';
 if(!confirm('仅将行业、预算与媒体汇总数量发送给 '+providerLabel+'；不传客户 Brief、媒体明细或原始库存。授权本次真实模型调用？'))return;
 const b=$('clientModel');b.disabled=true;
 try{
  const x=await api('/runs/'+state.lastRun.run_id+'/model-tools','POST',{external_consent:true,max_steps:4});
  $('clientModelOutput').classList.remove('hidden');
  $('clientModelOutput').textContent=x.provider+' '+x.model+' · '+x.executed_tools.length+' 次受限工具调用\n'+(x.summary||'模型没有附加解释')+'\n'+(x.selected_scenario?'选中参考预算：'+x.selected_scenario.budget_wan+'万元':'未选择参考预算')+'\n未确认2027档期或商业锁位';
 }catch(e){toast(e.message)}finally{b.disabled=false}
};
