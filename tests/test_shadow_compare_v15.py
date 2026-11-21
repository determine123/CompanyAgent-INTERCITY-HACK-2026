"""Offline, synthetic-only migration Shadow Mode acceptance checks."""
import pytest
from enterprise.shadow_compare import compare_shadow

def snapshot(task_id="cron-public",schedule="0 9 * * *",checksum="b"*64):
    return {
        "task_id":task_id,"schedule":schedule,
        "input_sha256":"a"*64,"result_sha256":checksum,
        "read_only":True,"external_side_effects":False,
    }

def test_shadow_equal_read_only_tasks_are_comparable_but_not_production():
    report=compare_shadow([snapshot()],[snapshot()])
    assert report["match"]
    assert report["production_cutover_permitted"] is False
    assert report["real_shadow_execution_verified"] is False

@pytest.mark.parametrize("changed,reason",[
    ({"result_sha256":"c"*64},"mismatch_result_sha256"),
    ({"schedule":"1 9 * * *"},"mismatch_schedule"),
    ({"input_sha256":"d"*64},"mismatch_input_sha256"),
    ({"read_only":False},"shadow_writes_or_external_effects"),
    ({"external_side_effects":True},"shadow_writes_or_external_effects"),
])
def test_shadow_drift_or_side_effects_fail_closed(changed,reason):
    second=snapshot()
    second.update(changed)
    report=compare_shadow([snapshot()],[second])
    assert report["match"] is False
    assert reason in {x["reason"] for x in report["failures"]}

def test_shadow_missing_or_unexpected_task_blocks():
    report=compare_shadow([snapshot()],[snapshot("cron-other")])
    assert {"missing_shadow_task","unexpected_shadow_task"} == {x["reason"] for x in report["failures"]}

def test_shadow_duplicate_ids_rejected():
    with pytest.raises(ValueError,match="duplicate"):
        compare_shadow([snapshot()],[snapshot(),snapshot()])

def test_shadow_missing_required_fields_rejected():
    bad=snapshot()
    del bad["external_side_effects"]
    with pytest.raises(ValueError,match="missing required"):
        compare_shadow([snapshot()],[bad])
