"""Transparent, deterministic extraction from customer media brief, NOT an LLM.

A sample 2026 LED/outdoor brief is supplied for structure only. It is outside
contest inventory (bus + metro) and date window (2027). No auto-silent mapping.
"""
import re
from typing import Any
from datetime import date

SAMPLE_4A = """【投放需求】某国际品牌 2026 年 5 月上海户外大牌 brief
客户：某国际品牌（品类保密）；目标：品牌形象投放。
媒体形式：城市核心商圈户外大牌（LED 优先，静态大牌备选）。
投放区域：上海核心商圈，陆家嘴、正大广场级客流点位。
投放周期：2026 年 5 月 1 日 – 5 月 10 日，共 10 天。
数量：1 块，可拆两段排期。
素材：4 月下旬提供终稿；年度代理折扣。
上刊当日上刊照片（带报头日期）；下刊后 5 个工作日内下刊照片。
请在 2 个工作日内反馈可售清单、建议排期与折后报价。
"""

DATE_RE = re.compile(r'(20\d{2})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})\s*日?')
AMOUNT_RE = re.compile(r'(?<!\d)(\d+(?:\.\d+)?)\s*(?:万元|万预算)')

def analyze_brief(text: str) -> dict[str, Any]:
    t = text.strip()
    if not t:
        raise ValueError('客户 Brief 不能为空')
    if len(t) > 12000:
        raise ValueError('客户 Brief 最多 12000 字')
    dates = []
    for a,b,c in DATE_RE.findall(t):
        try: dates.append(date(int(a),int(b),int(c)).isoformat())
        except ValueError: continue
    media = []
    if re.search(r'公交|巴士|车身|大三侧',t): media.append('公交车身')
    if re.search(r'地铁|出入口|灯箱',t): media.append('地铁出入口')
    if re.search(r'LED|户外大牌|静态大牌|广告大牌|大屏',t,re.I): media.append('户外大牌/LED（当前赛题媒介范围外）')
    places = [name for name in ['陆家嘴','正大广场','人民广场','新天地','南京西路','徐家汇','上海南站','静安寺','五角场'] if name in t]
    checks = []
    if not AMOUNT_RE.search(t): checks.append('客户预算未明确：必须确认100/200/500万元或比赛允许的区间。')
    if not dates: checks.append('未识别完整投放日期：需确认2027年实际档期。')
    if any(d[:4]!='2027' for d in dates): checks.append('示例/客户 Brief 中含非2027日期，不能直接用于本次赛事档期。')
    if any(x.startswith('户外大牌') for x in media): checks.append('Brief 中包含 LED/户外大牌，超出本次比赛限定的公交车身和地铁出入口；不能擅自替换为公交或地铁。')
    if '折扣' in t: checks.append('客户要求折扣，但赛事只有区间刊例：不得自动提供年度代理折扣。')
    if '监测' in t or '照片' in t: checks.append('客户要求监测照片；具体拍摄、时限与验收标准须按实际合同确认。')
    checks += ['依据门店与地标的实际位置，在赛事可视化平台导出覆盖媒体名单。',
               '在红豆系统按2027目标日期逐条核验合同/预定/空位；未核验前不得承诺可售。']
    return {
        'kind':'deterministic_rules_not_ai', 'media_requested':media,
        'mentioned_dates':dates, 'mentioned_places':places,
        'budget_mentions_wan':[float(x) for x in AMOUNT_RE.findall(t)][:12],
        'response_checklist':['客户品牌与Campaign定位','目标门店/地标和覆盖范围','可售候选媒体清单（线路或点位、等级、数量）','拟投放日期与分批施工说明','刊例区间与未确认折扣、制作费','监测素材与验收依据'],
        'needs_review':checks, 'sample_warning':'06文件为脱敏模拟 brief，不是2027客户真实需求；对外回复需重新确认。'
    }
