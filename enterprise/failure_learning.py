"""Failure-to-experiment Skill improvement candidates; never unattended changes.

Only an allowlisted 'match_coverage' tool addition can be approved here. Every
candidate is evaluated on the SAME frozen input records as the observed run.
The owner must approve and may rollback, with version-conflict checks.
"""
from __future__ import annotations
import json
from fastapi import APIRouter,HTTPException,Request
from .store import actor,db,now,audit,safe_json
from .engine import perform
from src.coverage import join_coverage

router=APIRouter(prefix='/enterprise/api',tags=['Failure-guided Skill experiments'])


def record_failure(owner_id,agent_id,run_id,skill_id,code,reason,proposed_tool=''):
    """Persist safe failure metadata. No secrets, prompts or full error traces."""
    proposal={'kind':'add_readonly_tool' if proposed_tool=='match_coverage' else 'manual_data_check',
              'tool':proposed_tool if proposed_tool=='match_coverage' else '',
              'next_step':('先在冻结数据上测试新增覆盖工具，随后请 Skill 所有者审批' if proposed_tool else
                           '核验授权库存、覆盖或模型连接配置，不能由 Agent 自行授权访问')}
    with db() as c:
        cur=c.execute('''INSERT INTO failure_cases(owner_id,agent_id,run_id,skill_id,code,reason,proposal_json,eval_json,status,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)''',(owner_id,agent_id,run_id,skill_id,code,str(reason)[:240],safe_json(proposal),'{}','proposed',now()))
    return cur.lastrowid


def _case(c,fid,who):
    f=c.execute('SELECT * FROM failure_cases WHERE id=?',(fid,)).fetchone()
    if not f or (who['role']!='admin' and f['owner_id']!=who['id']):raise HTTPException(404,'诊断不存在或无权查看')
    return f


def _owner_skill(c,f,who):
    if not f['skill_id']:raise HTTPException(409,'该故障不支持自动修改 Skill')
    skill=c.execute('SELECT * FROM skills WHERE id=?',(f['skill_id'],)).fetchone()
    if not skill or (who['role']!='admin' and skill['owner_id']!=who['id']):raise HTTPException(403,'仅 Skill 所有者可以发布改进')
    return skill

@router.get('/failures')
def failures(request:Request):
    who=actor(request)
    with db() as c:
        if who['role']=='admin':rows=c.execute('SELECT * FROM failure_cases ORDER BY id DESC LIMIT 100').fetchall()
        else:rows=c.execute('SELECT * FROM failure_cases WHERE owner_id=? ORDER BY id DESC LIMIT 100',(who['id'],)).fetchall()
    return {'items':[{'id':x['id'],'run_id':x['run_id'],'agent_id':x['agent_id'],'skill_id':x['skill_id'],
                      'code':x['code'],'reason':x['reason'],'status':x['status'],
                      'proposal':json.loads(x['proposal_json']),'evaluation':json.loads(x['eval_json'])} for x in rows]}


def _recheck(c,f,skill,who):
    if f['run_id'] is None:raise HTTPException(409,'没有可重放的原始执行快照，需先完成数据导入并重新运行')
    r=c.execute('SELECT * FROM runs WHERE id=?',(f['run_id'],)).fetchone()
    if not r:raise HTTPException(409,'原任务已删除')
    saved=json.loads(r['result_json'])
    ids=saved.get('input_dataset_ids',{})
    if not ids.get('inventory') or not ids.get('coverage'):
        raise HTTPException(409,'原任务缺少库存或覆盖数据，不能证明工具改进有效')
    data={}
    descriptions={}
    for kind in ('inventory','coverage','pricing'):
        ds=c.execute('SELECT * FROM datasets WHERE id=?',(ids[kind],)).fetchone() if ids.get(kind) else None
        if ds and who['role']!='admin' and ds['visibility']=='private' and ds['owner_id']!=who['id']:
            raise HTTPException(403,'冻结数据不再授权')
        if ds:
            # Dataset drift detection before claiming a legitimate controlled experiment.
            import hashlib
            if kind in saved.get('replay_manifest',{}).get('record_fingerprints',{}):
                from .reliability import digest
                if digest(json.loads(ds['records_json']))!=saved['replay_manifest']['record_fingerprints'][kind]:
                    raise HTTPException(409,'数据快照发生漂移，拒绝不公平的前后对照')
        data[kind]=json.loads(ds['records_json']) if ds else []
        descriptions[kind]=str(ds['name']) if ds else '无'
    agent=c.execute('SELECT * FROM agents WHERE id=?',(f['agent_id'],)).fetchone()
    if not agent:raise HTTPException(409,'Agent 不存在')
    skill_ids=json.loads(agent['skill_ids_json'])
    if skill['id'] not in skill_ids:raise HTTPException(409,'Skill 已不再绑定该 Agent')
    skills=[c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone() for sid in skill_ids]
    if any(s is None for s in skills):raise HTTPException(409,'Agent 绑定的 Skill 不完整')
    frozen_skill=next((k for k in saved.get('replay_manifest',{}).get('skills',[]) if k['id']==skill['id']),None)
    if not frozen_skill or skill['tools_json']!=frozen_skill['tools_json']:
        raise HTTPException(409,'原始 Skill 工具授权已发生变化，拒绝不公平的前后对照')
    before_tools=json.loads(skill['tools_json'])
    if 'match_coverage' in before_tools:raise HTTPException(409,'覆盖工具已经存在，无需再次增加')
    frozen_policy=saved.get('skill_policy') or {}
    if frozen_policy.get('strict_coverage'):
        # An invalid precondition would be visible in both sides; do not bypass it silently.
        raise HTTPException(409,'原任务要求严格覆盖但 Skill 缺工具，需人工复核旧策略')
    req=json.loads(r['request_json'])
    baseline=perform(req,agent,skills,data['inventory'],data['coverage'],descriptions,data['pricing'],policy=frozen_policy)
    replaced=[]
    for s in skills:
        d=dict(s)
        if s['id']==skill['id']:d['tools_json']=safe_json(sorted(set(before_tools+['match_coverage'])))
        replaced.append(d)
    candidate=perform(req,agent,replaced,data['inventory'],data['coverage'],descriptions,data['pricing'],policy=frozen_policy)
    b=baseline['quality'];a=candidate['quality']
    passed=bool(b['unsupported_selected']>a['unsupported_selected'] and
                a['within_budget'] and a['has_candidates'] and data['coverage'])
    return {'passed':passed,'before':{'unsupported':b['unsupported_selected'],'items':baseline['plan']['item_count'],
                                       'spent_wan':baseline['plan']['spent_wan']},
            'after':{'unsupported':a['unsupported_selected'],'items':candidate['plan']['item_count'],
                     'spent_wan':candidate['plan']['spent_wan']},
            'frozen_dataset_ids':ids,'old_skill_tools':before_tools,
            'candidate_skill_tools':sorted(set(before_tools+['match_coverage'])),
            'reason':('同源覆盖证据缺失减少且预算与候选约束通过' if passed else '未证明净改善，不可发布'),
            'evaluated_at':now()}

@router.post('/failures/{case_id}/evaluate')
def evaluate(case_id:int,request:Request):
    who=actor(request)
    with db() as c:
        f=_case(c,case_id,who);sk=_owner_skill(c,f,who)
        proposal=json.loads(f['proposal_json'])
        if proposal.get('tool')!='match_coverage':raise HTTPException(409,'该问题属于数据或凭证故障，应人工修复并重新测试')
        if f['status'] not in ('proposed','evaluated','rejected'):raise HTTPException(409,'已发布或回滚，不能再次评估')
        result=_recheck(c,f,sk,who)
        c.execute('UPDATE failure_cases SET eval_json=?,status=? WHERE id=?',
                  (safe_json(result),'evaluated' if result['passed'] else 'rejected',case_id))
    audit(who['id'],'failure_skill_evaluate',f'case={case_id};passed={result["passed"]}')
    return result

@router.post('/failures/{case_id}/publish')
def publish(case_id:int,request:Request):
    who=actor(request)
    with db() as c:
        f=_case(c,case_id,who);sk=_owner_skill(c,f,who)
        if f['status']!='evaluated':raise HTTPException(409,'只能发布通过对照实验的候选')
        e=json.loads(f['eval_json'])
        if not e.get('passed'):raise HTTPException(409,'对照实验没有通过')
        # Re-evaluate frozen sources and current Skill before publishing; no
        # post-evaluation dataset drift or modified agent binding is accepted.
        fresh=_recheck(c,f,sk,who)
        if not fresh['passed'] or fresh['before']!=e['before'] or fresh['after']!=e['after']:
            raise HTTPException(409,'数据或 Agent 配置在评估后改变，请重新进行对照测试')
        current=json.loads(sk['tools_json'])
        if current!=e['old_skill_tools']:raise HTTPException(409,'Skill 已有更改，拒绝覆盖最新版本')
        new_tools=e['candidate_skill_tools']
        if set(new_tools)-set(current)!={'match_coverage'}:
            raise HTTPException(409,'只能增加一项审核过的只读覆盖工具')
        c.execute('UPDATE skills SET tools_json=? WHERE id=?',(safe_json(new_tools),sk['id']))
        c.execute('UPDATE failure_cases SET status=?,prior_tools_json=?,published_tools_json=? WHERE id=?',
                  ('published',safe_json(current),safe_json(new_tools),case_id))
    audit(who['id'],'failure_skill_publish',f'case={case_id};skill={sk["id"]}')
    return {'ok':True,'skill_id':sk['id'],'tools':new_tools,'requires_human_approval':True}

@router.post('/failures/{case_id}/rollback')
def rollback(case_id:int,request:Request):
    who=actor(request)
    with db() as c:
        f=_case(c,case_id,who);sk=_owner_skill(c,f,who)
        if f['status']!='published':raise HTTPException(409,'只能回滚已发布方案')
        if sk['tools_json']!=f['published_tools_json']:
            raise HTTPException(409,'Skill 在发布后被修改，不能直接回滚覆盖新版本')
        c.execute('UPDATE skills SET tools_json=? WHERE id=?',(f['prior_tools_json'],sk['id']))
        c.execute('UPDATE failure_cases SET status=? WHERE id=?',('rolled_back',case_id))
    audit(who['id'],'failure_skill_rollback',f'case={case_id};skill={sk["id"]}')
    return {'ok':True,'restored_tools':json.loads(f['prior_tools_json'])}
