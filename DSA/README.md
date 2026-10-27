# Master Data & Regional Intelligence — Competition Operations Portal

A unified Streamlit portal with five connected workspaces: **Overview, Master Data, Regional Performance, Insights & Forecasts, and Administration**. This prototype intentionally has no invented product brand name. It uses synthetic data and simulated roles, not a production ERP tenant.

## Run locally

```bash
python -m pip install -r requirements.txt
python generate_data.py --reset
streamlit run app.py
```

Or start `streamlit run app.py` directly: it creates the synthetic SQLite database if missing.

## Judge demonstration: a business decision corrected by clean data

1. Open **Overview** and **Regional Performance**. Hospital ABC's primary source record appears **−40%**. The **Decision evidence** panel shows the verified identifier candidates and an explicitly unapproved **+20%** what-if preview based on actual synthetic PO source rows.
2. Open **Master Data → Approval inbox** and select seeded **RQ-0001**. Review the same identity evidence, assigned stewards and audit history. Change your simulated persona **only in the left sidebar's “Viewing as” selector**.
3. As **Finance Steward**, approve. As **BU Steward**, approve independently. As **MDM Steward**, confirm and finalize. The request becomes **Created** and an idempotent, mock SAP handoff is recorded; no production SAP record is written.
4. Return to **Regional Performance**. The consolidated growth becomes **+20%** in actual approved analytics; the original source PO rows and regional total volumes remain unchanged. The customer recommendation changes from drop-off investigation to growth opportunity.
5. Open **Insights & Forecasts**. Compare honest WAPE backtests, build a selectable **6 or 12-month country × product purchasing plan**, and export it as CSV. Planning bounds are sensitivity scenarios, not statistical confidence intervals.
6. In **Administration**, explore the editable routing rules and the **assumption-based operational savings calculator**. Show the clearly labeled difference between simulation, test-backed outcomes and unvalidated production business assumptions.
7. The bottom-right **Operations Assistant** provides guidance and navigation without changing roles. Email extraction, duplicate matching, SLA escalation, audit history and enterprise connector status are additional demonstrable features.

Use **Reset demonstration** in the sidebar before recording. The public SQLite state can be shared between sessions and is not a durable enterprise store.

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
| `portal.py` | Unified operations portal, guided stewardship and decision-evidence views |
| `assistant_guide.py` | Contextual navigation assistant that never changes user roles |
| `ui.py` | Shared portal styling and UI components |
| `tests/` | Workflow and analytics acceptance tests |

## Measurement and data accuracy

- **Genuine customer purchase orders** are kept separate from customer purchasing requests, general enquiries and internal MDM requests.
- Synthetic PO dataset: **36 months, 5 countries (SG, MY, ID, TH, VN), 3 products (A/B/C), 300 canonical customers + 25 aliases, 6,000 PO lines**, with a **12-month display** and preceding 12 months for YoY.
- Headline **Data Quality Decision Impact** = canonical customers whose growth category changes after approved identity mapping / eligible comparable canonical customers × 100. Categories use the latest 3 vs preceding 3 months (growing >5%, declining <−5%). Show numerator and denominator.
- Historical order rows are **never edited** by identity matching; mapping is an audited reference table. Regional total PO volume stays constant after a merge.
- **Forecast comparison** uses 3 one-step-ahead rolling-origin evaluations across 15 country-product series, on identical actual values. Users can build/export six- or twelve-month PO outlooks by country/product with explicit sensitivity bounds. No improvement is assumed. Customer-level attribution might change forecasts, but regional forecasts do not inherently change from identity merges.
- Similarity ≥90 is review, 75–89.9 is warning, below 75 is pass; actual legal identity verification is required before merging.

## Limitations and controls

- **Simulation, not a production system.** Role switcher is not authentication. Never use real customer names, bank numbers or financial details. Approvals and audit events are local; deployment may reset the database when the hosting environment restarts.
- Customer and Item forms are implemented; Vendor and Cost Center are configuration stubs. Sensitive fields should be restricted to Finance/MDM in a production SharePoint/Dataverse store.
- Final SAP handoff creates a JSON payload locally, **not** an ERP record. The payload contains a request ID, and the mock SAP table enforces one record per request. Identity-resolution requests generate a linkage payload rather than creating another customer. Production SAP integration needs proper access, reconciliation and retries.
- The proposed production architecture uses M365 Power Apps, Power Automate, Teams, restricted SharePoint/Dataverse storage and SAP B1 Service Layer, subject to licensing and security review.
- Azure OpenAI extraction and Teams webhook notifications are implemented as opt-in connectors, with an always-available rules-first fallback. A guarded SAP B1 Service Layer adapter is implemented; it never writes without configured credentials and explicit authorization. Ablation, regional map and linked-order hidden demand remain extensions.

## Email automation, SLAs and enterprise connection settings

- Page 1 accepts pasted emails, distinguishes **confirmed PO / Customer Request / Enquiry / MDM Setup**, extracts domain fields, and pre-fills the intake form. Only setup requests may enter the MDM queue. The rules-first parser works without credentials.
- Optional Azure OpenAI extraction: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_KEY` and optionally `AZURE_OPENAI_API_VERSION` in Streamlit secrets. The user opts in by selecting the Azure OpenAI checkbox; extracted values must be reviewed before submission.
- Page 2 computes working-day approval SLAs, due-soon reminders and overdue delegations. The app evaluates the queue on interactions; an unattended deployment should run `sla.process_sla(notify=True)` on a server schedule. Set `TEAMS_WEBHOOK_URL` to an authorized workflow endpoint to dispatch nonsensitive Teams notifications.
- SAP B1 test-system dispatch is available to the MDM steward only after completing the maker-checker approvals. Set `SAP_B1_SERVICE_LAYER_URL`, `SAP_B1_COMPANY_DB`, `SAP_B1_USERNAME`, `SAP_B1_PASSWORD` as deployment secrets. This uses SAP B1 Service Layer login/session authentication. Only basic Business Partner and Item create mappings are implemented; identity linking stays a local golden-record mapping until an approved SAP update mapping is provided. Unknown network outcomes are marked **pending reconciliation** rather than automatically retried. Real SAP integration is **not validated without an authorized test tenant**.
- A Streamlit role switcher is **not real authorization**. Do not configure live production SAP credentials on a public competition demo. Use a dedicated secured deployment with proper authentication for any real record creation.

## Deploy to Streamlit Community Cloud

1. Push these files into a GitHub repository. **Do not commit personal data or API tokens.**
2. In Streamlit Community Cloud select **Create app**, choose your repo/branch, set entrypoint `DSA/app.py`, then deploy.
3. Share the live app and public repository URL with the judges. Community Cloud's local SQLite may be ephemeral; for a demo, use the reset button before filming and do not depend on persistence across restarts.

## Competition handoff checklist

- Verify all five portal workspaces on the live hosted app, including the forecast export and steward transitions. Reset before filming.
- Update the two-page report with the measured reclassification rate and actual WAPE; do not claim that Holt–Winters wins unless it does.
- Upload the 2–3-minute YouTube walkthrough and include the video, repository, and live app links in the report.
- The dataset and SAP-ready export are simulated; this is not a live SAP connection.
- The role switcher is illustrative only: never enter real sensitive, banking, customer or patient data.
- Streamlit Community Cloud's SQLite may be ephemeral and shared across visitors; this is not production persistence.

## Validation

```bash
python -m pytest -q
```

`data/demo.sqlite` is generated automatically and excluded from git. The reproducible seed script is the dataset source.
