/* Public stateless judge preview: actual backend computes on fixed fictional CSV. */
const $=id=>document.getElementById(id);
const state={budget:200};
document.querySelectorAll('#budgetOptions button').forEach(b=>b.addEventListener('click',()=>{
  state.budget=Number(b.dataset.budget);
  document.querySelectorAll('#budgetOptions button').forEach(x=>x.classList.toggle('active',x===b));
}));
const e=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function generate(){
  const b=$('generate');b.disabled=true;
  $('status').textContent='运行中';
  $('loading').hidden=false;$('loading').textContent='正在调用安全的合成数据优化 API…';
  $('result').hidden=true;
  try{
    const p=new URLSearchParams({budget_wan:String(state.budget),medium:$('medium').value});
    const res=await fetch('/judge/api/plan?'+p.toString(),{method:'GET',credentials:'omit',cache:'no-store'});
    const data=await res.json();
    if(!res.ok)throw new Error(data.detail||'HTTP '+res.status);
    if(data.synthetic_only!==true||data.real_hongdou_connected!==false)throw new Error('演示安全状态异常，拒绝展示');
    $('planTitle').textContent=($('brand').value.trim().slice(0,40)||'模拟饮料品牌')+' · '+$('goal').value+'目标参考方案';
    $('outBudget').textContent=data.budget_wan+' 万';
    $('outSpent').textContent=data.spent_wan+' 万';
    $('outCount').textContent=data.item_count+' 项 / '+data.unit_count+' 单元';
    $('source').textContent='数据来源：'+data.source_file+'（'+data.sample_size+' 条虚构记录） · 同一确定性优化器 · 未接入红豆或覆盖 API';
    $('mediaRows').innerHTML=(data.selected||[]).map(x=>'<tr><td>'+e(x.media_name)+'</td><td>'+e(x.district)+'</td><td>'+x.quantity+'</td><td>'+x.line_total_wan+'</td></tr>').join('')||'<tr><td colspan="4">该约束下无候选，请切换媒体类型或预算。</td></tr>';
    $('risks').innerHTML=(data.risk_questions||[]).map((x,i)=>'<p><b>风险 '+(i+1)+'：</b>'+e(x)+'</p>').join('');
    $('actions').innerHTML=(data.actions||[]).map((x,i)=>'<p><b>P'+i+'：</b>'+e(x)+'</p>').join('');
    $('status').textContent='合成方案已生成';
    $('loading').hidden=true;
    $('result').hidden=false;
  }catch(err){
    $('status').textContent='暂不可用';
    $('loading').textContent='未能生成演示：'+err.message+'。可以在 GitHub 查看运行方式，或联系团队获取现场演示。';
  }finally{b.disabled=false}
}
$('generate').addEventListener('click',generate);
