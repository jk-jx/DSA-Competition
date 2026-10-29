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
from insights import (
    DISPLAY_START, LATEST, cross_sell, customer_growth, decision_impact, identity_case_evidence,
    dropoff, hero_customer, monthly, record_type_counts, regional_summary,
)
from intake_parser import extract_message
from sap_integration import configured as sap_configured, send_live, SAPIntegrationError
from sla import process_sla, sla_snapshot
from workflow import (
    WorkflowError, add_approval_rule, can_view_sensitive, decide, finalize, masked_payload, missing_fields,
    required_fields, reveal_sensitive, sensitive_fields, submit_request,
)
from ui import hero, panel, pill, metric_tile, section_label
from quality_monitor import quality_cases, quality_summary
from network_view import build_identity_network
from hidden_demand import hidden_demand_model
from email_routing import route_inbound_email
from classifier_evaluation import classifier_benchmark

SECTIONS = ["Overview", "Master Data", "Regional Performance", "Insights & Forecasts", "Administration"]
WORK_VIEWS = ["Quality exceptions", "Request tracker", "Create request", "Approval inbox"]


def go(section, work_view=None, request=None):
    """Navigate only; the role is controlled exclusively by the sidebar."""
    st.session_state["portal_section"] = section
    if work_view is not None:
        st.session_state["workspace_view"] = work_view
    if request is not None:
        st.session_state["chosen_request"] = request


def nav_button(title, section, work_view=None, request=None, primary=False, key=None):
    st.button(
        title, use_container_width=True, type="primary" if primary else "secondary",
        key=key, on_click=go, args=(section, work_view, request)
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
    from html import escape
    st.markdown(
        '<div class="portal-header-row"><div>'
        '<p class="portal-eyebrow">WORKSPACE / OPERATIONS</p>'
        f'<h1>{escape(title)}</h1><p>{escape(subtitle)}</p>'
        '</div><div class="portal-status"><span class="status-dot"></span>'
        'DEMO WORKSPACE</div></div>',
        unsafe_allow_html=True,
    )


def overview():
    portal_header("Good to have you here.", "A clear view of what needs attention across operations.")
    req = requests()
    pending = task_summary()
    mapped = load_df("SELECT COUNT(*) AS n FROM identity_map").iloc[0]["n"]
    counts = record_type_counts()
    section_label("At a glance", "Updated from the current synthetic workspace")
    k1, k2, k3, k4 = st.columns(4)
    with k1: metric_tile("Master-data requests", f"{len(req)}", "▤", "blue", "Tracked in the portal")
    with k2: metric_tile("Approvals waiting", f"{len(pending)}", "◷", "amber", "Steward decisions outstanding")
    with k3: metric_tile("Verified identity links", f"{int(mapped)}", "◇", "teal", "Customer records reconciled")
    with k4: metric_tile("Purchase-order lines", f"{counts.get('PO',0):,}", "↗", "slate", "Confirmed purchase orders")

    cases_summary=quality_summary()
    with st.container(border=True):
        a,b,c=st.columns([1,1,1])
        a.metric("Identity cases requiring attention",cases_summary["unresolved"])
        b.metric("Potential decision changes",cases_summary["decision_changers"])
        c.metric("Attributed PO units to examine",f'{cases_summary["units_attribution_exposure"]:,}')
        st.caption("Exceptions are derived from source identifiers and confirmed PO data, not hypothetical user-entered scores.")
        nav_button("Open data quality exceptions →","Master Data","Quality exceptions",key="overview_triage",primary=True)

    hero_data = hero_customer()
    impact = decision_impact()
    st.markdown(
        '<div class="portal-banner"><div class="tag">FEATURED INSIGHT  /  MASTER DATA QUALITY</div>'
        '<h2>The same customer. Two very different business decisions.</h2>'
        '<p>When duplicate customer identities are reconciled, sales teams can act on '
        'the right trend without changing a single original purchase order.</p></div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.35, 1])
    with left:
        with st.container(border=True, height=344):
            st.markdown("##### Featured account  ·  Hospital ABC")
            a, b = st.columns(2)
            with a:
                st.metric("Raw identity growth", f"{hero_data['raw']['growth']:+.0f}%")
            with b:
                st.metric("Approved consolidated growth", f"{hero_data['cleaned']['growth']:+.0f}%")
            if hero_data["resolved"]:
                st.success("Verified identity link · customer is growing")
            else:
                st.caption("The consolidated view becomes actionable after steward approval.")
            nav_button("Explore customer impact  →", "Regional Performance", key="home_impact")
    with right:
        with st.container(border=True, height=344):
            st.markdown("##### Decision-quality monitor")
            st.metric("Customer classifications changed", f"{impact['changed']} / {impact['eligible']}")
            st.caption(f"{impact['percent']:.2f}% decision impact on the synthetic comparable accounts.")
            st.caption("Accurate identity linking corrects attribution—not order volume.")
            nav_button("View insights & forecasts  →", "Insights & Forecasts", key="home_action")

    section_label("Your workspaces", "Quick access")
    a, b, c = st.columns(3)
    with a:
        with st.container(border=True, height=270):
            st.markdown('<div class="card-icon">✚</div><div class="panel-lead">Create a request</div>'
                        '<p class="card-description">Validate customer or item records before they enter the approval queue.</p>',
                        unsafe_allow_html=True)
            nav_button("Create request  →", "Master Data", "Create request",
                       primary=True, key="home_new")
    with b:
        with st.container(border=True, height=270):
            st.markdown('<div class="card-icon teal">✓</div><div class="panel-lead">Approval inbox</div>'
                        '<p class="card-description">Resolve requests with independent stewardship checks and traceable decisions.</p>',
                        unsafe_allow_html=True)
            nav_button("Review requests  →", "Master Data", "Approval inbox", key="home_review")
    with c:
        with st.container(border=True, height=270):
            st.markdown('<div class="card-icon violet">↗</div><div class="panel-lead">Regional performance</div>'
                        '<p class="card-description">Explore five-market purchasing trends, account performance and business opportunities.</p>',
                        unsafe_allow_html=True)
            nav_button("Explore analytics  →", "Regional Performance", key="home_regional")

    left, right = st.columns([1.45, 1])
    with left:
        section_label("Recent requests", "Latest activity")
        short = req[["request_key", "record_name", "domain", "status"]].head(6).rename(columns={
            "request_key": "Request", "record_name": "Record", "domain": "Type", "status": "Status"
        })
        st.dataframe(short, hide_index=True, use_container_width=True)
        nav_button("View all requests  →", "Master Data", "Request tracker", key="home_requests")
    with right:
        section_label("Approval health", "Working-day SLA")
        alerts = sla_snapshot()
        overdue = sum(1 for t in alerts if t["sla_status"] == "Overdue")
        soon = sum(1 for t in alerts if t["sla_status"] == "Due soon")
        with st.container(border=True, height=325):
            st.metric("Overdue decisions", overdue)
            st.caption(f"{soon} due soon  ·  {len(alerts)} currently tracked")
            st.progress((len(alerts) - overdue) / len(alerts) if alerts else 1.0,
                        text="Tasks not overdue")
            nav_button("Open review queue  →", "Master Data", "Approval inbox", key="home_sla")


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
    st.caption("Customer and item master-data intake")
    with st.expander("Sample request data"):
        st.button("Load sample customer record", on_click=_example_request,
                  use_container_width=False)

    st.radio("Intake channel", ["Quick form", "From email"],
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
            with st.expander("Email routing & response simulation"):
                mode=st.radio("Email transition policy",["Launch grace period","Structured form required"],horizontal=True,key="mail_policy")
                manual=st.checkbox("Authorized MDM manual override",key="mail_override")
                if pasted.strip():
                    routing=route_inbound_email(pasted,grace_period=mode=="Launch grace period",mdm_override=manual)
                    st.markdown("**Classification:** "+routing["record_type"])
                    st.markdown("**Routing:** "+routing["route"])
                    st.markdown("**Suggested reply:** "+routing["reply_subject"])
                    st.write(routing["reply_body"])
                    st.caption("Preview only. No Outlook message or Teams notification has been sent. Approvals remain governed in the inbox.")
                else:
                    st.caption("Paste a message to preview the classification, routing and reply.")
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
        st.caption("{}: domain setup is not yet active.".format(domain))
        return

    st.markdown("#### Request information")
    vals = {}
    a, b = st.columns(2)
    for i, (key, spec) in enumerate(info["fields"].items()):
        col = a if i % 2 == 0 else b
        with col:
            label = spec["label"] + (" *" if key in required_fields(info, vals) else "")
            widget_key = f"req_{domain}_{key}"
            if spec["type"] == "select":
                prefilled = st.session_state.get(widget_key)
                if prefilled is not None and prefilled not in spec["options"]:
                    # Email extraction yields free text such as "class b"; map it or leave the choice open.
                    text = str(prefilled).strip().lower()
                    st.session_state[widget_key] = next(
                        (o for o in spec["options"] if text in (o.lower(), o.lower().replace("class ", ""))), None)
                vals[key] = st.selectbox(label, spec["options"], index=None,
                                         placeholder="Select…", key=widget_key)
            elif spec["type"] == "country":
                vals[key] = st.selectbox(label, list(COUNTRIES), format_func=lambda v: COUNTRIES[v], key=widget_key)
            elif spec["type"] == "entity":
                configured = load_df("SELECT DISTINCT entity FROM approval_matrix")["entity"].tolist()
                vals[key] = st.selectbox(label, sorted(set(ENTITIES + configured)), key=widget_key)
            else:
                vals[key] = st.text_input(label, key=widget_key)

    missing = missing_fields(info, vals)
    match_source = match_target = None
    for rule in info.get("conditional_required", []):
        if rule["field"] in required_fields(info, vals):
            st.info(rule["reason"])
    if missing:
        labels = [info["fields"].get(field, {}).get("label", field) for field in missing]
        st.warning("Complete these required fields: " + ", ".join(labels))
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
                            prepared=st.session_state.get("prepared_alias")
                            match_source = st.selectbox("Existing duplicate / alias", candidates,
                                index=candidates.index(prepared) if prepared in candidates else 0,
                                format_func=lambda c: f"{options[c]['name']} ({c})")
                            targets = [x for x in ids if x != match_source and x not in mapped]
                            if targets:
                                preferred = [x for x in targets if x == options[x]["canonical_truth_id"]]
                                selected_target=st.session_state.get("prepared_target")
                                default_target=selected_target if selected_target in targets else preferred[0] if preferred else targets[0]
                                match_target = st.selectbox("Golden record to retain", targets,
                                    index=targets.index(default_target),
                                    format_func=lambda c: f"{options[c]['name']} ({c})")
                            st.caption("Link status: pending master-data validation · Transaction history retained")
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
            st.session_state.pop("prepared_alias",None)
            st.session_state.pop("prepared_target",None)
            st.success(f"Request {key} submitted. It is now in the approval queue.")
        except WorkflowError as exc:
            st.error(str(exc))
    if st.session_state.get("portal_last_request"):
        nav_button("Track and review request  →", "Master Data", "Approval inbox",
                   request=st.session_state["portal_last_request"], key="after_submit")


def request_tracker():
    st.markdown("### Request tracker")
    st.caption("Submitted records and approval status")
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


def request_details(key, domain, role):
    stored = json.loads(load_df("SELECT payload FROM mdm_requests WHERE request_key=?", (key,)).iloc[0].payload)
    fields = settings()["domains"][domain].get("fields", {})
    hidden = sensitive_fields(domain)
    reveal_flag = f"revealed_{key}_{role}"
    values = stored if st.session_state.get(reveal_flag) else masked_payload(domain, stored)
    rows = [{"Field": spec["label"] + (" (restricted)" if name in hidden else ""), "Value": str(values.get(name) or "")}
            for name, spec in fields.items() if str(stored.get(name) or "").strip()]
    with st.container(border=True):
        st.markdown("#### Request details")
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.caption("No field values recorded for this request.")
        if not any(name in hidden and str(stored.get(name) or "").strip() for name in fields):
            return
        if not can_view_sensitive(domain, role):
            st.caption("Bank and credit details are visible to Finance and MDM stewards only.")
        elif not st.session_state.get(reveal_flag):
            if st.button("Reveal sensitive fields (logged)", key=f"reveal_{key}"):
                try:
                    reveal_sensitive(key, role, ROLE_ACTOR[role])
                    st.session_state[reveal_flag] = True
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
        else:
            st.caption("Sensitive values shown. This view was recorded in the audit history.")


def approval_inbox():
    role=st.session_state["portal_role"]
    title="Request status" if role=="Requestor" else "Approval inbox"
    st.markdown(f"### {title}")
    req=requests()
    if req.empty:
        st.info("No requests have been submitted.")
        return

    task_rows=load_df(
        """SELECT request_key,steward,state FROM approval_tasks ORDER BY id"""
    )
    if role in ("Finance Steward","Quality Steward","BU Steward"):
        mine=task_rows[task_rows.steward==role]
        actionable=mine[mine.state=="Pending"]
        actionable=actionable[actionable.request_key.isin(req.loc[req.status=="In Approval","request_key"])]
        a,b=st.columns(2)
        a.metric("My pending reviews",len(actionable))
        b.metric("My completed reviews",len(mine[mine.state!="Pending"]))
        if actionable.empty:
            st.caption("No requests currently require your decision.")
    elif role=="MDM Steward":
        a,b=st.columns(2)
        a.metric("Ready for final validation",int((req.status=="Approved").sum()))
        b.metric("Records completed",int((req.status=="Created").sum()))
    elif role=="Requestor":
        owned=req[req.requested_by==ROLE_ACTOR["Requestor"]]
        a,b=st.columns(2)
        a.metric("My submitted requests",len(owned))
        b.metric("In progress",int(owned.status.isin(["Submitted","In Approval","Approved"]).sum()))
    else:
        st.caption("Request approvals and completion status across business units.")

    all_keys=req.request_key.tolist()
    current=st.session_state.get("chosen_request")
    preferred=st.session_state.get("portal_last_request")
    if current not in all_keys:
        st.session_state["chosen_request"]=preferred if preferred in all_keys else all_keys[0]

    key=st.selectbox(
        "Request",all_keys,key="chosen_request",
        format_func=lambda k: f"{k} · {req.loc[req.request_key==k,'record_name'].iloc[0]}"
    )
    item=req.set_index("request_key").loc[key]
    a,b,c=st.columns(3)
    a.metric("Request ID",key)
    b.metric("Status",item.status)
    c.metric("Record type",item.domain)
    st.caption(f"{item.record_name} · {item.entity} · {item.country} · Requested by {item.requested_by}")
    request_details(key, item.domain, role)

    tasks=load_df(
        "SELECT steward,state,decision_by,decision_at FROM approval_tasks WHERE request_key=? ORDER BY id",(key,)
    )
    if pd.notna(item.match_source_id) and pd.notna(item.match_target_id):
        panel("Identity reconciliation",f"{item.match_source_id} → {item.match_target_id} · Review of existing registered identities")

    if (item.domain=="Customer" and pd.notna(item.match_source_id)
            and pd.notna(item.match_target_id)
            and (item.match_source_id,item.match_target_id)==("SG-A001","SG-C001")):
        evidence=identity_case_evidence()
        with st.container(border=True):
            st.markdown("#### Supporting purchase-order evidence")
            a,b=st.columns(2)
            a.metric("Primary record growth",f"{evidence['primary_growth']:+.0f}%")
            b.metric("Combined identity growth",f"{evidence['combined_growth']:+.0f}%")
            if not evidence["approval_applied"]:
                st.caption("Unapproved identity scenario · Evidence for stewardship review, not a committed merge.")
            with st.expander("Source transactions · six months"):
                st.dataframe(evidence["monthly"],hide_index=True,use_container_width=True)
                st.caption("Source PO quantities are preserved without alteration.")

    st.markdown("#### Approval progress")
    st.dataframe(tasks.rename(columns={
        "steward":"Approver","state":"Status",
        "decision_by":"Decision by","decision_at":"Completed at"
    }),hide_index=True,use_container_width=True)

    pending=tasks[tasks.state=="Pending"].steward.tolist()
    active=role in pending
    if item.status=="In Approval":
        if active:
            st.markdown(f"#### Decision · {role}")
            a,b=st.columns(2)
            with a:
                if st.button("Approve request",type="primary",use_container_width=True,key="approve_this"):
                    try:
                        decide(key,role,ROLE_ACTOR[role],"Approved")
                        st.rerun()
                    except WorkflowError as exc:
                        st.error(str(exc))
            with b:
                if st.button("Reject request",use_container_width=True,key="reject_this"):
                    try:
                        decide(key,role,ROLE_ACTOR[role],"Rejected")
                        st.rerun()
                    except WorkflowError as exc:
                        st.error(str(exc))
        else:
            panel("In review", "Pending: "+", ".join(pending) if pending else "Review in progress")
    elif item.status=="Approved":
        if role=="MDM Steward":
            st.markdown("#### Final master-data validation")
            if st.button("Confirm and finalize",type="primary",key="finalize_this"):
                try:
                    finalize(key,ROLE_ACTOR[role])
                    st.rerun()
                except WorkflowError as exc:
                    st.error(str(exc))
        else:
            panel("Steward reviews complete","Awaiting final master-data validation")
    elif item.status=="Created":
        panel("Completed","Master-data approval and SAP-ready handoff recorded")
        nav_button("View business impact  →","Regional Performance",key="approved_impact",primary=True)
    elif item.status=="Rejected":
        panel("Rejected","No master-data creation or identity link was performed")

    with st.expander("Approval deadlines"):
        scoped=[i for i in sla_snapshot() if i["request_key"]==key]
        if scoped:
            st.dataframe(pd.DataFrame(scoped)[["steward","due_at","sla_status","delegate"]].rename(columns={
                "steward":"Reviewer","due_at":"Due","sla_status":"Status","delegate":"Backup"
            }),hide_index=True,use_container_width=True)
            if role in ("Finance Steward","Quality Steward","BU Steward","MDM Steward","Admin"):
                if st.button("Process reminders",key="do_reminders"):
                    try:
                        outcomes=process_sla(notify=True)
                        st.success(f"{len(outcomes)} reminder or escalation event(s) recorded.")
                    except Exception as exc:
                        st.error(f"Reminder processing unavailable: {type(exc).__name__}")
        else:
            st.caption("No active SLA tasks.")

    with st.expander("Audit history"):
        audit=load_df(
            "SELECT happened_at,actor,event,details FROM audit_log WHERE request_key=? ORDER BY id",(key,)
        )
        st.dataframe(audit.rename(columns={
            "happened_at":"When","actor":"By","event":"Event","details":"Detail"
        }),use_container_width=True,hide_index=True)

    sap=load_df("SELECT payload_json FROM sap_records WHERE request_key=?",(key,))
    if not sap.empty:
        with st.expander("ERP handoff"):
            data=json.loads(sap.iloc[0].payload_json)
            if not can_view_sensitive(item.domain, role):
                data={**data, "Values": masked_payload(item.domain, data.get("Values") or {})}
                st.caption("Bank and credit values are masked in this export for your role.")
            st.write("SAP-ready record prepared")
            st.caption("Integration status: local simulated handoff · No production ERP write")
            st.download_button("Export handoff",json.dumps(data,indent=2),
                               file_name=f"handoff_{key}.json",mime="application/json")
            if role=="MDM Steward" and sap_configured():
                confirmed=st.checkbox(
                    "I am authorized to dispatch to the configured SAP tenant",
                    key=f"sap_confirm_{key}"
                )
                if st.button("Dispatch to SAP test tenant",disabled=not confirmed):
                    try:
                        st.success("ERP accepted request: "+str(send_live(key,confirm=True)))
                    except SAPIntegrationError as exc:
                        st.error(str(exc))



def _prepare_quality_review(alias_id, case_data):
    """Prefill intake before widgets render; navigation stays consistent."""
    st.session_state["req_domain"]="Customer"
    st.session_state["req_Customer_name"]=case_data["alias_name"]
    st.session_state["req_Customer_country"]=case_data["country"]
    st.session_state["req_Customer_entity"]=case_data["entity"]
    st.session_state["req_Customer_registration_number"]=case_data["registration_number"]
    st.session_state["prepared_alias"]=alias_id
    st.session_state["prepared_target"]=case_data["target_id"]
    st.session_state["req_link_existing"]=True
    st.session_state["request_method"]="Quick form"
    go("Master Data","Create request")


def quality_exceptions():
    st.markdown("### Data quality exceptions")
    cases=quality_cases()
    summary=quality_summary(cases)
    a,b,c,d=st.columns(4)
    a.metric("Unresolved identity candidates",summary["unresolved"])
    b.metric("Cases under governance",summary["awaiting_review"])
    c.metric("Potential decision changes",summary["decision_changers"])
    d.metric("12-month alias units",f'{summary["units_attribution_exposure"]:,}')
    st.caption("Source: customer business identifiers and confirmed purchase orders. Candidate pairs are not automatically merged.")
    a,b=st.columns(2)
    with a: market=st.selectbox("Market",["All"]+list(COUNTRIES),key="exception_market")
    with b: status=st.selectbox("Case status",["All","Unreviewed","In review","Awaiting MDM","Needs revision","Resolved"],key="exception_status")
    shown=cases
    if market!="All":shown=shown[shown.country==market]
    if status!="All":shown=shown[shown.status==status]
    st.dataframe(shown[["alias_id","target_id","country","priority","status","risk_score","alias_12m_units","category_change"]].rename(columns={
        "alias_id":"Candidate alias","target_id":"Potential golden record","country":"Market","priority":"Priority",
        "status":"Status","risk_score":"Review score / 100","alias_12m_units":"Alias units (12m)",
        "category_change":"Decision category affected"
    }),hide_index=True,use_container_width=True)
    if shown.empty:
        st.caption("No cases match the selected filters.")
        return
    view_mode=st.segmented_control("Explore exceptions",["Table","3D identity network"],default="Table",key="exceptions_display")
    if view_mode=="3D identity network":
        st.plotly_chart(build_identity_network(shown,highlighted_alias=st.session_state.get("exception_selected")),use_container_width=True)
        st.caption("Orbit to inspect candidate identities and PO exposure. Orange = proposed, teal = approved, blue = potential golden record. Spatial positions are for exploration only.")
    choices=shown.alias_id.tolist()
    if st.session_state.get("exception_selected") not in choices:
        st.session_state["exception_selected"]=choices[0]
    selected=st.selectbox("Inspect candidate",choices,key="exception_selected")
    case=shown.set_index("alias_id").loc[selected]
    with st.container(border=True):
        st.markdown(f"#### {case.alias_name} · {selected}")
        st.caption(f"Potential retained identity: {case.target_name} ({case.target_id})")
        st.write(f"**Matching business identifier:** {case.registration_number} · **Market:** {case.country}")
        a,b,c=st.columns(3)
        a.metric("Review priority",case.priority)
        b.metric("PO lines attributed to alias (12m)",int(case.exposed_po_lines))
        c.metric("Alias volume (12m)",f"{int(case.alias_12m_units):,} units")
        if bool(case.category_change):
            st.warning(f"Customer growth category may change: {case.current_growth:+.1f}% → {case.potential_growth:+.1f}%. This is an unapproved scenario.")
        else:
            st.caption("No growth-category change detected for the current comparison period.")
        if case.status in ("In review","Awaiting MDM") and pd.notna(case.request_key):
            st.caption(f"Linked approval case: {case.request_key}")
            nav_button("Open governed review →","Master Data","Approval inbox",request=case.request_key,key="case_existing")
        elif case.status=="Resolved":
            st.success("Verified identity link has been completed.")
        else:
            st.button(
                "Prepare customer review",type="primary",key="prepare_case",
                on_click=_prepare_quality_review,args=(selected,case.to_dict()),
            )
        st.caption("Review score is a prioritization heuristic—not a probability or proof of legal identity.")


def master_data():
    portal_header("Master data workspace", "Create, track and approve clean customer and item records.")
    view = st.segmented_control(
        "Work area", WORK_VIEWS, key="workspace_view",
        label_visibility="collapsed", selection_mode="single",
    )
    st.divider()
    if view == "Quality exceptions":
        quality_exceptions()
    elif view == "Create request":
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

    st.markdown("### Decision evidence · Hospital ABC")
    st.caption("Why does the customer look like it is declining? Compare the two source customer IDs before approving an identity link.")
    evidence=identity_case_evidence()
    prior,recent=st.columns(2)
    with prior:
        with st.container(border=True):
            st.markdown("**Current primary record · SG-C001**")
            st.metric("Customer growth",f"{evidence['primary_growth']:+.0f}%")
            st.caption(f"Previous 3 months: {evidence['primary_previous']} units · Latest 3 months: {evidence['primary_latest']} units")
            st.warning("Account could be incorrectly flagged as declining.")
    with recent:
        with st.container(border=True):
            st.markdown("**Combined identities · SG-C001 + SG-A001**")
            st.metric("Growth after verified identity link",f"{evidence['combined_growth']:+.0f}%")
            st.caption(f"Previous 3 months: {evidence['combined_previous']} units · Latest 3 months: {evidence['combined_latest']} units")
            if evidence['approval_applied']:
                st.success("Approved · consolidated growth is live in customer analytics.")
            else:
                st.info("Evidence-only preview · awaiting final MDM approval.")
    chart_data=evidence['monthly'].melt(id_vars="Month",value_vars=["Primary record","Duplicate alias","Combined identity"],var_name="Identity view",value_name="Units")
    chart=px.line(chart_data,x="Month",y="Units",color="Identity view",markers=True,
                  color_discrete_map={"Primary record":"#d18b45","Duplicate alias":"#8699b8","Combined identity":"#128c83"})
    chart.update_layout(height=295,margin=dict(l=4,r=4,t=4,b=4),legend_title_text="",
                        paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(chart,use_container_width=True)
    with st.expander("Trace the underlying purchase orders"):
        st.dataframe(evidence['monthly'],hide_index=True,use_container_width=True)
        st.caption(f"Source evidence: {evidence['po_rows']} purchase-order rows, {evidence['total_po_units']:,} total units across these IDs in the full source history. No original transaction is edited or duplicated.")
    if not evidence['approval_applied']:
        nav_button("View steward approval for this case  →","Master Data","Approval inbox",
                   request="RQ-0001",key="case_evidence_review",primary=True)

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
    df = monthly(country, product, entity)
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
    st.caption("YoY compares Oct 2025–Sep 2026 with Oct 2024–Sep 2025, using 36 months of synthetic history. The chart displays the latest 12 months.")
    with st.expander("Explore customer growth classifications"):
        raw = st.toggle("View raw, unreconciled customer identities")
        d = customer_growth(cleaned=not raw)
        st.dataframe(d.sort_values("latest", ascending=False).head(30), hide_index=True, use_container_width=True)
    with st.expander("Data definitions"):
        st.caption("Only confirmed customer POs are forecast as demand. Enquiries, purchasing requests and internal MDM setup requests are excluded. Identity mapping changes account attribution but never duplicates transaction rows.")
    nav_button("See forecasts and recommended actions  →", "Insights & Forecasts",
               key="regional_next", primary=True)


@st.cache_data(ttl=3600, max_entries=1, show_spinner="Evaluating models using confirmed purchase orders…")
def forecast_results():
    """The 36-month synthetic PO history is unchanged by identity approvals.

    Cache shared validation results: 45 Holt-Winters fits and six pooled ML
    fits should never repeat on every user click or browser session.
    """
    from forecast import backtest
    return backtest()


@st.cache_data(ttl=3600, max_entries=24, show_spinner=False)
def purchasing_plan(country, product, horizon, method):
    """Reuse identical synthetic forecast plans across sessions/reruns."""
    from forecast import forward_plan
    return forward_plan(country, product, horizon, method)


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
    model_columns=st.columns(3)
    for col,name in zip(model_columns,["6-month moving average","Holt-Winters","Pooled gradient boosting"]):
        value=float(summary.loc[summary.model==name,"WAPE %"].iloc[0])
        col.metric(name,f"{value:.2f}% WAPE")
    st.caption("Reference evaluation: 15 market/product series × 3 rolling holdouts = 45 observations; synthetic PO data through September 2026.")
    st.plotly_chart(px.bar(summary, x="model", y="WAPE %", text="WAPE %",
                           labels={"model": "Model"}, color="model")
                    .update_layout(showlegend=False, height=270,
                                   margin=dict(l=5, r=5, t=5, b=5)),
                    use_container_width=True)
    baseline = float(summary.loc[summary.model == "6-month moving average", "WAPE %"].iloc[0])
    holt = float(summary.loc[summary.model == "Holt-Winters", "WAPE %"].iloc[0])
    ranked=summary[summary.model!="Unfiltered training (ablation)"].sort_values("WAPE %")
    winner=ranked.iloc[0]["model"]
    st.caption(f"Lowest measured PO-only WAPE: {winner}. The unfiltered series is a diagnostic ablation, not a valid ordering forecast.")
    ablation=summary[summary.model=="Unfiltered training (ablation)"]
    if not ablation.empty:
        st.metric("Unfiltered-input WAPE (contamination test)",f"{float(ablation.iloc[0]['WAPE %']):.2f}%")
        st.caption("This test deliberately trains on PO + enquiry + customer purchasing-request quantities; its holdout is genuine PO demand. MDM setups contain no order quantity and are not invented as transactions.")
    st.markdown("### Demand visibility · pending master-data setup")
    st.caption("Scenario estimate of purchasing activity potentially delayed by pending setups—not observed lost revenue or actual blocked orders.")
    h1,h2,h3=st.columns(3)
    with h1: days=st.number_input("Assumed waiting days",min_value=0,max_value=60,value=18,key="hidden_days")
    with h2: fraction=st.slider("Share needing an order",0,100,35,5,key="hidden_fraction")
    with h3: avg_order=st.number_input("Typical PO value (SGD, assumed)",min_value=0,max_value=1000000,value=1800,step=100,key="hidden_order_value")
    pending_estimate=hidden_demand_model(days,avg_order,fraction/100)
    hm1,hm2,hm3=st.columns(3)
    hm1.metric("Pending MDM setups",pending_estimate["pending_setups"])
    hm2.metric("Illustrative delayed PO equivalents",f'{pending_estimate["estimated_blocked_order_equivalents"]:.2f}')
    hm3.metric("Indicative delayed-order value",f'SGD {pending_estimate["illustrative_delayed_value_sgd"]:,.0f}')
    st.caption("No setup-to-PO linkage exists in the sample data. This sensitivity model estimates potential visibility, not confirmed demand, sales loss or sales gained.")

    st.markdown("### Forward purchasing plan · 6–12 months")
    st.caption("Choose a market, product, forecast model and time horizon. Estimates use only genuine synthetic POs; planning scenarios are sensitivities, not statistical confidence intervals.")
    p1,p2,p3,p4=st.columns(4)
    with p1: f_country=st.selectbox("Market",list(COUNTRIES),format_func=lambda x:COUNTRIES[x],key="plan_market")
    with p2: f_product=st.selectbox("Product",["A","B","C"],key="plan_product")
    with p3: f_horizon=st.selectbox("Horizon",[6,12],format_func=lambda x:f"{x} months",key="plan_horizon")
    with p4: f_model=st.selectbox("Model",ranked.model.tolist(),key="plan_model")
    plan=purchasing_plan(f_country,f_product,f_horizon,f_model)
    n1,n2=st.columns([1,2])
    with n1:
        st.metric("Planned units",f"{int(plan['Forecast units'].sum()):,}")
        st.caption("No purchase orders are automatically placed.")
        st.download_button("Export purchasing plan (CSV)",plan.to_csv(index=False),
                           file_name=f"purchasing_plan_{f_country}_{f_product}_{f_horizon}m.csv",
                           mime="text/csv",use_container_width=True)
    with n2:
        st.line_chart(plan.set_index("Month")[["Forecast units","Low planning scenario","High planning scenario"]])
    with st.expander("View monthly planning quantities"):
        st.dataframe(plan,hide_index=True,use_container_width=True)

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
    with st.expander("Record classification quality · labelled synthetic examples"):
        accuracy=classifier_benchmark()
        a,b=st.columns(2)
        a.metric("Rules-based accuracy",f'{accuracy["accuracy"]:.1f}%')
        b.metric("Synthetic labelled cases",accuracy["count"])
        st.caption("Curated synthetic message examples only. This is NOT a production email benchmark or independently measured AI accuracy.")
        st.dataframe(accuracy["details"][["Expected category","Predicted category","Correct"]],hide_index=True,use_container_width=True)
    with st.expander("Methodology"):
        st.caption("36 months of synthetic data, 15 country–product series, three matched monthly forecasting origins. Six-month moving average, Holt–Winters and pooled gradient boosting are evaluated on the same PO holdout; a fourth run uses contaminated input as an ablation. Recommendations are rule-based and must be checked by sales teams.")
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
    st.caption("Integration status reflects the configured environment.")

    st.markdown("### Illustrative operational savings calculator")
    st.caption("Change the assumptions to estimate capacity released from faster, cleaner requests. This is not a measured production saving.")
    a,b,c,d=st.columns(4)
    with a: monthly_requests=st.number_input("Requests / month",min_value=0,max_value=10000,value=50,step=10)
    with b: before_minutes=st.number_input("Minutes / request, before",min_value=1,max_value=1000,value=65)
    with c: after_minutes=st.number_input("Minutes / request, after",min_value=1,max_value=1000,value=26)
    with d: hourly_cost=st.number_input("Loaded labour cost (SGD / hour)",min_value=0,max_value=1000,value=40)
    saved_minutes=max(0,before_minutes-after_minutes)*monthly_requests
    hours=saved_minutes/60
    x,y,z=st.columns(3)
    x.metric("Monthly hours released",f"{hours:,.1f}")
    y.metric("Illustrative monthly capacity",f"SGD {hours*hourly_cost:,.0f}")
    z.metric("Illustrative annual capacity",f"SGD {hours*hourly_cost*12:,.0f}")
    st.caption("This estimates staff time capacity only, not realized cost savings, ROI or an independently measured baseline.")
    st.divider()

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
        st.caption("Routing rule maintenance is restricted to administrators.")
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
