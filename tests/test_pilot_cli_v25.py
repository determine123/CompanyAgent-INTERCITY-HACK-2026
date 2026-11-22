"""Verify the documented private CLI works when run directly and as a module."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path
from test_evidence_cohort_v25 import cases

ROOT=Path(__file__).resolve().parents[1]


def invoke(tmp_path, runner):
    file=tmp_path/"private-pseudonymous.json"
    file.write_text(json.dumps({"trials":cases(10)},ensure_ascii=False),encoding="utf-8")
    env=dict(os.environ)
    env["COMPANYAGENT_DEPLOYMENT_MODE"]="local"
    p=subprocess.run([sys.executable,*runner,str(file)],cwd=ROOT,env=env,
                     capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    data=json.loads(p.stdout)
    assert data["case_count"]==10
    assert data["commercial_claim_permitted"] is False
    assert "proposal_000" not in p.stdout


def test_private_cli_module_invocation(tmp_path):
    invoke(tmp_path,["-m","scripts.evaluate_enterprise_pilot"])


def test_private_cli_direct_invocation(tmp_path):
    invoke(tmp_path,["scripts/evaluate_enterprise_pilot.py"])


def test_private_cli_cloud_denied(tmp_path):
    path=tmp_path/"fake.json"
    path.write_text('{"trials":[]}',encoding="utf-8")
    env=dict(os.environ)
    env["COMPANYAGENT_DEPLOYMENT_MODE"]="cloud_synthetic"
    p=subprocess.run([sys.executable,"-m","scripts.evaluate_enterprise_pilot",str(path)],
                     cwd=ROOT,env=env,capture_output=True,text=True,timeout=20)
    assert p.returncode==2
    assert "Local-only" in p.stderr
