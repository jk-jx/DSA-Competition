# Operations Portal — Workspace User Guide

**SMU DSA Society 2026 Data Case Competition · Lives Group case**

The app demonstrates the solution in the original **DSA Competition (1).pdf**: validate new master-data records, investigate duplicate identities, route independent approvals, prepare an SAP-ready handoff, then use confirmed purchase orders and clean identities for better regional decisions.

**[Open the live portal](https://dsa-competition-4w84ptpcxfowwbvj5l3kkh.streamlit.app/)** · **[View the source repository](https://github.com/jk-jx/DSA-Competition)**

> **Synthetic competition demonstration:** The portal uses Streamlit + SQLite, with simulated user roles and SAP/Outlook/Teams handoffs. It is not a production-secure enterprise system. Do not enter real customers, patient details, passwords or financial records.

## Getting around

The left sidebar has **five workspaces**:

| Workspace | What employees do |
| --- | --- |
| **Overview** | Monitor pending reviews, quality exceptions and purchasing insights |
| **Master Data** | Open **Quality exceptions**, **Request tracker**, **Create request** or **Approval inbox** |
| **Regional Performance** | Explore five-country, product A/B/C purchases and customer identity impact |
| **Insights & Forecasts** | Review actions, test three forecast models, create a 6/12-month plan and estimate potential hidden demand |
| **Administration** | Inspect integrations, edit approval routing and examine illustrative time savings |

The left-sidebar **Viewing as (demo role)** selector sets the simulated persona. **No in-page button or assistant shortcut changes roles.** The floating **✦ Ask Operations** guide gives optional context and navigation; it is not a generative AI chatbot.

## Main judge demo: clean identity → correct business action

The app starts with a seeded customer review, **RQ-0001**, for **ABC Hospital / Hospital ABC**. Use this rather than creating another request when recording a time-limited demonstration.

1. Open **Overview**, then **Master Data → Quality exceptions**. See 25 synthetic candidate identity pairs and their purchasing exposure. Select the sample Singapore alias **SG-A001** to inspect its possible canonical record **SG-C001**. You may switch from table to the optional **3D identity network** (zoom/rotate/tooltips). This visualization proposes links; it does not merge records.
2. Open **Master Data → Approval inbox** and select **RQ-0001**. Review the registered-identity evidence, PO history and pending reviewer tasks.
3. In **Viewing as** (left sidebar), select **Finance Steward**. Open RQ-0001 and select **Approve request**.
4. Change **Viewing as** to **BU Steward** and approve the same request.
5. Change **Viewing as** to **MDM Steward**. When its status is **Approved**, select **Confirm and finalize**. It becomes **Created** and records a safe-retry, SAP-ready mock handoff.
6. Visit **Regional Performance**. Before approved matching, Hospital ABC's primary ID falls from **100 → 60 units (−40%)**. The alias adds **60 units** in the latest period; **after** verified consolidation the same account is **100 → 120 units (+20%)**. No source PO transaction or country-level total is changed.
7. Visit **Insights & Forecasts**. Examine the changing account recommendation, the three PO-only model backtests, contamination ablation, 6/12-month demand planner and **Export purchasing plan (CSV)**.

**Measurement:** the seeded approved reconciliation reclassifies **1 of 233 eligible comparable canonical customers (about 0.43%)**. Before MDM finalization the +20% view is clearly an **unapproved scenario**, not live consolidated analytics.

**Reset carefully:** **Reset demonstration** in the sidebar restores the original seeded data and RQ-0001. The public SQLite database may be shared across visitors and is not durable across hosting restarts. A reset can interrupt another person's work.

## How to use each workspace

### Master Data → Quality exceptions

- Filter by **Market** and **Case status**. The queue displays alias ID, proposed golden record, country, review priority, possible decision-category change, and purchase-order exposure.
- Choose a candidate under **Inspect candidate**, then select **Prepare customer review** to prefill **Create request** with its identity details. Independently confirm the suggested identifiers and retained record before submitting.
- The queue's 25 seeded candidate pairs rely partly on synthetic known reference relationships. **This is not a measured real-world duplicate-detection recall rate.** Fuzzy name matching is separate and never auto-merges real companies.

### Master Data → Create request

1. Choose **Quick form** or **From email** under **Intake channel**.
2. Select **Customer** or **Item** (fully functional). **Vendor** and **Cost Center** are configuration-only examples.
3. Enter the required domain fields. For customers, similarity suggestions and verified-registration comparisons can propose linking an existing alias to a retained/golden record.
4. Tick the details confirmation and select **Submit for approval**. Open **Request tracker** to follow the resulting RQ-numbered case.

**Email simulation:** Choose **From email**, paste a synthetic message and select **Extract and prefill**. Rules-first extraction works offline. **Use configured Azure OpenAI extraction** requires separate authorized credentials. **Email routing & response simulation** previews how an MDM mailbox would classify the message, send a proposed reply, observe a two-week grace period or enable authorized MDM override. **It does not send Outlook mail or create Teams Adaptive Cards.**

Example email:

> Please create customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001.

**Record categories remain distinct:** confirmed PO, customer purchasing request, enquiry and internal MDM setup. Only setup messages can enter the MDM approval workflow.

### Master Data → Request tracker and Approval inbox

The tracker provides request IDs, originators, domain, market and status. The inbox adapts to the chosen demo persona:

| Sidebar persona | Available work |
| --- | --- |
| **Requestor** | Review own submitted requests and current status |
| **Finance Steward** | Customer domain decisions assigned to Finance |
| **BU Steward** | Business-unit review alongside Finance or Quality |
| **Quality Steward** | Item domain decisions assigned to Quality |
| **MDM Steward** | Final validation after all assigned stewards approve |
| **Admin** | Maintain approval rules in Administration |

Eligible stewards see **Approve request** and **Reject request**; other users see only the case status. Customer requests use **Finance + BU**; Item uses **Quality + BU**, both with final **MDM validation**. Maker-checker separation prevents the requestor approving their own request.

Statuses: **Submitted → In Approval → Approved → Created** or **Rejected**. Expand **Approval deadlines**, **Audit history**, or **ERP handoff** to inspect supporting information. SLA events are idempotent; unattended real reminders would require an external scheduler.

The mock ERP handoff is exportable JSON with a stable request ID. Real SAP creation is *not* part of the public walkthrough, and local identity links are not live SAP Business Partner merges.

### Regional Performance

Filter by country, Product **A/B/C**, and business unit. Review recent confirmed PO trend, year-on-year comparison and the identity impact. The evidence panel provides a six-month source-order breakdown for Hospital ABC and shows **current vs unapproved/approved consolidated** growth. A verified mapping changes account attribution, not the original physical order quantities.

The five selected markets — **Singapore, Malaysia, Indonesia, Thailand and Vietnam** — are **project assumptions**; the Lives Group brief specifies five country locations without naming them.

### Insights & Forecasts

- **Confirmed purchase orders only** feed valid forecasts. The dataset also includes **700 enquiries** and **300 customer purchasing requests**, excluded from PO demand. MDM requests are in their own workflow table.
- Compare **six-month moving average**, **Holt–Winters** and **pooled gradient boosting** over the **same 45 held-out country × product × month observations**. **Lower WAPE is better.** There is no assumed winner.
- The **unfiltered-input ablation** deliberately contaminates model training with quantities from enquiries/customer requests, but evaluates against **confirmed PO actuals**. It is a diagnostic run, not a purchasable forecast. MDM setups have no transaction quantity and are not invented as orders.
- Create a plan by selecting **Market**, **Product A/B/C**, **6 or 12 months** and one of the **three valid PO-only models**. Review low/base/high *planning scenarios* and select **Export purchasing plan (CSV)**. Scenarios are sensitivity bands, not confidence intervals.
- Explore drop-off and cross-sell candidates; these are **rules-based recommendations**, not automated customer decisions.
- Adjust the **Demand visibility** assumptions — days waiting, share needing a PO and illustrative PO value — to estimate *potential* delayed-order exposure. The dataset does not link setup requests to actual blocked orders. **This is not measured lost revenue.**
- The classifier benchmark uses a **small, curated synthetic labelled dataset**; it is not a claim about actual Outlook or LLM precision.

### Administration

View optional connector status and the **Approval routing matrix** keyed by entity, domain and country. In the **Admin** demo role, use **Add a new routing rule** to configure a business unit, steward and working-day SLA without editing code.

Change the **Illustrative operational savings** assumptions. Defaults: **50 requests/month**, **65 minutes before**, **26 minutes after**, **S$40/hour** → **32.5 hours/month** or **S$1,300/month in gross staff capacity**, not realized cash savings or verified ROI.

## FAQ and troubleshooting

| Problem | Check |
| --- | --- |
| Extra page links labelled app/actions/approvals/intake/regional | Refresh or reboot; the unified entry point hides Streamlit's legacy auto-generated navigation |
| Approve button unavailable | Correct role in **Viewing as**; selected request must be **In Approval** with a task assigned to that steward |
| Case has already been finalized | Inspect a different case, or reset only when other visitors are not using the shared demo |
| +20% appears as a preview | Both stewards **and** MDM must finalize before it becomes live consolidated analytics |
| Azure OpenAI extraction unavailable | Switch to rules-first extraction |
| No automatic Outlook / Teams / SAP activity | These integrations are **demonstrated as simulations** by default, not connected corporate services |
| Forecast takes time on first visit | Three-model chronological backtesting can require an initial calculation; subsequent results are cached |

## Install and validate locally

From the repository root:

~~~bash
cd DSA
python -m pip install -r requirements.txt pytest
python generate_data.py --reset
streamlit run app.py
~~~

Automated tests:

~~~bash
cd DSA
python -m pytest -q
~~~

**Streamlit deployment settings:** repo **jk-jx/DSA-Competition**, branch **main**, entry point **DSA/app.py**.

Optional secret names (never commit credentials): **AZURE_OPENAI_ENDPOINT**, **AZURE_OPENAI_DEPLOYMENT**, **AZURE_OPENAI_API_KEY**, **TEAMS_WEBHOOK_URL**, **SAP_B1_SERVICE_LAYER_URL**, **SAP_B1_COMPANY_DB**, **SAP_B1_USERNAME**, **SAP_B1_PASSWORD**. An authorized external scheduler is needed for unattended SLA notifications. **Never connect production SAP credentials to the public demo.**

## The PDF is the base — prototype vs production

| Current synthetic implementation | Original PDF's proposed enterprise deployment |
| --- | --- |
| Streamlit forms, role selector and PO dashboards | Power Apps / Power BI with authentic corporate user accounts |
| SQLite statuses, routing matrix and append-only audit events | SharePoint Lists or Dataverse, with restricted Finance/MDM data |
| In-app approval, reminders and mock notifications | Power Automate, Teams Approvals / Adaptive Cards and escalations |
| Pasted emails, rules-first/optional AI extraction, response preview | Shared Outlook mailbox interceptor, prefilled draft and controlled transition |
| RapidFuzz + human matching review | SAP-backed matching service / Azure Function with steward validation |
| Stable SAP-ready JSON and mock ledger | SAP Business One Service Layer and production reconciliation controls |

**Working in the demo:** Customer/Item intake, independent approvals, audit and routing, prioritized synthetic identity exceptions, 3D exploration, customer decision change, regional PO analytics, three models + ablation, 6/12-month export, email response/grace-period simulation and hidden-demand scenario.

**Not proven:** live enterprise authentication, real mail/Teams/SAP tenancy, production-sensitive-field protections, full Vendor/Cost Center forms, actual unknown-duplicate detection accuracy, real postponed orders, production time savings, or financial payback. The uploaded **DSA Competition (1).pdf** remains the authoritative solution design.

## Competition deliverables

Submit the **final two-page report (or two slides)**, **functioning prototype**, **public GitHub code**, and **2–3 minute YouTube demo**. Verify the live walkthrough and report claims, then insert the *real* YouTube URL before submission.

**Qualifying deadline: 28 October 2026, 12 PM Singapore time.**
