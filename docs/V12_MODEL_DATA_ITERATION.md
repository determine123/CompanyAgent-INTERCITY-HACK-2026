# CompanyAgent v1.2 — Model, Data Bridge, Failure-guided Skills

**Scope:** INTERCITY HACK 2026, Shanghai Xin Yun Media. This is a local single-organization hackathon MVP, **not** a production-ready enterprise SaaS or live inventory booking tool.

## 1. Real B1X model calling — gated, not simulated

The endpoint `POST /enterprise/api/runs/{run_id}/model-tools` uses OpenAI-compatible **Chat Completions** at the fixed URL `https://token.b1x.work/v1/chat/completions` with model `deepseek-v4.1-flash-1017`. It is optional and requires a server-side `B1X_API_KEY` and explicit user consent on each request.

The model is allowed to choose **only three registered read-only functions**:

| Tool | Permission required in the frozen Agent Skill | What is returned |
|---|---|---|
| `inspect_coverage` | `match_coverage` | Aggregate selected/matched counts; **no geographic names or raw CSV** |
| `inspect_inventory` | `load_inventory` | Inventory aggregate, quality caveats; **no media names, routes, exact locations, or raw rows** |
| `select_budget_scenario` | `optimize_budget` | One of **100/200/500** precomputed budget-constrained scenarios. The model never computes/edits the quote. |

Security controls: 4 rounds max; one tool call per round; strict parameter validation; no shell, SQL, fetch URL, remote login, external Skill, arbitrary MCP, publish/approve/booking/write tools. No raw customer Brief, employee identity, media inventory, coordinates, complete data source, token or password sent to the provider. HTTP endpoint and model fixed server-side; no redirects, environment proxy or arbitrary hostname. Model suggestion never overrides deterministic business gates. Execution trace is recorded in `model_tool_runs`, with separate user/administrator access controls and CSRF check. Replayed result is checked against its original plan fingerprint before calling the model.

The public CI uses an isolated **mock HTTP transport** to check protocol, tool loop, invalid calls, auth and non-leakage. A real live B1X call is *not* claimed to have passed without a valid user-supplied server-side key and external access. The local deterministic planner still operates without B1X.

### Enable the opt-in model

In an **authorized local machine environment**:

```powershell
$env:B1X_API_KEY = "YOUR_SECRET_FROM_B1X"
py server.py
```

Never write the token in source, exported chat logs, a screenshot, a README, or public CI secrets. In the workbench, execute a deterministic task, click **真实 B1X 受限工具调用**, read the summary-only disclosure, and explicitly consent. The model cannot reserve inventory or finalize prices.

## 2. Approved Hongdou inventory + Xin Yun coverage bridge

Admin/staff may upload competition-authorized exports as `inventory` (Hongdou CSV/XLSX), `coverage` (Xin Yun two-section CSV/XLSX), `pricing` (de-identified rate card); or admin may configure a vetted HTTPS direct CSV/XLSX endpoint / export-folder polling. **Not** automatic login, captcha handling, cookie re-use, internal API guessing or bypassing source restrictions.

A logged-in user selects the two datasets and a landmark in **Data Hub → 核验并关联授权数据**. The `POST /enterprise/api/data/bridge/reconcile` endpoint:

- validates both source IDs, type and employee visibility;
- preserves SHA-256 checksums, source origin, data dimensions;
- matches equal typed media identifiers and names, with **only a narrowly specified `961` ↔ `961路` numeric bus route suffix normalization**;
- rejects ambiguous matches and does not use substrings (`100` must never match `1001`);
- retains repeated evidence hits but does not count them as separate inventory;
- returns matched media/coverage summary and **always sets `verified_for_2027: false`, `NOT_RESERVED`** until a separate approved schedule verification workflow actually exists.

**One real, private, local-only integration smoke** using the contest handout and three uploaded exports (not uploaded to GitHub) on 2026-11-21 produced:

| Source | Rows |
|---|---:|
| 01 bus inventory handout | 431 |
| Zhengda / Shanghai South / Xintiandi coverage | 19 / 10 / 15 = 44 |
| Matched inventory media in this raw handout | 32 |
| Matched coverage evidence rows | 33 |
| Zhengda matched bus inventory | 14 |
| Confirmed 2027 availability, metro inventory, locked slots | **none verified** |

These counts are **evidence matching**, not real-time sellable units, exact quotations or campaign reach. The difference from older derived snapshots comes from parser/line-name normalization and source transformations; do not compare the figures without data-version context.

## 3. Failure → experiment → human publish → rollback

Auto-generated diagnosis is saved for (a) model absent/invalid tool calls, (b) business planning failures, (c) known allowed coverage data that cannot be used because the Skill lacks `match_coverage`, and (d) missing inventory. `/enterprise/api/failures` displays status and next action.

For a **missing coverage tool**, the owner/admin can run a frozen-data before/after experiment via `/failures/{id}/evaluate`, changing **only** the candidate allowlisted `match_coverage` permission. Approval via `/publish` is rejected unless the experiment decreases unsupported media recommendations while respecting the budget and having positive candidates; it re-verifies the data/Skill snapshot before publication. `/rollback` is version guarded and keeps audit history. Other failure types become **manual data/credentials diagnoses**, never fabricated 'automatic self repair'.

It does **not** generate or execute arbitrary code, install an external Skill, publish without owner approval, alter the original run, or assume the fault is always fixable by granting a tool.

## 4. Verification status and known limitations

- Local regression: `python -m pytest -q` (tests including real protocol mocked transport, negative controls, CSRF, provenance, frozen experiment and rollback).
- Python `compileall`, Node `--check` (frontend JS), server resource/route check.
- Real authenticated HTTP web interface: FastAPI TestClient verified; Chromium browser acceptance blocked by this execution environment's administrative localhost policy, **not recorded as passed**.
- Live B1X request: **not run**, because no usable B1X credential is available in the execution environment.
- Source-system integration: **authorized exported files, not live Hongdou and coverage site API access**.
- No 2027 stock lock, schedule availability, official media price quote, impressions/ROI or self-modifying production code.

## References

- B1X competition data: user-supplied contest guide and approved reference/export files.
- OpenAI Chat Completions function-calling schema: https://developers.openai.com/api/docs/guides/function-calling
- Alibaba Cloud Model Studio DeepSeek model capability: https://www.alibabacloud.com/help/en/model-studio/deepseek-api
