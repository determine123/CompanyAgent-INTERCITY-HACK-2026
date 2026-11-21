"""Problem-driven, gated improvement loop.

No model-written code, hidden network login, or unattended production changes.
A candidate changes ONLY a fixed, auditable policy ('strict_coverage'),
and may be published after deterministic side-by-side regression and owner approval.
"""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from .store import actor, audit, db, now, safe_json
from .engine import perform

router = APIRouter(prefix='/enterprise/api', tags=['Governed Iteration'])
VALID_CATEGORIES = {'coverage_integrity', 'pricing_accuracy', 'schedule_risk', 'other'}

class FeedbackInput(BaseModel):
    run_id: int
    score: int = Field(ge=1, le=5)
    category: str = 'coverage_integrity'
    comment: str = Field(default='', max_length=800)

def _run_for_user(c, run_id, who):
    r = c.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
    if not r or (who['role'] != 'admin' and r['owner_id'] != who['id']):
        raise HTTPException(404, '任务不存在或无访问权限')
    return r

def _proposal_for_user(c, proposal_id, who):
    p = c.execute('SELECT * FROM improvements WHERE id=?', (proposal_id,)).fetchone()
    if not p or (who['role'] != 'admin' and p['creator_id'] != who['id']):
        raise HTTPException(404, '建议不存在或无访问权限')
    return p

def _owned_skill(c, sid, who):
    sk = c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone()
    if not sk or (who['role'] != 'admin' and sk['owner_id'] != who['id']):
        raise HTTPException(403,'只有 Skill 创建者或管理员可以发布策略变更')
    return sk

def auto_suggest(run_id, uid, skill_rows, result):
    """Automatically spot the first measurable evidence defect; never auto-publish."""
    unsupported = result.get('quality', {}).get('unsupported_selected', 0)
    if not unsupported or result.get('quality', {}).get('strict_coverage'):
        return None
    with db() as c:
        # Only suggest directly on skills owned by the caller, otherwise admin review
        skills = [s for s in skill_rows if s['owner_id'] == uid]
        if not skills:
            return '检测到缺少覆盖证据的推荐，请由企业 Skill 所有者复核'
        sid = skills[0]['id']
        existed = c.execute('SELECT 1 FROM improvements WHERE run_id=? AND skill_id=? AND kind=?',
                            (run_id,sid,'strict_coverage')).fetchone()
        if existed: return None
        c.execute('''INSERT INTO improvements(run_id,skill_id,creator_id,feedback_id,kind,status,reason,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (run_id,sid,uid,None,'strict_coverage','proposed',
             f'质量检查识别到 {unsupported} 项缺乏指定商圈覆盖证据的推荐，建议试验严格覆盖过滤。',now(),now()))
    return '已自动发现覆盖证据问题并生成一条待实验的 Skill 改进建议'

@router.post('/feedback')
def feedback(request: Request, data: FeedbackInput):
    who = actor(request)
    if data.category not in VALID_CATEGORIES:
        raise HTTPException(400,'反馈类别无效')
    with db() as c:
        run = _run_for_user(c,data.run_id,who)
        cur = c.execute('INSERT INTO task_feedback(run_id,owner_id,score,category,comment,created_at) VALUES(?,?,?,?,?,?)',
                        (data.run_id,who['id'],data.score,data.category,data.comment,now()))
        feedback_id = cur.lastrowid
        suggestion = None
        if data.category == 'coverage_integrity':
            result = json.loads(run['result_json'])
            if not result.get('quality',{}).get('strict_coverage'):
                agent = c.execute('SELECT * FROM agents WHERE id=?',(run['agent_id'],)).fetchone()
                if agent:
                    for sid in json.loads(agent['skill_ids_json']):
                        skill = c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone()
                        if skill and (skill['owner_id']==who['id'] or who['role']=='admin'):
                            existing = c.execute('SELECT id FROM improvements WHERE run_id=? AND skill_id=? AND kind=?',
                                                 (data.run_id,sid,'strict_coverage')).fetchone()
                            if existing:
                                suggestion = existing['id']
                            else:
                                cur2 = c.execute('''INSERT INTO improvements(run_id,skill_id,creator_id,feedback_id,kind,status,reason,created_at,updated_at)
                                    VALUES(?,?,?,?,?,?,?,?,?)''',
                                    (data.run_id,sid,who['id'],feedback_id,'strict_coverage','proposed',
                                     '用户反馈覆盖证据不足：试验要求所有候选具有目标地标覆盖证据。',now(),now()))
                                suggestion = cur2.lastrowid
                            break
    audit(who['id'],'task_feedback',f'run={data.run_id};category={data.category};score={data.score}')
    return {'ok':True,'feedback_id':feedback_id,'improvement_id':suggestion,
            'next_step':'在迭代实验室执行对照测试，只有改进通过且获得 Skill 所有者批准才可发布' if suggestion else '已记录反馈；该类别需要人工分析后决定改进方向'}

@router.get('/improvements')
def list_improvements(request:Request):
    who = actor(request)
    with db() as c:
        if who['role']=='admin':
            rows=c.execute('SELECT * FROM improvements ORDER BY id DESC LIMIT 100').fetchall()
        else:
            rows=c.execute('SELECT * FROM improvements WHERE creator_id=? ORDER BY id DESC LIMIT 100',(who['id'],)).fetchall()
    return {'items':[dict(x) | {'eval':json.loads(x['eval_json'])} for x in rows]}

@router.get('/feedback')
def list_feedback(request:Request):
    who = actor(request)
    with db() as c:
        if who['role']=='admin':
            rows=c.execute('SELECT * FROM task_feedback ORDER BY id DESC LIMIT 100').fetchall()
        else:
            rows=c.execute('SELECT * FROM task_feedback WHERE owner_id=? ORDER BY id DESC LIMIT 100',(who['id'],)).fetchall()
    return {'items':[dict(x) for x in rows]}

def _simulate(run_id, skill_id, who):
    with db() as c:
        run=_run_for_user(c,run_id,who)
        req=json.loads(run['request_json'])
        old_result=json.loads(run['result_json'])
        agent=c.execute('SELECT * FROM agents WHERE id=?',(run['agent_id'],)).fetchone()
        if not agent: raise HTTPException(409,'原 Agent 已不存在')
        skill_ids=json.loads(agent['skill_ids_json'])
        if skill_id not in skill_ids:raise HTTPException(409,'Agent 已取消绑定该 Skill，不能发布历史建议')
        skills=[c.execute('SELECT * FROM skills WHERE id=?',(sid,)).fetchone() for sid in skill_ids]
        if any(s is None for s in skills):raise HTTPException(409,'原 Skill 已不存在')
        ids=old_result.get('input_dataset_ids',{})
        if not ids or not ids.get('inventory'):
            raise HTTPException(409,'历史任务缺少可复现实验的数据集 ID，请使用 v0.9 新任务')
        def retrieve(kind):
            did=ids.get(kind)
            if did is None:return [],'无对应数据集'
            ds=c.execute('SELECT * FROM datasets WHERE id=?',(did,)).fetchone()
            if ds is None:raise HTTPException(409,f'实验依赖的{kind}数据集已被删除')
            if who['role']!='admin' and ds['visibility']!='team' and ds['owner_id']!=who['id']:
                raise HTTPException(403,'无权读取实验所需数据')
            return json.loads(ds['records_json']), f"{ds['name']} [{ds['origin']}]"
        inventory, ni=retrieve('inventory')
        coverage,nc=retrieve('coverage')
        prices,np=retrieve('pricing')
        desc={'inventory':ni,'coverage':nc,'pricing':np}
    # Identical fixed input and same dataset versions; only the proposed guard changes
    before=perform(req,agent,skills,inventory,coverage,desc,prices,policy={'strict_coverage':False})
    after=perform(req,agent,skills,inventory,coverage,desc,prices,policy={'strict_coverage':True})
    b,a=before['quality'],after['quality']
    passed=(a['unsupported_selected']==0 and a['within_budget'] and a['has_candidates']
            and a['unsupported_selected']<b['unsupported_selected'])
    return {'passed':passed,'before':{'selected':before['plan']['item_count'],'spent_wan':before['plan']['spent_wan'],**b},
            'after':{'selected':after['plan']['item_count'],'spent_wan':after['plan']['spent_wan'],**a},
            'explanation':('覆盖证据不足推荐减少，且仍存在可行候选；可以人工审批发布。' if passed else
                           '本次未证明净改进，可能没有覆盖数据或没有有效候选；禁止自动发布。'),
            'dataset_ids':ids,'tested_at':now()}

@router.post('/improvements/{proposal_id}/evaluate')
def evaluate(request:Request,proposal_id:int):
    who=actor(request)
    with db() as c:
        p=_proposal_for_user(c,proposal_id,who)
        _owned_skill(c,p['skill_id'],who)
        if p['status'] not in ('proposed','evaluated','rejected'):
            raise HTTPException(409,'该建议已发布或回滚，不能重新实验')
        current=c.execute('SELECT strict_coverage FROM skill_policies WHERE skill_id=?',(p['skill_id'],)).fetchone()
        if current and current['strict_coverage']:raise HTTPException(409,'目标 Skill 已启用严格覆盖策略')
    result=_simulate(p['run_id'],p['skill_id'],who)
    with db() as c:
        c.execute('UPDATE improvements SET eval_json=?,status=?,updated_at=? WHERE id=?',
                  (safe_json(result),'evaluated' if result['passed'] else 'rejected',now(),proposal_id))
    audit(who['id'],'improvement_evaluate',f'id={proposal_id},pass={result["passed"]}')
    return {'proposal_id':proposal_id,**result}

@router.post('/improvements/{proposal_id}/publish')
def publish(request:Request,proposal_id:int):
    who=actor(request)
    with db() as c:
        p=_proposal_for_user(c,proposal_id,who)
        _owned_skill(c,p['skill_id'],who)
        if p['status']!='evaluated':raise HTTPException(409,'必须先通过对照测试')
        evaluation=json.loads(p['eval_json'])
        if not evaluation.get('passed'):raise HTTPException(409,'回归测试没有通过')
        policy=c.execute('SELECT * FROM skill_policies WHERE skill_id=?',(p['skill_id'],)).fetchone()
        old={'strict_coverage':bool(policy['strict_coverage']) if policy else False,
             'version':int(policy['version']) if policy else 1}
        if old['strict_coverage']:raise HTTPException(409,'策略已启用；请先查看现有版本')
        version=old['version']+1
        c.execute('''INSERT INTO skill_policies(skill_id,strict_coverage,version) VALUES(?,?,?)
                     ON CONFLICT(skill_id) DO UPDATE SET strict_coverage=excluded.strict_coverage,version=excluded.version''',
                  (p['skill_id'],1,version))
        evaluation['published_version']=version
        c.execute('UPDATE improvements SET status=?,eval_json=?,prior_policy_json=?,updated_at=? WHERE id=?',
                  ('published',safe_json(evaluation),safe_json(old),now(),proposal_id))
    audit(who['id'],'improvement_publish',f'id={proposal_id},skill={p["skill_id"]},version={version}')
    return {'ok':True,'skill_id':p['skill_id'],'version':version,'policy':{'strict_coverage':True},
            'notice':'只发布白名单覆盖证据策略；2027 库存和价格仍需核验'}

@router.post('/improvements/{proposal_id}/rollback')
def rollback(request:Request,proposal_id:int):
    who=actor(request)
    with db() as c:
        p=_proposal_for_user(c,proposal_id,who)
        _owned_skill(c,p['skill_id'],who)
        if p['status']!='published':raise HTTPException(409,'只能回滚已发布的建议')
        ev=json.loads(p['eval_json'])
        row=c.execute('SELECT * FROM skill_policies WHERE skill_id=?',(p['skill_id'],)).fetchone()
        if not row or row['version']!=ev.get('published_version'):
            raise HTTPException(409,'Skill 已有后续版本，不能覆盖最新发布')
        old=json.loads(p['prior_policy_json'])
        c.execute('UPDATE skill_policies SET strict_coverage=?,version=? WHERE skill_id=?',
                  (int(old.get('strict_coverage',False)),row['version']+1,p['skill_id']))
        c.execute('UPDATE improvements SET status=?,updated_at=? WHERE id=?',('rolled_back',now(),proposal_id))
    audit(who['id'],'improvement_rollback',f'id={proposal_id},skill={p["skill_id"]}')
    return {'ok':True,'skill_id':p['skill_id'],'strict_coverage':bool(old.get('strict_coverage')),
            'notice':'已恢复上一策略；审计记录保留'}
