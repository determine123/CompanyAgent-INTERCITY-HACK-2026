"""Seed only the explicitly user-provided contest handouts in a PRIVATE build.
Public source bundle omits data/contest_private and therefore seeds synthetic DEMO only.
"""
import hashlib,json,csv,io
from pathlib import Path
from .store import db,now,safe_json
from .dataflows import parse_bytes
ROOT=Path(__file__).resolve().parent.parent

def seed():
    with db() as c:
        if c.execute('SELECT 1 FROM datasets LIMIT 1').fetchone():return
        admin=c.execute('SELECT id FROM users WHERE username=?',('admin',)).fetchone()
        if not admin:return
        owner=admin['id']
    priv=ROOT/'data'/'contest_private'
    inv=priv/'bus_snapshot_2026-11-13_reference_price.csv'
    if inv.is_file():
        raw=inv.read_bytes()
        rows=parse_bytes('inventory',raw,inv.name)['records']
        with db() as c:
            c.execute('''INSERT INTO datasets(owner_id,kind,name,origin,records_json,count,checksum,visibility,imported_at,notes)
                      VALUES(?,?,?,?,?,?,?,?,?,?)''',(owner,'inventory','赛事公交台账｜2026-11-13历史快照','contest_private_snapshot',safe_json(rows),len(rows),hashlib.sha256(raw).hexdigest(),'team',now(),
                      '只适合情景优化；不证明2027可售；未授权不得公开'))
        folder=priv/'coverage_exports'
        cover=[]; raw_sum=b''
        for f in sorted(folder.glob('*.csv')) if folder.exists() else []:
            b=f.read_bytes();raw_sum+=b
            cover.extend(parse_bytes('coverage',b,f.name)['records'])
        if cover:
            with db() as c:
                c.execute('''INSERT INTO datasets(owner_id,kind,name,origin,records_json,count,checksum,visibility,imported_at,notes)
                          VALUES(?,?,?,?,?,?,?,?,?,?)''',(owner,'coverage','三商圈覆盖分析｜原始授权导出','contest_private_coverage',safe_json(cover),len(cover),hashlib.sha256(raw_sum).hexdigest(),'team',now(),
                          '仅轨迹覆盖证据，不证明人流、价格或2027库存'))
    else:
        demo=ROOT/'data'/'demo_inventory.csv'
        raw=demo.read_bytes();records=parse_bytes('inventory',raw,demo.name)['records']
        with db() as c:
            c.execute('''INSERT INTO datasets(owner_id,kind,name,origin,records_json,count,checksum,visibility,imported_at,notes)
                      VALUES(?,?,?,?,?,?,?,?,?,?)''',(owner,'inventory','虚构演示库存｜仅用于界面体验','synthetic_demo',safe_json(records),len(records),hashlib.sha256(raw).hexdigest(),'team',now(),
                      '全部记录为虚构示例，禁止作为真实业务证据'))
