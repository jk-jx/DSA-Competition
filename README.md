# Lives Group Case — Master Data & Regional Intelligence

**SMU DSA Society 2026 Data Case Competition** · Unified operations portal prototype

**[Open the working Streamlit portal](https://dsa-competition-4w84ptpcxfowwbvj5l3kkh.streamlit.app/)**

## How to use it

The complete **[Workspace User Guide](DSA/README.md)** explains all five workspaces, roles, approval steps, forecasting, admin settings, and demo limitations.

For a short demonstration:

1. **Master Data → Quality exceptions:** inspect customer aliases and purchasing risk.
2. **Master Data → Approval inbox:** open preloaded request **RQ-0001**.
3. Change **Viewing as** in the left sidebar to **Finance Steward** and approve; then **BU Steward** and approve; then **MDM Steward** to **Confirm and finalize**.
4. **Regional Performance:** examine the source evidence and the resulting customer growth correction **−40% → +20%**. Physical PO quantities remain unchanged.
5. **Insights & Forecasts:** inspect purchase-order-only forecasting, the machine-learning and unfiltered-data comparison, then build/export a 6- or 12-month purchasing plan.

**Data are synthetic.** User roles, Outlook/Teams routing and SAP handoff are demonstrations, not Live Lives Group integrations. The original project PDF is the authoritative design: Streamlit/SQLite serves as the prototype for a proposed M365/SAP production rollout.

## Source and deployment

- Application: [DSA/app.py](DSA/app.py); full project in [DSA/](DSA/).
- Streamlit Community Cloud: repository `jk-jx/DSA-Competition`, branch `main`, entry point `DSA/app.py`.
- Local setup: open [DSA/README.md](DSA/README.md#install-and-validate-locally).
- Competition submission: final two-page report, public GitHub repository, working app and 2–3-minute YouTube walkthrough.

**Deadline: 28 October 2026, 12 PM SGT.**
