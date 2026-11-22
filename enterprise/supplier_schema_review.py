"""Offline Hongdou response-contract inspection. No network, no credential handling.

Unknown field meanings (especially availability, booked/held stock and price)
MUST be checked by the corporate data owner before any inventory can feed a
proposal. Shape checks alone NEVER establish bookable inventory.
"""
from __future__ import annotations
import re
from typing import Any

_SAFE_FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_REQUIRED = ("resource_id", "media_name", "reported_units", "stock_status")
_TYPES = {"resource_id": (str, int), "media_name": (str,),
          "reported_units": (int,), "stock_status": (str,)}
_ALLOWED_CONTAINER = ("records", "list", "rows")


class SupplierSchemaBlocked(ValueError):
    pass


def _reject():
    raise SupplierSchemaBlocked("Supplier schema is unapproved or incompatible; raw values suppressed")


def inspect_candidate_mapping(payload: Any, mapping: dict[str, str], kind: str) -> dict:
    """Inspect a **locally held**, approved-to-inspect fixture.

    Reports only data *shape* and counts; NEVER exports media records, token,
    material-specific status strings, or inventory quantities.
    """
    if kind not in ("bus", "metro") or not isinstance(mapping, dict) or set(mapping) != set(_REQUIRED):
        _reject()
    if any(not isinstance(k, str) or not isinstance(v, str) or not _SAFE_FIELD.fullmatch(v)
           for k, v in mapping.items()):
        _reject()
    if len(set(mapping.values())) != len(_REQUIRED):
        _reject()
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        _reject()
    data = payload["data"]
    matches = [k for k in _ALLOWED_CONTAINER if k in data]
    if len(matches) != 1 or not isinstance(data[matches[0]], list):
        _reject()
    rows = data[matches[0]]
    if len(rows) > 100:
        _reject()
    shapes = set()
    for row in rows:
        if not isinstance(row, dict) or len(row) > 80 or not all(v in row for v in mapping.values()):
            _reject()
        for attr, field in mapping.items():
            value = row[field]
            if type(value) not in _TYPES[attr]:
                _reject()
            if attr in ("resource_id", "media_name") and not 1 <= len(str(value)) <= 160:
                _reject()
            if attr == "reported_units" and not 0 <= value <= 50000:
                _reject()
            if attr == "stock_status" and not 1 <= len(value) <= 80:
                _reject()
        shapes.add(tuple(sorted((key, type(row[key]).__name__) for key in mapping.values())))
    return {
        "media_kind": kind,
        "fixture_rows_inspected": len(rows),
        "structural_shape_count": len(shapes),
        "mapping_fields": sorted(mapping.keys()),
        "status": "schema_shape_only",
        "planning_eligible": False,
        "supplier_semantics_approved": False,
        "quantity_is_bookable": False,
        "price_is_formal": False,
        "raw_rows_returned": False,
        "network_called": False,
        "enterprise_database_written": False,
        "next_gates": [
            "The data owner must sign a redacted field dictionary and stock-status interpretation",
            "Validate booked/held/future-date states and tenant scope against supplier UI",
            "Approve source freshness, pagination and reconciliation checks",
            "Perform real HTTPS read-only query only inside independently authorized private gateway",
        ],
    }
