"""Context-aware, persistent operations assistant for the competition portal.

The assistant is a guided in-app helper, not a generative chatbot.
Suggestions reflect the current request state and actual approval tasks.
"""
from dataclasses import dataclass

import streamlit as st

from database import load_df


@dataclass(frozen=True)
class GuideState:
    message: str
    action: str
    section: str
    workspace: str | None = None
    role: str | None = None
    request: str | None = None
    footnote: str = ""


WORKSPACE_EXPLANATIONS = {
    "Overview": "Your overview brings together the request queue, data-quality checks and regional purchasing results.",
    "Master Data": "Master Data is where requests are submitted, reviewed by independent stewards and finalized by MDM.",
    "Regional Performance": "This view compares real purchase orders by country and product. Customer identity links reattribute orders without creating new transactions.",
    "Insights & Forecasts": "This workspace compares forecast accuracy and recommends actions based on cleaned, confirmed purchase orders.",
    "Administration": "The approval matrix routes work by business unit, country and domain. An MDM administrator can update rules without changing code.",
}


def _request():
    preferred = (
        st.session_state.get("chosen_request")
        or st.session_state.get("portal_last_request")
        or "RQ-0001"
    )
    rows = load_df(
        """SELECT request_key, record_name, status, match_source_id, match_target_id
           FROM mdm_requests WHERE request_key=?""",
        (preferred,),
    )
    if rows.empty:
        rows = load_df(
            """SELECT request_key, record_name, status, match_source_id, match_target_id
               FROM mdm_requests ORDER BY id DESC LIMIT 1"""
        )
    if rows.empty:
        return None, []
    row = rows.iloc[0].to_dict()
    tasks = load_df(
        """SELECT steward,state FROM approval_tasks
           WHERE request_key=? ORDER BY id""",
        (row["request_key"],),
    )
    pending = tasks.loc[tasks["state"] == "Pending", "steward"].tolist()
    return row, pending


def suggestion(section, workspace, role, request, pending, resolved):
    """Pure decision rules that can be tested without rendering Streamlit."""
    key = request["request_key"] if request else None
    name = request["record_name"] if request else "a customer"

    if section == "Overview":
        if request and request["status"] == "In Approval":
            next_reviewer = pending[0] if pending else "Finance Steward"
            return GuideState(
                f"{name} has an identity review waiting. Let's complete the stewardship checks before looking at the corrected growth result.",
                "Open the pending review",
                "Master Data", "Approval inbox", next_reviewer, key,
                "No identities are merged until the final MDM check.",
            )
        if request and request["status"] == "Approved":
            return GuideState(
                f"{name} has passed its assigned reviewers. The final MDM check is the next step.",
                "Complete final MDM check", "Master Data", "Approval inbox", "MDM Steward", key,
            )
        if request and request["status"] == "Created":
            return GuideState(
                "The customer identity review is complete. See how the verified link changes a sales decision.",
                "See the business impact", "Regional Performance",
            )
        return GuideState(
            "Welcome back. You can create a request, review the queue or explore purchasing performance.",
            "Create a new request", "Master Data", "Create request",
        )

    if section == "Master Data":
        if workspace == "Create request":
            return GuideState(
                "Enter a customer or item request, or use the sample case. I'll help you move it into steward review.",
                "Open the approval inbox", "Master Data", "Approval inbox", None, key,
                "The duplicate check suggests matches; only authorized stewards confirm identities.",
            )
        if workspace == "Request tracker":
            if request and request["status"] in ("In Approval", "Approved"):
                return GuideState(
                    f"Request {key} is {request['status'].lower()}. Follow its reviews to see who needs to act next.",
                    "Review this request", "Master Data", "Approval inbox", None, key,
                )
            return GuideState(
                "The tracker shows who requested each record, its current status and the next handoff.",
                "Create a request", "Master Data", "Create request",
            )
        if request:
            if request["status"] == "In Approval" and pending:
                if role in pending:
                    return GuideState(
                        f"{key} is waiting for your {role} decision. Review the matched record and select Approve or Reject.",
                        "Stay on this review", "Master Data", "Approval inbox", role, key,
                        "Independent stewards can approve in any order; final MDM checking follows both.",
                    )
                return GuideState(
                    f"{key} is waiting for {pending[0]}. Switch to that steward's demo role to review it.",
                    f"View as {pending[0]}", "Master Data", "Approval inbox", pending[0], key,
                    "This role selector demonstrates the workflow; it is not production authentication.",
                )
            if request["status"] == "Approved":
                return GuideState(
                    f"{key} has all its steward approvals. The MDM steward can now confirm the golden-record mapping.",
                    "Continue as MDM Steward", "Master Data", "Approval inbox", "MDM Steward", key,
                )
            if request["status"] == "Created":
                return GuideState(
                    f"{key} is complete. The customer record is now linked in the analytics view.",
                    "See corrected customer growth", "Regional Performance",
                )
            if request["status"] == "Rejected":
                return GuideState(
                    f"{key} was rejected, so no record was created. You can correct the details and submit a new request.",
                    "Create another request", "Master Data", "Create request",
                )
        return GuideState(
            "This is the approval inbox. Choose a request to see each reviewer's decision.",
            "Open the request tracker", "Master Data", "Request tracker",
        )

    if section == "Regional Performance":
        if not resolved:
            return GuideState(
                "Hospital ABC currently appears to be declining because its orders are split across two customer identities.",
                "Resolve the identity review", "Master Data", "Approval inbox", "Finance Steward", key,
                "Cleaning customer identities does not increase regional purchase-order totals.",
            )
        return GuideState(
            "The approved identity link changes Hospital ABC from declining to growing. The next step is to review the recommended sales action.",
            "View recommended action", "Insights & Forecasts",
            footnote="The result comes from the synthetic dataset and an approved reference mapping.",
        )

    if section == "Insights & Forecasts":
        if not resolved:
            return GuideState(
                "Some account-level recommendations are incomplete until the duplicate customer is reviewed.",
                "Finish the review", "Master Data", "Approval inbox", "Finance Steward", key,
            )
        return GuideState(
            "The verified customer is growing. Consider an expansion conversation, and use measured WAPE to choose a forecast baseline.",
            "Explore regional performance", "Regional Performance",
            footnote="Forecast improvements are measured, not assumed. Recommendations require business review.",
        )

    return GuideState(
        "This area controls approval routing and connector configuration. Only an MDM super-user should change business rules.",
        "View the approval queue", "Master Data", "Approval inbox",
        footnote="Role changes in this demo simulate company access and are not security controls.",
    )


def current_suggestion():
    section = st.session_state.get("portal_section", "Overview")
    workspace = st.session_state.get("workspace_view", "Request tracker")
    role = st.session_state.get("portal_role", "Requestor")
    request, pending = _request()
    resolved = not load_df(
        "SELECT alias_id FROM identity_map WHERE alias_id=?",
        ("SG-A001",),
    ).empty
    return suggestion(section, workspace, role, request, pending, resolved)


def _navigate(target):
    # Widget callbacks run before Streamlit reconstructs the portal's sidebar.
    st.session_state["portal_section"] = target.section
    if target.workspace:
        st.session_state["workspace_view"] = target.workspace
    if target.role:
        st.session_state["portal_role"] = target.role
    if target.request:
        st.session_state["chosen_request"] = target.request


def _answer(topic, section):
    if topic == "What should I do next?":
        return current_suggestion().message
    if topic == "Why do duplicate records matter?":
        return (
            "One customer can appear as two separate accounts. After a verified identity link, "
            "customer growth and the recommended sales action may change while regional order totals remain the same."
        )
    if topic == "Who approves a request?":
        return (
            "Customer requests require independent Finance and business-unit stewards. "
            "Item requests use Quality and business-unit stewards. The MDM steward finalizes "
            "only after all assigned approvals, with maker–checker separation."
        )
    if topic == "Which orders are forecast?":
        return (
            "The forecast uses genuine confirmed customer purchase orders only. "
            "Enquiries, customer purchasing requests and internal MDM setup requests are excluded."
        )
    return WORKSPACE_EXPLANATIONS.get(section, WORKSPACE_EXPLANATIONS["Overview"])


def render_assistant():
    """Render once after the active workspace, anchored at the bottom right."""
    section = st.session_state.get("portal_section", "Overview")
    target = current_suggestion()

    st.markdown(
        """<style>
/* Stable class is provided by the key on st.container. */
div.st-key-operations_assistant_dock {
    position:fixed!important;
    right:24px!important;
    bottom:20px!important;
    width:max-content!important;
    max-width:calc(100vw - 24px)!important;
    z-index:100001!important;
    margin:0!important;
}
div.st-key-operations_assistant_dock button {
    background:linear-gradient(120deg,#123b65,#2469a3)!important;
    color:white!important;
    border:1px solid #75b3d9!important;
    border-radius:28px!important;
    padding:12px 18px!important;
    min-height:49px!important;
    font-weight:800!important;
    box-shadow:0 10px 28px rgba(11,41,74,.29)!important;
}
div.st-key-operations_assistant_dock button:hover {
    background:#164d85!important;
}
div.st-key-operations_assistant_dock [data-testid="stPopover"] {width:max-content}
@media(max-width:700px) {
    div.st-key-operations_assistant_dock {right:12px!important;bottom:12px!important}
    div.st-key-operations_assistant_dock button {font-size:.81rem!important;padding:9px 12px!important}
}
</style>""",
        unsafe_allow_html=True,
    )

    with st.container(key="operations_assistant_dock"):
        with st.popover("🧭  Operations Assistant", help="Open your context-aware portal guide"):
            st.markdown("#### 🧭 Operations Assistant")
            st.caption("Your guide to requests, approvals and purchasing intelligence")
            st.info(target.message)
            st.button(
                target.action + "  →",
                key="assistant_primary_action",
                type="primary",
                use_container_width=True,
                on_click=_navigate,
                args=(target,),
            )
            if target.footnote:
                st.caption(target.footnote)
            st.divider()
            st.markdown("**Quick answers**")
            question = st.selectbox(
                "Choose a question",
                [
                    "What should I do next?",
                    "What can I do in this workspace?",
                    "Why do duplicate records matter?",
                    "Who approves a request?",
                    "Which orders are forecast?",
                ],
                key="assistant_topic",
                label_visibility="collapsed",
            )
            st.write(_answer(question, section))
            st.caption("Guidance uses the live synthetic workflow status; it is not an AI chatbot.")
