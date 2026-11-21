"""Authorized data ingestion only. No cookie reuse, UI login automation or captcha bypass."""
from __future__ import annotations
import hashlib, os, re, urllib.parse, ipaddress, socket, json
from pathlib import Path
import httpx
from src.ingest import rows_from_bytes,parse_inventory,parse_prices
from src.coverage import coverage_rows_from_bytes,parse_coverage
from .store import STATE,db,now,safe_json

MAX_BYTES=10_000_000

def parse_bytes(kind,raw,filename):
    if len(raw)>MAX_BYTES: raise ValueError('文件超过10MB')
    if not filename.lower().endswith(('.csv','.xlsx')): raise ValueError('只接受CSV/XLSX文件')
    if kind=='coverage':
        if filename.lower().endswith('.csv'):
            rows,_=coverage_rows_from_bytes(raw,filename)
        else: rows=rows_from_bytes(raw,filename)
        result=parse_coverage(rows,filename)
    elif kind=='inventory': result=parse_inventory(rows_from_bytes(raw,filename),filename)
    elif kind=='pricing':
        raw_result=parse_prices(rows_from_bytes(raw,filename),filename)
        result={'records':raw_result['prices'],'warnings':raw_result.get('warnings',[])}
    else: raise ValueError('不支持的数据类型')
    if not result['records']: raise ValueError('没有可用数据行，检查表头和媒体类型')
    return result

def ingest(kind,raw,filename,owner_id,origin='manual_upload',visibility='team',source_id=None):
    if visibility not in ('team','private'): raise ValueError('可见范围错误')
    res=parse_bytes(kind,raw,filename)
    checksum=hashlib.sha256(raw).hexdigest()
    with db() as c:
        existing=c.execute('SELECT id FROM datasets WHERE kind=? AND checksum=? AND owner_id=?',
                           (kind,checksum,owner_id)).fetchone()
        if existing: return {'dataset_id':existing['id'],'duplicate':True,'record_count':len(res['records']), 'warnings':res.get('warnings',[])}
        cur=c.execute('''INSERT INTO datasets(owner_id,kind,name,origin,records_json,count,checksum,visibility,imported_at,source_id,notes)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                      (owner_id,kind,filename[:200],origin,safe_json(res['records']),len(res['records']),checksum,visibility,now(),source_id,
                       '导入的库存/覆盖数据不构成2027可售、价格或实际曝光的独立核实'))
        return {'dataset_id':cur.lastrowid,'duplicate':False,'record_count':len(res['records']), 'warnings':res.get('warnings',[])}

def approved_url(url):
    # Admin must explicitly set allowlist; NO unrestricted URL fetching / localhost / metadata endpoints.
    allow={x.strip().lower() for x in os.getenv('COMPANYAGENT_ALLOWED_DATA_HOSTS','').split(',') if x.strip()}
    u=urllib.parse.urlsplit(url)
    if not allow or u.scheme!='https' or not u.hostname or u.hostname.lower() not in allow or u.username or u.password or u.port not in (None,443):
        raise ValueError('仅允许管理员显式列入环境变量白名单的 HTTPS 主机（标准443端口）')
    if not u.path.lower().endswith(('.csv','.xlsx')) or u.query or u.fragment:
        raise ValueError('接口需直返CSV/XLSX，URL不得含查询参数/片段')
    # Reject private IP literals and private DNS results to reduce SSRF risk.
    try:
        addresses=socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
        if not addresses: raise ValueError('未解析到地址')
        for ans in addresses:
            ip=ipaddress.ip_address(ans[4][0])
            if not ip.is_global: raise ValueError('目标主机解析为非公网IP')
    except OSError as exc: raise ValueError('目标域名无法解析') from exc
    return u

def pull_source(source):
    approved_url(source['url'])
    headers={'Accept':'text/csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    token_env=source['token_env']
    if token_env:
        if not re.fullmatch(r'COMPANYAGENT_SOURCE_[A-Z0-9_]+_TOKEN',token_env): raise ValueError('凭证变量名不符合规范')
        token=os.getenv(token_env)
        if not token: raise ValueError('服务端尚未配置指定凭证环境变量')
        headers['Authorization']='Bearer '+token
    # Redirects disabled so a whitelisted host cannot redirect to a forbidden destination.
    with httpx.Client(timeout=15.0,follow_redirects=False,trust_env=False) as client:
        with client.stream('GET',source['url'],headers=headers) as resp:
            if resp.status_code!=200: raise ValueError('数据源未返回HTTP 200')
            chunks=[]; total=0
            for part in resp.iter_bytes(32768):
                total+=len(part)
                if total>MAX_BYTES: raise ValueError('远程文件超过10MB')
                chunks.append(part)
    raw=b''.join(chunks)
    filename=urllib.parse.unquote(urllib.parse.urlsplit(source['url']).path.rsplit('/',1)[-1])
    return ingest(source['kind'],raw,filename,source['owner_id'],origin='approved_https_export',source_id=source['id'])

def poll_folder(owner_id):
    """Scan private local drop folder. Save exports here from the browser; do not read browser cookies."""
    folder=STATE/'imports'
    folder.mkdir(parents=True,exist_ok=True)
    out=[]
    for file in sorted(folder.iterdir()):
        if not file.is_file() or file.is_symlink() or file.suffix.lower() not in ('.csv','.xlsx'):continue
        if file.name.startswith('inventory_'): kind='inventory'
        elif file.name.startswith('coverage_'): kind='coverage'
        elif file.name.startswith('pricing_'): kind='pricing'
        else: continue
        if file.stat().st_size>MAX_BYTES: continue
        try:
            out.append({'file':file.name,**ingest(kind,file.read_bytes(),file.name,owner_id,'watched_export_folder')})
        except Exception as e:
            out.append({'file':file.name,'error':str(e)[:180]})
    return out
