import streamlit as st
import pandas as pd
import json
from config import ROLE_ACTOR, COUNTRIES, ENTITIES, settings
from database import load_df
from workflow import decide,finalize,add_approval_rule,WorkflowError

def render(role):
    st.title('Tracker, Steward Approvals & Administration')
    st.caption('State machine: Draft → Submitted → In Approval → Approved → Created; rejection is an alternate terminal state. All recorded decisions are timestamped.')
    req=load_df('''SELECT request_key AS request_id,domain,record_name,country,entity,requested_by,status,
                match_source_id,match_target_id FROM mdm_requests ORDER BY id DESC''')
    st.dataframe(req,use_container_width=True,hide_index=True)
    if req.empty:return
    key=st.selectbox('Inspect request',req.request_id.tolist(),index=req.request_id.tolist().index('RQ-0001') if 'RQ-0001' in req.request_id.tolist() else 0)
    item=req.set_index('request_id').loc[key]
    if item.match_source_id and item.match_target_id:
        st.info(f'Golden-record review: {item.match_source_id} → {item.match_target_id}. Requires matching verified identifiers and final MDM approval. Historical transactions will remain unchanged.')
    tasks=load_df('SELECT steward,state,decision_by,decision_at FROM approval_tasks WHERE request_key=?',(key,))
    st.subheader('Parallel data-steward decisions')
    st.dataframe(tasks,use_container_width=True,hide_index=True)
    st.caption('Maker–checker rule: the requestor cannot approve their own request. Each steward sees only their assigned task.')
    if role in ['Finance Steward','Quality Steward','BU Steward']:
        pending=tasks[(tasks.steward==role)&(tasks.state=='Pending')]
        if item.status=='In Approval' and len(pending):
            c1,c2=st.columns(2)
            with c1:
                if st.button('Approve as '+role,type='primary'):
                    try:decide(key,role,ROLE_ACTOR[role],'Approved');st.rerun()
                    except WorkflowError as e:st.error(str(e))
            with c2:
                if st.button('Reject as '+role):
                    try:decide(key,role,ROLE_ACTOR[role],'Rejected');st.rerun()
                    except WorkflowError as e:st.error(str(e))
    if role=='MDM Steward' and item.status in ('Approved','Created'):
        if st.button('Finalize, map golden record & create SAP-ready payload',type='primary'):
            try:
                outcome=finalize(key,ROLE_ACTOR[role]);st.success('Request already created (safe retry)' if outcome['already_created'] else 'Golden-record mapping confirmed and mock SAP payload created.')
                st.rerun()
            except WorkflowError as e:st.error(str(e))
    sap=load_df('SELECT payload_json FROM sap_records WHERE request_key=?',(key,))
    if len(sap):
        data=json.loads(sap.iloc[0]['payload_json'])
        with st.expander('SAP Business One handoff · simulated, idempotent',expanded=True):
            st.json(data)
            st.download_button('Download SAP-ready JSON',json.dumps(data,indent=2),'sap_payload_'+key+'.json','application/json')
            st.caption('Unique request ID prevents duplicate mock records on retry. A real SAP Service Layer integration would additionally require server-side idempotency/reconciliation.')
    with st.expander('Append-only audit trail',expanded=True):
        st.dataframe(load_df('SELECT happened_at,actor,event,details FROM audit_log WHERE request_key=? ORDER BY id',(key,)),hide_index=True,use_container_width=True)
    st.divider()
    if role=='Admin':
        st.subheader('Approval matrix · no-code administration')
        matrix=load_df('SELECT entity,domain,country,steward,delegate,sla_days FROM approval_matrix ORDER BY entity,domain,country,steward')
        with st.expander('Current routing matrix'):
            st.dataframe(matrix,use_container_width=True,hide_index=True)
        with st.form('add_rule'):
            a,b,c,d=st.columns(4)
            with a: entity=st.text_input('Entity / new business unit',value='SPD',help='Enter a new code to demonstrate no-code business-unit onboarding')
            with b: domain=st.selectbox('Domain',list(settings()['domains']))
            with c: country=st.selectbox('Country',list(COUNTRIES))
            with d: steward=st.selectbox('Steward',['Finance Steward','Quality Steward','BU Steward','MDM Steward'])
            sla=st.number_input('SLA (working days)',1,30,2)
            submitted=st.form_submit_button('Add routing rule without code change')
        if submitted:
            try:add_approval_rule(entity,domain,country,steward,sla_days=sla);st.success('Configuration saved. Subsequent requests for this combination use the updated rule.')
            except WorkflowError as e:st.warning(str(e))
    else:st.caption('Switch demo role to Admin to demonstrate approval-matrix configuration without code changes.')
