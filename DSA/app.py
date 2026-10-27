"""Unified, role-aware company operations portal for a synthetic competition case."""
import streamlit as st
from generate_data import seed
from sla import process_sla
from ui import style
from portal import SECTIONS, render
from assistant_guide import render_assistant

st.set_page_config(page_title="Operations | Master Data & Regional Insights",
                   page_icon="◈",layout="wide",initial_sidebar_state="expanded")
# Register a single hidden page to disable Streamlit's automatic pages/ menu.
# All employee workspaces are displayed by the portal's own sidebar.
st.navigation([st.Page(lambda: None, title="Operations portal", default=True)], position="hidden").run()
seed()
try:
    process_sla(notify=False)
except Exception:
    pass
style()

if "portal_section" not in st.session_state:
    st.session_state["portal_section"]="Overview"
if "portal_role" not in st.session_state:
    st.session_state["portal_role"]="Requestor"
if "workspace_view" not in st.session_state:
    st.session_state["workspace_view"]="Request tracker"
if "request_method" not in st.session_state:
    st.session_state["request_method"]="Quick form"

def reset_demo():
    seed(reset=True)
    for key in list(st.session_state):
        if key.startswith(("req_", "sap_confirm_")) or key in (
            "portal_last_request","chosen_request","parsed_email","portal_email",
            "req_link_existing","req_ack","request_method"):
            st.session_state.pop(key,None)
    st.session_state["portal_section"]="Overview"
    st.session_state["portal_role"]="Requestor"
    st.session_state["workspace_view"]="Request tracker"
    st.session_state["request_method"]="Quick form"

with st.sidebar:
    st.markdown("""<div class="portal-brand"><div class="portal-logo">L</div>
      <div><div class="portal-brand-name">LIVES GROUP</div>
      <div class="portal-brand-sub">Operations workspace</div></div></div>""",
      unsafe_allow_html=True)
    st.markdown('<div class="portal-side-rule"></div>',unsafe_allow_html=True)
    st.divider()
    section=st.radio("WORKSPACES",SECTIONS,key="portal_section")
    st.markdown('<div class="portal-side-rule"></div>',unsafe_allow_html=True)
    role=st.selectbox("Viewing as (demo role)",[
        "Requestor","Finance Steward","Quality Steward","BU Steward","MDM Steward","Admin"],
        key="portal_role")
    if st.session_state.get("portal_last_request"):
        st.caption("Recent request")
        st.markdown("**"+st.session_state["portal_last_request"]+"**")
    with st.popover("Reset demonstration",use_container_width=True):
        st.warning("This resets the shared demo database for every current visitor, including their request and approval progress.")
        confirmed=st.checkbox("I understand this will affect other viewers",key="confirm_shared_reset")
        st.button("Reset all sample data",on_click=reset_demo,
                  disabled=not confirmed,use_container_width=True,type="primary")
    st.markdown('<div class="portal-side-rule"></div>',unsafe_allow_html=True)
    st.caption("DEMO ENVIRONMENT")
    st.caption("Synthetic data · Simulated access · No production ERP records")

render()
render_assistant()
