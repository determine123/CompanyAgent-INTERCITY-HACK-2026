"""Local Agent Hub: staff-owned Agents/Skills, provenance, scheduled allowed feeds, audit."""
from __future__ import annotations
import hashlib,json,os,re,secrets,time,threading
import httpx
from pathlib import Path
from fastapi import APIRouter,Request,HTTPException,UploadFile,File
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from .store import STATE,COOKIE,TOOLS,db,init,hashed,password_ok,actor,allowed,can_modify,audit,now,safe_json
from .dataflows import ingest,poll_folder,approved_url,pull_source
from .engine import perform, choose_params

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

@router.post('/runs')
def run_task(request:Request,data:Task):
    who=req_actor(request)
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
        if not ds: raise HTTPException(400,'没有可用的已授权库存数据，请先导入')
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
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    result['input_dataset_ids']={'inventory':ds['id'],'coverage':cs['id'] if cs else None,'pricing':ps['id'] if ps else None}
    result['skill_policy']=effective_policy
    with db() as c:
        cur=c.execute('INSERT INTO runs(owner_id,agent_id,request_json,result_json,status,created_at) VALUES(?,?,?,?,?,?)',
             (who['id'],data.agent_id,safe_json(data.model_dump()),safe_json(result),'completed',now()))
    audit(who['id'],'agent_run',f"Agent#{data.agent_id} Run#{cur.lastrowid}")
    from .iteration import auto_suggest
    suggestion=auto_suggest(cur.lastrowid,who['id'],skill_rows,result)
    return {'run_id':cur.lastrowid,'agent_name':ag['name'],'improvement_hint':suggestion,**result}

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
