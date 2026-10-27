import streamlit as st
import pandas as pd
from config import COUNTRIES,ENTITIES,settings,ROLE_ACTOR
from dedup import find_matches
from workflow import submit_request, WorkflowError
from database import load_df

def render(role):
    st.title('Smart Intake & Data Quality')
    st.write('Validate master-data requests before they enter stewardship approval. Customer and Item forms are functional; Vendor and Cost Center are configuration examples.')
    cfg=settings()['domains']
    domain=st.selectbox('Request domain',list(cfg),index=0)
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
    acknowledgement=True
    if matches and max(m['score'] for m in matches)>=settings()['matching']['review']:
        acknowledgement=st.checkbox('I reviewed potential duplicates. Route this request for stewardship review rather than automatic creation.')
    if st.button('Submit for approval',type='primary',disabled=bool(missing) or not acknowledgement):
        try:
            key=submit_request(domain,values,requester=ROLE_ACTOR[role])
            st.success(f'{key} submitted. Check Page 2 for the parallel approval tasks.')
        except WorkflowError as e:st.error(str(e))
    st.divider()
    with st.expander('Why name similarity is not enough'):
        st.write('Matching uses normalized names and fuzzy similarity. Similarity ≥90 triggers review; 75–89.9 warns; below 75 passes. The demo also compares legal/business identifiers before authorizing a customer mapping. False-positive near misses should never be merged automatically.')
