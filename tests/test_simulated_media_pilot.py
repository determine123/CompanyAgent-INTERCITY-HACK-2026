import pytest

from scripts.simulate_media_pilot import reconcile, run


@pytest.mark.parametrize("ledger", [{}, {"x": -1}, {"x": 2}, {"x": True}])
def test_incomplete_or_invalid_owner_snapshot(ledger):
    with pytest.raises(ValueError):
        reconcile([{"id": "x", "available_count": "1"}], ledger)


def test_paired_simulation():
    result = run()
    for route in ("agent", "manual"):
        assert not result["plans"][route + "_initial"]["passes"]
        plan = result["plans"][route + "_final"]
        assert plan["mix"] == {"bus": 15, "metro": 7}
        assert plan["passes"] and not plan["conflicts"]
    assert result["cost_summary"]["difference_fen"] == 8400
    assert not result["independently_verified"]
