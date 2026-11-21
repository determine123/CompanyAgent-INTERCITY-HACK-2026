"""Conservative import/join of authorized platform media-coverage exports.

An exact match is evidence that a media name appeared in a source export; it is
NOT evidence of booked inventory, unique impressions, or verified coordinates.
"""
from __future__ import annotations
from typing import Any
import math
import csv
import io
import re
import unicodedata


def normalized(value: Any) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or ""))).casefold()


def pick(row: dict, *keys: str) -> Any:
    values = {normalized(k): v for k, v in row.items()}
    for k in keys:
        value = values.get(normalized(k))
        if value is not None and str(value).strip():
            return value
    return None


def nonnegative_number(value: Any) -> float | None:
    if value is None or not str(value).strip():
        return None
    try:
        value = str(value).strip().replace(",", "").replace("米", "").replace("m", "")
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (ValueError, TypeError):
        return None


def infer_media_type(value: Any) -> str:
    s = str(value or "").lower()
    if "地铁" in s or "metro" in s or "subway" in s:
        return "metro"
    if "公交" in s or "巴士" in s or "bus" in s:
        return "bus"
    return ""  # never guess media type solely from a line number



def coverage_rows_from_bytes(data: bytes, filename: str) -> tuple[list[dict[str, Any]], str]:
    """Parse the *actual* New Cloud coverage CSV, which has TWO stacked tables.

    Only 汇总分析 is used. 明细分析 repeats media names and would double-count
    evidence if fed through a generic DictReader. Standard template CSVs also work.
    No executable spreadsheet formula is ever evaluated.
    """
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("gb18030")
    lines = list(csv.reader(io.StringIO(text)))
    if lines and lines[0] and lines[0][0].strip() == "汇总分析":
        if len(lines) < 3:
            raise ValueError("覆盖导出中未发现汇总表头")
        headings = [x.strip() for x in lines[1]]
        needed = {"媒体类型", "媒体名称", "覆盖中心点", "覆盖半径", "最近距离"}
        if not needed.issubset(set(headings)):
            raise ValueError("覆盖导出缺少汇总分析必要字段")
        rows = []
        for cells in lines[2:]:
            if not cells or (len(cells) == 1 and cells[0].strip() == "明细分析"):
                break
            if len(cells) != len(headings):
                raise ValueError("汇总分析出现不规则行，拒绝猜测列对应关系")
            if cells[0].strip() not in ("公交线路", "地铁出入口"):
                raise ValueError("汇总分析包含未识别的媒体类型")
            rows.append(dict(zip(headings, cells)))
            if len(rows) > 12000:
                raise ValueError("每次导入最多12000条")
        return rows, "platform_two_section_export"
    rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) > 12000:
        raise ValueError("每次导入最多12000条")
    return rows, "standard_csv"


def coordinate(value: Any, maximum: float) -> float | None:
    """Spreadsheet export uses ="121.50" wrapping for numeric coordinates."""
    s = str(value or "").strip()
    m = re.fullmatch(r'(?:=)?"?(-?\d+(?:\.\d+)?)"?', s)
    if not m:
        return None
    num = float(m.group(1))
    return num if math.isfinite(num) and -maximum <= num <= maximum else None


def distance_in_meters(value: Any) -> float | None:
    s = str(value or "").strip().replace(",", "")
    if not s:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(米|m|公里|千米|km)?", s, re.I)
    if not m:
        return None
    val = float(m.group(1)) * (1000 if m.group(2) in ("公里", "千米", "km") else 1)
    return val if math.isfinite(val) and val >= 0 else None

def parse_coverage(rows: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    """Accept a coverage-export CSV/XLSX as evidence, not inventory.

    The platform's export schema may change; provide a standard template as a
    fallback. Do not accept audience counts as verified reach metrics.
    """
    results = []
    skipped = 0
    for row in rows:
        name = pick(row, "媒体名称", "线路名称", "公交线路", "线路号", "点位名称", "媒体点位", "media_name", "media")
        uid = pick(row, "媒体ID", "点位编号", "线路编号", "media_id")
        if not name and not uid:
            skipped += 1
            continue
        typ = infer_media_type(pick(row, "媒体类型", "媒介类型", "资源类型", "media_type"))
        data_month = str(pick(row, "数据月份", "人流数据月份", "查询月份", "data_month") or "").strip()
        if data_month and re.search(r"20\d{2}", data_month) and not re.search(r"2023", data_month):
            # Per contest guide, only 2023 crowd data is supported. A wrong-year
            # export must not silently become matching coverage evidence.
            skipped += 1
            continue
        landmark = pick(row, "覆盖中心点", "地标", "门店", "搜索地标", "圈选地标", "商圈", "landmark", "place")
        radius = nonnegative_number(pick(row, "覆盖半径", "查询半径(米)", "覆盖半径(米)", "半径(米)", "查询半径", "半径", "radius_m"))
        distance = distance_in_meters(pick(row, "最近距离", "距离(米)", "距离", "与地标距离", "distance_m"))
        # Platform's 站点经纬度 belongs to a station, not necessarily to an ad unit.
        lat = coordinate(pick(row, "纬度", "lat"), 90)
        lon = coordinate(pick(row, "经度", "lon", "lng"), 180)
        station_lat = coordinate(pick(row, "站点纬度"), 90)
        station_lon = coordinate(pick(row, "站点经度"), 180)
        # Coordinates are preserved as metadata; the UI never plots them as
        # verified unless the user supplies a real coverage export.
        results.append({
            "media_name": str(name or "").strip(),
            "media_id": str(uid or "").strip(),
            "media_type": typ,
            "landmark": str(landmark or "未提供地标").strip(),
            "radius_m": radius,
            "distance_m": distance,
            "lat": lat if lat is not None and lat <= 90 else None,
            "lon": lon if lon is not None and lon <= 180 else None,
            "source": f"COVERAGE:{filename}",
            "data_month": data_month,
            "coverage_points": nonnegative_number(pick(row, "覆盖点数")),
            "nearest_station": str(pick(row, "最近站点") or "").strip(),
            "station_distance_m": distance_in_meters(pick(row, "站点距离")),
            "station_lat": station_lat,
            "station_lon": station_lon,
            "station_coordinate_kind": "公交/地铁站点坐标，不是广告位坐标",
        })
    return {
        "records": results,
        "total_rows": len(rows),
        "usable": len(results),
        "warnings": [
            f"{skipped}行缺少媒体名称或ID，已跳过。" if skipped else "未发现无名称行。",
            "覆盖分析导出只能提供候选点位/线路关联，不证明指定档期可售、成交或实际触达人数。",
            "仅使用媒体名称/编号严格匹配；不做包含关系或模糊匹配，以免错误关联。",
            "此文件是空间覆盖分析，并非人流月度报告；只有单独查询人流时才适用平台的2023年月限制。",
            "最近距离是媒体轨迹点距离；站点距离另列。站点坐标不能当作广告位坐标。",
        ],
    }


def join_coverage(inventory: list[dict], coverage: list[dict]) -> dict[str, Any]:
    """Attach exact, unambiguous evidence to inventory rows without changing price/quantity."""
    if len(inventory) > 12000 or len(coverage) > 12000:
        raise ValueError("最多支持12000条媒体和12000条覆盖结果")
    index: dict[tuple[str, str], set[int]] = {}
    for pos, row in enumerate(inventory):
        typ = str(row.get("media_type", ""))
        for value in (row.get("media_name"), row.get("id")):
            key = normalized(value)
            if key:
                index.setdefault((typ, key), set()).add(pos)
    matched_evidence: dict[int, list[dict]] = {}
    unmatched = ambiguous = 0
    for c in coverage:
        if not isinstance(c, dict):
            unmatched += 1
            continue
        typ = c.get("media_type")
        keys = [normalized(c.get("media_id")), normalized(c.get("media_name"))]
        possible: set[int] = set()
        for key in keys:
            if not key:
                continue
            for t in ([typ] if typ in ("bus", "metro") else ["bus", "metro"]):
                possible.update(index.get((t, key), set()))
        if len(possible) != 1:
            ambiguous += (len(possible) > 1)
            unmatched += (len(possible) == 0)
            continue
        pos = next(iter(possible))
        matched_evidence.setdefault(pos, []).append(c)
    merged=[]
    for i, row in enumerate(inventory):
        clean = dict(row)
        hits = matched_evidence.get(i, [])
        clean["coverage_match_count"] = len(hits)
        clean["coverage_landmarks"] = list(dict.fromkeys(str(h.get("landmark", "")) for h in hits))[:10]
        clean["coverage_source"] = list(dict.fromkeys(str(h.get("source", "")) for h in hits))[:4]
        merged.append(clean)
    return {
        "records": merged,
        "matched_inventory_count": len(matched_evidence),
        "matched_coverage_rows": sum(len(x) for x in matched_evidence.values()),
        "unmatched_coverage_rows": unmatched,
        "ambiguous_coverage_rows": ambiguous,
        "warnings": ["只对严格匹配的媒体标记覆盖分析来源；不能据此推断真实客流、到店或2027可售性。"],
    }
