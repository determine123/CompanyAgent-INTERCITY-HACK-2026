#!/usr/bin/env python3
"""Offline-only review of user-approved exported inventory/coverage/pricing.

Does not import into DB, send to an LLM, or upload any content.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from enterprise.ingress_review import inspect_export,IngressRejected,MAX_BYTES

def main():
    p=argparse.ArgumentParser(description="Offline metadata-only data contract inspection")
    p.add_argument("export",type=Path,help="Authorized local CSV/XLSX; never an internal website URL")
    p.add_argument("manifest",type=Path,help="Metadata-only manifest with approval ticket references")
    args=p.parse_args()
    try:
        if args.export.stat().st_size>MAX_BYTES or args.manifest.stat().st_size>100_000:
            raise IngressRejected("source size exceeds review limit")
        data=json.loads(args.manifest.read_text(encoding="utf-8"))
        evidence=inspect_export(args.export.read_bytes(),args.export.name,data)
    except (IngressRejected,ValueError,OSError,json.JSONDecodeError) as exc:
        print(json.dumps({"status":"rejected","reason":"source or manifest did not pass offline review","database_written":False},ensure_ascii=False))
        return 2
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
    return 0 if evidence["classification"]=="synthetic" else 2

if __name__=="__main__":
    sys.exit(main())
