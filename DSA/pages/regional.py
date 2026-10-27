import streamlit as st
import pandas as pd
import plotly.express as px
from config import COUNTRIES,ENTITIES
from insights import (decision_impact,regional_summary,monthly,hero_customer,record_type_counts,transactions,
                      LATEST,DISPLAY_START)

def render(role):
    st.title('Regional Purchasing & Data Quality Impact')
    st.caption(f'Synthetic purchase orders · Display: {DISPLAY_START} to {LATEST} · YoY comparison against the preceding 12 months')
    impact=decision_impact(); hero=hero_customer(); counts=record_type_counts()
    k1,k2,k3,k4=st.columns(4)
    k1.metric('Growth classifications corrected',f"{impact['percent']:.1f}%",help=f"{impact['changed']}/{impact['eligible']} eligible canonical customers")
    k2.metric('Customers reclassified',f"{impact['changed']} / {impact['eligible']}")
    k3.metric('Approved aliases',int(len(__import__('database').load_df('SELECT alias_id FROM identity_map'))))
    k4.metric('Genuine PO lines',f"{counts.get('PO',0):,}")
    st.info('Important: customer identity cleaning can change customer-level trends and decisions, but cannot increase total regional order volume merely by merging aliases.')
    st.subheader('Featured customer: sales interpretation before vs after')
    x,y=st.columns(2)
    for col,label,p in [(x,'Raw customer identity',hero['raw']),(y,'Confirmed canonical identity',hero['cleaned'])]:
        with col:
            st.markdown('**'+label+'**')
            st.metric('Latest 3-month growth',f"{p['growth']:+.1f}%")
            st.write(f"**{p['category']}** · Previous 3 months: {p['previous']} units · Latest: {p['latest']} units")
    st.caption('The cleaned result changes only after approved mapping on Page 2. Example: −40% becomes +20%, and a false drop-off alert is removed.')
    st.divider()
    c1,c2,c3=st.columns(3)
    with c1: country=st.selectbox('Country',['All']+list(COUNTRIES),format_func=lambda x: COUNTRIES.get(x,x))
    with c2: product=st.selectbox('Product',['All','A','B','C'])
    with c3: entity=st.selectbox('Business entity',['All']+ENTITIES)
    country=None if country=='All' else country
    product=None if product=='All' else product
    entity=None if entity=='All' else entity
    summary=regional_summary(country,product,entity)
    st.subheader('Country × product purchasing performance')
    st.dataframe(summary.style.format({'YoY growth %':'{:+.1f}%'},na_rep='—'),use_container_width=True,hide_index=True)
    df=monthly(country,product)
    fig=px.line(df,x='period',y='qty',color='product',markers=True,title='Genuine purchase-order quantity by month',labels={'qty':'Units','period':'Order month','product':'Product'})
    fig.update_layout(margin=dict(l=10,r=10,t=45,b=10))
    st.plotly_chart(fig,use_container_width=True)
    raw_mode=st.toggle('Show customer-level records before approved golden-record consolidation',value=False)
    from insights import customer_growth
    customers=customer_growth(cleaned=not raw_mode)
    st.subheader('Customer-level growth classifications')
    st.dataframe(customers.sort_values('latest',ascending=False).head(30),hide_index=True,use_container_width=True)
    with st.expander('Data lineage and scope'):
        st.write(f"Orders are filtered to record_type='PO'. Excluded from demand analysis: {counts.get('Enquiry',0)} enquiries and {counts.get('Customer Request',0)} customer purchasing requests. Internal MDM requests are held in a separate table and never counted as orders.")
        st.write('Five locations (SG, MY, ID, TH, VN) and three business entities are illustrative assumptions. Raw transactions are preserved; approved customer mappings change attribution only.')
