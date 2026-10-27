import streamlit as st
import pandas as pd
from config import COUNTRIES,ENTITIES,settings,ROLE_ACTOR
from dedup import find_matches
from workflow import submit_request, WorkflowError
from database import load_df
from intake_parser import extract_message
from ui import next_step

def render(role):
    st.title('Submit a master-data request')
    st.caption('Start with an email or enter the details yourself. The app checks for missing fields and duplicates before approval.')
    st.info('Try the example: ABC Hospital · QTS · Singapore · SG-REG-000001. After submission, go to Review & approve.')
    with st.expander('Paste an email · classify and prefill',expanded=True):
        pasted=st.text_area('Paste a synthetic email or request',key='pasted_email',
            placeholder='Please create customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001.')
        use_llm=st.checkbox('Use configured Azure OpenAI extraction (optional)',value=False,
            help='Rules-first works offline; Azure OpenAI requires a configured secret.')
        if st.button('Classify and prefill form',disabled=not pasted.strip()):
            try:
                parsed=extract_message(pasted,use_llm=use_llm)
                st.session_state['email_parsed']=parsed
                for name,value in parsed['fields'].items():
                    chosen=parsed['domain']
                    if name in settings()['domains'].get(chosen,{}).get('fields',{}):
                        st.session_state[f'{chosen}_{name}']=value
                st.session_state['intake_domain']=parsed['domain']
                st.rerun()
            except Exception as exc:
                st.error(f'Extraction failed: {exc}')
        parsed=st.session_state.get('email_parsed')
        if parsed:
            st.success('Request analyzed — relevant fields have been prefilled below. Please review before submitting.')
            result_type, result_domain, result_method = st.columns(3)
            result_type.metric('Request type', parsed['record_type'])
            result_domain.metric('Form', parsed['domain'])
            result_method.metric('Extraction', 'AI-assisted' if parsed['method'] != 'rules' else 'Rules-based')
            if parsed['fields']:
                labels = {
                    'name': 'Name', 'country': 'Country', 'entity': 'Business entity',
                    'registration_number': 'Registration number', 'contact_email': 'Contact email',
                    'item_category': 'Item category', 'regulatory_class': 'Regulatory class',
                }
                field_rows = [{'Field': labels.get(key, key.replace('_', ' ').title()), 'Extracted value': value}
                              for key, value in parsed['fields'].items()]
                st.dataframe(pd.DataFrame(field_rows), hide_index=True, use_container_width=True)
            with st.expander('Technical details (JSON)', expanded=False):
                st.json(parsed)
            if parsed['record_type']!='MDM Setup':
                st.warning('This is not a master-data setup request. A PO, purchasing request or enquiry must not enter the MDM approval queue.')
    cfg=settings()['domains']
    st.subheader('Review your request details')
    domain=st.selectbox('Request domain',list(cfg),index=0,key='intake_domain')
    if cfg[domain].get('prototype_status')=='config_only':
        st.info(f'{domain} is configuration-ready, but its full field validation and SAP payload are outside this competition MVP. Try Customer or Item.')
        st.code(str(cfg[domain]),language='yaml'); return
    a,b=st.columns([2,1])
    with a:
        values={}
        fields=cfg[domain]['fields']
        for key,detail in fields.items():
            label=detail['label']+(' *' if key in cfg[domain]['required'] else '')
            if detail['type']=='country': values[key]=st.selectbox(label,list(COUNTRIES),format_func=lambda x:COUNTRIES[x],key=f'{domain}_{key}')
            elif detail['type']=='entity':
                configured=load_df('SELECT DISTINCT entity FROM approval_matrix')['entity'].tolist()
                values[key]=st.selectbox(label,sorted(set(ENTITIES+configured)),key=f'{domain}_{key}')
            else: values[key]=st.text_input(label,key=f'{domain}_{key}',placeholder='Required' if key in cfg[domain]['required'] else 'Optional')
    matches=[]
    if domain=='Customer' and values.get('name','').strip():
        matches=find_matches(values['name'],domain,values['country'])
    with b:
        st.subheader('Quality gate')
        missing=[i for i in cfg[domain]['required'] if not str(values.get(i,'')).strip()]
        if missing:st.warning('Missing: '+', '.join(missing))
        else:st.success('Required fields complete')
        if matches:
            st.warning(f'{len(matches)} candidate match(es) detected. A steward must confirm legal identity before a merge.')
            st.dataframe(pd.DataFrame(matches)[['existing_name','customer_id','score','tier']],hide_index=True,use_container_width=True)
        elif values.get('name'):st.success('No high-scoring name matches in the selected country')
    source_id=target_id=None
    if domain=='Customer' and values.get('registration_number','').strip():
        verified=load_df('''SELECT customer_id,name,entity,registration_number,canonical_truth_id
                            FROM customers WHERE country=? AND registration_number=? ORDER BY customer_id''',
                         (values['country'],values['registration_number'].strip()))
        if len(verified)>=2:
            st.subheader('Match and merge → golden record')
            st.caption('Two existing source records share a business identifier. Select the alias and retained record for human approval; historical orders are preserved.')
            resolve=st.checkbox('Link these verified duplicate records instead of creating a new customer',value=True,key='resolve_identity')
            if resolve:
                rows=verified.set_index('customer_id').to_dict('index')
                def display(cid): return f"{cid} · {rows[cid]['name']} ({rows[cid]['entity']})"
                ids=list(rows)
                aliases=[x for x in ids if x!=rows[x]['canonical_truth_id']]
                source_id=st.selectbox('Existing alias / duplicate ID',ids,index=ids.index(aliases[0]) if aliases else 0,format_func=display)
                targets=[x for x in ids if x!=source_id]
                canonical=[x for x in targets if x==rows[x]['canonical_truth_id']]
                target_id=st.selectbox('Golden record to retain',targets,index=targets.index(canonical[0]) if canonical else 0,format_func=display)
                st.info('Matching legal identifier is evidence for review, not automatic authority to merge.')
    acknowledgement=True
    if matches and max(m['score'] for m in matches)>=settings()['matching']['review']:
        acknowledgement=st.checkbox('I reviewed the candidates and will send this for steward approval before any new SAP record is created.')
    if st.button('Submit for approval',type='primary',disabled=bool(missing) or not acknowledgement or bool(st.session_state.get('email_parsed') and st.session_state['email_parsed']['record_type']!='MDM Setup')):
        try:
            key=submit_request(domain,values,requester=ROLE_ACTOR[role],merge_source=source_id,merge_target=target_id)
            st.session_state['last_request']=key
            st.success(f'{key} submitted for independent steward review.')
        except WorkflowError as e:st.error(str(e))
    if st.session_state.get('last_request'):
        st.info(f"Next: approve request {st.session_state['last_request']} using the guided roles on Step 2.")
        next_step(1,'Continue to review and approvals →')
    st.divider()
    with st.expander('Why name similarity is not enough'):
        st.write('Matching uses normalized names and fuzzy similarity. Similarity ≥90 triggers review; 75–89.9 warns; below 75 passes. The demo also compares legal/business identifiers before authorizing a customer mapping. False-positive near misses should never be merged automatically.')
