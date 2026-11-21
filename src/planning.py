"""Deterministic outdoor-media proposal optimizer (no LLM for numeric decisions)."""
from __future__ import annotations
from collections import Counter
from datetime import date, timedelta
from typing import Any
import math

INDUSTRIES = {
    "银行保险": ["黄浦区", "陆家嘴", "浦东新区", "静安区", "徐汇区"],
    "食品饮料": ["黄浦区", "静安区", "徐汇区", "浦东新区", "长宁区"],
    "保健品": ["徐汇区", "静安区", "长宁区", "杨浦区", "浦东新区"],
    "私立医院": ["徐汇区", "长宁区", "浦东新区", "普陀区", "静安区"],
    "乐园（主题公园）": ["浦东新区", "闵行区", "宝山区", "静安区", "黄浦区"],
}
MEDIA_LABELS = {"bus": "公交车身", "metro": "地铁出入口"}

def _date_or_none(value: Any) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10].replace("/", "-"))
    except ValueError:
        return None


def optimize_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Select available media units using transparent heuristic, not false impact metrics.

    Price convention: unit_price_wan is catalog price in 10k RMB per FOUR weeks per unit.
    Campaign duration uses ceil(days/28) billing cycles to avoid underquoting.
    A positive stock snapshot is NOT evidence of an available future booking window.
    """
    budget = float(payload.get("budget_wan", 200))
    if not math.isfinite(budget) or not 100 <= budget <= 500:
        raise ValueError("预算需在100至500万元之间")
    industry = str(payload.get("industry", "食品饮料"))
    brand = str(payload.get("brand", "未指定品牌")).strip()[:120] or "未指定品牌"
    start = _date_or_none(payload.get("start_date", "2027-05-01"))
    weeks = int(payload.get("weeks", 4))
    if not start or start.year != 2027 or weeks not in (4, 8, 12):
        raise ValueError("请选择2027年的开始日期及4/8/12周周期")
    end = start + timedelta(days=weeks * 7 - 1)
    if end.year != 2027:
        raise ValueError("档期必须完整落在2027年")
    medium = str(payload.get("medium", "both"))
    if medium not in ("both", "bus", "metro"):
        raise ValueError("媒体类型不支持")
    focus_district = str(payload.get("focus_district", "all"))
    focus_landmark = str(payload.get("focus_landmark", "")).strip()[:100]
    coverage_only = bool(payload.get("coverage_only", False))
    records = payload.get("records", [])
    if not isinstance(records, list) or len(records) > 12000:
        raise ValueError("媒体记录上限12000条")

    candidates = []
    input_is_reference = any(str(r.get("price_basis", "")).startswith("scenario_") for r in records if isinstance(r, dict))
    reasons = Counter()
    source_counts = Counter()
    seen_ids = set()
    cycles = math.ceil(weeks * 7 / 28)
    for raw in records:
        if not isinstance(raw, dict):
            reasons["无效记录"] += 1
            continue
        t = str(raw.get("media_type", ""))
        if t not in MEDIA_LABELS or (medium != "both" and medium != t):
            continue
        source_counts[str(raw.get("source", "unknown"))] += 1
        if coverage_only and (not raw.get("coverage_match_count") or (focus_landmark and focus_landmark not in (raw.get("coverage_landmarks") or []))):
            reasons["覆盖证据不足（按选中地标过滤）"] += 1
            continue
        identity = f"{t}:{str(raw.get('id', ''))}"
        if identity in seen_ids:
            reasons["重复媒体ID（已去重）"] += 1
            continue
        seen_ids.add(identity)
        try:
            price = float(raw.get("unit_price_wan"))
            quantity = int(float(raw.get("available_count", 0)))
        except (TypeError, ValueError):
            reasons["缺少可用刊例价或数量"] += 1
            continue
        if not (math.isfinite(price) and price > 0 and 0 < quantity <= 5000):
            reasons["无可用库存或价格"] += 1
            continue
        # The contest price sheet is monthly and intervalized; for a 4/8/12-week scenario
        # one 28-day cycle is treated as one MONTH, explicitly a planning assumption.
        production_fee = float(raw.get("production_fee_upper_wan") or 0)
        if not math.isfinite(production_fee) or production_fee < 0:
            reasons["无效制作费"] += 1
            continue
        publication_upper = round(price * cycles, 4)
        price = round(publication_upper + production_fee, 4)
        if price > budget:
            reasons["单价超出预算"] += 1
            continue
        date_start = _date_or_none(raw.get("available_from"))
        date_end = _date_or_none(raw.get("available_to"))
        # Date-window metadata is only candidate-filtering information, never a booking guarantee.
        if (date_start and date_start > start) or (date_end and date_end < end):
            reasons["档期不匹配"] += 1
            continue
        district = str(raw.get("district", "未标注区域"))
        preferred = INDUSTRIES.get(industry, [])
        industry_fit = (22 if district in preferred else 12)
        district_fit = 17 if focus_district != "all" and district == focus_district else 0
        if focus_district != "all" and district != focus_district:
            industry_fit -= 5
        level = 8 if "核心" in str(raw.get("format", "")) else 4
        source_landmarks = raw.get("coverage_landmarks") or []
        # Prefer evidence-linked media only for a user-selected exact landmark.
        coverage_fit = 30 if focus_landmark and focus_landmark in source_landmarks else 0
        base = 30 + industry_fit + district_fit + level + coverage_fit
        cand = dict(raw)
        cand.update(unit_price_wan=round(price, 2), available_count=quantity,
                    _fit_score=base, _raw_unit_price_wan=float(raw.get("unit_price_wan")),
                    _publication_upper_wan=publication_upper, _production_upper_wan=production_fee,
                    _verified_window=bool(date_start and date_end) and str(raw.get("availability_basis")) == "confirmed_window")
        candidates.append(cand)

    # Deterministic greedy with diminishing returns for repeatedly selecting one area or inventory entry.
    allocation: dict[str, dict[str, Any]] = {}
    area_counts = Counter()
    type_counts = Counter()
    remaining = round(budget, 4)
    for _ in range(12000):
        best = None
        best_value = -float("inf")
        for r in candidates:
            key = str(r.get("media_type"))+":"+str(r.get("id"))
            used = allocation.get(key, {}).get("quantity", 0)
            if used >= r["available_count"] or r["unit_price_wan"] > remaining + 1e-6:
                continue
            district = str(r.get("district", ""))
            media_type = r["media_type"]
            # Repeated placements in the same district receive diminishing benefits.
            diversity = 16 / (1 + area_counts[district] * 0.5)
            mix = 12 if medium == "both" and type_counts[media_type] == 0 else 0
            penalty = 0.75 * used
            score = (r["_fit_score"] + diversity + mix - penalty) / (r["unit_price_wan"] ** 0.42)
            if score > best_value or (abs(score - best_value) < 1e-9 and key < str(best.get("id") if best else "~")):
                best_value = score
                best = r
        if best is None:
            break
        key = str(best.get("media_type"))+":"+str(best.get("id"))
        if key not in allocation:
            allocation[key] = {k: v for k, v in best.items() if not k.startswith("_")}
            allocation[key]["quantity"] = 0
            allocation[key]["line_total_wan"] = 0
        allocation[key]["quantity"] += 1
        allocation[key]["publication_upper_wan"] = round(allocation[key]["quantity"] * best["_publication_upper_wan"], 2)
        allocation[key]["production_upper_wan"] = round(allocation[key]["quantity"] * best["_production_upper_wan"], 2)
        allocation[key]["line_total_wan"] = round(allocation[key]["quantity"] * best["unit_price_wan"], 2)
        area_counts[str(best.get("district", ""))] += 1
        type_counts[best["media_type"]] += 1
        remaining = round(remaining - best["unit_price_wan"], 4)

    selected = sorted(allocation.values(), key=lambda r: (-r["line_total_wan"], str(r["id"])))
    spent = round(sum(r["line_total_wan"] for r in selected), 2)
    known_districts = {r.get("district") for r in selected if str(r.get("district", "")) not in ("未提供定位", "未标注区域", "")}
    coverage_matched_selected = sum(1 for r in selected if int(r.get("coverage_match_count") or 0)>0)
    coverage_places = sorted(set(place for r in selected for place in (r.get("coverage_landmarks") or [])))
    all_verified = bool(selected) and all(r.get("availability_basis") == "confirmed_window" for r in selected)
    # Never describe automatic planned inventory as booked or guaranteed.
    schedule_state = "来源含连续可售窗口字段；仍需红豆系统复核与锁位" if all_verified else "仅候选排期：需回红豆系统核对占用明细与锁位"
    return {
        "brand": brand, "industry": industry, "budget_wan": budget,
        "start_date": start.isoformat(), "end_date": end.isoformat(), "weeks": weeks,
        "medium": medium, "focus_district": focus_district, "focus_landmark": focus_landmark,
        "coverage_only": coverage_only,
        "selected": selected, "item_count": len(selected), "unit_count": sum(r["quantity"] for r in selected),
        "candidate_count": len(candidates), "district_count": len(known_districts),
        "spent_wan": spent, "remaining_wan": round(budget - spent, 2),
        "utilization_pct": round(100 * spent / budget, 1),
        "type_counts": dict(type_counts), "type_totals_wan": {
            t: round(sum(r["line_total_wan"] for r in selected if r["media_type"] == t), 2)
            for t in MEDIA_LABELS
        },
        "district_counts": {d:n for d,n in area_counts.items() if d in known_districts}, "excluded": dict(reasons),
        "coverage_matched_selected": coverage_matched_selected,
        "coverage_landmarks": coverage_places[:30],
        "estimated_publication_upper_wan": round(sum(r.get("publication_upper_wan", r["line_total_wan"]) for r in selected),2),
        "estimated_production_upper_wan": round(sum(r.get("production_upper_wan",0) for r in selected),2),
        "is_reference_estimate": input_is_reference,
        "stock_snapshot_date": "2026-11-13" if any(str(r.get("stock_asof"))=="2026-11-13" for r in records if isinstance(r, dict)) else "",
        "location_state": (f"已按媒体名称严格关联 {coverage_matched_selected} 条覆盖分析来源；并非地理坐标或客流核验" if coverage_matched_selected else "资料未提供门店坐标/线路地理覆盖，区域与客流分析待赛事平台导出") if selected and not known_districts else "已有部分区域信息，真实覆盖仍需可视化平台核对",
        "schedule_state": schedule_state,
        "assumptions": [
            "赛事参考价格使用脱敏月刊例价区间上沿，投放周期按每28天近似1个月、向上取整；公交制作费按每车一次性区间上沿计入；仍不含税费、折扣及其他执行费。" if input_is_reference else "每28天按1周期计算媒介费，当前普通导入未自动加制作费、税费或折扣。",
            "匹配评分是可解释的业务启发式，不是实际触达人数或ROI预测。",
            "媒体覆盖数据只按严格名称/ID匹配；与目标地标一致的来源记录可提高候选优先级，但不证明真实人流或2027年的可售档期。",
            "静态库存快照不能保证2027年指定档期可售；最终排期须回红豆系统逐条复核。",
            "本次赛事附件01公交台账记录的是2026-11-13单日查询快照，不能作为2027年实时可售证明。" if input_is_reference else "模拟数据仅用于功能演示，不得作为真实媒体库存或对客报价。",
            "赛事附件07仅含脱敏区间化价格；本方案使用各等级公交月刊例区间上沿、每车制作费上沿1万元测算，且假设每28天按1个月计费。未确定广告形式差价/折扣/税费，最终必须人工复核。" if input_is_reference else "价格为每28天一个简化计费周期，未计算折扣、税费和制作安装费。",
            "当前仅有431条公交历史库存和三个商圈空间覆盖CSV；仍缺真实地铁库存与2027完整档期，不得宣称地铁可售或真实客流。" if input_is_reference else "真实地图、客流和ROI尚未接入。"
        ],
        "source_counts": dict(source_counts),
        "is_demo": bool(selected) and all(str(r.get("source", "")).startswith("DEMO") for r in selected),
        "needs_review": True,
    }
