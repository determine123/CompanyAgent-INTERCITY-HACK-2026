"""Deterministic evidence and financial quality gates for proposal reviews.

Inspired by enterprise Agent evaluation/checkpoints, not a substitute for
inventory booking, commercial approval or a model-based assessment.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('NaN')


def assess_result(result: dict) -> dict:
    """Check one persisted agent result without calling the network or trusting LLM prose."""
    plan = result.get('plan') or {}
    selected = plan.get('selected') or []
    budget = _decimal(plan.get('budget_wan'))
    spent = _decimal(plan.get('spent_wan'))
    focus = plan.get('focus_landmark') or ''
    blockers, warnings, passes = [], [], []

    if not budget.is_finite() or not spent.is_finite() or not Decimal('100') <= budget <= Decimal('500'):
        blockers.append({'code':'INVALID_FINANCIALS','message':'预算或已使用金额无效'})
    elif spent < 0 or spent > budget:
        blockers.append({'code':'OVER_BUDGET','message':'方案超过预算或金额为负数'})
    else:
        passes.append({'code':'BUDGET_BOUND','message':'预算上限校验通过'})

    if not selected:
        blockers.append({'code':'NO_MEDIA','message':'未选择可交付媒体，不可进入客户演示审批'})
    line_total = sum((_decimal(x.get('line_total_wan')) for x in selected),Decimal('0'))
    units_ok = all(isinstance(x.get('quantity'),int) and x['quantity']>0 and
                   (x.get('available_count') is None or x['quantity']<=int(x['available_count']))
                   for x in selected)
    if not units_ok:
        blockers.append({'code':'INVALID_QUANTITY','message':'媒体数量超出数据中的可用数或格式不正确'})
    if not line_total.is_finite() or not spent.is_finite() or abs(line_total-spent)>Decimal('0.02'):
        blockers.append({'code':'TOTAL_MISMATCH','message':'所选媒体明细合计与总金额不一致'})
    else:
        passes.append({'code':'TOTAL_RECONCILED','message':'明细金额与汇总一致'})

    evidence_count=sum(bool(focus) and focus in (r.get('coverage_landmarks') or []) for r in selected)
    missing=len(selected)-evidence_count
    if not focus:
        warnings.append({'code':'MISSING_LANDMARK','message':'没有明确目标地标，无法证明品牌与点位匹配'})
    if missing:
        warnings.append({'code':'COVERAGE_GAP','message':f'{missing} 项媒体没有目标地标的精确覆盖证据'})
    else:
        passes.append({'code':'COVERAGE_MATCHED','message':'每一项选中媒体都有目标地标覆盖证据'})

    if plan.get('is_reference_estimate'):
        warnings.append({'code':'REFERENCE_PRICE','message':'价格为脱敏区间情景测算，不是正式报价'})
    if any(str(r.get('availability_basis') or '').lower()=='demo' for r in selected) or 'synthetic_demo' in str(result.get('data_sources',{})).lower():
        warnings.append({'code':'SYNTHETIC_DATA','message':'使用虚构样例媒体数据，仅适合测试和产品演示'})
    if not selected or not all(r.get('availability_basis')=='confirmed_window' for r in selected):
        warnings.append({'code':'SCHEDULE_UNVERIFIED','message':'尚无全部点位的目标档期连续可售证据'})
    # Even source-side availability fields are not a reservation or commitment.
    warnings.append({'code':'NOT_BOOKED','message':'覆盖分析和库存窗口不构成实际锁位或商业承诺'})
    if not result.get('data_sources',{}).get('inventory'):
        warnings.append({'code':'SOURCE_UNKNOWN','message':'库存数据来源缺失'})

    # A proposal with blockers is not even safe to demonstrate. Other checks
    # are transparent caveats which an admin may approve for demo ONLY.
    status = 'blocked' if blockers else ('needs_review' if warnings else 'demo_ready')
    return {'status':status,'demo_approvable':not blockers,'blockers':blockers,
            'warnings':warnings,'passes':passes,
            'evidence':{'matched_items':evidence_count,'total_items':len(selected),
                        'coverage_pct':round(evidence_count/len(selected)*100,1) if selected else 0,
                        'focus_landmark':focus},
            'data_sources':result.get('data_sources',{}),
            'approval_scope':'仅限比赛演示审批；不代表可售、锁位或正式报价'}
