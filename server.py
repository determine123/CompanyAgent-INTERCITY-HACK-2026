"""CompanyAgent hackathon local server. Default bind: 127.0.0.1, not public internet."""
import csv, io, json, os
from pathlib import Path
from typing import Any
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.planning import optimize_plan
from src.ingest import rows_from_bytes, parse_inventory, parse_prices
from src.brief import analyze_brief, SAMPLE_4A
from src.operations import execution_review
from src.coverage import parse_coverage, join_coverage, coverage_rows_from_bytes
from src.preflight import assess

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="CompanyAgent Hackathon MVP", version="0.9.0")

class PlanInput(BaseModel):
    industry: str = "食品饮料"
    brand: str = "某头部饮料品牌"
    budget_wan: float = 200
    start_date: str = "2027-05-01"
    weeks: int = 4
    medium: str = "both"
    focus_district: str = "all"
    focus_landmark: str = ""
    coverage_only: bool = False
    records: list[dict[str, Any]] = []

class BriefInput(BaseModel):
    text: str

class ExecutionInput(BaseModel):
    plan: dict[str, Any]

class CoverageJoinInput(BaseModel):
    records: list[dict[str, Any]]
    coverage: list[dict[str, Any]]

class PreflightInput(BaseModel):
    plan: dict[str, Any]

class AiInput(BaseModel):
    brand: str
    industry: str
    brief: str = ""
    summary: dict[str, Any]

@app.get("/api/health")
def health():
    return {"ok": True, "ai_enabled": bool(os.getenv("B1X_API_KEY")), "version":"1.0.0"}

@app.get("/api/brief/sample")
def sample_brief():
    return {"text": SAMPLE_4A, "source": "06 客户brief邮件样本（脱敏；2026 LED非本届赛题直接可投媒介）"}

@app.post("/api/brief/analyze")
def parse_brief(data: BriefInput):
    try: return analyze_brief(data.text)
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@app.post("/api/brief/import")
async def import_brief(file: UploadFile = File(...)):
    """In-memory extraction only, no storage, external requests or uploading to LLM."""
    if not file.filename or not file.filename.lower().endswith((".docx", ".txt")):
        raise HTTPException(400, "Brief 导入仅支持 .docx 或 .txt")
    raw = await file.read(2_000_001)
    if len(raw)>2_000_000: raise HTTPException(413, "Brief 文件超过2MB")
    try:
        if file.filename.lower().endswith(".docx"):
            from docx import Document
            d=Document(io.BytesIO(raw))
            lines=[p.text for p in d.paragraphs if p.text.strip()]
            for tbl in d.tables:
                for row in tbl.rows: lines.append(" | ".join(c.text.replace("\n", " ") for c in row.cells))
            text="\n".join(lines)
        else:
            try: text=raw.decode("utf-8-sig")
            except UnicodeDecodeError: text=raw.decode("gb18030")
        text=text[:12000]
        return {"text":text, "analysis":analyze_brief(text), "filename":file.filename,
                "privacy":"仅在本地服务内存中读取；未传给模型或第三方"}
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    except Exception as exc: raise HTTPException(400,"无法解析 Brief，请确认文件有效") from exc

@app.post("/api/execution/review")
def review_execution(data: ExecutionInput):
    try: return execution_review(data.plan)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@app.get("/api/demo")
def demo():
    with (ROOT / "data/demo_inventory.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    result = parse_inventory(rows, "DEMO-SYNTHETIC")
    for record in result["records"]:
        record["source"] = "DEMO-SYNTHETIC"
        record["availability_basis"] = "demo"
    return result | {"demo": True}

@app.get("/api/templates/{kind}")
def import_template(kind: str):
    if kind not in ("inventory", "pricing", "coverage"):
        raise HTTPException(404, "模板不存在")
    path=ROOT/"data"/f"{kind}_template.csv"
    return FileResponse(path, media_type="text/csv; charset=utf-8", filename=path.name)

@app.get("/api/contest")
def contest_reference():
    """Bundled contest handout; private on disk and never a verified 2027 stock feed."""
    path = ROOT / "data/contest_private/bus_snapshot_2026-11-13_reference_price.csv"
    if not path.exists():
        raise HTTPException(404, "比赛参考数据尚未安装，请导入授权的文件")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    data = parse_inventory(rows, path.name)
    data["demo"] = False
    data["is_contest_reference"] = True
    data["snapshot_date"] = "2026-11-13"
    data["warnings"].extend([
        "431条公交台账来自赛事资料01；这是2026-11-13单日快照，不是2027可售数据。",
        "刊例价来自赛事资料07：S约5–7、A++约4–6、A+约3–5万元/辆/月。预算优化仅按区间上沿做风险预留情景测算。",
        "每辆制作费按照表中约5–10千元的上沿1万元计入一次性费用；广告形式差异与具体合同价格待确认。",
        "历史台账无行政区/坐标；用户可导入覆盖分析辅助圈选，但仍缺2027实时库存及完整地铁库存；AA等级缺价而排除。",
    ])
    return data

@app.post("/api/plan")
def plan(data: PlanInput):
    try:
        return optimize_plan(data.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

async def _read_upload(file: UploadFile):
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(400, "仅支持 .csv 或 .xlsx")
    data=await file.read(10_000_001)
    if len(data)>10_000_000: raise HTTPException(413,"文件超过10MB")
    try:
        rows=rows_from_bytes(data,file.filename)
        if len(rows)>12000: raise ValueError("每次导入上限12000条")
        return rows
    except Exception as exc:
        raise HTTPException(400, f"无法解析该文件：{exc}") from exc

@app.post("/api/import")
async def import_inventory(file: UploadFile = File(...)):
    rows=await _read_upload(file)
    return parse_inventory(rows,file.filename or "upload")

@app.post("/api/import-prices")
async def import_prices(file: UploadFile = File(...)):
    rows=await _read_upload(file)
    return parse_prices(rows,file.filename or "pricebook")


@app.get("/api/contest/coverage")
def contest_text_coverage():
    """Preload all three USER-UPLOADED original contest-platform exports, if installed.

    Never contact the platform or suggest the exports verify 2027 inventory.
    Public build has no contest data.
    """
    directory = ROOT / "data" / "contest_private" / "coverage_exports"
    files = sorted(directory.glob("*.csv")) if directory.exists() else []
    if not files:
        return {"records": [], "usable": 0, "total_rows": 0,
                "source_kind": "not_installed", "warnings": ["未安装赛事覆盖分析原始导出。"]}
    all_records, all_warnings, source_counts = [], [], {}
    for path in files:
        rows, schema = coverage_rows_from_bytes(path.read_bytes(),path.name)
        result = parse_coverage(rows, path.name)
        if schema != "platform_two_section_export":
            all_warnings.append(f"{path.name}不是已知的官方两段式CSV布局，请核查")
        all_records.extend(result["records"])
        source_counts[path.name] = result["usable"]
    return {"records": all_records, "total_rows": len(all_records),
            "usable": len(all_records), "source_kind":"user_uploaded_platform_csv_exports",
            "source_counts":source_counts, "warnings":all_warnings + [
                "已按平台汇总分析区段提取媒体，未重复导入明细分析区段。",
                "同名媒体在同一地标可能因站点不同重复出现：保留证据记录，库存严格按唯一媒体匹配。",
                "空间覆盖命中不等于2027年档期可售，也不证明媒体刊例价、客流和ROI。"
            ]}

@app.post("/api/coverage/import")
async def import_coverage(file: UploadFile = File(...)):
    if file.filename and file.filename.lower().endswith(".csv"):
        raw = await file.read(10_000_001)
        if len(raw)>10_000_000: raise HTTPException(413,"文件超过10MB")
        try:
            rows, kind = coverage_rows_from_bytes(raw,file.filename)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(400,f"无法识别覆盖分析CSV：{exc}") from exc
    else:
        rows=await _read_upload(file)
        kind = "standard_xlsx"
    result=parse_coverage(rows, file.filename or "coverage-export")
    result["source_kind"] = kind
    return result

@app.post("/api/coverage/join")
def combine_coverage(data: CoverageJoinInput):
    try:
        return join_coverage(data.records, data.coverage)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc

@app.post("/api/preflight")
def run_preflight(data: PreflightInput):
    try:
        return assess(data.plan)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc

@app.post("/api/ai")
async def ai_strategy(data: AiInput):
    key = os.getenv("B1X_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "未设置 B1X_API_KEY；不影响确定性预算优化")
    # No entire raw customer inventory/CSV is sent to the model. Only aggregate plan metadata.
    s=data.summary
    compact={k:s.get(k) for k in ["budget_wan","spent_wan","remaining_wan","start_date","end_date","item_count","unit_count","district_count","type_totals_wan","is_demo"]}
    compact["district_names"]=list((s.get("district_counts") or {}).keys())[:20]
    compact["schedule_state"]=s.get("schedule_state")
    sys=("你是广告提案策略助理。输出简体中文，150-250字，分为「策略定位」「媒介逻辑」「注意事项」三段。"
         "只描述输入事实和建议；严禁虚构人流、转化率、ROI、点位/合同真实可售性，"
         "严禁说已锁位。模拟数据必须指出仅为演示。价格必须写作参考刊例预算。")
    user=json.dumps({"行业":data.industry[:60],"品牌":data.brand[:80],"客户brief":data.brief[:800],"方案摘要":compact},ensure_ascii=False)
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            r=await client.post("https://token.b1x.work/v1/chat/completions",
                headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
                json={"model":"deepseek-v4.1-flash-1017","messages":[{"role":"system","content":sys},{"role":"user","content":user}],"temperature":0.25,"max_tokens":550})
        r.raise_for_status()
        payload=r.json()
        content=payload["choices"][0]["message"]["content"]
        if not isinstance(content,str): raise ValueError("模型返回非文本内容")
        return {"content":content[:5000],"model":"deepseek-v4.1-flash-1017", "source":"B1X API"}
    except Exception as exc:
        # Intentionally avoid echoing request or key in errors.
        raise HTTPException(502, "模型调用失败，请检查比赛额度、模型可用性和网络；核心提案功能仍可使用") from exc


# Enterprise Agent Hub: fixed tool allowlist and local-only auth (not a public SaaS).
from enterprise.store import init as enterprise_init
from enterprise.api import router as enterprise_router, background_sync
from enterprise.iteration import router as improvement_router
enterprise_init()
from enterprise.seed import seed as enterprise_seed
enterprise_seed()
app.include_router(enterprise_router)
app.include_router(improvement_router)
app.mount("/enterprise", StaticFiles(directory=ROOT/"enterprise_web", html=True), name="enterprise")

@app.on_event("startup")
def enterprise_startup():
    background_sync()

app.mount("/", StaticFiles(directory=ROOT/"web",html=True),name="web")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app,host=os.getenv("HOST","127.0.0.1"),port=int(os.getenv("PORT","8765")),log_level="info")
