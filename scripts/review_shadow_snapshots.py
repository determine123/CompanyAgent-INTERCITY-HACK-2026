#!/usr/bin/env python3
"""Compare two authorized REDACTED task snapshots; never executes or changes jobs."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enterprise.shadow_compare import compare_shadow

def main():
    p=argparse.ArgumentParser()
    p.add_argument("openclaw_json",type=Path)
    p.add_argument("companyagent_json",type=Path)
    args=p.parse_args()
    try:
        if args.openclaw_json.stat().st_size>200000 or args.companyagent_json.stat().st_size>200000:
            raise ValueError("snapshots exceed allowed size")
        old=json.loads(args.openclaw_json.read_text(encoding="utf-8"))
        new=json.loads(args.companyagent_json.read_text(encoding="utf-8"))
        result=compare_shadow(old,new)
    except (ValueError,OSError,UnicodeError,json.JSONDecodeError):
        print(json.dumps({"mode":"offline_snapshot_comparison","match":False,"production_cutover_permitted":False,
                          "error":"invalid or incomplete snapshot"},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    # Even a matching snapshot is not a real run and should never cause an automatic cutover.
    return 0 if result["match"] else 2

if __name__=="__main__":sys.exit(main())
