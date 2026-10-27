"""Student demonstration: four connected pages, no production access or authentication."""
import streamlit as st
from config import ROLE_ACTOR
from generate_data import seed

st.set_page_config(page_title='Master Data & Regional Intelligence',page_icon='📊',layout='wide')
seed()
st.markdown('''<style>
[data-testid="stAppViewContainer"] {background: #ffffff;}
h1 {font-weight: 760; letter-spacing: -0.03em;}
.small-label {color:#49616b; font-size:0.84rem}
</style>''',unsafe_allow_html=True)
with st.sidebar:
    st.caption('LIVES GROUP · STUDENT CONCEPT DEMO')
    st.title('Master Data & Regional Intelligence')
    page=st.radio('Navigate',[
        '01 · Smart Intake & Quality',
        '02 · Tracker, Approvals & Admin',
        '03 · Regional View',
        '04 · Forecasts, Insights & Actions'])
    st.divider()
    role=st.selectbox('Demo role',list(ROLE_ACTOR),index=0)
    st.caption('Role switching simulates identity. Not secure authentication.')
    if st.button('Reset demonstration data',help='Restores original synthetic dataset and pending hero request'):
        seed(reset=True)
        st.rerun()
    st.divider()
    st.caption('Synthetic data only • No SAP integration • 36-month source history • 12-month dashboard')

if page.startswith('01'):
    from pages.intake import render
elif page.startswith('02'):
    from pages.approvals import render
elif page.startswith('03'):
    from pages.regional import render
else:
    from pages.actions import render
render(role)
