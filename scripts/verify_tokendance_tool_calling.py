#!/usr/bin/env python3
"""One-shot live TokenDance tool calling check on synthetic, non-customer data.

Not run in CI. Requires explicit user approval, server-side environment variables,
and a TokenDance model that supports OpenAI Chat Completions function calling.
Prints a redacted result only, never tokens, raw requests or media inventory.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enterprise.model_tools import ModelError, run_model_tools

DATA = {
    "plan": {
        "industry": "食品饮料",
        "budget_wan": 200,
        "focus_landmark": "SYNTHETIC_TEST_ONLY",
        "candidate_count": 4,
        "item_count": 2,
        "selected": [{"type": "synthetic_bus"}, {"type": "synthetic_metro"}],
    },
    "quality_report": {"evidence": {"matched_items": 1}},
    "budget_variants": {
        "100": {"item_count": 1, "spent_wan": 95, "remaining_wan": 5},
        "200": {"item_count": 2, "spent_wan": 195, "remaining_wan": 5},
        "500": {"item_count": 4, "spent_wan": 460, "remaining_wan": 40},
    },
}
ALLOWED = {"inspect_inventory", "inspect_coverage", "select_budget_scenario"}


def main() -> int:
    p = argparse.ArgumentParser(description="Synthetic-only live TokenDance Tool Calling acceptance check.")
    p.add_argument("--i-authorize-external-call", action="store_true", help="Required per-run permission to send only synthetic aggregates.")
    args = p.parse_args()

    if not args.i_authorize_external_call:
        print("未执行：需要 --i-authorize-external-call 明确本次外发授权")
        return 2
    if not os.environ.get("TOKENDANCE_API_KEY", "").strip():
        print("未执行：请在本机服务端设置 TOKENDANCE_API_KEY（不要复制到聊天或 Git）")
        return 2
    if not os.environ.get("TOKENDANCE_MODEL", "").strip():
        print("未执行：请在 TokenDance 控制台确认支持 Tool Calling 的模型并设置 TOKENDANCE_MODEL")
        return 2

    try:
        response = run_model_tools(DATA, ALLOWED, provider="tokendance", max_steps=4)
    except ModelError as exc:
        print("联调失败（不包含任何凭据）：" + str(exc))
        return 1

    # A normal text completion is not a tool calling success.
    if response["verification_status"] != "tool_calls_executed":
        print("联调未通过：模型返回了文字，但没有实际调用白名单工具")
        return 1

    evidence = {
        "provider": response["provider"],
        "model": response["model"],
        "transport": response["mode"],
        "verification_status": response["verification_status"],
        "tool_call_count": len(response["executed_tools"]),
        "tools": [row["tool"] for row in response["executed_tools"]],
        "budget_scenario": response["selected_scenario"]["budget_wan"] if response["selected_scenario"] else None,
        "non_mutating": True,
        "real_stock_verified": False,
        "company_private_data_sent": False,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
