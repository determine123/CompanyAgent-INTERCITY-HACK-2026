"""Workshop-specific proposal evidence contract (internal rubric; NOT official scoring).

Only reads authenticated, frozen run artifacts. Never calls Hongdou,
attempts website login, or treats sample inventory as confirmed stock.
"""
from __future__ import annotations

from typing import Any
from .quality import assess_result

FAKE_ORIGINS={"synthetic_demo","demo_synthetic_repo_seed"}
HISTORY_ORIGINS={"contest_private_snapshot","contest_private_coverage"}
KNOWN_UPLOAD_ORIGINS={"manual_authorized_export","manual_upload"}

def source_snapshot(row:Any, *, kind:str)->dict:
    """Return a safe, non-sensitive trace of an input dataset."""
    if row is None:
        return {"kind":kind,"present":False,"class":"missing",
                "dataset_id":None,"checksum_short":None,"record_count":0}
    origin=str(row["origin"])
    source_class=("synthetic_demo" if origin in FAKE_ORIGINS else
                  "historical_reference" if origin in HISTORY_ORIGINS else
                  "uploaded_unverified" if origin in KNOWN_UPLOAD_ORIGINS else
                  "other_unverified")
    return {"kind":kind,"present":True,"class":source_class,
            "dataset_id":int(row["id"]),
            "checksum_short":str(row["checksum"])[:12],
            "record_count":int(row["count"]),
            "snapshot_at":str(row["imported_at"]),
            "commercially_verified":False}

def workshop_readiness(request:dict,result:dict)->dict:
    """An honest evidence checklist; zero official score/ROI/booking claims."""
    plan=result.get("plan") or {}
    hypothesis=result.get("campaign_hypothesis") or {}
    sources=result.get("source_evidence") or {}
    quality=assess_result(result)
    blockers={item["code"] for item in quality["blockers"]}
    inventory=sources.get("inventory") or {}
    coverage=sources.get("coverage") or {}
    selected=plan.get("selected") or []
    variants=result.get("budget_variants") or {}
    budget_ok=(bool(selected) and not blockers.intersection({
        "INVALID_FINANCIALS","OVER_BUDGET","TOTAL_MISMATCH","INVALID_QUANTITY","NO_MEDIA"}))
    three_budget=all(str(v) in variants and
                     isinstance(variants[str(v)].get("spent_wan"),(int,float)) and
                     0<=variants[str(v)]["spent_wan"]<=v for v in (100,200,500))
    source_frozen=bool(inventory.get("present") and inventory.get("checksum_short") and
                       (result.get("replay_manifest") or {}).get("dataset_checksums",{}).get("inventory"))
    coverage_count=(quality.get("evidence") or {}).get("coverage_pct",0)
    coverage_ok=bool(selected and plan.get("focus_landmark") and coverage.get("present")
                     and coverage_count==100)
    checks=[
      ("single_industry","食品饮料单行业范围",
       request.get("industry")=="食品饮料" and plan.get("industry")=="食品饮料",
       "赛题只选一个行业，不以五行业回归冒充本次交付"),
      ("seven_campaign_elements","Campaign 七要素",
       bool(hypothesis.get("complete")),"七项都填写才算输入齐备；不代表客户已经正式确认"),
      ("frozen_inventory_source","库存来源与快照指纹",
       source_frozen,"必须能追溯授权数据集、导入时间和快照指纹"),
      ("budget_feasible","预算与媒体约束",
       budget_ok,"媒体组合明细合计、数量和预算需通过确定性校验"),
      ("budget_scenarios","三档预算独立重算",
       three_budget,"100／200／500 万在同一来源上分别优化，不能同比例捏造"),
      ("business_coverage","商圈覆盖证据",
       coverage_ok,"可视化无已授权 API；必须提供经许可离线导出并精确匹配"),
      ("target_date_stock","目标档期实际可售",
       False,"尚未确认目标日期的红豆真实可售与锁位状态；历史或合成库存不作准"),
      ("formal_pricing","合同正式报价",
       False,"折扣、税费、制作施工成本及商业条款待销售财务审核"),
      ("human_approval","客户确认与执行审批",
       False,"不得自动锁位、发客户、替代法务合同或运营审核"),
    ]
    output=[]
    for key,label,ok,explain in checks:
        output.append({"id":key,"label":label,"status":"evidence_present" if ok else
                       ("blocked" if key=="single_industry" or (key=="budget_feasible" and blockers) else "needs_review"),
                       "explanation":explain})
    passed=sum(x["status"]=="evidence_present" for x in output)
    blocked=any(x["status"]=="blocked" for x in output)
    return {
      "review_version":"internal-workshop-v1",
      "rubric_official":False,"official_proposal_standard_available":False,
      "message":"仅供新云传媒 workshop 需求自检；并非主办方官方评审打分",
      "status":"blocked" if blocked else "draft_needs_human_review",
      "passed_checks":passed,"total_checks":len(output),"checks":output,
      "source_evidence":sources,
      "integration_contract":{
          "hongdou_bus":{"method":"GET","status":"approval_and_schema_pending","live_connected":False},
          "hongdou_metro":{"method":"GET","status":"approval_and_schema_pending","live_connected":False},
          "coverage_visualization":{"status":"no_authorized_api","supported_mode":"approved_offline_export_only"}
      },
      "booking_permitted":False,"commercial_quote_approved":False,"customer_roi_verified":False,
      "next_human_actions":[
          "请客户确认七要素及 KPI 的真实核验方式",
          "由业务人员核对商圈覆盖授权离线导出及快照有效期",
          "红豆公交/地铁仅在企业批准的私有环境做只读联调，核验档期、租户和字段口径",
          "销售、财务、运营与客户依次完成报价、制作、监拍、锁位及合同审批"],
    }
