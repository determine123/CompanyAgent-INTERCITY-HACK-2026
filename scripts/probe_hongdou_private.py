#!/usr/bin/env python3
"""Private enterprise owner-approved one-shot bus/metro contract probe.

Never run in public Railway, public GitHub Actions, or consumer model services.
Never prints source URLs, access tokens, data rows, or provider JSON bodies.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enterprise.hongdou_private_pilot import PrivatePilotBlocked, probe_hongdou_inventory


def main() -> int:
    p=argparse.ArgumentParser(description="One-shot, read-only, private Hongdou envelope probe")
    p.add_argument("--media",choices=("bus","metro"),required=True)
    p.add_argument("--start-date",required=True)
    p.add_argument("--end-date",required=True)
    p.add_argument("--line-name",default="")
    p.add_argument("--keyword",default="")
    p.add_argument("--i-confirm-owner-approval",action="store_true")
    p.add_argument("--i-confirm-approved-private-network",action="store_true")
    args=p.parse_args()
    if not args.i_confirm_owner_approval or not args.i_confirm_approved_private_network:
        print(json.dumps({"result":"BLOCKED","reason":"Owner and private network approval must both be confirmed",
                          "real_call_executed":False},ensure_ascii=False))
        return 2
    try:
        result=probe_hongdou_inventory(
            args.media,start_date=args.start_date,end_date=args.end_date,
            line_name=args.line_name,keyword=args.keyword,page_size=1,
            owner_approved=args.i_confirm_owner_approval,
            network_approved=args.i_confirm_approved_private_network)
    except (PrivatePilotBlocked,ValueError) as exc:
        # Errors here have been sanitized by the client. Do not log raw HTTP.
        print(json.dumps({"result":"BLOCKED_OR_FAILED","reason":str(exc),
                          "real_stock_verified":False},ensure_ascii=False))
        return 2
    print(json.dumps({"result":"HTTP_CONTRACT_PROBE_SUCCEEDED",**result},ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":
    sys.exit(main())
