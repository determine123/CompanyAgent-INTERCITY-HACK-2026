"""Offline supplier schema-shape checks; NEVER treat fake availability as real."""
from __future__ import annotations
import pytest
from enterprise.supplier_schema_review import inspect_candidate_mapping, SupplierSchemaBlocked

MAPPING={"resource_id":"resourceId","media_name":"mediaName",
         "reported_units":"availableCount","stock_status":"businessStatus"}


def fixture():
    return {"code":200,"data":{"records":[
        {"resourceId":"FAKE-BUS-01","mediaName":"模拟公交广告","availableCount":5,
         "businessStatus":"SOME_UNKNOWN_PROVIDER_CODE","anyPrivateField":"must not leak"}]}}


@pytest.mark.parametrize("kind",["bus","metro"])
def test_schema_inspection_exposes_shape_only_and_no_stock_claim(kind):
    report=inspect_candidate_mapping(fixture(),MAPPING,kind)
    assert report["media_kind"]==kind
    assert report["fixture_rows_inspected"]==1
    assert report["structural_shape_count"]==1
    assert report["planning_eligible"] is False
    assert report["quantity_is_bookable"] is False
    assert report["supplier_semantics_approved"] is False
    assert report["raw_rows_returned"] is False
    assert report["network_called"] is False
    assert report["enterprise_database_written"] is False
    assert "SOME_UNKNOWN_PROVIDER_CODE" not in str(report)
    assert "FAKE-BUS-01" not in str(report)
    assert "must not leak" not in str(report)
    assert "5" not in str(report["mapping_fields"])


@pytest.mark.parametrize("mutator",[
    lambda p,m:(p,dict(m,resource_id="unknown")),
    lambda p,m:(p,dict(m,stock_status="availableCount")),
    lambda p,m:({"data":{"list":p["data"]["records"],"rows":[]}},m),
    lambda p,m:({"data":{"records":[dict(p["data"]["records"][0],availableCount=True)]}},m),
    lambda p,m:({"data":{"records":[dict(p["data"]["records"][0],availableCount=-1)]}},m),
    lambda p,m:({"data":{"records":[dict(p["data"]["records"][0],availableCount=1.5)]}},m),
    lambda p,m:({"data":{"records":[dict(p["data"]["records"][0],businessStatus=None)]}},m),
    lambda p,m:({"data":{"records":[dict(p["data"]["records"][0],resourceId="")]}},m),
])
def test_malformed_or_unknown_supplier_contract_fails_closed(mutator):
    payload,mapping=mutator(fixture(),MAPPING)
    with pytest.raises(SupplierSchemaBlocked) as error:
        inspect_candidate_mapping(payload,mapping,"bus")
    assert "FAKE-BUS-01" not in str(error.value)
    assert "SOME_UNKNOWN_PROVIDER_CODE" not in str(error.value)


def test_invalid_media_and_too_many_rows_are_rejected():
    with pytest.raises(SupplierSchemaBlocked):
        inspect_candidate_mapping(fixture(),MAPPING,"billboard")
    with pytest.raises(SupplierSchemaBlocked):
        inspect_candidate_mapping({"data":{"records":fixture()["data"]["records"]*101}},
                                  MAPPING,"bus")
