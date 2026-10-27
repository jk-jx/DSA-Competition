"""Unified, role-aware company operations portal for a synthetic competition case."""
import streamlit as st
from generate_data import seed
from sla import process_sla
from ui import style
from portal import SECTIONS, render

st.set_page_config(page_title="Operations | Master Data & Regional Insights",
                   page_icon="◈",layout="wide",initial_sidebar_state="expanded")
seed()
try:
    process_sla(notify=False)
except Exception:
    pass
style()
st.markdown("""<style>
.portal-eyebrow{letter-spacing:.13em;font-size:.7rem;font-weight:800;color:#557697;margin-bottom:5px}
.portal-status{font-size:.72rem;font-weight:800;color:#2a6c62;text-align:right;
  border-radius:99px;background:#e4f5ee;padding:11px 10px}
.status-dot{display:inline-block;width:8px;height:8px;background:#0e9e72;border-radius:50%;margin-right:4px}
[data-testid="stSidebar"] .stRadio label{margin-bottom:3px}
</style>""",unsafe_allow_html=True)

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
    st.markdown("**LIVES GROUP**")
    st.markdown("### Operations portal")
    st.caption("Master data · Procurement intelligence")
    st.divider()
    section=st.radio("WORKSPACES",SECTIONS,key="portal_section")
    st.divider()
    role=st.selectbox("Viewing as (demo role)",[
        "Requestor","Finance Steward","Quality Steward","BU Steward","MDM Steward","Admin"],
        key="portal_role")
    if st.session_state.get("portal_last_request"):
        st.caption("Recent request")
        st.markdown("**"+st.session_state["portal_last_request"]+"**")
    st.button("Reset demonstration",on_click=reset_demo,use_container_width=True)
    st.divider()
    st.caption("Synthetic case data · Role switching simulates access. No production ERP connection is needed.")

render()
