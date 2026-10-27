import streamlit as st
import pandas as pd
import json
from config import ROLE_ACTOR, COUNTRIES, ENTITIES, settings
from database import load_df
from workflow import decide,finalize,add_approval_rule,WorkflowError
from sla import sla_snapshot, process_sla
from sap_integration import configured as sap_configured, send_live, SAPIntegrationError

def render(role):
    st.title('Tracker, Steward Approvals & Administration')
    st.caption('State machine: Draft → Submitted → In Approval → Approved → Created; rejection is an alternate terminal state. All recorded decisions are timestamped.')
    req=load_df('''SELECT request_key AS request_id,domain,record_name,country,entity,requested_by,status,
                match_source_id,match_target_id FROM mdm_requests ORDER BY id DESC''')
    st.dataframe(req,use_container_width=True,hide_index=True)
    if req.empty:return
    key=st.selectbox('Inspect request',req.request_id.tolist(),index=req.request_id.tolist().index(st.session_state.get('last_request')) if st.session_state.get('last_request') in req.request_id.tolist() else 0)
    item=req.set_index('request_id').loc[key]
    if item.match_source_id and item.match_target_id:
        st.info(f'Golden-record review: {item.match_source_id} → {item.match_target_id}. Requires matching verified identifiers and final MDM approval. Historical transactions will remain unchanged.')
    tasks=load_df('SELECT steward,state,decision_by,decision_at FROM approval_tasks WHERE request_key=?',(key,))
    st.subheader('Parallel data-steward decisions')
    st.dataframe(tasks,use_container_width=True,hide_index=True)
    st.caption('Maker–checker rule: the requestor cannot approve their own request. Each steward sees only their assigned task.')
    st.subheader('Live SLA queue · working days and delegates')
    snapshot=sla_snapshot()
    scoped=[entry for entry in snapshot if entry['request_key']==key]
    if scoped:
        st.dataframe(pd.DataFrame(scoped),hide_index=True,use_container_width=True)
        if st.button('Process due reminders and escalation',help='Records exactly-once reminder/escalation events; sends non-sensitive text to Teams only if a webhook is configured.'):
            try:
                events=process_sla(notify=True)
                st.success(f"{len(events)} new reminder/escalation event(s) processed. Existing events are not repeated.")
                if events: st.dataframe(pd.DataFrame(events),hide_index=True)
            except Exception as exc:
                st.error(f"SLA processing failed: {type(exc).__name__}: {exc}")
    else:
        st.caption('No pending SLA tasks for this request.')
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
            st.caption('Unique request ID prevents duplicate mock records on retry. Live SAP writes require a test tenant and explicit confirmation, with manual reconciliation after ambiguous network failures.')
            if role=='MDM Steward':
                if sap_configured():
                    confirm=st.checkbox('I am authorized to dispatch to the configured SAP B1 tenant; I verified the mapping.',key='sap_confirm_'+key)
                    if st.button('Dispatch to SAP B1 Service Layer',disabled=not confirm):
                        try:
                            result=send_live(key,confirm=True)
                            st.success('SAP returned: '+str(result))
                        except SAPIntegrationError as exc:
                            st.error(str(exc))
                else:
                    st.info('Live SAP B1 adapter installed; configure SAP_B1_SERVICE_LAYER_URL, SAP_B1_COMPANY_DB, SAP_B1_USERNAME and SAP_B1_PASSWORD in deployment secrets to enable dispatch.')
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
