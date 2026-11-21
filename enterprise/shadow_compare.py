"""Pure read-only Shadow Mode comparator, for authorized REDACTED task inventories.

No task execution, network calls, scheduler modification, side effects, or
production cutover. Input checksums must be generated externally.
"""
from __future__ import annotations
from collections import Counter

REQUIRED = {"task_id","schedule","input_sha256","result_sha256","read_only",
            "external_side_effects"}
def _index(rows, label):
    if not isinstance(rows,list) or len(rows)>1000:
        raise ValueError(f"{label} snapshot invalid/too large")
    idx={}
    for row in rows:
        if not isinstance(row,dict) or not REQUIRED.issubset(row):
            raise ValueError(f"{label} row missing required fields")
        task=row["task_id"]
        if not isinstance(task,str) or not (1<=len(task)<=80):
            raise ValueError(f"{label} row has invalid task ID")
        if task in idx:raise ValueError(f"{label} duplicate task ID")
        if any(not isinstance(row[k],str) or len(row[k])>200
               for k in ("schedule","input_sha256","result_sha256")):
            raise ValueError(f"{label} invalid schedule/hash format")
        if not isinstance(row["read_only"],bool) or not isinstance(row["external_side_effects"],bool):
            raise ValueError(f"{label} requires boolean side-effect flags")
        idx[task]=row
    return idx

def compare_shadow(openclaw:list, companyagent:list)->dict:
    old=_index(openclaw,"openclaw")
    new=_index(companyagent,"companyagent")
    failures=[]
    for task in sorted(old.keys()|new.keys()):
        if task not in old:
            failures.append({"task":task,"reason":"unexpected_shadow_task"})
            continue
        if task not in new:
            failures.append({"task":task,"reason":"missing_shadow_task"})
            continue
        left,right=old[task],new[task]
        if not right["read_only"] or right["external_side_effects"]:
            failures.append({"task":task,"reason":"shadow_writes_or_external_effects"})
        for field in ("schedule","input_sha256","result_sha256"):
            if left[field]!=right[field]:
                failures.append({"task":task,"reason":"mismatch_"+field})
    return {
        "mode":"offline_snapshot_comparison",
        "task_count_old":len(old),"task_count_shadow":len(new),
        "match":not failures,
        "failures":failures[:100],
        "production_cutover_permitted":False,
        "real_shadow_execution_verified":False,
        "rollback_policy":"any mismatch, duplicate, or side effect must block migration and preserve OpenClaw scheduler",
    }
