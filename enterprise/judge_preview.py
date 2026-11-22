"""No-credential judge preview backed exclusively by a bundled fictional CSV.

This is deliberately NOT the enterprise database, Hongdou or a third-party LLM.
Every result uses the same deterministic media optimizer as the authenticated
workbench, against fixed source-controlled fictional rows. No writes, secrets
or customer data are involved and no free-text is accepted by the endpoint.
"""
from __future__ import annotations
import csv
from functools import lru_cache
from pathlib import Path
from src.ingest import parse_inventory
from src.planning import optimize_plan

_DEMO = Path(__file__).resolve().parent.parent / 'data' / 'demo_inventory.csv'
_BUDGETS=(100,200,500)
_MEDIA=('both','bus','metro')


def preview(budget_wan:int,medium:str)->dict:
    # Keep strict type validation *before* cache lookup: 200 == 200.0 in Python.
    if type(budget_wan) is not int or budget_wan not in _BUDGETS:
        raise ValueError('演示预算只能为100、200或500万元')
    if medium not in _MEDIA:
        raise ValueError('演示媒体只能为公交、地铁或组合')
    return _render_preview(budget_wan,medium)


@lru_cache(maxsize=9)
def _render_preview(budget_wan:int,medium:str)->dict:
    with _DEMO.open(encoding='utf-8-sig',newline='') as stream:
        parsed=parse_inventory(list(csv.DictReader(stream)),'DEMO-SYNTHETIC')
    records=parsed['records']
    # Explicitly avoid business names/landmarks from the real environment.
    plan=optimize_plan({
        'brand':'模拟饮料品牌A','industry':'食品饮料','budget_wan':budget_wan,
        'start_date':'2027-05-01','weeks':4,'medium':medium,
        'focus_district':'all','focus_landmark':'','coverage_only':False,
        'records':records,
    })
    selected=[{
        'id':str(x['id']), 'media_type':x['media_type'],
        'media_name':str(x.get('media_name','')),
        'district':str(x.get('district','')),
        'quantity':int(x['quantity']),
        'line_total_wan':round(float(x['line_total_wan']),2),
        'coverage_verified':False,
    } for x in plan['selected']]
    return {
        'demo':True,'synthetic_only':True,'real_hongdou_connected':False,
        'runtime':'same_deterministic_optimizer_as_enterprise',
        'business_type':'食品饮料','data_origin':'versioned_repo_fictional_csv',
        'source_file':'data/demo_inventory.csv','sample_size':len(records),
        'start_date':'2027-05-01','weeks':4,'medium':medium,
        'budget_wan':budget_wan,'spent_wan':round(float(plan['spent_wan']),2),
        'remaining_wan':round(float(plan['remaining_wan']),2),
        'item_count':int(plan['item_count']),
        'unit_count':int(plan['unit_count']),
        'selected':selected,
        'selection_truncated':False,
        'evidence':{
            'budget_checked':float(plan['spent_wan'])<=budget_wan,
            'coverage_confirmed':False,
            'future_inventory_available':False,
            'commercial_quote_approved':False,
            'booked':False,'roi_verified':False,
        },
        'risk_questions':[
            '正大广场及目标商圈是否有授权覆盖证据？目前没有导入。',
            '红豆真实库存的 2027 年目标档期是否可售？当前未接入。',
            '正式媒体折扣、制作与执行成本由谁审核？此处仅演示参考预算。',
        ],
        'actions':[
            '确认客户真实生意目标、人群与唯一 Campaign KPI',
            '在企业审批的私有环境核验公交/地铁库存与覆盖导出',
            '由销售、财务、运营确认报价、排期、合同与制作执行',
        ],
        'disclaimer':'所有媒体及价格均为虚构样例；不表示库存实际可售、正式报价、交付承诺或ROI',
    }
