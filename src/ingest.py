"""Import conservative CSV/XLSX inventory/price-sheet data; never fabricate prices."""
from __future__ import annotations
import csv, io, re, math
from typing import Any
from openpyxl import load_workbook

ALIASES = {
 "id": ["id", "编号", "资源编号", "媒体编号", "点位编号", "线路编号", "媒体id", "line_id"],
 "media_type": ["media_type", "媒体类型", "媒介类型", "资源类型", "类型"],
 "media_name": ["media_name", "媒体名称", "线路名称", "资源名称", "媒体线路", "线路", "点位名称", "点位"],
 "district": ["district", "行政区", "区域", "所在区", "城区", "商圈"],
 "location": ["location", "位置", "详细地址", "地理位置", "路段"],
 "format": ["format", "广告形式", "媒体形式", "资源级别", "媒体级别", "等级", "媒体类型", "线路等级"],
 "unit_price_wan": ["unit_price_wan", "单元4周刊例价(万元)", "4周刊例价(万元)", "单价(万元/4周)"],
 "available_count": ["available_count", "空车数", "空位数", "空位数", "可售数", "空余数量", "可售数量", "剩余数量"],
 "available_from": ["available_from", "可售开始日期", "档期开始", "开始日期"],
 "available_to": ["available_to", "可售结束日期", "档期结束", "结束日期"],
 "lat": ["lat", "纬度"],
 "lon": ["lon", "lng", "经度"],
 "availability_basis": ["availability_basis", "档期证明类型"],
}
PRICE_ALIASES = {"media_type": ALIASES["media_type"], "format": ALIASES["format"],
                 "unit_price_wan": ALIASES["unit_price_wan"]}

def _key(k: Any) -> str:
    return re.sub(r"\s+", "", str(k or "")).lower().replace("（", "(").replace("）", ")")

def _get(row: dict[str, Any], names: list[str]) -> Any:
    d = {_key(k): v for k, v in row.items()}
    for n in names:
        v = d.get(_key(n))
        if v is not None and str(v).strip() != "":
            return v
    return None

def _type(value: Any, name: Any = "") -> str:
    s = (str(value or "") + " " + str(name or "")).lower()
    if "地铁" in s or "metro" in s or "subway" in s:
        return "metro"
    if "公交" in s or "巴士" in s or "bus" in s or any(k in s for k in ("车身三侧", "大三侧", "全色车")):
        return "bus"
    return ""

def _numeric(value: Any, integer=False) -> int | float | None:
    if value is None or str(value).strip() == "":
        return None
    s = str(value).replace(",", "").strip()
    # Price ranges / ambiguous strings must be reviewed, never approximated.
    if any(x in s for x in ["~", "～", "至", "—", "–"]):
        return None
    try:
        f = float(s)
        if not math.isfinite(f) or f < 0:
            return None
        return int(f) if integer and f.is_integer() else (None if integer else f)
    except ValueError:
        return None

def _date(value: Any) -> str:
    if value is None: return ""
    s = str(value).strip()
    return s[:10].replace("/", "-") if len(s) >= 10 else ""

def rows_from_bytes(data: bytes, filename: str) -> list[dict[str, Any]]:
    low = filename.lower()
    if low.endswith(".csv"):
        try: text = data.decode("utf-8-sig")
        except UnicodeDecodeError: text = data.decode("gb18030")
        result = []
        for row in csv.DictReader(io.StringIO(text)):
            result.append(row)
            if len(result) > 12000: raise ValueError("每次导入最多12000条")
        return result
    if low.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headings = [str(x).strip() if x is not None else "" for x in next(it, [])]
        # 07 媒体刊例价第一行只有标题，真实表头在第二行。
        if len([x for x in headings if x]) <= 1 and ("刊例" in (headings[0] or "")):
            headings = [str(x).strip() if x is not None else "" for x in next(it, [])]
        # 07 媒体刊例价第一行只有标题，真实表头在第二行。
        if len([x for x in headings if x]) <= 1 and ("刊例" in (headings[0] or "")):
            headings = [str(x).strip() if x is not None else "" for x in next(it, [])]
        # 07 媒体刊例价第一行只有标题，真实表头在第二行。
        if len([x for x in headings if x]) <= 1 and ("刊例" in (headings[0] or "")):
            headings = [str(x).strip() if x is not None else "" for x in next(it, [])]
        result = []
        for vals in it:
            if any(v is not None for v in vals): result.append(dict(zip(headings, vals)))
            if len(result) > 12000:
                wb.close()
                raise ValueError("每次导入最多12000条")
        wb.close()
        return result
    raise ValueError("仅支持CSV或XLSX文件")

def parse_inventory(rows: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    parsed, issues = [], []
    for ix, row in enumerate(rows, 2):
        name = _get(row, ALIASES["media_name"])
        t = _type(_get(row, ALIASES["media_type"]), name)
        if not name or not t:
            if len(issues)<15: issues.append(f"第{ix}行：缺少名称或无法判断公交/地铁媒体类型，已跳过")
            continue
        price = _numeric(_get(row, ALIASES["unit_price_wan"]))
        quantity = _numeric(_get(row, ALIASES["available_count"]), integer=True)
        if quantity is None: quantity = 0
        # Additional fields are copied for traceability, not used to claim 2027 availability.
        def optional_number(key):
            return _numeric(_get(row, [key]))
        r = {
            "id": str(_get(row, ALIASES["id"]) or f"IMP-{ix}"),
            "media_type": t, "media_name": str(name),
            "district": str(_get(row, ALIASES["district"]) or "未标注区域"),
            "location": str(_get(row, ALIASES["location"]) or ""),
            "format": str(_get(row, ALIASES["format"]) or ("公交车身" if t=="bus" else "地铁出入口")),
            "unit_price_wan": price, "available_count": quantity,
            "available_from": _date(_get(row, ALIASES["available_from"])),
            "available_to": _date(_get(row, ALIASES["available_to"])),
            "lat": _numeric(_get(row, ALIASES["lat"])),
            "lon": _numeric(_get(row, ALIASES["lon"])),
            "availability_basis": "snapshot", "source": str(_get(row,["source"]) or f"IMPORT:{filename}"),
            "grade": str(_get(row, ["grade", "线路等级"]) or ""),
            "operator": str(_get(row, ["operator", "运营公司"]) or ""),
            "price_min_wan": optional_number("price_min_wan"),
            "price_max_wan": optional_number("price_max_wan"),
            "production_fee_min_wan": optional_number("production_fee_min_wan"),
            "production_fee_upper_wan": optional_number("production_fee_upper_wan") or 0,
            "price_period": str(_get(row, ["price_period"]) or ""),
            "price_basis": str(_get(row, ["price_basis"]) or ""),
            "stock_asof": str(_get(row, ["stock_asof"]) or ("2026-11-13" if "公交媒体台账" in filename else "")),
            "snapshot_contract_count": optional_number("contract_count"),
            "snapshot_reserved_count": optional_number("reserved_count"),
            "snapshot_maintenance_count": optional_number("maintenance_count"),
            "snapshot_renewal_count": optional_number("renewal_count")
        }
        parsed.append(r)
    missing = sum(r["unit_price_wan"] is None for r in parsed)
    if missing:
        issues.append(f"{missing}条媒体缺少明确的「单元4周刊例价(万元)」，不会使用推测价；请上传价格表或手动补全")
    issues.append("导入的「空车数/空位数」按库存快照处理；不能据此确认未来整个投放档期")
    if any(r.get("price_basis", "").startswith("scenario_") for r in parsed):
        issues.append("价格为脱敏区间价的上沿测算，并含每车一次性制作费上沿，不是正式刊例或合同报价")
    return {"records": parsed, "warnings": issues, "total_rows": len(rows), "usable": len(parsed)}

def parse_prices(rows: list[dict[str, Any]], filename: str) -> dict[str, Any]:
    """Exact prices remain exact; privacy-obfuscated bands become upper-bound *scenarios*."""
    parsed=[]
    current_type=""
    for row in rows:
        ty=_get(row, ["媒体类型", "media_type"])
        if ty: current_type=str(ty).replace("\n", "").strip()
        t=_type(current_type)
        fmt=str(_get(row, ["format", "广告形式", "发布线路/位置/级别/形式"]) or "").strip()
        p=_numeric(_get(row, PRICE_ALIASES["unit_price_wan"]))
        if t and p is not None and p>0:
            parsed.append({"media_type":t,"format":fmt,"unit_price_wan":p,"source":f"PRICE:{filename}","price_basis":"explicit"})
            continue
        raw=str(_get(row, ["刊例价（区间化口径）", "区间刊例价"]) or "")
        match=re.search(r"(\d+(?:\.\d+)?)\s*[–—~～-]\s*(\d+(?:\.\d+)?)",raw)
        period=str(_get(row,["发布期"]) or "")
        if t and match and period=="1月" and fmt in ("S","A++","A+"):
            lo,hi=(float(match.group(1)),float(match.group(2)))
            if hi<lo:continue
            pr={"media_type":t,"format":"","grade":fmt,"unit_price_wan":hi,
                "price_min_wan":lo,"price_max_wan":hi,"price_period":"1月",
                "price_basis":"scenario_upper_bound_grade_only","source":f"PRICE:{filename}"}
            if t=="bus":
                pr["production_fee_min_wan"]=0.5
                pr["production_fee_upper_wan"]=1.0
            parsed.append(pr)
    is_bands=any(p.get("price_basis","").startswith("scenario_") for p in parsed)
    warnings=["区间价格/未知折扣不能作为精确合同报价；正式发布需按档期与广告形式复核。"]
    if is_bands:
        warnings.append("原刊例为脱敏区间，按每月价格上沿做预算情景估算；公交每车制作费另按0.5–1万元区间计算。")
    return {"prices":parsed,"warnings":warnings,"total_rows":len(rows)}
