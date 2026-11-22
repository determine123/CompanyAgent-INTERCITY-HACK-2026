"""Aggregated historical real-deidentified data evidence, no private files in CI."""
import json
from pathlib import Path

def test_real_deidentified_history_is_consistent_and_honestly_labeled():
    report=json.loads((Path(__file__).resolve().parents[1]/"docs"/"evidence"/"DEIDENTIFIED_HISTORICAL_20261122.json").read_text(encoding="utf-8"))
    r=report
    inv=r["inventory"];cov=r["coverage"]
    assert r["stock_snapshot_date"]=="2026-11-13"
    assert r["target_campaign_period"]==["2027-05-01","2027-05-28"]
    assert inv["rows"]==431
    assert sum(inv["grade_counts"].values())==431
    assert sum(inv["format_counts"].values())==431
    assert inv["capacity_total"]==2525
    assert inv["capacity_total"]==inv["empty_on_2026_11_13"]+inv["contract_occupied"]+inv["reserved_occupied"]+inv["maintenance"]+inv["renewal_protection"]
    assert inv["row_arithmetic_failures"]==0 and inv["negative_rows"]==0
    assert inv["empty_exceeds_capacity_rows"]==0
    assert inv["unpriced_AA_rows"]==2
    assert cov["summary_rows"]==44
    assert cov["bus_coverage_rows"]==37
    assert cov["metro_coverage_rows"]==7
    assert cov["strict_historical_bus_matches"]==28
    assert sum(s["summary"] for s in cov["site_counts"])==44
    assert sum(s["strict_historical_matches"] for s in cov["site_counts"])==28
    assert len(r["source_original_sha256"])==2
    assert all(len(h)==64 for h in r["source_original_sha256"].values())
    assert all(len(s["sha256"])==64 for s in cov["site_counts"])
    assert not any(r["scope"].values())

def test_coverage_is_not_equated_with_2027_stock():
    r=json.loads((Path(__file__).resolve().parents[1]/"docs"/"evidence"/"DEIDENTIFIED_HISTORICAL_20261122.json").read_text(encoding="utf-8"))
    assert r["coverage"]["metro_coverage_rows"]==7
    assert r["scope"]["verified_2027_metro_stock"] is False
    assert r["scope"]["live_hongdou_called"] is False
    assert r["scope"]["ROI_verified"] is False
