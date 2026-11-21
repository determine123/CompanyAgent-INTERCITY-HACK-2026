"""Evidence-constrained impact analysis of advertising campaign changes.

This module generates a reviewable work order dependency DAG; it does not
reserve inventory, alter schedules, send notifications, or update a real ERP.
"""
from __future__ import annotations
from datetime import date

CHANGE_TYPES = {
    'creative_revision': '客户改稿',
    'vehicle_reassignment': '车辆换线',
    'vehicle_maintenance': '车辆进保',
    'city_restriction': '城市管制',
    'contractor_rework': '外包返工',
    'weather_monitoring': '监拍雨天',
}

# Each stage is a read-only planning suggestion. The sequence is deliberate:
# verify source first, then inventory / route, schedule, production, installer,
# and finally customer confirmation.
STAGES = {
 'source_check': ('核对变更单与来源', '销售/客户经理', '核对变更生效时间、联系人与证据附件'),
 'inventory': ('核验候选车线及档期', '媒体资源管理员', '在红豆系统核对替代车线、空车/合同车/预定车和2027连续档期'),
 'schedule': ('重新计算排期', '排期专员', '根据库存、合同与截止日期生成待审核的新排期'),
 'production': ('复核制作单与画面', '设计/制作供应商', '核对版面、版本、改稿次数与重新制作成本'),
 'installation': ('重排上刊与施工计划', '施工负责人', '协调安装队、作业窗口、监测时间及现场限制'),
 'monitor': ('补充上刊监测与结案证据', '监测专员', '安排监拍补拍，保存证据与异常说明'),
 'customer': ('客户通知与重新确认', '销售/客户经理', '向客户提交变更影响、报价待确认项及修订方案'),
}
AFFECTED = {
 'creative_revision': ('source_check','production','installation','customer'),
 'vehicle_reassignment': ('source_check','inventory','schedule','production','installation','customer'),
 'vehicle_maintenance': ('source_check','inventory','schedule','installation','customer'),
 'city_restriction': ('source_check','inventory','schedule','installation','customer'),
 'contractor_rework': ('source_check','production','installation','monitor','customer'),
 'weather_monitoring': ('source_check','schedule','monitor','customer'),
}
FIELD_KEYS = {
 'inventory': '车线绑定', 'schedule': '排期', 'production':'制作单',
 'installation':'施工计划', 'monitor':'监测/结案', 'customer':'客户通知',
}

def analyze_change(result:dict, *, kind:str, effective_date:str, note:str) -> dict:
    """Plan a change against an existing frozen result without mutating it."""
    if kind not in CHANGE_TYPES:
        raise ValueError('不支持的变更来源')
    if len(note.strip()) < 4 or len(note) > 1000:
        raise ValueError('变更说明须为4到1000字')
    try: when = date.fromisoformat(effective_date)
    except (ValueError,TypeError) as exc: raise ValueError('请输入有效的变更日期') from exc
    if when.year != 2027:raise ValueError('当前赛事投放变更限于2027年')
    plan = result.get('plan') or {}
    if not plan or not isinstance(plan.get('selected'),list):
        raise ValueError('原任务缺少可核验的投放方案')
    steps=[]
    affected=AFFECTED[kind]
    for i,key in enumerate(affected,1):
        title,owner,detail=STAGES[key]
        steps.append({'order':i, 'id':key,'title':title,'owner':owner,
                      'detail':detail,'status':'requires_human_confirmation',
                      'depends_on':[affected[i-2]] if i>1 else []})
    keys={FIELD_KEYS[x] for x in affected if x in FIELD_KEYS}
    missing=[]
    if not plan.get('selected'): missing.append('原提案尚无可选媒体')
    if not plan.get('focus_landmark'):missing.append('未指定目标商圈及覆盖分析')
    if not all(x.get('availability_basis')=='confirmed_window' for x in plan['selected']):
        missing.append('缺少全部媒体的2027目标档期连续可售证明')
    if kind in ('creative_revision','contractor_rework'):
        missing.append('缺少签署后的画面版本与制作成本确认')
    if kind in ('vehicle_reassignment','vehicle_maintenance','city_restriction'):
        missing.append('替代车辆/线路未在红豆系统核实并获得锁位授权')
    # Reject unsupported numerical side effects: no price/date adjustment is guessed.
    return {'case':'media_change_impact','change_type':kind,'change_label':CHANGE_TYPES[kind],
            'original_plan':{'brand':str(plan.get('brand') or '客户待确认'),
                             'budget_wan':plan.get('budget_wan'),
                             'start_date':plan.get('start_date'),
                             'focus_landmark':str(plan.get('focus_landmark') or ''),
                             'selected_media_count':len(plan['selected'])},
            'effective_date':effective_date,'change_note':note.strip(),
            'status':'needs_human_review',
            'affected_forms':sorted(keys),
            'dependency_steps':steps,
            'evidence_gaps':missing,
            'requires_new_quote':kind in ('creative_revision','vehicle_reassignment','contractor_rework'),
            'real_system_mutated':False,'customer_notified':False,'inventory_reserved':False,
            'customer_notice_draft':('关于贵方'+str(plan.get('brand') or '本次')+'户外广告计划：因'+CHANGE_TYPES[kind]+
                '，拟对'+ '、'.join(sorted(keys))+'进行重新核对。新排期、费用及施工安排须在库存和供应商确认后另行发送，当前不构成正式变更承诺。'),
            'limitations':'仅生成待审核的影响分析及责任清单；未操作红豆、未修改客户排期、未发送通知。'}
