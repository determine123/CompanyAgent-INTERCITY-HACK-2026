"""Local Agent Hub: staff-owned Agents/Skills, provenance, scheduled allowed feeds, audit."""
from __future__ import annotations
import hashlib,json,os,re,secrets,time,threading
import httpx
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException,UploadFile,File
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel,Field
from .store import STATE,COOKIE,TOOLS,db,init,hashed,password_ok,actor,allowed,can_modify,audit,now,safe_json
from .dataflows import ingest,poll_folder,approved_url,pull_source
from .engine import perform, choose_params
from src.planning import INDUSTRIES
from .quality import assess_result
from .proposal import render_proposal
from .reliability import create_manifest, evaluation, replay, plan_fingerprint
from .bridge import reconcile
from .model_tools import run_model_tools, ModelError, MODEL as B1X_MODEL
from .provider_config import provider_name, provider_configured
from .deployment_policy import deployment_mode
from .failure_learning import record_failure
from .change_workflow import analyze_change, CHANGE_TYPES

router=APIRouter(prefix='/enterprise/api',tags=['Enterprise Agent Hub'])

class Login(BaseModel):
    username:str
    password:str
class Profile(BaseModel):
    password:str
    new_password:str
class NewUser(BaseModel):
    username:str
    display:str
    role:str='employee'
class Asset(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    description:str=Field(default='',max_length=600)
    instructions:str=Field(default='',max_length=4000)
    visibility:str='private'
    tools:list[str]=Field(default_factory=list)
    skill_ids:list[int]=Field(default_factory=list)
class NaturalBrief(BaseModel):
    text:str=Field(min_length=1,max_length=12000)
class ProblemDefinition(BaseModel):
    problem:str=Field(min_length=10,max_length=2000)
    name:str=Field(default='',max_length=80)


class Task(BaseModel):
    agent_id:int
    brief:str=Field(default='',max_length=12000)
    industry:str='食品饮料'
    brand:str=''
    budget_wan:float=200
    start_date:str='2027-05-01'
    weeks:int=4
    landmark:str='正大广场'
    medium:str='both'
    coverage_only:bool=True
    inventory_dataset_id:int|None=None
    coverage_dataset_id:int|None=None
class BenchmarkRequest(BaseModel):
    landmark:str='正大广场'
    start_date:str='2027-05-01'
    medium:str='both'
    weeks:int=4
    coverage_only:bool=False


class ProposalDecision(BaseModel):
    decision:str
    comment:str=Field(default="",max_length=500)

class ChangeRequest(BaseModel):
    change_type:str
    effective_date:str
    note:str=Field(min_length=4,max_length=1000)

class BridgeRequest(BaseModel):
    inventory_dataset_id:int
    coverage_dataset_id:int
    landmark:str=Field(default='',max_length=90)

class ToolCallingRequest(BaseModel):
    external_consent:bool=False
    max_steps:int=Field(default=4,ge=1,le=4)

class Source(BaseModel):
    name:str=Field(min_length=2,max_length=90)
    kind:str
    url:str
    token_env:str=''
    interval_minutes:int=60

FAILED={}

def req_actor(request): return actor(request)

def require_admin(who):
    if who['role']!='admin':raise HTTPException(403,'仅管理员可操作')

def view(rows,actor_user):
    result=[]
    for r in rows:
        if allowed(r,actor_user):
            value=dict(r)
            for k in ('skill_ids_json','tools_json'):
                if k in value: value[k[:-5]]=json.loads(value.pop(k))
            result.append(value)
    return result

@router.post('/auth/login')
def login(request:Request,data:Login):
    key=(request.client.host if request.client else 'local',data.username[:80])
    previous=FAILED.get(key,[])
    current=int(time.time())
    previous=[t for t in previous if current-t<600]
    if len(previous)>=7: raise HTTPException(429,'尝试次数过多，请十分钟后重试')
    with db() as c:
        u=c.execute('SELECT * FROM users WHERE username=?',(data.username.strip(),)).fetchone()
        if not u or not password_ok(data.password,u['password_hash']):
            FAILED[key]=previous+[current]
            raise HTTPException(401,'用户名或密码错误')
        token=secrets.token_urlsafe(48)
        csrf=secrets.token_urlsafe(24)
        c.execute('DELETE FROM sessions WHERE expires<?',(current,))
        c.execute('INSERT INTO sessions(token_hash,user_id,csrf,expires) VALUES(?,?,?,?)',
                  (hashlib.sha256(token.encode()).hexdigest(),u['id'],csrf,current+36000))
    FAILED.pop(key,None)
    if u['username']=='admin':
        # One-time bootstrap secret is no longer needed after the first successful login.
        (STATE/'FIRST_LOGIN.txt').unlink(missing_ok=True)
    audit(u['id'],'login','通过本地企业工作台登录')
    response=JSONResponse({'user':{'id':u['id'],'username':u['username'],'display':u['display'],'role':u['role']},'csrf':csrf})
    response.set_cookie(COOKIE,token,max_age=36000,httponly=True,samesite='strict',secure=os.getenv('COMPANYAGENT_COOKIE_SECURE')=='true',path='/enterprise')
    return response

@router.get('/me')
def me(request:Request):
    who=req_actor(request)
    return {'user':{k:who[k] for k in ('id','username','display','role')},'csrf':who['csrf'],
            'runtime':'deterministic-tool-orchestrated','production_ready':False}

@router.post('/auth/logout')
def logout(request:Request):
    who=req_actor(request)
    token=request.cookies.get(COOKIE,'')
    with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    audit(who['id'],'logout')
    r=JSONResponse({'ok':True});r.delete_cookie(COOKIE,path='/enterprise');return r

@router.post('/auth/password')
def change_password(request:Request,data:Profile):
    who=req_actor(request)
    if len(data.new_password)<12: raise HTTPException(400,'新密码至少12字符')
    with db() as c:
        u=c.execute('SELECT password_hash FROM users WHERE id=?',(who['id'],)).fetchone()
        if not password_ok(data.password,u['password_hash']):raise HTTPException(403,'旧密码错误')
        c.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed(data.new_password),who['id']))
    audit(who['id'],'password_change');return {'ok':True}

@router.get('/users')
def users(request:Request):
    who=req_actor(request)
    with db() as c:rs=c.execute('SELECT id,username,display,role,created_at FROM users ORDER BY id').fetchall()
    return {'items':[dict(x) for x in rs]}

@router.post('/users')
def create_user(request:Request,data:NewUser):
    who=req_actor(request);require_admin(who)
    if not re.fullmatch('[a-zA-Z][a-zA-Z0-9_.-]{2,35}',data.username):raise HTTPException(400,'用户名格式错误')
    if data.role not in ('employee','manager'):raise HTTPException(400,'不允许创建管理员')
    password=secrets.token_urlsafe(16)
    try:
        with db() as c:
            cur=c.execute('INSERT INTO users(username,display,role,password_hash,created_at) VALUES(?,?,?,?,?)',
                          (data.username,data.display[:80] or data.username,data.role,hashed(password),now()))
    except Exception as exc: raise HTTPException(409,'用户名可能已存在') from exc
    audit(who['id'],'user_create',data.username)
    return {'id':cur.lastrowid,'username':data.username,'initial_password':password,'note':'初始密码仅显示这一次，请安全转交员工并立即修改'}

@router.get('/skills')
def skills(request:Request):
    who=req_actor(request)
    with db() as c:rows=c.execute('SELECT * FROM skills ORDER BY id DESC').fetchall()
    return {'items':view(rows,who),'supported_tools':sorted(TOOLS)}

@router.post('/skills')
def skill_create(request:Request,data:Asset):
    who=req_actor(request)
    if data.visibility not in ('private','team'):raise HTTPException(400,'无效可见范围')
    if not data.tools or any(x not in TOOLS for x in data.tools):raise HTTPException(400,'只能选择平台允许的业务工具')
    with db() as c:
        cur=c.execute('INSERT INTO skills(owner_id,name,description,instructions,tools_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
              (who['id'],data.name,data.description,data.instructions,safe_json(sorted(set(data.tools))),data.visibility,now()))
    audit(who['id'],'skill_create',data.name)
    return {'id':cur.lastrowid,'ok':True}

@router.put('/skills/{item_id}')
def skill_update(item_id:int,request:Request,data:Asset):
    who=req_actor(request)
    if data.visibility not in ('private','team') or not data.tools or any(x not in TOOLS for x in data.tools):raise HTTPException(400,'工具或可见范围错误')
    with db() as c:
        r=c.execute('SELECT * FROM skills WHERE id=?',(item_id,)).fetchone()
        if not can_modify(r,who):raise HTTPException(403,'只能编辑自己的Skill')
        c.execute('UPDATE skills SET name=?,description=?,instructions=?,tools_json=?,visibility=? WHERE id=?',
                  (data.name,data.description,data.instructions,safe_json(sorted(set(data.tools))),data.visibility,item_id))
    audit(who['id'],'skill_update',item_id)
    return {'ok':True}

@router.get('/agents')
def agents(request:Request):
    who=req_actor(request)
    with db() as c:rows=c.execute('SELECT * FROM agents ORDER BY id DESC').fetchall()
    return {'items':view(rows,who)}

def validate_skill_ids(c,ids,who):
    if not ids:raise HTTPException(400,'请至少绑定一个Skill')
    for sid in set(ids):
        sk=c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone()
        if not allowed(sk,who):raise HTTPException(403,'Skill 不存在或无权访问')

@router.post('/agents')
def agent_create(request:Request,data:Asset):
    who=req_actor(request)
    if data.visibility not in ('private','team'):raise HTTPException(400,'无效可见范围')
    with db() as c:
        validate_skill_ids(c,data.skill_ids,who)
        cur=c.execute('INSERT INTO agents(owner_id,name,description,instructions,skill_ids_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
                (who['id'],data.name,data.description,data.instructions,safe_json(sorted(set(data.skill_ids))),data.visibility,now()))
    audit(who['id'],'agent_create',data.name)
    return {'id':cur.lastrowid,'ok':True}

@router.put('/agents/{item_id}')
def agent_update(item_id:int,request:Request,data:Asset):
    who=req_actor(request)
    if data.visibility not in ('private','team'):raise HTTPException(400,'无效可见范围')
    with db() as c:
        r=c.execute('SELECT * FROM agents WHERE id=?',(item_id,)).fetchone()
        if not can_modify(r,who):raise HTTPException(403,'只能编辑自己的Agent')
        validate_skill_ids(c,data.skill_ids,who)
        c.execute('UPDATE agents SET name=?,description=?,instructions=?,skill_ids_json=?,visibility=? WHERE id=?',
                  (data.name,data.description,data.instructions,safe_json(sorted(set(data.skill_ids))),data.visibility,item_id))
    audit(who['id'],'agent_update',item_id)
    return {'ok':True}

@router.post('/agents/from-problem')
def create_agent_from_problem(request:Request,data:ProblemDefinition):
    """Human-triggered Agent/Skill bootstrap from a business problem, NOT auto-generated executable code."""
    who=req_actor(request)
    content=data.problem.strip()
    domain_keywords=('广告','投放','媒体','媒介','商圈','公交','地铁','报价','预算','品牌','库存','提案')
    if not any(word in content for word in domain_keywords):
        raise HTTPException(422,'当前仅支持媒体投放提案领域，请使用已有工具或等待管理员注册新领域 Skill')
    title=data.name.strip() or ('媒体提案 Agent · '+content[:12])
    if len(title)<2:raise HTTPException(422,'Agent 名称过短')
    skill_title='媒体选点与预算优化 · '+title[:34]
    toolset=sorted(TOOLS)
    policy=('先使用授权数据查找媒体与库存，再按预算重新优化，输出可核验的推荐。'
            '任何覆盖结论必须有来源；历史库存不等于2027档期可售，区间刊例不是正式报价。'
            '不得调用未授权工具或对外发送比赛资料。')
    with db() as c:
        sid=c.execute('INSERT INTO skills(owner_id,name,description,instructions,tools_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
                      (who['id'],skill_title,'由业务问题生成的安全工具组合',policy,safe_json(toolset),'private',now())).lastrowid
        aid=c.execute('INSERT INTO agents(owner_id,name,description,instructions,skill_ids_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
                      (who['id'],title,content[:600],policy,safe_json([sid]),'private',now())).lastrowid
    audit(who['id'],'agent_bootstrap',f'agent={aid},skill={sid},行业=户外媒体提案')
    return {'ok':True,'agent_id':aid,'skill_id':sid,'name':title,'tools':toolset,
            'human_approval':'用户显式创建，仅使用预先审核的确定性工具；不生成或执行任意代码'}

@router.get('/datasets')
def list_datasets(request:Request):
    who=req_actor(request)
    with db() as c:
        rows=c.execute('SELECT id,owner_id,kind,name,origin,count,checksum,visibility,imported_at,notes FROM datasets ORDER BY id DESC').fetchall()
    return {'items':[dict(row) for row in rows if allowed(row,who)]}

@router.post('/datasets/upload')
async def data_upload(request:Request,kind:str='inventory',visibility:str='team',file:UploadFile=File(...)):
    who=req_actor(request)
    if not file.filename:raise HTTPException(400,'缺少文件名')
    raw=await file.read(10_000_001)
    try: result=ingest(kind,raw,file.filename,who['id'],'manual_authorized_export',visibility)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    audit(who['id'],'dataset_upload',f'{kind}:{file.filename}')
    return result

@router.get('/sources')
def list_sources(request:Request):
    who=req_actor(request)
    with db() as c: rows=c.execute('SELECT * FROM sources ORDER BY id DESC').fetchall()
    return {'items':[dict(x) for x in rows] if who['role']=='admin' else []}

@router.post('/sources')
def register_source(request:Request,data:Source):
    who=req_actor(request);require_admin(who)
    if data.kind not in ('inventory','coverage','pricing'):raise HTTPException(400,'数据源类型必须为库存、覆盖或刊例')
    if not 5<=data.interval_minutes<=1440:raise HTTPException(400,'同步间隔5至1440分钟')
    if data.token_env and not re.fullmatch(r'COMPANYAGENT_SOURCE_[A-Z0-9_]+_TOKEN',data.token_env):raise HTTPException(400,'服务端凭证环境变量名不符合要求')
    try:approved_url(data.url)
    except ValueError as e:raise HTTPException(400,str(e)) from e
    with db() as c:
        cur=c.execute('INSERT INTO sources(owner_id,name,kind,url,token_env,interval_minutes,active) VALUES(?,?,?,?,?,?,1)',
                  (who['id'],data.name,data.kind,data.url,data.token_env,data.interval_minutes))
    audit(who['id'],'source_create',data.name)
    return {'id':cur.lastrowid,'ok':True}

@router.post('/sources/{source_id}/sync')
def source_sync(source_id:int,request:Request):
    who=req_actor(request);require_admin(who)
    with db() as c:source=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone()
    if not source: raise HTTPException(404,'不存在该数据源')
    try: res=pull_source(source)
    except Exception as exc:
        with db() as c:c.execute('UPDATE sources SET last_sync=?,last_status=?,last_error=? WHERE id=?',(now(),'error',str(exc)[:200],source_id))
        audit(who['id'],'source_sync_failed',str(source_id))
        raise HTTPException(400,'同步失败：'+str(exc)[:180]) from exc
    with db() as c:c.execute('UPDATE sources SET last_sync=?,last_status=?,last_error=NULL WHERE id=?',(now(),'ok',source_id))
    audit(who['id'],'source_sync',str(source_id))
    return res

@router.post('/sources/poll-folder')
def folder_sync(request:Request):
    who=req_actor(request);require_admin(who)
    out=poll_folder(who['id'])
    audit(who['id'],'folder_sync',str(len(out)))
    return {'items':out,'folder':str(STATE/'imports')}

@router.post('/data/bridge/reconcile')
def reconcile_authorized_data(request:Request,data:BridgeRequest):
    """Read-only strict link between two specifically selected, authorized datasets."""
    who=req_actor(request)
    with db() as c:
        i=c.execute('SELECT * FROM datasets WHERE id=? AND kind=?',(data.inventory_dataset_id,'inventory')).fetchone()
        v=c.execute('SELECT * FROM datasets WHERE id=? AND kind=?',(data.coverage_dataset_id,'coverage')).fetchone()
    if not allowed(i,who) or not allowed(v,who):raise HTTPException(403,'数据源不存在或当前员工无权读取')
    report=reconcile(json.loads(i['records_json']),json.loads(v['records_json']),
        landmark=data.landmark,inventory_origin=i['origin'],coverage_origin=v['origin'],
        inventory_checksum=i['checksum'],coverage_checksum=v['checksum'])
    audit(who['id'],'authorized_data_reconcile',f'inventory={i["id"]};coverage={v["id"]};hits={report["summary"]["filtered_matched_items"]}')
    return report

@router.post('/runs/{run_id}/model-tools')
def bounded_tool_calling(request:Request,run_id:int,data:ToolCallingRequest):
    """Model chooses read-only, aggregate-only tools; business result is immutable."""
    who=req_actor(request)
    run=_run_for_view(run_id,who)
    if not data.external_consent:raise HTTPException(412,'必须明确同意仅将聚合数据发送给当前选定的外部模型服务商')
    result=json.loads(run['result_json'])
    # Tool grants come from the frozen run manifest, not from user-controlled input.
    manifest=result.get('replay_manifest') or {}
    if not manifest.get('skills'):raise HTTPException(409,'任务缺少冻结 Skill 权限快照')
    if plan_fingerprint(result)!=manifest.get('plan_fingerprint'):
        raise HTTPException(409,'原执行结果快照已经改变，拒绝基于不可信结果调用外部模型')
    skill_tools=set()
    for sk in manifest['skills']:
        skill_tools.update(json.loads(sk['tools_json']))
    grants=set()
    if 'match_coverage' in skill_tools:grants.add('inspect_coverage')
    if 'load_inventory' in skill_tools:grants.add('inspect_inventory')
    if 'optimize_budget' in skill_tools:grants.add('select_budget_scenario')
    try:
        answer=run_model_tools(result,grants,max_steps=data.max_steps)
    except ModelError as exc:
        reason=str(exc)
        # No secret or raw request is copied into failure metadata.
        code='MODEL_NOT_CONFIGURED' if any(key in reason for key in ('B1X_API_KEY','TOKENDANCE_API_KEY','TOKENDANCE_MODEL')) else 'MODEL_TOOL_REJECTED'
        sid=next((x['id'] for x in manifest['skills'] if x['id']),None)
        fid=record_failure(who['id'],run['agent_id'],run_id,sid,code,reason)
        audit(who['id'],'model_tool_failed',f'run={run_id};code={code};failure={fid}')
        raise HTTPException(503 if code=='MODEL_NOT_CONFIGURED' else 502,reason) from exc
    with db() as c:
        cid=c.execute('INSERT INTO model_tool_runs(owner_id,run_id,trace_json,created_at) VALUES(?,?,?,?)',
                      (who['id'],run_id,safe_json(answer),now())).lastrowid
    audit(who['id'],'model_tool_success',f'run={run_id};call={cid};tools={len(answer["executed_tools"])}')
    return {'model_call_id':cid,'run_id':run_id,**answer}

@router.post('/runs/{run_id}/change-impact')
def impact_of_change(run_id:int, request:Request, data:ChangeRequest):
    """Generate an accountable change-worklist without altering a real schedule."""
    who=req_actor(request)
    run=_run_for_view(run_id,who)
    result=json.loads(run['result_json'])
    try:
        report=analyze_change(result,kind=data.change_type,
                              effective_date=data.effective_date,note=data.note)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc
    audit(who['id'],'change_impact',f'run={run_id};type={data.change_type}')
    return {'run_id':run_id,**report}

@router.get('/runs/{run_id}/model-tools')
def model_trace(request:Request,run_id:int):
    who=req_actor(request)
    _run_for_view(run_id,who)
    with db() as c:
        rows=c.execute('SELECT id,owner_id,trace_json,created_at FROM model_tool_runs WHERE run_id=? ORDER BY id DESC LIMIT 15',(run_id,)).fetchall()
    return {'items':[{'id':r['id'],'trace':json.loads(r['trace_json']),'created_at':r['created_at']} for r in rows
                     if who['role']=='admin' or r['owner_id']==who['id']]}

@router.post('/runs')
def run_task(request:Request,data:Task):
    who=req_actor(request)
    if deployment_mode() == 'cloud_synthetic' and data.industry != '食品饮料':
        raise HTTPException(400,'公网合成演示仅支持食品饮料行业')
    with db() as c:
        ag=c.execute('SELECT * FROM agents WHERE id=?',(data.agent_id,)).fetchone()
        if not allowed(ag,who):raise HTTPException(403,'Agent不存在或无权访问')
        skill_rows=[]
        for sid in json.loads(ag['skill_ids_json']):
            sk=c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone()
            if not allowed(sk,who):raise HTTPException(403,'Agent绑定了无权限的Skill')
            skill_rows.append(sk)
        inventories=c.execute('SELECT * FROM datasets WHERE kind=? ORDER BY id DESC',('inventory',)).fetchall()
        pricebooks=c.execute('SELECT * FROM datasets WHERE kind=? ORDER BY id DESC',('pricing',)).fetchall()
        covers=c.execute('SELECT * FROM datasets WHERE kind=? ORDER BY id DESC',('coverage',)).fetchall()
        ds=next((d for d in inventories if allowed(d,who) and
                 (data.inventory_dataset_id is None or d['id']==data.inventory_dataset_id)),None)
        if not ds:
            record_failure(who['id'],data.agent_id,None,None,'INVENTORY_DATA_MISSING',
                           '当前用户没有可访问的授权库存快照；需人工导入或配置批准的只读接口')
            raise HTTPException(400,'没有可用的已授权库存数据，请先导入')
        cs=next((d for d in covers if allowed(d,who) and
                 (data.coverage_dataset_id is None or d['id']==data.coverage_dataset_id)),None)
        ps=next((d for d in pricebooks if allowed(d,who)),None)
    inventory=json.loads(ds['records_json'])
    coverage=json.loads(cs['records_json']) if cs else []
    prices=json.loads(ps['records_json']) if ps else []
    source_desc={'inventory':f"{ds['name']} [{ds['origin']}]",'coverage':f"{cs['name']} [{cs['origin']}]" if cs else '未导入',
                 'pricing':f"{ps['name']} [{ps['origin']}]" if ps else '无单独价格表'}
    with db() as c:
        policy_rows=c.execute('SELECT * FROM skill_policies WHERE skill_id IN ('+','.join('?' for _ in skill_rows)+')',
                              [r['id'] for r in skill_rows]).fetchall() if skill_rows else []
    effective_policy={'strict_coverage':any(bool(x['strict_coverage']) for x in policy_rows)}
    try: result=perform(data.model_dump(),ag,skill_rows,inventory,coverage,source_desc,prices,policy=effective_policy)
    except ValueError as exc:
        own=next((sk for sk in skill_rows if sk['owner_id']==who['id']),None)
        record_failure(who['id'],data.agent_id,None,own['id'] if own else None,
                       'BUSINESS_EXECUTION_BLOCKED',str(exc)[:160])
        raise HTTPException(400,str(exc)) from exc
    result['input_dataset_ids']={'inventory':ds['id'],'coverage':cs['id'] if cs else None,'pricing':ps['id'] if ps else None}
    result['skill_policy']=effective_policy
    result['quality_report']=assess_result(result)
    result['evaluation_report']=evaluation(result)
    result['replay_manifest']=create_manifest(
        dict(ag), [dict(sk) for sk in skill_rows],
        {'inventory':ds,'coverage':cs,'pricing':ps},
        {'inventory':inventory,'coverage':coverage,'pricing':prices},
        source_desc,effective_policy,result)
    with db() as c:
        cur=c.execute('INSERT INTO runs(owner_id,agent_id,request_json,result_json,status,created_at) VALUES(?,?,?,?,?,?)',
             (who['id'],data.agent_id,safe_json(data.model_dump()),safe_json(result),'completed',now()))
    audit(who['id'],'agent_run',f"Agent#{data.agent_id} Run#{cur.lastrowid}")
    from .iteration import auto_suggest
    suggestion=auto_suggest(cur.lastrowid,who['id'],skill_rows,result)
    failure_id=None
    if coverage and not any('match_coverage' in json.loads(sk['tools_json']) for sk in skill_rows):
        own=next((sk for sk in skill_rows if sk['owner_id']==who['id']),None)
        if own and result['quality']['unsupported_selected']:
            failure_id=record_failure(who['id'],data.agent_id,cur.lastrowid,own['id'],
                'COVERAGE_TOOL_NOT_GRANTED', '存在授权覆盖数据但 Skill 缺少读取工具，导致媒体推荐没有目标商圈证据', 'match_coverage')
    return {'run_id':cur.lastrowid,'agent_name':ag['name'],'improvement_hint':suggestion,
            'failure_improvement_id':failure_id,**result}

def _run_for_view(run_id:int,who):
    with db() as c:
        row=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row or (who['role']!='admin' and row['owner_id']!=who['id']):
        raise HTTPException(404,'任务不存在或无权查看')
    return row


def _review_info(c,run_id:int,result:dict):
    existing=c.execute('SELECT * FROM proposal_reviews WHERE run_id=?',(run_id,)).fetchone()
    sha=hashlib.sha256(safe_json(result).encode('utf-8')).hexdigest()
    if not existing:
        return {'status':'pending','comment':'尚未由管理员审核','snapshot_sha256':sha}
    if existing['snapshot_sha256']!=sha:
        return {'status':'stale','comment':'结果快照发生变化，原审批失效','snapshot_sha256':sha}
    return {'status':existing['status'],'comment':existing['comment'],
            'reviewer_id':existing['reviewer_id'],'reviewed_at':existing['reviewed_at'],
            'snapshot_sha256':sha}


@router.post('/runs/{run_id}/replay')
def replay_past_run(run_id:int,request:Request):
    """Read-only deterministic replay with snapshot grants, not the mutable current Skill."""
    who=req_actor(request)
    row=_run_for_view(run_id,who)
    saved=json.loads(row['result_json'])
    manifest=saved.get('replay_manifest')
    if not manifest:
        raise HTTPException(409,'旧版运行没有冻结清单，不能声称可重放')
    # Never silently fall back to newer dataset versions or another employee's data.
    dataset_ids=manifest['dataset_ids']
    with db() as c:
        datasets={k:c.execute('SELECT * FROM datasets WHERE id=?',(v,)).fetchone() if v else None
                  for k,v in dataset_ids.items()}
    # Cross-user access to private datasets remains denied even to a run owner.
    if any(d and not allowed(d,who) for d in datasets.values()):
        raise HTTPException(403,'原数据集不再授权给当前用户，拒绝重放')
    records={k:json.loads(v['records_json']) if v else [] for k,v in datasets.items()}
    outcome=replay(manifest,json.loads(row['request_json']),saved,datasets,records)
    audit(who['id'],'agent_replay',f'Run#{run_id},status={outcome["status"]}')
    return {'run_id':run_id,**outcome}


@router.get('/runs/{run_id}/evaluation')
def evaluation_for_run(run_id:int,request:Request):
    who=req_actor(request)
    row=_run_for_view(run_id,who)
    saved=json.loads(row['result_json'])
    return {'run_id':run_id,'evaluation':evaluation(saved),
            'manifest_available':bool(saved.get('replay_manifest'))}


@router.post('/agents/{agent_id}/benchmark')
def benchmark_agent(agent_id:int,request:Request,data:BenchmarkRequest):
    """Agno-style runnable 5×3 regression matrix, using only approved local tools."""
    who=req_actor(request)
    with db() as c:
        agent=c.execute('SELECT * FROM agents WHERE id=?',(agent_id,)).fetchone()
        if not allowed(agent,who):raise HTTPException(404,'Agent不存在或无权评估')
        skills=[]
        for sid in json.loads(agent['skill_ids_json']):
            skill=c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone()
            if not allowed(skill,who):raise HTTPException(403,'Agent技能无权访问')
            skills.append(skill)
        datasets={kind:next((d for d in c.execute('SELECT * FROM datasets WHERE kind=? ORDER BY id DESC',(kind,)).fetchall() if allowed(d,who)),None)
                  for kind in ('inventory','coverage','pricing')}
        policy_rows=c.execute('SELECT * FROM skill_policies WHERE skill_id IN ('+','.join('?' for _ in skills)+')',
                              [s['id'] for s in skills]).fetchall() if skills else []
    if not datasets['inventory']:raise HTTPException(400,'没有授权的媒体库存数据，无法评估')
    policy={'strict_coverage':any(bool(x['strict_coverage']) for x in policy_rows)}
    records={k:json.loads(ds['records_json']) if ds else [] for k,ds in datasets.items()}
    source_desc={'inventory':datasets['inventory']['name'],
                 'coverage':datasets['coverage']['name'] if datasets['coverage'] else '未导入',
                 'pricing':datasets['pricing']['name'] if datasets['pricing'] else '未导入'}
    tests=[]
    for industry in INDUSTRIES:
        for budget in (100,200,500):
            task={'industry':industry,'budget_wan':budget,'brand':'评估品牌（虚构）',
                  'landmark':data.landmark,'start_date':data.start_date,'weeks':data.weeks,
                  'medium':data.medium,'coverage_only':data.coverage_only}
            try:
                result=perform(task,agent,skills,records['inventory'],records['coverage'],source_desc,
                               prices=records['pricing'],policy=policy)
                report=evaluation(result)
                passed=not assess_result(result)['blockers'] and result['plan']['spent_wan']<=budget
                tests.append({'industry':industry,'budget_wan':budget,'passed':passed,
                              'spent_wan':result['plan']['spent_wan'],
                              'media_items':result['plan']['item_count'],
                              'checks_passed':report['passed'],'checks_total':report['total'],
                              'quality_status':report['status']})
            except ValueError as error:
                tests.append({'industry':industry,'budget_wan':budget,'passed':False,'error':str(error)[:200]})
    count=sum(t['passed'] for t in tests)
    audit(who['id'],'agent_benchmark',f'Agent#{agent_id},passed={count}/15')
    return {'agent_id':agent_id,'passed':count,'total':15,'tests':tests,
            'model_calls':0,'scope':'五行业×三预算的固定工具回归；不证明2027库存、广告ROI或正式报价'}


@router.get('/runs/{run_id}/quality')
def quality_for_run(run_id:int,request:Request):
    who=req_actor(request)
    row=_run_for_view(run_id,who)
    result=json.loads(row['result_json'])
    with db() as c:review=_review_info(c,run_id,result)
    return {'run_id':run_id,'quality':assess_result(result),'review':review}


@router.post('/runs/{run_id}/review')
def review_run(run_id:int,request:Request,data:ProposalDecision):
    who=req_actor(request)
    require_admin(who)  # No implicit access to employee/private runs for managers.
    if data.decision not in ('approve','reject'):
        raise HTTPException(400,'审核操作只能 approve/reject')
    row=_run_for_view(run_id,who)
    result=json.loads(row['result_json'])
    quality=assess_result(result)
    if data.decision=='approve' and not quality['demo_approvable']:
        raise HTTPException(409,'质量门禁存在阻断项，不允许批准演示')
    status='approved' if data.decision=='approve' else 'rejected'
    checksum=hashlib.sha256(safe_json(result).encode('utf-8')).hexdigest()
    with db() as c:
        c.execute('INSERT INTO proposal_reviews(run_id,reviewer_id,status,comment,snapshot_sha256,reviewed_at) '
                  'VALUES(?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET '
                  'reviewer_id=excluded.reviewer_id,status=excluded.status, '
                  'comment=excluded.comment,snapshot_sha256=excluded.snapshot_sha256, '
                  'reviewed_at=excluded.reviewed_at',
                  (run_id,who['id'],status,data.comment.strip(),checksum,now()))
    audit(who['id'],'proposal_demo_review',f'Run#{run_id} {status} [not commercial booking]')
    return {'run_id':run_id,'status':status,'quality':quality,
            'note':'仅批准比赛演示；不构成2027库存锁定或正式报价'}


@router.get('/runs/{run_id}/proposal.html')
def export_run_proposal(run_id:int,request:Request):
    who=req_actor(request)
    row=_run_for_view(run_id,who)
    req=json.loads(row['request_json']);result=json.loads(row['result_json'])
    quality=assess_result(result)
    with db() as c:review=_review_info(c,run_id,result)
    body=render_proposal(run_id,req,result,quality,review)
    audit(who['id'],'proposal_html_export',f'Run#{run_id}, review={review["status"]}')
    return HTMLResponse(body,headers={
        'Content-Disposition':f'attachment; filename="CompanyAgent_Run_{run_id}.html"',
        'X-Content-Type-Options':'nosniff',
        'Cache-Control':'private, no-store',
        'Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})


@router.post('/brief/parse')
def parse_natural_brief(request:Request,data:NaturalBrief):
    who=req_actor(request)
    try: params,analysis=choose_params({'brief':data.text})
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    return {'fields':{k:v for k,v in params.items() if k!='records'},'analysis':analysis,
            'mode':'deterministic_extraction','note':'仅提取可识别字段；未提取出的值需要人工确认'}

@router.post('/runs/{run_id}/ai-explain')
async def model_explain(run_id:int,request:Request):
    """Optional user-triggered B1X explanation. Sends ONLY aggregate summary, never raw rows."""
    who=req_actor(request)
    key=os.getenv('B1X_API_KEY','').strip()
    if not key:raise HTTPException(503,'模型未配置；可继续使用确定性Agent编排')
    with db() as c:row=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row or (who['role']!='admin' and row['owner_id']!=who['id']):raise HTTPException(404,'任务不存在')
    req=json.loads(row['request_json']);result=json.loads(row['result_json']);p=result['plan']
    # Whitelist only concise aggregate fields. Do not include inventory rows/coverage exports.
    summary={k:p.get(k) for k in ('brand','industry','budget_wan','spent_wan','remaining_wan','item_count','unit_count','focus_landmark','start_date','end_date','schedule_state','is_reference_estimate')}
    instructions=('你是广告提案辅助Agent，只依据提供的摘要生成150字以内的中文建议。'
                  '强调库存与档期待核验、价格为情景估算；不得编造人流、ROI、正式价格或实际点位可售。')
    try:
        async with httpx.AsyncClient(timeout=25,follow_redirects=False) as client:
            response=await client.post('https://token.b1x.work/v1/chat/completions',
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},
                json={'model':'deepseek-v4.1-flash-1017','messages':[{'role':'system','content':instructions},
                      {'role':'user','content':safe_json(summary)}],'temperature':0.2,'max_tokens':350})
        response.raise_for_status();text=response.json()['choices'][0]['message']['content']
        if not isinstance(text,str):raise ValueError('模型返回数据格式无效')
    except Exception as exc:raise HTTPException(502,'B1X模型调用失败；不影响已完成的预算优化') from exc
    audit(who['id'],'llm_explain',f'run={run_id},仅发送聚合摘要')
    return {'content':text[:1800],'model':'deepseek-v4.1-flash-1017','data_sent':'仅品牌、预算、媒体数量等聚合摘要，不包括库存明细'}

@router.get('/runs')
def runs(request:Request):
    who=req_actor(request)
    with db() as c:
        rows=c.execute('SELECT id,owner_id,agent_id,status,created_at,request_json,result_json FROM runs '+('' if who['role']=='admin' else 'WHERE owner_id=? ')+'ORDER BY id DESC LIMIT 50',() if who['role']=='admin' else (who['id'],)).fetchall()
    output=[]
    for row in rows:
        req=json.loads(row['request_json']);res=json.loads(row['result_json'])
        output.append({'id':row['id'],'created_at':row['created_at'],'agent_id':row['agent_id'],
                       'owner_id':row['owner_id'],'status':row['status'],'brand':req.get('brand'),
                       'budget_wan':req.get('budget_wan'),'spent_wan':res['plan'].get('spent_wan'),'item_count':res['plan'].get('item_count')})
    return {'items':output}

@router.get('/runs/{run_id}')
def run_detail(run_id:int,request:Request):
    who=req_actor(request)
    with db() as c:row=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
    if not row or (who['role']!='admin' and row['owner_id']!=who['id']):raise HTTPException(404,'记录不存在')
    return {'id':row['id'],'created_at':row['created_at'],'request':json.loads(row['request_json']),
            'result':json.loads(row['result_json'])}

@router.get('/audit')
def audit_list(request:Request):
    who=req_actor(request)
    with db() as c:rows=c.execute('SELECT * FROM audit '+('' if who['role']=='admin' else 'WHERE user_id=? ')+'ORDER BY id DESC LIMIT 120',() if who['role']=='admin' else (who['id'],)).fetchall()
    return {'items':[dict(x) for x in rows]}

@router.get('/status')
def status(request:Request):
    who=req_actor(request)
    with db() as c:
        cnt={x:c.execute(f'SELECT COUNT(*) FROM {x}').fetchone()[0] for x in ['agents','skills','datasets','runs','users']}
    return {'counts':cnt,'import_folder':str(STATE/'imports'),'allowed_hosts':os.getenv('COMPANYAGENT_ALLOWED_DATA_HOSTS',''),
            'automated_sync':os.getenv('COMPANYAGENT_AUTO_SYNC')=='true',
            'model_configured':bool(os.getenv('B1X_API_KEY','').strip()),
            'deployment_mode':deployment_mode(),
            'fixed_industry':'食品饮料' if deployment_mode()=='cloud_synthetic' else None,
            'visual_coverage_api_available':False,
            'hongdou_real_api_connected':False,
            'tool_model_provider':provider_name(),
            'tool_model_configured':provider_configured(),
            'limits':['单组织本地MVP，不具备多租户隔离与单点登录','不自动绕过红豆或大数据平台验证码','2027实际可售需业务系统核验']}

_daemon_started=False

def background_sync():
    """Optional 60-second polling loop. Scoped to local server process; no async delivery promises."""
    import datetime
    global _daemon_started
    if _daemon_started or os.getenv('COMPANYAGENT_AUTO_SYNC')!='true':return
    _daemon_started=True
    def tick():
        while True:
            try:
                with db() as c:
                    admin=c.execute('SELECT id FROM users WHERE role=? ORDER BY id LIMIT 1',('admin',)).fetchone()
                    src=c.execute('SELECT * FROM sources WHERE active=1').fetchall()
                if admin:poll_folder(admin['id'])
                for s in src:
                    try:
                        if s['last_sync']:
                            from datetime import datetime,timezone
                            seconds=(datetime.now(timezone.utc)-datetime.fromisoformat(s['last_sync'])).total_seconds()
                            if seconds<s['interval_minutes']*60:continue
                        pull_source(s)
                        with db() as c:c.execute('UPDATE sources SET last_sync=?,last_status=?,last_error=NULL WHERE id=?',(now(),'ok',s['id']))
                    except Exception as exc:
                        with db() as c:c.execute('UPDATE sources SET last_sync=?,last_status=?,last_error=? WHERE id=?',(now(),'error',str(exc)[:200],s['id']))
            except Exception:pass
            time.sleep(60)
    threading.Thread(target=tick,name='companyagent-readonly-sync',daemon=True).start()
