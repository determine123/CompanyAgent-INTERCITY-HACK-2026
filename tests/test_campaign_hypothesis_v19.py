"""INTERCITY HACK 新云传媒评委七要素 Campaign 假设书与预算复用验收。"""
import pytest
from fastapi.testclient import TestClient
from enterprise.campaign import build_hypothesis, scenario_changes
from enterprise.proposal import render_proposal
from server import app

def request_data():
    return {
        "agent_id":1,
        "brief":"上海模拟饮料品牌开展夏季新品活动，以便利店试饮与到店为主",
        "industry":"食品饮料",
        "brand":"模拟饮料品牌A",
        "budget_wan":200,
        "start_date":"2027-06-01",
        "weeks":8,
        "medium":"both",
        "landmark":"正大广场",
        "coverage_only":False,
        "business_goal":"上海便利店新品试饮和铺货转化（模拟假设）",
        "campaign_goal":"到店",
        "target_audience":"18–30 岁上海通勤白领（模拟画像）",
        "success_kpi":"活动扫码次数（目标由客户确认）",
        "measurement_method":"客户扫码后台核验，现场上下刊照片与结案报告",
    }

def test_seven_requirements_complete_only_on_explicit_business_inputs():
    req=request_data()
    p={"start_date":"2027-06-01","end_date":"2027-07-26","budget_wan":200}
    h=build_hypothesis(req,p)
    assert h["complete"] is True
    assert h["completed"]==h["required"]==7
    assert all(e["complete"] for e in h["elements"])
    assert h["elements"][-1]["value"].startswith("指标：")
    assert h["approval_status"].startswith("待客户确认")
    assert "2027" in h["elements"][4]["value"]
    assert "公交车身 + 地铁出入口" in h["elements"][5]["value"]

def test_missing_goals_not_auto_fabricated_from_brief_text():
    p={"start_date":"2027-06-01","end_date":"2027-06-28","budget_wan":100}
    req={"brand":"模拟品牌","industry":"食品饮料","campaign_goal":"抢占市场","business_goal":"",
         "target_audience":"","success_kpi":"","measurement_method":"","medium":"bus"}
    h=build_hypothesis(req,p)
    assert not h["complete"]
    assert h["completed"]==3
    assert len(h["missing"])==4
    assert h["elements"][2]["value"]=="待客户确认"
    assert not any("预测" in el["value"] for el in h["elements"])

def test_budget_ladder_is_independently_compared_not_scaled():
    def plan(rows,budget):
        return {"spent_wan":float(len(rows))*10,"remaining_wan":budget-len(rows)*10,
                "item_count":len(rows),"unit_count":sum(x["quantity"] for x in rows),
                "selected":rows}
    x={"id":"A","media_type":"bus","quantity":1}
    y={"id":"B","media_type":"metro","quantity":2}
    v={"100":plan([x],100),"200":plan([x,y],200),"500":plan([{"id":"A","media_type":"bus","quantity":2}],500)}
    out=scenario_changes(v)
    assert [a["budget_wan"] for a in out]==[100,200,500]
    assert out[1]["added_vs_prior_units"]==2
    assert out[1]["removed_vs_prior_units"]==0
    assert out[2]["added_vs_prior_units"]==1
    assert out[2]["removed_vs_prior_units"]==2
    assert all(a["not_real_booking"] for a in out)

def test_portable_html_has_assumptions_and_pre_escaped_data():
    req=request_data()
    req["business_goal"]="<img src=x onerror=alert(1)>"
    h=build_hypothesis(req,{"start_date":"2027-06-01","end_date":"2027-07-26","budget_wan":200})
    sample={"budget_wan":200,"brand":"模拟饮料品牌A","industry":"食品饮料","start_date":"2027-06-01",
            "end_date":"2027-07-26","spent_wan":20,"remaining_wan":180,
            "unit_count":1,"item_count":1,"selected":[{"id":"DEMO-1","media_type":"bus",
                                                        "media_name":"样例线路","quantity":1,
                                                        "line_total_wan":20}]}
    result={"plan":sample,"campaign_hypothesis":h,"scenario_changes":scenario_changes({"200":sample}),
            "data_sources":{"inventory":"合成"}, "budget_variants":{"200":sample}}
    quality={"status":"needs_review","evidence":{"matched_items":0,"total_items":1},"warnings":[],"blockers":[]}
    html=render_proposal(55,req,result,quality,{"status":"pending"})
    assert "七要素" in html
    assert "budgetButtons" in html
    assert "hypothesisRows" in html
    assert "scenarioRows" in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "\\u003cimg" in html

@pytest.fixture
def auth():
    with TestClient(app) as client:
        r=client.post("/enterprise/api/auth/login",
                      json={"username":"admin","password":"CI-generated-isolated-password-ONLY"})
        assert r.status_code==200,r.text
        client.headers["X-CSRF-Token"]=r.json()["csrf"]
        yield client

def test_client_ui_contains_business_measurement_fields_and_no_real_brand_default(auth):
    text=auth.get("/enterprise/").text
    assert all(term in text for term in ("clientBusinessGoal","clientCampaignGoal",
                                        "clientAudience","clientKpi","clientMeasurement",
                                        "clientHypothesisStatus","clientScenarioRows"))
    assert 'value="农夫山泉"' not in text

def test_end_to_end_campaign_goal_saved_and_exported(auth):
    response=auth.post("/enterprise/api/runs",json=request_data())
    assert response.status_code==200,response.text
    result=response.json()
    assert result["campaign_hypothesis"]["complete"] is True
    assert len(result["scenario_changes"])==3
    assert "CAMPAIGN_HYPOTHESIS_INCOMPLETE" not in {e["code"] for e in result["quality_report"]["warnings"]}
    rid=result["run_id"]
    saved=auth.get(f"/enterprise/api/runs/{rid}")
    assert saved.status_code==200
    assert saved.json()["result"]["campaign_hypothesis"]["complete"] is True
    exported=auth.get(f"/enterprise/api/runs/{rid}/proposal.html")
    assert exported.status_code==200
    assert "目标人群" in exported.text
    assert "预算 100 / 200 / 500" in exported.text
    assert "交给运营的执行核验清单" in exported.text
    assert "executionRows" in exported.text
    assert "误一补二" in exported.text

def test_old_studio_runs_still_allowed_but_warn_for_missing_assumptions(auth):
    minimal={k:v for k,v in request_data().items()
             if k not in {"business_goal","campaign_goal","target_audience",
                          "success_kpi","measurement_method"}}
    response=auth.post("/enterprise/api/runs",json=minimal)
    assert response.status_code==200,response.text
    result=response.json()
    assert not result["campaign_hypothesis"]["complete"]
    assert "CAMPAIGN_HYPOTHESIS_INCOMPLETE" in {x["code"] for x in result["quality_report"]["warnings"]}

def test_unknown_campaign_goal_and_long_fields_are_rejected_or_marked_pending(auth):
    bad=request_data()
    bad["business_goal"]="A"*301
    response=auth.post("/enterprise/api/runs",json=bad)
    assert response.status_code==422
    bad=request_data()
    bad["campaign_goal"]="编造达到千万真实曝光"
    response=auth.post("/enterprise/api/runs",json=bad)
    assert response.status_code==200
    assert response.json()["campaign_hypothesis"]["complete"] is False
