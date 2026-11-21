"""Local single-organization Agent Hub state. No demo passwords checked in."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, sqlite3, threading, time
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException, Request

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.getenv('COMPANYAGENT_RUNTIME_DIR', str(ROOT / 'runtime'))).resolve()
DB = STATE / 'companyagent.sqlite3'
COOKIE = 'companyagent_session'
TOOLS = {'brief_parse','load_inventory','match_coverage','optimize_budget','review_risks','explain_plan'}
LOCK = threading.RLock()

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def db():
    STATE.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB,timeout=15)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA foreign_keys=ON')
    return con

def hashed(password, salt=None):
    salt=salt or secrets.token_hex(16)
    val=hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),bytes.fromhex(salt),240000)
    return f'{salt}${val.hex()}'

def password_ok(password, stored):
    try:
        salt, _=stored.split('$',1)
        return hmac.compare_digest(hashed(password,salt),stored)
    except (ValueError,TypeError): return False

def init():
    with LOCK:
        with db() as c:
            c.executescript('''
              CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,
                 display TEXT NOT NULL,role TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,
                 csrf TEXT NOT NULL,expires INTEGER NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id));
              CREATE TABLE IF NOT EXISTS skills(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 name TEXT NOT NULL,description TEXT NOT NULL,instructions TEXT NOT NULL,
                 tools_json TEXT NOT NULL,visibility TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS agents(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 name TEXT NOT NULL,description TEXT NOT NULL,instructions TEXT NOT NULL,
                 skill_ids_json TEXT NOT NULL,visibility TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS datasets(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 kind TEXT NOT NULL,name TEXT NOT NULL,origin TEXT NOT NULL,records_json TEXT NOT NULL,
                 count INTEGER NOT NULL,checksum TEXT NOT NULL,visibility TEXT NOT NULL,imported_at TEXT NOT NULL,
                 source_id INTEGER,notes TEXT NOT NULL DEFAULT '');
              CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 name TEXT NOT NULL,kind TEXT NOT NULL,url TEXT NOT NULL,token_env TEXT NOT NULL,
                 interval_minutes INTEGER NOT NULL,active INTEGER NOT NULL DEFAULT 1,
                 last_sync TEXT,last_status TEXT,last_error TEXT);
              CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 agent_id INTEGER NOT NULL,request_json TEXT NOT NULL,result_json TEXT NOT NULL,
                 status TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,
                 detail TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS skill_policies(skill_id INTEGER PRIMARY KEY, strict_coverage INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 1);
              CREATE TABLE IF NOT EXISTS proposal_reviews(run_id INTEGER PRIMARY KEY,
                 reviewer_id INTEGER NOT NULL,status TEXT NOT NULL,comment TEXT NOT NULL,
                 snapshot_sha256 TEXT NOT NULL,reviewed_at TEXT NOT NULL,
                 FOREIGN KEY(run_id) REFERENCES runs(id));
              CREATE TABLE IF NOT EXISTS task_feedback(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL,owner_id INTEGER NOT NULL,
                 score INTEGER NOT NULL,category TEXT NOT NULL,comment TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS improvements(id INTEGER PRIMARY KEY,run_id INTEGER NOT NULL,skill_id INTEGER NOT NULL,
                 creator_id INTEGER NOT NULL,feedback_id INTEGER,kind TEXT NOT NULL,status TEXT NOT NULL,
                 reason TEXT NOT NULL,eval_json TEXT NOT NULL DEFAULT '{}',prior_policy_json TEXT NOT NULL DEFAULT '{}',
                 created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS failure_cases(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 agent_id INTEGER NOT NULL,run_id INTEGER,skill_id INTEGER,code TEXT NOT NULL,
                 reason TEXT NOT NULL,proposal_json TEXT NOT NULL,eval_json TEXT NOT NULL,
                 status TEXT NOT NULL,prior_tools_json TEXT DEFAULT NULL,published_tools_json TEXT DEFAULT NULL,
                 created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS model_tool_runs(id INTEGER PRIMARY KEY,owner_id INTEGER NOT NULL,
                 run_id INTEGER NOT NULL,trace_json TEXT NOT NULL,created_at TEXT NOT NULL);
              CREATE INDEX IF NOT EXISTS idx_failure_owner ON failure_cases(owner_id,id DESC);
              CREATE INDEX IF NOT EXISTS idx_model_runs_owner ON model_tool_runs(owner_id,id DESC);
              CREATE INDEX IF NOT EXISTS idx_imp_creator ON improvements(creator_id,id DESC);
              CREATE INDEX IF NOT EXISTS idx_runs_user ON runs(owner_id, id DESC);
              CREATE INDEX IF NOT EXISTS idx_datasets_kind ON datasets(kind,id DESC);
            ''')
            if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                pw=os.getenv('COMPANYAGENT_ADMIN_PASSWORD','')
                if not pw:
                    pw=secrets.token_urlsafe(17)
                    credential_path=STATE/'FIRST_LOGIN.txt'
                    credential_path.write_text('CompanyAgent 本地初始管理员\n用户名: admin\n一次性初始密码: '+pw+'\n登录后请更改密码；不要公开此文件。\n',encoding='utf-8')
                    try: credential_path.chmod(0o600)
                    except OSError: pass
                    print(f'\n[CompanyAgent] 首次登录凭证保存在: {credential_path}\n',flush=True)
                elif len(pw)<12: raise RuntimeError('COMPANYAGENT_ADMIN_PASSWORD 至少12个字符')
                c.execute('INSERT INTO users(username,display,role,password_hash,created_at) VALUES(?,?,?,?,?)',
                          ('admin','平台管理员','admin',hashed(pw),now()))
            admin_id=c.execute('SELECT id FROM users WHERE username=?',('admin',)).fetchone()
            if admin_id and not c.execute('SELECT 1 FROM skills LIMIT 1').fetchone():
                c.execute('INSERT INTO skills(owner_id,name,description,instructions,tools_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
                          (admin_id['id'],'户外媒体智能选点','对客户需求、覆盖与库存进行可解释选点','不得编造价格、人流或档期；覆盖≠可售；未授权数据不得传出。',json.dumps(sorted(TOOLS)), 'team',now()))
            if admin_id and not c.execute('SELECT 1 FROM agents LIMIT 1').fetchone():
                sid=c.execute('SELECT id FROM skills LIMIT 1').fetchone()['id']
                c.execute('INSERT INTO agents(owner_id,name,description,instructions,skill_ids_json,visibility,created_at) VALUES(?,?,?,?,?,?,?)',
                          (admin_id['id'],'广告智能提案 Agent','解析 Brief、选择媒体、核算预算、生成可审计建议',
                           '只能使用已授权输入和只读数据。商业报价、库存锁位必须人工确认。',json.dumps([sid]),'team',now()))

            # Public demo uses REPOSITORY-OWNED FICTIONAL inventory only.
            # Never infer live stock, dates, or prices from this fixture.
            if os.getenv('COMPANYAGENT_DEPLOYMENT_MODE') == 'cloud_synthetic' and admin_id:
                exists=c.execute('SELECT 1 FROM datasets WHERE kind=? LIMIT 1',('inventory',)).fetchone()
                if not exists:
                    from src.ingest import rows_from_bytes, parse_inventory
                    seed=Path(__file__).resolve().parents[1]/'data'/'demo_inventory.csv'
                    raw=seed.read_bytes()
                    records=parse_inventory(rows_from_bytes(raw,seed.name),seed.name)['records']
                    if not records or any(not str(x.get('source','')).startswith('DEMO-') for x in records):
                        raise RuntimeError('CLOUD_SYNTHETIC_BLOCKED: demo seed provenance invalid')
                    c.execute("""INSERT INTO datasets
                        (owner_id,kind,name,origin,records_json,count,checksum,visibility,imported_at,source_id,notes)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (admin_id['id'],'inventory','仅供演示：虚构公交/地铁库存',
                         'demo_synthetic_repo_seed',safe_json(records),len(records),
                         hashlib.sha256(raw).hexdigest(),'team',now(),None,
                         '完全虚构合成数据；不表示真实红豆库存、可售、价格或合同档期。'))

def actor(request:Request):
    token=request.cookies.get(COOKIE,'')
    if not token: raise HTTPException(401,'请先登录企业工作台')
    th=hashlib.sha256(token.encode()).hexdigest()
    with db() as c:
        row=c.execute('SELECT u.id,u.username,u.display,u.role,s.csrf,s.expires FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token_hash=?',(th,)).fetchone()
    if not row or row['expires']<int(time.time()): raise HTTPException(401,'会话已失效，请重新登录')
    if request.method in ('POST','PUT','PATCH','DELETE') and request.headers.get('X-CSRF-Token','')!=row['csrf']:
        raise HTTPException(403,'缺少有效的会话防伪校验')
    return dict(row)

def allowed(row, who):
    return bool(row) and (row['visibility']=='team' or row['owner_id']==who['id'] or who['role']=='admin')

def can_modify(row,who):
    return bool(row) and (row['owner_id']==who['id'] or who['role']=='admin')

def audit(user_id,action,detail=''):
    with db() as c:
        c.execute('INSERT INTO audit(user_id,action,detail,created_at) VALUES(?,?,?,?)',
                  (user_id,action,str(detail)[:1000],now()))

def record_to_dict(r): return dict(r) if r else None

def safe_json(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
