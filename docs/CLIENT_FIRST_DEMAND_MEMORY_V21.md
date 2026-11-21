# CompanyAgent v2.1 · Customer-first, private database, enterprise demand memory

## Product framing
Inspired by the simple Real Monad interaction pattern supplied by the user:
enter what the customer wants, get a credible assessment and a short action plan.
For this advertising media use case, "best" means *best under the selected
budget, accessible inventory snapshot, matching and governance constraints*.
It cannot establish campaign ROI or predict confirmed future stock.

## Customer-facing workbench (authenticated)
`/enterprise/` now opens the Client Brief view after staff login.
Form -> existing `POST /enterprise/api/runs` -> database-backed deterministic media
planning -> `GET /enterprise/api/runs/{id}/decision-brief`.
The pre-review shows three evidence-based risks (no fabricated scores),
six concrete customer/judge questions and three priority actions.
It shows actual dataset source labels and coverage caveats. No real booking,
quote or customer message is sent. Current demo requires login and Basic Auth;
not an anonymous customer intake service.

## Back office: learn from demand, not from prompt injections
`GET /enterprise/api/insights`: aggregate the 250 most recent authorized Run
records, by campaign objective, budget band, media preference, and known
quality warnings. Raw brands, customer Brief text and media rows are deliberately
omitted. Employee: own Runs; admin: this single organization's recent Runs.

`POST /enterprise/api/insights/drafts`: create a candidate based on a
deterministic known template; require at least one Run and limit outstanding
drafts. `GET /enterprise/api/insights/drafts`: owner-only pending/used status.

`POST /enterprise/api/insights/drafts/{id}/adopt`: explicit human approval
creates both a private Skill and private Agent, only with pre-approved
allowlisted read/optimization/risk tools. Each draft can be adopted at most
once, no automatic code execution, external sending or privilege expansion.

`GET /enterprise/api/runs/{id}/decision-brief`: reuses the frozen plan quality
results and authorization checks; no LLM required.

## Security and correctness
- Public Railway is **synthetic-only**, not an enterprise data environment.
- Authentication/CSRF remain required. No anonymous access to company data.
- Recommendation/prompt text never changes allowlisted tool permissions.
- Analytics intentionally excludes free-text names and customer records.
- Existing SQLite on Railway lacks a persistent volume: demo history can be
  lost across redeploys; production use needs a company-approved database,
  backups, RBAC/SSO, tenant separation and privacy review.
- Live Hongdou read-only inventory is still **not verified**; visualization
  has no known approved API. Enterprise pilot requires approval in a private
  environment and verified schema/time-window semantics.

## Judge walkthrough (90 seconds)
1. Log in, land on customer request page and edit synthetic beverage campaign.
2. Generate proposal; show the selected bus/metro media and source labels.
3. Present the 3 potential failure points, 6 hard questions and 3 next actions.
4. Switch budget 100 / 200 / 500, view delta, and optional change impact.
5. Open Enterprise Demand Memory: historical goal/quality patterns.
6. Generate a candidate Agent/Skill; explicitly approve private creation.
7. Show allowlisted tools and privacy/real-inventory restrictions.

## Tests
`python -m pytest -q tests/test_demand_memory_v21.py`
and entire CI regression suite. All tests are synthetic and network-free.
