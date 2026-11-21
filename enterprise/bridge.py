"""Read-only reconciliation of explicitly authorized Hongdou exports with coverage.

A strict match shows the same medium appears in a coverage export and an
inventory snapshot. It does NOT prove sellability in an arbitrary 2027 window.
"""
from __future__ import annotations
from collections import Counter
from src.coverage import join_coverage
from .engine import canonical_place


def reconcile(inventory:list[dict], coverage:list[dict], *, landmark:str='', inventory_origin:str='', coverage_origin:str='',
              inventory_checksum:str='', coverage_checksum:str=''):
    if len(inventory)>12000 or len(coverage)>12000:raise ValueError('数据行超过上限')
    match=join_coverage(inventory,coverage)
    focus=canonical_place(landmark) if landmark else ''
    linked=[]
    for row in match['records']:
        places=[canonical_place(x) for x in row.get('coverage_landmarks',[])]
        if not focus or focus in places:
            if row.get('coverage_match_count',0):
                linked.append({'media_type':row.get('media_type'), 'media_name':row.get('media_name'),
                               'source_id':row.get('id'), 'coverage_points':row.get('coverage_match_count',0),
                               'available_count_snapshot':row.get('available_count',0),
                               'stock_asof':row.get('stock_asof',''),
                               'window_start':row.get('available_from',''),
                               'window_end':row.get('available_to',''),
                               'origin':row.get('source','')})
    duplicated=max(0,len(coverage)-len(set((x.get('media_type'),x.get('media_name'),canonical_place(x.get('landmark'))) for x in coverage)))
    return {
        'summary':{'inventory_rows':len(inventory),'coverage_rows':len(coverage),
                   'matched_inventory_rows':match['matched_inventory_count'],
                   'matched_coverage_rows':match['matched_coverage_rows'],
                   'unmatched_coverage_rows':match['unmatched_coverage_rows'],
                   'ambiguous_coverage_rows':match['ambiguous_coverage_rows'],
                   'repeated_evidence_rows':duplicated,
                   'filtered_landmark':focus,'filtered_matched_items':len(linked),
                   'bus_matched':sum(x['media_type']=='bus' for x in linked),
                   'metro_matched':sum(x['media_type']=='metro' for x in linked)},
        'matched_media':linked[:120],
        'provenance':{'inventory':{'origin':inventory_origin,'sha256':inventory_checksum},
                      'coverage':{'origin':coverage_origin,'sha256':coverage_checksum}},
        'verified_for_2027':False, 'booking_state':'NOT_RESERVED',
        'warnings':['空间覆盖与库存快照的严格关联不构成目标2027档期可售证明。',
                    '正式方案必须复核红豆按投放日期查询的空车、合同、预定占用及有效报价。',
                    '不能把相同媒体不同站点的覆盖记录视为独立可售库存。']}
