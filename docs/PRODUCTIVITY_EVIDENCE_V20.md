# CompanyAgent v2.0 · One-run productivity evidence (2026-11-21)

## Why this closes a business gap
The existing v1.9 media proposal workflow has real proposal generation and review gates,
but a browser response time alone is not enterprise productivity evidence. In particular,
review, corrections and comparability matter more than isolated model latency.

This increment fixes customer-screen timing (previously only the older task studio
recorded `lastClientDurationMs`) and adds an auditable *single-case* effort record
bound to a specific immutable proposal Run.

## What an operator can do

1. Generate a synthetic food-and-beverage media proposal on `/enterprise/`.
2. Record a same-scope manual proposal's total effort.
3. Enter AI response time (captured automatically), human review and correction effort.
4. Optionally enter two error counts using the SAME error definition.
5. Explicitly attest same task scope and traceability of the time/error source.
6. Save the comparison to the authenticated run; the server returns a breakdown,
   difference in minutes, self-reported error delta and evidence state.

Endpoints: `POST/GET /enterprise/api/runs/{run_id}/impact-measurement`.
Writes require app authentication, CSRF, and per-run access. The frozen request/result
snapshot is hashed; records become unusable if the snapshot no longer matches.
The audit trail records save events, and records are scoped to the Run owner.

### Integrity boundaries

- `synthetic_illustration`: public Railway demonstration values, never verified ROI.
- `not_comparable`: missing matching scope or evidence attestation.
- `single_case_self_reported`: the operator asserts scope and record sources;
  this is **not** independent enterprise verification or a causal A/B experiment.
- All three states set `roi_verified=false` and `enterprise_savings_verified=false`.
- No organization-wide savings, salary-based amounts, actual sales lift or confirmed
  inventory is computed. A negative time delta is a productivity LOSS, not hidden.
- Numeric-only stored inputs reduce accidental client data retention; no customer name
  or raw inventory is sent to this endpoint.
- Approval/booking/enterprise data permissions are unchanged.

### Follow-up enterprise pilot

Compare 20+ same-complexity proposal pairs with audited timestamps and identical output
acceptance criteria, document selection bias, quantify corrections and downstream
handoff cost, then ask the business owner to approve the validated sample.
Only then consider a cost model and ROI, separate from the hackathon demo.

### QA

`python -m pytest -q tests/test_productivity_evidence_v20.py`
and full `python -m pytest -q` via GitHub Actions.
