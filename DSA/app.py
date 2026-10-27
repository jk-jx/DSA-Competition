"""Four connected workflow screens for a synthetic competition demonstration."""
import streamlit as st
from generate_data import seed
from sla import process_sla
from ui import STEPS, style, workflow_progress

st.set_page_config(page_title="Master Data & Regional Insights", page_icon="📊", layout="wide")
seed()

# In an enterprise installation, a scheduled worker would process this queue.
# Running this here makes reminders demonstrable without an external worker.
try:
    process_sla(notify=False)
except Exception:
    pass

style()

def reset_demo():
    seed(reset=True)
    for key in list(st.session_state.keys()):
        if (key.startswith(("Customer_", "Item_", "Vendor_", "Cost Center_", "sap_confirm_"))
                or key in ("last_request", "email_parsed", "pasted_email",
                           "intake_domain", "resolve_identity", "selected_request",
                           "approval_role", "intake_method", "intake_ack")):
            st.session_state.pop(key, None)
    st.session_state["nav_step"] = STEPS[0]

with st.sidebar:
    st.markdown("**LIVES GROUP / OPERATIONS**")
    st.markdown("### Master Data & Regional Insights")
    st.caption("Clean records. Faster decisions.")
    st.divider()
    page = st.radio("Your workflow", STEPS, key="nav_step")
    st.divider()
    if st.session_state.get("last_request"):
        st.success(f"Last request: {st.session_state['last_request']}")
    st.button("↺ Reset demo", on_click=reset_demo, use_container_width=True,
              help="Restores synthetic records and the original pending example; clears the form.")
    with st.expander("About this demonstration"):
        st.caption("Synthetic data. Roles are simulated, not secure sign-in. No production SAP records are created. Enterprise connectors require a separate authorized setup.")

workflow_progress(STEPS.index(page))
if page == STEPS[0]:
    from pages.intake import render
elif page == STEPS[1]:
    from pages.approvals import render
elif page == STEPS[2]:
    from pages.regional import render
else:
    from pages.actions import render
render("Requestor")
