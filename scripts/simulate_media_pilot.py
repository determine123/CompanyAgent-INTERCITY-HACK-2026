"""Replay one fictional four-week beverage brief against a simulated owner ledger."""
import csv
import json

from enterprise.judge_preview import _DEMO, preview
from scripts.evaluate_enterprise_pilot import summarize_costs
from src.ingest import parse_inventory
from src.planning import optimize_plan


def run():
    with _DEMO.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    brief = dict(brand="模拟饮料品牌A", industry="食品饮料", budget_wan=100,
                 start_date="2027-05-01", weeks=4, medium="both",
                 focus_district="all", focus_landmark="", coverage_only=False)
    # In this fixture all other units retain the CSV status for the entire flight.
    owner = {"DEMO-BUS-003": (2, "四个中两个锁位"), "DEMO-METRO-027": (0, "全档期占用")}
    catalog = {r["id"]: r for r in rows}

    def manual(picks):
        return [{"id": key, "quantity": qty,
                 "line_total_wan": round(float(catalog[key]["unit_price_wan"])*qty, 2)}
                for key, qty in picks.items()]

    def review(items):
        assert len({x["id"] for x in items}) == len(items)
        conflicts = []
        for item in items:
            key = item["id"]
            row = catalog[key]
            cap = owner.get(key, (int(row["available_count"]), ""))[0]
            if row["available_from"] > "2027-05-01" or row["available_to"] < "2027-05-28":
                cap = 0
            if item["quantity"] > cap:
                conflicts.append(key)
        spend = round(sum(x["line_total_wan"] for x in items), 2)
        both = {catalog[x["id"]]["media_type"] for x in items} == {"bus", "metro"}
        return dict(items=items, spend_wan=spend, units=sum(x["quantity"] for x in items),
                    conflicts=conflicts, passes=both and spend <= 100 and not conflicts)

    first = {"DEMO-BUS-003": 4, "DEMO-METRO-027": 4, "DEMO-BUS-027": 4,
             "DEMO-METRO-014": 2, "DEMO-BUS-013": 1, "DEMO-BUS-026": 1}
    revised = {**first, "DEMO-BUS-003": 2, "DEMO-METRO-001": 1, "DEMO-BUS-007": 1}
    del revised["DEMO-METRO-027"]
    agent_initial = preview(100, "both")["selected"]
    corrected = []
    for row in rows:
        count = owner.get(row["id"], (int(row["available_count"]), ""))[0]
        if count:
            corrected.append(dict(row, available_count=str(count)))
    records = parse_inventory(corrected, "DEMO-SYNTHETIC")["records"]
    agent_final = optimize_plan(dict(brief, records=records))["selected"]
    plans = dict(manual_initial=review(manual(first)), manual_final=review(manual(revised)),
                 agent_initial=review(agent_initial), agent_final=review(agent_final))
    for route in ("manual", "agent"):
        assert set(plans[route+"_initial"]["conflicts"]) == set(owner)
        assert plans[route+"_final"]["passes"]

    # Minutes for equal deliverables; scenario assumptions, never measured staff time.
    minutes = {"manual": [15, 55, 25, 20, 10], "agent": [15, 12, 25, 12, 10]}
    rates = [120, 120, 180, 120, 150]  # CNY/hour by step
    labor = {k: sum(m*r*100//60 for m, r in zip(v, rates)) for k, v in minutes.items()}
    costs = dict(manual_labor=labor["manual"], manual_other=200, assisted_labor=labor["agent"],
                 model=0, infrastructure=300, rollout_allocation=1500, assisted_other=200)
    return dict(synthetic=True, brief=brief, owner_overrides=owner, plans=plans,
                steps=["需求确认", "生成与整理", "媒介核对", "返工", "财务与交接"],
                minutes=minutes, hourly_rates_cny=rates, ledger_fen=costs,
                cost_summary=summarize_costs([{"case_id":"demo"}], {"demo":costs}))


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
