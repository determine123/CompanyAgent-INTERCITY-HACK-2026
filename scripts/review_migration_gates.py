#!/usr/bin/env python3
"""Read-only governance preflight. NEVER triggers a production deployment."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enterprise.migration_gates import review_manifest

def main():
    p=argparse.ArgumentParser(description="Review evidence refs; not an approval or deploy action")
    p.add_argument("manifest",type=Path)
    args=p.parse_args()
    try:
        result=review_manifest(args.manifest)
    except (ValueError,OSError,UnicodeError,json.JSONDecodeError) as exc:
        print(json.dumps({"review_state":"blocked","reason":"manifest invalid","deployment_permitted":False},ensure_ascii=False))
        return 2
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["stage"]=="cloud_synthetic" and result["review_state"]=="ready_for_manual_go_no_go" else 2

if __name__=="__main__":
    sys.exit(main())
