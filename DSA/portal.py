"""Integrated operations portal backed by the existing synthetic MDM and PO database.

Views share a role switcher, request selection, consistent navigation and data.
This is an interactive case-study portal, not a production access-control system.
"""
import json
import pandas as pd
import plotly.express as px
import streamlit as st

from config import COUNTRIES, ENTITIES, ROLE_ACTOR, settings
from database import load_df
from dedup import find_matches
from forecast import backtest
from insights import (
    DISPLAY_START, LATEST, cross_sell, customer_growth, decision_impact,
    dropoff, hero_customer, monthly, record_type_counts, regional_summary,
)
from intake_parser import extract_message
from sap_integration import configured as sap_configured, send_live, SAPIntegrationError
from sla import process_sla, sla_snapshot
from workflow import (
    WorkflowError, add_approval_rule, decide, finalize, submit_request,
)
from ui import hero, panel, pill

SECTIONS = ["Overview", "Master Data", "Regional Performance", "Insights & Forecasts", "Administration"]
WORK_VIEWS = ["Request tracker", "Create request", "Approval inbox"]


def go(section, work_view=None, role=None, request=None):
    st.session_state["portal_section"] = section
    if work_view is not None:
        st.session_state["workspace_view"] = work_view
    if role is not None:
        st.session_state["portal_role"] = role
    if request is not None:
        st.session_state["chosen_request"] = request


def nav_button(title, section, work_view=None, role=None, request=None, primary=False, key=None):
    st.button(
        title, use_container_width=True, type="primary" if primary else "secondary",
        key=key, on_click=go, args=(section, work_view, role, request)
    )


def requests():
    return load_df(
        """SELECT request_key, domain, record_name, country, entity,
                  requested_by, status, match_source_id, match_target_id, created_at
           FROM mdm_requests ORDER BY id DESC"""
    )


def task_summary():
    return load_df(
        """SELECT a.request_key, a.steward, a.state, r.record_name, r.country,
                  r.domain, r.status
           FROM approval_tasks a JOIN mdm_requests r
           ON a.request_key=r.request_key
           WHERE a.state='Pending' AND r.status='In Approval'
           ORDER BY r.id DESC"""
    )


def portal_header(title, subtitle):
    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        st.markdown(
            '<p class="portal-eyebrow">LIVES GROUP &nbsp; / &nbsp; OPERATIONS</p>',
            unsafe_allow_html=True,
        )
        st.markdown("## " + title)
        st.caption(subtitle)
    with right:
        st.markdown(
            '<div class="portal-status"><span class="status-dot"></span>'
            ' DEMONSTRATION ENVIRONMENT</div>',
            unsafe_allow_html=True,
        )
    st.divider()


def overview():
    portal_header("Operations overview", "A shared view of master data, approvals and regional purchasing.")
    req = requests()
    pending = task_summary()
    mapped = load_df("SELECT COUNT(*) AS n FROM identity_map").iloc[0]["n"]
    counts = record_type_counts()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Master-data requests", f"{len(req)}")
    k2.metric("Pending approvals", f"{len(pending)}")
    k3.metric("Verified identity links", f"{int(mapped)}")
    k4.metric("Purchase-order lines", f"{counts.get('PO',0):,}")

    st.markdown("### Your workspace")
    a, b, c = st.columns(3)
    with a:
        with st.container(border=True):
            st.markdown("#### Create a request")
            st.caption("Validate customer or item details, detect possible duplicates and send for review.")
            nav_button("New request  →", "Master Data", "Create request", primary=True, key="home_new")
    with b:
        with st.container(border=True):
            st.markdown("#### Review approvals")
            st.caption("See the pending work queue, delegated deadlines and latest decisions.")
            nav_button("Open approval inbox  →", "Master Data", "Approval inbox", key="home_review")
    with c:
        with st.container(border=True):
            st.markdown("#### Regional performance")
            st.caption("Explore five-country purchasing trends and the effect of verified records.")
            nav_button("View purchasing  →", "Regional Performance", key="home_regional")

    st.markdown("### Decision intelligence")
    hero_data = hero_customer()
    impact = decision_impact()
    x, y = st.columns([1.45, 1])
    with x:
        with st.container(border=True):
            st.markdown("**Featured account · Hospital ABC**")
            st.caption("An identity issue can reverse a sales interpretation.")
            b, a = st.columns(2)
            b.metric("Before reconciliation", f"{hero_data['raw']['growth']:+.0f}%")
            a.metric("Approved consolidated view", f"{hero_data['cleaned']['growth']:+.0f}%")
            if hero_data["resolved"]:
                st.success("Identity verified: the account is growing, not declining.")
            else:
                st.info("A pending identity check is hiding the true customer trend.")
            nav_button("Review impact and source data  →", "Regional Performance", key="home_impact")
    with y:
        with st.container(border=True):
            st.markdown("**Data-quality decision impact**")
            st.metric("Customers reclassified", f"{impact['changed']} / {impact['eligible']}")
            st.caption("Percentage: {:.2f}% of eligible comparable canonical accounts.".format(impact["percent"]))
            st.caption("Confirmed PO totals are never inflated by alias reconciliation.")
            nav_button("Explore recommendations  →", "Insights & Forecasts", key="home_action")

    left, right = st.columns([1.3, 1])
    with left:
        st.markdown("### Recent requests")
        short = req[["request_key", "record_name", "domain", "status"]].head(6).rename(columns={
            "request_key": "Request", "record_name": "Record", "domain": "Type", "status": "Status"
        })
        st.dataframe(short, hide_index=True, use_container_width=True)
        nav_button("Open request tracker  →", "Master Data", "Request tracker", key="home_requests")
    with right:
        st.markdown("### Attention required")
        alerts = sla_snapshot()
        overdue = sum(1 for t in alerts if t["sla_status"] == "Overdue")
        soon = sum(1 for t in alerts if t["sla_status"] == "Due soon")
        with st.container(border=True):
            st.metric("Overdue steward tasks", overdue)
            st.caption("{} more due within 24 hours · {} active tasks".format(soon, len(alerts)))
            st.caption("Approval SLAs and escalation are calculated in working days.")
            nav_button("Manage approval queue  →", "Master Data", "Approval inbox", key="home_sla")


def _example_request():
    st.session_state["req_domain"] = "Customer"
    st.session_state["req_Customer_name"] = "ABC Hospital"
    st.session_state["req_Customer_country"] = "SG"
    st.session_state["req_Customer_entity"] = "QTS"
    st.session_state["req_Customer_registration_number"] = "SG-REG-000001"
    st.session_state["parsed_email"] = None
    st.session_state["request_method"] = "Quick form"


def request_form():
    st.markdown("### New master-data request")
    st.caption("Start with the sample case or paste an email. All requests are checked before they enter the approval queue.")
    left, right = st.columns([1, 2], vertical_alignment="center")
    with left:
        st.button("Use sample customer request", on_click=_example_request,
                  type="primary", use_container_width=True)
    with right:
        st.caption("Example: ABC Hospital, QTS, Singapore. The app finds an existing customer alias and routes it for human verification.")

    st.radio("How would you like to start?", ["Quick form", "From email"],
             key="request_method", horizontal=True)
    if st.session_state["request_method"] == "From email":
        with st.container(border=True):
            pasted = st.text_area("Request email", key="portal_email", height=115,
                placeholder="Please create customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001.")
            llm = st.checkbox("Use configured Azure OpenAI extraction", value=False,
                              help="The rules-based option works without any external credentials.")
            if st.button("Extract and prefill", disabled=not pasted.strip(), use_container_width=True):
                try:
                    result = extract_message(pasted, use_llm=llm)
                    st.session_state["parsed_email"] = result
                    domain = result["domain"]
                    st.session_state["req_domain"] = domain
                    fields = settings()["domains"].get(domain, {}).get("fields", {})
                    for field, value in result["fields"].items():
                        if field in fields:
                            st.session_state[f"req_{domain}_{field}"] = value
                    st.rerun()
                except Exception as exc:
                    st.error("Could not extract details: " + str(exc))
            parsed = st.session_state.get("parsed_email")
            if parsed:
                st.success("Email analyzed. Review the prefilled fields below.")
                a, b, c = st.columns(3)
                a.metric("Message type", parsed["record_type"])
                b.metric("Request domain", parsed["domain"])
                c.metric("Extraction", "AI assisted" if parsed["method"] != "rules" else "Rules")
                if parsed["record_type"] != "MDM Setup":
                    st.warning("This is not a master-data setup request. PO, enquiries and customer purchasing requests are excluded from MDM setup approval.")
                if st.button("Clear extracted message"):
                    st.session_state.pop("parsed_email", None)
                    st.rerun()

    cfg = settings()["domains"]
    domain = st.selectbox("Master-data domain", list(cfg), key="req_domain")
    info = cfg[domain]
    if info.get("prototype_status") == "config_only":
        st.info("{} uses configuration-only rules in this student version. Choose Customer or Item for end-to-end processing.".format(domain))
        return

    st.markdown("#### Request information")
    vals = {}
    a, b = st.columns(2)
    for i, (key, spec) in enumerate(info["fields"].items()):
        col = a if i % 2 == 0 else b
        with col:
            label = spec["label"] + (" *" if key in info["required"] else "")
            widget_key = f"req_{domain}_{key}"
            if spec["type"] == "country":
                vals[key] = st.selectbox(label, list(COUNTRIES), format_func=lambda v: COUNTRIES[v], key=widget_key)
            elif spec["type"] == "entity":
                configured = load_df("SELECT DISTINCT entity FROM approval_matrix")["entity"].tolist()
                vals[key] = st.selectbox(label, sorted(set(ENTITIES + configured)), key=widget_key)
            else:
                vals[key] = st.text_input(label, key=widget_key)

    missing = [field for field in info["required"] if not str(vals.get(field, "")).strip()]
    match_source = match_target = None
    if missing:
        st.warning("Complete these required fields: " + ", ".join(missing))
    else:
        st.success("Required fields complete.")

    if domain == "Customer" and vals.get("name", "").strip():
        matches = find_matches(vals["name"], domain, vals["country"])
        if matches:
            with st.container(border=True):
                st.markdown("#### Possible duplicates")
                st.caption("Similar names are suggestions, not evidence of identical legal entities.")
                md = pd.DataFrame(matches)[["existing_name", "customer_id", "score", "tier"]]
                st.dataframe(md.rename(columns={
                    "existing_name": "Existing customer", "customer_id": "Record",
                    "score": "Similarity", "tier": "Risk"
                }), hide_index=True, use_container_width=True)
        else:
            st.caption("No high-scoring customer-name match found.")

        if vals.get("registration_number", "").strip():
            verified = load_df(
                """SELECT customer_id,name,entity,canonical_truth_id FROM customers
                   WHERE country=? AND registration_number=? ORDER BY customer_id""",
                (vals["country"], vals["registration_number"].strip())
            )
            if len(verified) >= 2:
                ids = verified["customer_id"].tolist()
                mapped = set(load_df("SELECT alias_id FROM identity_map")["alias_id"].tolist())
                options = verified.set_index("customer_id").to_dict("index")
                candidates = [x for x in ids if x not in mapped and x != options[x]["canonical_truth_id"]]
                if candidates:
                    with st.container(border=True):
                        st.markdown("#### Match and merge → golden record")
                        st.caption("Matching business identifiers found. Link an existing alias, rather than creating another customer, after steward approval.")
                        enable = st.checkbox("Propose verified identity resolution", value=True, key="req_link_existing")
                        if enable:
                            match_source = st.selectbox("Existing duplicate / alias", candidates,
                                format_func=lambda c: f"{options[c]['name']} ({c})")
                            targets = [x for x in ids if x != match_source and x not in mapped]
                            if targets:
                                preferred = [x for x in targets if x == options[x]["canonical_truth_id"]]
                                match_target = st.selectbox("Golden record to retain", targets,
                                    index=targets.index(preferred[0]) if preferred else 0,
                                    format_func=lambda c: f"{options[c]['name']} ({c})")
                            st.caption("The MDM steward confirms this choice. Original purchase-order rows are never rewritten.")
                else:
                    st.info("These existing identities have already been reconciled.")

    parsed = st.session_state.get("parsed_email")
    permitted = not parsed or parsed["record_type"] == "MDM Setup" or st.session_state["request_method"] == "Quick form"
    reviewed = st.checkbox("I have checked the details and possible duplicates.", key="req_ack")
    if st.button("Submit for approval", type="primary", use_container_width=True,
                 disabled=bool(missing) or not permitted or not reviewed):
        try:
            key = submit_request(domain, vals, requester=ROLE_ACTOR[st.session_state["portal_role"]],
                                 merge_source=match_source, merge_target=match_target)
            st.session_state["portal_last_request"] = key
            st.session_state["chosen_request"] = key
            st.success(f"Request {key} submitted. It is now in the approval queue.")
        except WorkflowError as exc:
            st.error(str(exc))
    if st.session_state.get("portal_last_request"):
        nav_button("Track and review request  →", "Master Data", "Approval inbox",
                   request=st.session_state["portal_last_request"], key="after_submit")


def request_tracker():
    st.markdown("### Request tracker")
    st.caption("A single view of what was submitted, who is reviewing and what has been completed.")
    data = requests()
    if data.empty:
        st.info("No requests yet. Create a new master-data request.")
        nav_button("Create request", "Master Data", "Create request", key="empty_new")
        return
    a, b = st.columns([1, 1])
    with a:
        status = st.selectbox("Filter by status", ["All"] + sorted(data["status"].unique().tolist()))
    with b:
        search = st.text_input("Search requests", placeholder="Customer name or request ID")
    shown = data
    if status != "All":
        shown = shown[shown.status == status]
    if search:
        shown = shown[shown["record_name"].str.contains(search, case=False, na=False) |
                      shown["request_key"].str.contains(search, case=False, na=False)]
    st.dataframe(shown[["request_key", "record_name", "domain", "country", "status", "created_at"]].rename(
        columns={"request_key": "Request", "record_name": "Name", "domain": "Type",
                 "country": "Country", "status": "Status", "created_at": "Submitted at"}),
        hide_index=True, use_container_width=True)
    a, b = st.columns(2)
    with a:
        nav_button("Create new request", "Master Data", "Create request", key="track_create", primary=True)
    with b:
        nav_button("Open approval inbox", "Master Data", "Approval inbox", key="track_approve")


def _set_role(role):
    st.session_state["portal_role"] = role


def approval_inbox():
    st.markdown("### Approval inbox")
    st.caption("Independent data stewards review their assigned tasks before final MDM authorization.")
    req = requests()
    if req.empty:
        st.info("No requests available.")
        return
    keys = req["request_key"].tolist()
    preferred = st.session_state.get("portal_last_request")
    if st.session_state.get("chosen_request") not in keys:
        st.session_state["chosen_request"] = preferred if preferred in keys else keys[0]
    key = st.selectbox("Request", keys, key="chosen_request",
        format_func=lambda k: f"{k} · {req.loc[req.request_key==k,'record_name'].iloc[0]}")
    item = req.set_index("request_key").loc[key]
    role = st.session_state["portal_role"]
    if role == "Requestor":
        st.info("You are viewing this as Requestor. Choose a steward role in the sidebar to make an approval decision.")
    x, y, z = st.columns(3)
    x.metric("Request", key)
    y.metric("Status", item.status)
    z.metric("Domain", item.domain)
    if pd.notna(item.match_source_id) and pd.notna(item.match_target_id):
        panel("Identity resolution proposed",
              f"{item.match_source_id} → {item.match_target_id} · Existing customer IDs are reviewed; original orders stay intact.")
    tasks = load_df(
        "SELECT steward,state,decision_by,decision_at FROM approval_tasks WHERE request_key=? ORDER BY id", (key,)
    )
    st.markdown("#### Approval progress")
    st.dataframe(tasks.rename(columns={
        "steward": "Approver", "state": "Status", "decision_by": "Decision by",
        "decision_at": "Completed at"
    }), hide_index=True, use_container_width=True)
    active = tasks[(tasks.steward == role) & (tasks.state == "Pending")]
    if item.status == "In Approval" and not active.empty:
        st.markdown(f"**Your action · {role}**")
        a, b = st.columns(2)
        with a:
            if st.button("Approve request", type="primary", use_container_width=True, key="approve_this"):
                try:
                    decide(key, role, ROLE_ACTOR[role], "Approved")
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
        with b:
            if st.button("Reject request", use_container_width=True, key="reject_this"):
                try:
                    decide(key, role, ROLE_ACTOR[role], "Rejected")
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
    elif item.status == "In Approval":
        remaining = tasks[tasks.state == "Pending"].steward.tolist()
        if remaining:
            st.info(f"Awaiting {', '.join(remaining)}.")
            other = remaining[0]
            st.button(f"Switch to {other}", on_click=_set_role, args=(other,))
    elif item.status == "Approved":
        st.success("All assigned stewards approved this request. Ready for final MDM review.")
        if role == "MDM Steward":
            if st.button("Confirm and finalize", type="primary", key="finalize_this"):
                try:
                    finalize(key, ROLE_ACTOR[role])
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
        else:
            st.button("Continue as MDM Steward", on_click=_set_role, args=("MDM Steward",),
                      type="primary")
    elif item.status == "Created":
        st.success("Completed. The approved identity and SAP-ready handoff are recorded.")
        nav_button("See the effect on customer growth  →", "Regional Performance",
                   key="approved_impact", primary=True)
    elif item.status == "Rejected":
        st.warning("This request was rejected. No SAP-ready creation was performed.")

    with st.expander("Deadlines and escalation"):
        scoped = [i for i in sla_snapshot() if i["request_key"] == key]
        if scoped:
            st.dataframe(pd.DataFrame(scoped)[
                ["steward", "due_at", "sla_status", "delegate"]].rename(columns={
                "steward": "Reviewer", "due_at": "Due",
                "sla_status": "Status", "delegate": "Escalate to"}),
                hide_index=True, use_container_width=True)
            if st.button("Process reminders", key="do_reminders"):
                try:
                    outcomes = process_sla(notify=True)
                    st.success(f"{len(outcomes)} new reminder or escalation event(s) processed.")
                except Exception as exc:
                    st.error(f"Could not process notifications: {type(exc).__name__}")
        else:
            st.caption("No active SLA tasks for this request.")
    with st.expander("Activity history"):
        audit = load_df(
            "SELECT happened_at,actor,event,details FROM audit_log WHERE request_key=? ORDER BY id", (key,))
        st.dataframe(audit.rename(columns={
            "happened_at": "When", "actor": "By", "event": "Event", "details": "Detail"}),
            use_container_width=True, hide_index=True)
    sap = load_df("SELECT payload_json FROM sap_records WHERE request_key=?", (key,))
    if not sap.empty:
        with st.expander("SAP handoff and integration"):
            data = json.loads(sap.iloc[0].payload_json)
            st.caption("Prepared for SAP Business One. This public demo does not create a real ERP record.")
            st.write("Action: " + ("Link existing identity" if data.get("Action") == "LinkExistingIdentity"
                                     else "Create master record"))
            st.download_button("Export handoff file", json.dumps(data, indent=2),
                               file_name=f"handoff_{key}.json", mime="application/json")
            if role == "MDM Steward" and sap_configured():
                confirmed = st.checkbox("I am authorized to dispatch to the configured SAP tenant",
                                        key=f"sap_confirm_{key}")
                if st.button("Dispatch to SAP test tenant", disabled=not confirmed):
                    try:
                        st.success("ERP accepted request: " + str(send_live(key, confirm=True)))
                    except SAPIntegrationError as exc:
                        st.error(str(exc))


def master_data():
    portal_header("Master data workspace", "Create, track and approve clean customer and item records.")
    view = st.radio("Work area", WORK_VIEWS, key="workspace_view", horizontal=True,
                    label_visibility="collapsed")
    st.divider()
    if view == "Create request":
        request_form()
    elif view == "Approval inbox":
        approval_inbox()
    else:
        request_tracker()


def regional():
    portal_header("Regional purchasing", "Confirmed purchase orders across five markets and three product families.")
    impact = decision_impact()
    order = record_type_counts()
    x, y, z = st.columns(3)
    x.metric("Confirmed PO lines", f"{order.get('PO', 0):,}")
    y.metric("Customers reclassified", f"{impact['changed']} / {impact['eligible']}")
    z.metric("Decision-impact rate", f"{impact['percent']:.2f}%")

    account = hero_customer()
    st.markdown("### Featured customer · Before and after reconciliation")
    a, b = st.columns(2)
    with a:
        with st.container(border=True):
            st.caption("Raw customer record")
            st.metric("Latest 3 months vs previous 3", f"{account['raw']['growth']:+.1f}%")
            pill(account["raw"]["category"], "amber")
    with b:
        with st.container(border=True):
            st.caption("Approved consolidated customer")
            st.metric("Latest 3 months vs previous 3", f"{account['cleaned']['growth']:+.1f}%")
            pill(account["cleaned"]["category"], "green" if account["resolved"] else "gray")
    if not account["resolved"]:
        st.info("The duplicate is not yet approved. Complete the request in Master Data to reveal the corrected sales interpretation.")
        nav_button("Open approval inbox  →", "Master Data", "Approval inbox",
                   key="regional_review")
    else:
        st.success("The verified merge changes the account from declining to growing. Regional order totals remain unchanged.")

    st.markdown("### Market and product performance")
    a, b, c = st.columns(3)
    with a:
        country = st.selectbox("Country", ["All"] + list(COUNTRIES), format_func=lambda v: COUNTRIES.get(v, v))
    with b:
        product = st.selectbox("Product", ["All", "A", "B", "C"])
    with c:
        entity = st.selectbox("Business unit", ["All"] + ENTITIES)
    country = None if country == "All" else country
    product = None if product == "All" else product
    entity = None if entity == "All" else entity
    df = monthly(country, product)
    fig = px.line(df, x="period", y="qty", color="product", markers=True,
                  labels={"period": "Month", "qty": "PO quantity", "product": "Product"})
    fig.update_traces(line_width=3)
    fig.update_layout(height=340, margin=dict(l=10, r=10, t=15, b=0),
                      legend_title_text="", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    result = regional_summary(country, product, entity).rename(columns={
        "country": "Country", "product": "Product",
        "Latest 12 months": "Latest 12m", "Prior 12 months": "Prior 12m",
        "YoY growth %": "YoY growth %"
    })
    st.dataframe(result, hide_index=True, use_container_width=True)
    st.caption("YoY compares Sep 2025–Sep 2026 display year with the preceding twelve months in the 36-month history. Chart displays latest 12 months only.")
    with st.expander("Explore customer growth classifications"):
        raw = st.toggle("View raw, unreconciled customer identities")
        d = customer_growth(cleaned=not raw)
        st.dataframe(d.sort_values("latest", ascending=False).head(30), hide_index=True, use_container_width=True)
    with st.expander("Data definitions"):
        st.caption("Only confirmed customer POs are forecast as demand. Enquiries, purchasing requests and internal MDM setup requests are excluded. Identity mapping changes account attribution but never duplicates transaction rows.")
    nav_button("See forecasts and recommended actions  →", "Insights & Forecasts",
               key="regional_next", primary=True)


@st.cache_data(show_spinner="Evaluating forecasts on matched historical periods…")
def forecast_results():
    return backtest()


def insights():
    portal_header("Insights & forecasts", "Evidence-based demand predictions and account actions.")
    impact = decision_impact()
    k1, k2, k3 = st.columns(3)
    counts = record_type_counts()
    k1.metric("Decision impact", f"{impact['percent']:.2f}%")
    k2.metric("POs analyzed", f"{counts.get('PO',0):,}")
    k3.metric("Enquiries excluded", f"{counts.get('Enquiry',0):,}")

    st.markdown("### What should the account team do?")
    customer = hero_customer()
    x, y = st.columns(2)
    with x:
        with st.container(border=True):
            st.caption("Before identity reconciliation")
            st.metric("Hospital ABC", f"{customer['raw']['growth']:+.0f}%")
            st.warning("Possible customer drop-off → investigate")
    with y:
        with st.container(border=True):
            st.caption("After identity reconciliation")
            st.metric("Hospital ABC", f"{customer['cleaned']['growth']:+.0f}%")
            if customer["resolved"]:
                st.success("Growing account → assess expansion and cross-selling")
            else:
                st.info("Awaiting verified identity mapping")
    st.markdown("### Compare forecast models")
    summary, history = forecast_results()
    st.caption("Rolling-origin evaluation on exactly the same confirmed PO actuals; lower WAPE is better.")
    a, b = st.columns(2)
    for col, row in zip((a, b), summary.itertuples(index=False)):
        with col:
            st.metric(row.model, f"{float(getattr(row, '_1', float('nan'))):.1f}%" if False else
                      f"{float(summary.loc[summary.model==row.model, 'WAPE %'].iloc[0]):.2f}% WAPE")
    st.plotly_chart(px.bar(summary, x="model", y="WAPE %", text="WAPE %",
                           labels={"model": "Model"}, color="model")
                    .update_layout(showlegend=False, height=270,
                                   margin=dict(l=5, r=5, t=5, b=5)),
                    use_container_width=True)
    baseline = float(summary.loc[summary.model == "6-month moving average", "WAPE %"].iloc[0])
    holt = float(summary.loc[summary.model == "Holt-Winters", "WAPE %"].iloc[0])
    winner = "6-month moving average" if baseline <= holt else "Holt-Winters"
    st.caption(f"Best evaluated method: {winner}. No forecast improvement is claimed without measured evidence.")
    a, b = st.columns(2)
    with a:
        st.markdown("#### Customer drop-off watchlist")
        d = dropoff()
        if len(d):
            st.dataframe(d[["resolved_id", "growth_pct"]].rename(columns={
                "resolved_id": "Customer ID", "growth_pct": "Recent growth %"
            }), hide_index=True, use_container_width=True)
        else:
            st.caption("No accounts trigger the current rule.")
    with b:
        st.markdown("#### Cross-selling candidates")
        c = cross_sell()
        if len(c):
            st.dataframe(c[["resolved_id", "action"]].rename(columns={
                "resolved_id": "Customer ID", "action": "Suggested next step"
            }), hide_index=True, use_container_width=True)
        else:
            st.caption("No accounts trigger the current rule.")
    with st.expander("Methodology"):
        st.caption("36 months of synthetic data, 15 country–product series, three matched monthly forecasting origins. Holt–Winters is evaluated against a six-month moving average. Recommendations are rule-based and must be checked by sales teams.")
        st.dataframe(summary, hide_index=True, use_container_width=True)


def administration():
    portal_header("Administration", "Maintain approval routing and review system connection status.")
    role = st.session_state["portal_role"]
    st.markdown("### Enterprise integrations")
    from intake_parser import setting
    statuses = [
        ("Email extraction", "Rules-based enabled · optional Azure OpenAI" if not setting("AZURE_OPENAI_API_KEY") else "Azure OpenAI configured"),
        ("Teams notifications", "Configured" if setting("TEAMS_WEBHOOK_URL") else "Demonstration mode"),
        ("SAP Business One", "Configured for authorized dispatch" if sap_configured() else "SAP-ready handoff only"),
    ]
    st.dataframe(pd.DataFrame(statuses, columns=["Service", "Status"]), hide_index=True, use_container_width=True)
    st.caption("No production credentials are needed for the competition walkthrough.")

    st.markdown("### Approval routing matrix")
    matrix = load_df("SELECT entity,domain,country,steward,delegate,sla_days FROM approval_matrix ORDER BY entity,domain,country,steward")
    filters = st.columns([1, 1, 1])
    with filters[0]:
        entity = st.selectbox("Business unit", ["All"] + sorted(matrix.entity.unique().tolist()))
    with filters[1]:
        domain = st.selectbox("Domain", ["All"] + sorted(matrix.domain.unique().tolist()))
    with filters[2]:
        country = st.selectbox("Market", ["All"] + list(COUNTRIES))
    shown = matrix
    for field, value in [("entity", entity), ("domain", domain), ("country", country)]:
        if value != "All":
            shown = shown[shown[field] == value]
    st.dataframe(shown.rename(columns={
        "entity": "Unit", "domain": "Domain", "country": "Market",
        "steward": "Approver", "delegate": "Backup", "sla_days": "SLA days"
    }), hide_index=True, use_container_width=True)

    if role != "Admin":
        st.info("Switch to the Admin demo role in the sidebar to add routing rules.")
        return
    with st.expander("Add a new routing rule"):
        with st.form("routing_form"):
            a, b, c = st.columns(3)
            with a:
                ent = st.text_input("Business unit", value="NEWBU")
            with b:
                dom = st.selectbox("Record domain", list(settings()["domains"]))
            with c:
                cc = st.selectbox("Country", list(COUNTRIES))
            steward = st.selectbox("Assigned data steward", [
                "Finance Steward", "BU Steward", "Quality Steward"
            ])
            sla = st.number_input("SLA (working days)", min_value=1, max_value=30, value=2)
            submitted = st.form_submit_button("Save approval rule", type="primary")
        if submitted:
            try:
                add_approval_rule(ent.strip().upper(), dom, cc, steward, sla_days=int(sla))
                st.success("Approval rule saved. New requests use the updated routing without code changes.")
            except WorkflowError as exc:
                st.error(str(exc))


def render():
    section = st.session_state["portal_section"]
    if section == "Overview":
        overview()
    elif section == "Master Data":
        master_data()
    elif section == "Regional Performance":
        regional()
    elif section == "Insights & Forecasts":
        insights()
    else:
        administration()
