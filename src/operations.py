"""Operational gate checklist grounded in contest handout 02 and provided samples.
This is NOT an automated proof of fulfillment, legal review, booking, or SLA.
"""
from typing import Any

STEPS = [
    ('策略与媒介','确认客户行业、品牌、Campaign、目标门店/地标，导出覆盖分析结果。','未验证', '08 系统使用说明；06 客户brief'),
    ('库存锁位','按 2027 年目标日期在红豆系统核对空车/合同车/预定车及占用明细。','未验证', '08 系统使用说明'),
    ('折扣及合同','核准媒介形式与价格区间、制作费、代理折扣、税费、合同/排期单，以及本合同是否适用“误一补二”等补刊条款。','未验证','07 刊例价；M3 4A订单/直客合同'),
    ('素材定稿','检查广告素材、画面适配、客户审批与媒介内容审核完成。','未验证','02 上下刊流程卡点'),
    ('制作与施工','按数量核实单晚夜间施工能力，需分批时为每批安排可执行日期；留出天气/管制缓冲。','未验证','02 上下刊流程卡点'),
    ('上刊监测','按约定收集上刊照片、日期信息与现场证明，防止错版、漏刊和监拍滞后。','未验证','02 上下刊流程卡点；M4 监测样例'),
    ('下刊与结案','确认下刊时间、下刊照片、效果与完成情况、异常补刊及财务对账。','未验证','M5 结案样本；M3 合同'),
]

def execution_review(plan: dict[str, Any]) -> dict[str, Any]:
    selected = plan.get('selected') or []
    if not isinstance(selected,list):
        raise ValueError('selected 必须为列表')
    qty = sum(max(0,int(x.get('quantity',0))) for x in selected if isinstance(x,dict))
    warnings = [
      '当前所有执行节点均为待确认；仅生成建议清单，不代表可售锁位、制作审批或实际刊播完成。',
      '如本次正式合同适用“误一补二”，需预留可能的补刊资源并经法务/运营核验；不得把样本合同条款自动套用到所有客户。',
      '02 流程说明没有给出单晚施工车辆/点位容量，不能据媒体数量推断准确施工晚数。',
      '06 客户 brief 的“上刊当日照片/下刊后5个工作日”是特定样本要求，不自动成为所有客户的交付SLA。',
    ]
    if plan.get('stock_snapshot_date'):
        warnings.append('库存参考日期为 '+str(plan['stock_snapshot_date'])+'，与目标 '+str(plan.get('start_date',''))+' 档期不同，必须重查。')
    if qty >= 30:
        warnings.append('当前候选单元为 '+str(qty)+'，存在分批夜间安装的可能；需施工方确认窗口、人员和物料。')
    if not selected:
        warnings.append('没有可报价的候选媒介，应补齐库存及价格，不能提交正式媒介排期。')
    return {
        'project_start':plan.get('start_date'), 'project_end':plan.get('end_date'),
        'units_to_schedule':qty, 'ready_for_execution':False,
        'readiness_label':'仅参考提案 / 未完成商业与施工核验',
        'gates':[{'stage':s,'action':a,'status':status,'evidence':ev} for s,a,status,ev in STEPS],
        'warnings':warnings,
        'execution_chain':'品牌/场景 → 覆盖分析 → 红豆档期核验 → 报价与合同 → 素材审核 → 制作/夜间安装 → 上下刊监测 → 结案',
    }
