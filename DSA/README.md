# Master Data & Regional Intelligence — Competition Prototype

A **four-page Streamlit app** exploring how governed master records improve approvals and change regional purchasing insights. The app intentionally has no product brand name.

**Pages:** Smart Intake & Quality; Tracker, Approvals & Admin; Regional View; Forecasts, Insights & Actions.

## Run locally

```bash
python -m pip install -r requirements.txt
python generate_data.py --reset
streamlit run app.py
```

Or start `streamlit run app.py` directly: it creates the synthetic SQLite database if missing.

## Demo sequence

1. **Page 3:** Hospital ABC shows **−40%** growth in its original record; confirmed identity mapping has not occurred yet.
2. **Page 1:** Enter `ABC Hospital` for Singapore, QTS, registration `SG-REG-000001`; observe similar customer records. **Page 2 already contains seeded request `RQ-0001`** so the recording can skip typing.
3. **Page 2:** Switch to **Finance Steward**, approve RQ-0001. Switch to **BU Steward**, approve it. Switch to **MDM Steward**, finalize. Inspect audit events and the mock SAP payload.
4. **Page 3:** Hospital ABC's consolidated growth changes to **+20%**. The headline reclassification metric is calculated from live database values. Overall country-product total orders stay constant.
5. **Page 4:** Drop-off alert becomes an expansion review recommendation. Show honest WAPE backtest and cross-sell candidates.
6. **Optional:** Switch to **Admin** on Page 2 and add a configuration routing rule without editing the app code.

Press **Reset demonstration data** in the sidebar to replay the story.

## Implementation

| File | Responsibility |
|---|---|
| `generate_data.py` | Seed deterministic 36-month synthetic purchase-order and identity data |
| `database.py` | SQLite tables; append-only audit trigger; unique mock SAP request key |
| `domains.yaml` | Field and domain routing defaults, fuzzy matching tiers |
| `dedup.py` | Candidate detection using normalized fuzzy names |
| `workflow.py` | Maker–checker, concurrent approvals, verified merge and idempotent handoff |
| `insights.py` | Five-country ordering, YoY growth, customer category changes, cross-selling |
| `forecast.py` | Matched rolling-origin WAPE: moving average vs Holt–Winters |
| `pages/` | Four UI pages |
| `tests/` | Workflow and analytics acceptance tests |

## Measurement and data accuracy

- **Genuine customer purchase orders** are kept separate from customer purchasing requests, general enquiries and internal MDM requests.
- Synthetic PO dataset: **36 months, 5 countries (SG, MY, ID, TH, VN), 3 products (A/B/C), 300 canonical customers + 25 aliases, 6,000 PO lines**, with a **12-month display** and preceding 12 months for YoY.
- Headline **Data Quality Decision Impact** = canonical customers whose growth category changes after approved identity mapping / eligible comparable canonical customers × 100. Categories use the latest 3 vs preceding 3 months (growing >5%, declining <−5%). Show numerator and denominator.
- Historical order rows are **never edited** by identity matching; mapping is an audited reference table. Regional total PO volume stays constant after a merge.
- **Forecast comparison** uses 3 one-step-ahead rolling-origin evaluations across 15 country-product series, on identical actual values. No improvement is assumed. Customer-level attribution might change forecasts, but regional forecasts do not inherently change from identity merges.
- Similarity ≥90 is review, 75–89.9 is warning, below 75 is pass; actual legal identity verification is required before merging.

## Limitations and controls

- **Simulation, not a production system.** Role switcher is not authentication. Never use real customer names, bank numbers or financial details. Approvals and audit events are local; deployment may reset the database when the hosting environment restarts.
- Customer and Item forms are implemented; Vendor and Cost Center are configuration stubs. Sensitive fields should be restricted to Finance/MDM in a production SharePoint/Dataverse store.
- Final SAP handoff creates a JSON payload locally, **not** an ERP record. The payload contains a request ID, and the mock SAP table enforces one record per request. Identity-resolution requests generate a linkage payload rather than creating another customer. Production SAP integration needs proper access, reconciliation and retries.
- The proposed production architecture uses M365 Power Apps, Power Automate, Teams, restricted SharePoint/Dataverse storage and SAP B1 Service Layer, subject to licensing and security review.
- LLM extraction, ablation, regional map, webhooks and linked-order hidden-demand estimates are optional, not required for this prototype.

## Deploy to Streamlit Community Cloud

1. Push these files into a GitHub repository. **Do not commit personal data or API tokens.**
2. In Streamlit Community Cloud select **Create app**, choose your repo/branch, set entrypoint `app.py`, then deploy.
3. Share the live app and public repository URL with the judges. Community Cloud's local SQLite may be ephemeral; for a demo, use the reset button before filming and do not depend on persistence across restarts.

## Validation

```bash
python -m pytest -q
```

`data/demo.sqlite` is generated automatically and excluded from git. The reproducible seed script is the dataset source.
