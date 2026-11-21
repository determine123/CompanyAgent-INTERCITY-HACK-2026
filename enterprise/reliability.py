"""Deterministic replay and evaluation for authorized CompanyAgent media plans.

Design influences: LangGraph checkpointer snapshots, Agno evaluations, and
PydanticAI validated execution. This uses no third-party agent runtime.
Replaying cannot cause an external booking or a write to a media system.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .quality import assess_result
from .store import safe_json

MANIFEST_VERSION = 1


def digest(value: Any) -> str:
    """Fingerprint structured data; this is NOT a signed or tamper-proof audit."""
    return hashlib.sha256(safe_json(value).encode('utf-8')).hexdigest()


def plan_fingerprint(result: dict) -> str:
    """Compare stable planning outputs, excluding timestamps, trace and prose."""
    variants = result.get('budget_variants') or {}
    return digest({'plan': result.get('plan'), 'budget_variants': variants,
                   'quality': assess_result(result)})


def create_manifest(agent: dict, skills: list[dict], datasets: dict,
                    input_records: dict, source_desc: dict, policy: dict, result: dict) -> dict:
    """Freeze tool/skill permissions and input dataset fingerprints per run."""
    agent_snapshot = {'id': agent['id'], 'name': agent['name'],
                      'instructions': agent['instructions']}
    skills_snapshot = [{'id': s['id'], 'name': s['name'],
                        'instructions': s['instructions'],
                        'tools_json': s['tools_json']} for s in skills]
    return {
        'schema_version': MANIFEST_VERSION,
        'engine': 'fixed-authorized-media-tools',
        'agent': agent_snapshot,
        'skills': skills_snapshot,
        'policy': dict(policy),
        'dataset_ids': {kind: (row['id'] if row else None) for kind, row in datasets.items()},
        'dataset_checksums': {kind: (row['checksum'] if row else None) for kind, row in datasets.items()},
        'record_fingerprints': {kind: digest(input_records[kind]) for kind in ('inventory', 'coverage', 'pricing')},
        'source_desc': dict(source_desc),
        'plan_fingerprint': plan_fingerprint(result),
    }


def evaluation(result: dict) -> dict:
    """Auditable, rule-based demo readiness checks; NOT predictive campaign ROI."""
    quality = assess_result(result)
    plan = result.get('plan') or {}
    variants = result.get('budget_variants') or {}
    checks = [
        {'id': 'financial_guard', 'passed': not any(i['code'] in ('OVER_BUDGET','INVALID_FINANCIALS','TOTAL_MISMATCH') for i in quality['blockers']),
         'detail': '预算与明细金额一致，不超预算'},
        {'id': 'positive_media', 'passed': bool(plan.get('item_count', 0)) and not any(i['code']=='NO_MEDIA' for i in quality['blockers']),
         'detail': '存在可展示的媒体候选'},
        {'id': 'three_budget_variants', 'passed': all(str(v) in variants and 0 <= variants[str(v)].get('spent_wan', -1) <= v for v in (100,200,500)),
         'detail': '100/200/500 万方案分别计算且不超预算'},
        {'id': 'tool_trace', 'passed': any(step.get('tool')=='optimize_budget' and step.get('status')=='ok' for step in result.get('trace', [])),
         'detail': '有可追溯的确定性优化工具执行记录'},
        {'id': 'coverage_evidence', 'passed': bool(quality['evidence']['total_items']) and quality['evidence']['matched_items']==quality['evidence']['total_items'],
         'detail': '所有推荐媒体均有目标商圈覆盖证据'},
        {'id': 'source_provenance', 'passed': bool((result.get('data_sources') or {}).get('inventory')),
         'detail': '保留了库存数据来源'},
    ]
    passed=sum(c['passed'] for c in checks)
    return {'status': 'blocked' if quality['blockers'] else ('passed_with_caveats' if passed==len(checks) else 'needs_review'),
            'checks':checks,'passed':passed,'total':len(checks),
            'caveats':[item['code'] for item in quality['warnings']],
            'scope':'仅评估样例/授权数据下的提案技术质量；不衡量广告收益或正式可售性'}


def replay(manifest: dict, request_json: dict, persisted_result: dict,
           datasets: dict, records: dict) -> dict:
    """Repeat a past run with its frozen tool grants and policy; never call external APIs."""
    from .engine import perform
    if manifest.get('schema_version') != MANIFEST_VERSION:
        return {'status':'unsupported_manifest','verified':False,'issues':['MANIFEST_VERSION_UNSUPPORTED']}
    issues=[]
    for kind in ('inventory','coverage','pricing'):
        ds=datasets.get(kind)
        expected_id=manifest['dataset_ids'].get(kind)
        if (ds['id'] if ds else None) != expected_id:
            issues.append(f'{kind.upper()}_MISSING_OR_REPLACED')
        if ds and ds['checksum'] != manifest['dataset_checksums'].get(kind):
            issues.append(f'{kind.upper()}_DATASET_CHECKSUM_CHANGED')
        if digest(records.get(kind, [])) != manifest['record_fingerprints'].get(kind):
            issues.append(f'{kind.upper()}_RECORDS_CHANGED')
    if issues:
        return {'status':'source_drift','verified':False,'issues':issues}
    if plan_fingerprint(persisted_result) != manifest.get('plan_fingerprint'):
        return {'status':'result_changed','verified':False,'issues':['SAVED_RESULT_CHANGED']}
    agent=manifest['agent']; skills=manifest['skills']
    rerun=perform(request_json, agent, skills,
                  records['inventory'], records['coverage'], manifest['source_desc'],
                  prices=records['pricing'], policy=manifest['policy'])
    actual=plan_fingerprint(rerun)
    verified=actual==manifest['plan_fingerprint']
    return {'status':'matched' if verified else 'mismatch','verified':verified,
            'issues':[] if verified else ['DETERMINISTIC_RESULT_MISMATCH'],
            'original_fingerprint':manifest['plan_fingerprint'],
            'replay_fingerprint':actual,
            'media_items':rerun['plan']['item_count'],
            'budget_wan':rerun['plan']['budget_wan'],
            'note':'使用冻结的 Skill 工具权限、策略与本地数据集重算；不调用外部平台、不预订媒体'}
