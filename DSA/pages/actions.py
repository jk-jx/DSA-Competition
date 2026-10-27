import streamlit as st
import pandas as pd
import plotly.express as px
from forecast import backtest
from insights import (decision_impact,hero_customer,cross_sell,dropoff,record_type_counts)

@st.cache_data(show_spinner='Running 3 rolling forecast origins over 15 country-product series…')
def forecast_results():
    return backtest()

def render(role):
    st.title('Forecasting, Insights & Recommended Actions')
    st.caption('Quantify analytic quality and show how a verified identity resolution changes decisions. All findings use synthetic data.')
    impact=decision_impact(); hero=hero_customer(); counts=record_type_counts()
    a,b,c=st.columns(3)
    a.metric('Data Quality Decision Impact',f"{impact['percent']:.1f}%",help=f"{impact['changed']}/{impact['eligible']} eligible customers")
    b.metric('PO lines used',f"{counts.get('PO',0):,}")
    c.metric('Enquiries excluded',f"{counts.get('Enquiry',0):,}")
    st.subheader('Recommendations change after correcting an identity')
    left,right=st.columns(2)
    with left:
        st.markdown('**Before: raw customer identity**')
        st.metric('Hospital ABC growth',f"{hero['raw']['growth']:+.1f}%")
        st.warning('Investigate possible customer drop-off.' if hero['raw']['category']=='Declining' else 'No decline warning for the primary record.')
    with right:
        st.markdown('**After: approved customer consolidation**')
        st.metric('Hospital ABC growth',f"{hero['cleaned']['growth']:+.1f}%")
        if hero['resolved']:
            st.success('Customer is growing. Review Product B/C cross-selling suitability, existing demand and account strategy.')
        else:
            st.info('Awaiting steward-approved identity mapping. Complete Page 2 to change the recommendation.')
    st.divider()
    st.subheader('Forecast accuracy: same genuine PO holdout')
    summary,history=forecast_results()
    k1,k2=st.columns(2)
    for col, row in zip((k1,k2),summary.itertuples(index=False)):
        with col:
            st.metric(row.model, f"{summary.loc[summary.model==row.model,'WAPE %'].iloc[0]:.1f}% WAPE")
    st.dataframe(summary,hide_index=True,use_container_width=True)
    fig=px.bar(summary,x='model',y='WAPE %',text='WAPE %',title='Lower WAPE = better backtested forecast accuracy')
    st.plotly_chart(fig,use_container_width=True)
    st.caption('6-month historical average vs Holt–Winters; 3 rolling one-month-ahead test periods × 15 country-product series. Evaluated on the same genuine purchase-order actuals. WAPE is not claimed to improve due to alias consolidation at regional level.')
    st.subheader('Actionable regional sales opportunities')
    c1,c2=st.columns(2)
    with c1:
        st.markdown('**Possible customer drop-off**')
        d=dropoff()
        if d.empty:st.info('No customers meet current drop-off threshold.')
        else:st.dataframe(d[['resolved_id','previous','latest','growth_pct']],hide_index=True,use_container_width=True)
    with c2:
        st.markdown('**Potential cross-selling**')
        cs=cross_sell()
        if cs.empty:st.info('No cross-sell candidates meet current rules.')
        else:st.dataframe(cs[['resolved_id','A','B','C','action']],hide_index=True,use_container_width=True)
    with st.expander('Method and interpretation'):
        st.write('Customer-level decline: latest 3 months vs prior 3 months, decline below −5%, with nonzero previous period. Cross-sell: customers buying A and B but not C in the last 12 months; recommendations require sales verification and regulatory/product suitability checks.')
        st.write('Headline percentage is the number of eligible canonical customers whose growth category differs from their raw primary record, divided by eligible canonical customers. Results are simulation-only. Total regional product quantities do not change from identity matching.')
