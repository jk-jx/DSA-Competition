"""Operational exception triage over synthetic master records and real seeded PO rows.

This module flags *candidate* identity links using matching country and business
registration identifiers. Canonical references are supplied by the synthetic
case dataset; a match is never committed without independent stewardship.
"""
import pandas as pd
from database import load_df
from insights import PREV3, LAST3, DISPLAY_START, growth_category


def quality_cases():
    """Rank unresolved master-data identity exceptions by business consequences."""
    pairs = load_df(
        """SELECT a.customer_id AS alias_id, a.name AS alias_name,
                  a.country, a.entity, a.registration_number,
                  c.customer_id AS target_id, c.name AS target_name
           FROM customers a
           JOIN customers c
             ON a.canonical_truth_id = c.customer_id
            AND a.customer_id <> c.customer_id
            AND a.country = c.country
            AND a.registration_number = c.registration_number
           ORDER BY a.country, a.customer_id"""
    )
    columns = [
        'alias_id','alias_name','country','entity','registration_number',
        'target_id','target_name','prior_primary','recent_primary',
        'prior_combined','recent_combined','current_growth',
        'potential_growth','category_change','alias_12m_units',
        'exposed_po_lines','risk_score','priority','status','request_key',
    ]
    if pairs.empty:
        return pd.DataFrame(columns=columns)

    transactions=load_df(
        """SELECT customer_id,period,SUM(qty) AS units,COUNT(*) AS po_lines
           FROM transactions WHERE record_type='PO'
           GROUP BY customer_id,period"""
    )
    merged=transactions.groupby('customer_id')
    volumes={customer:group.set_index('period') for customer,group in merged}
    linked=set(load_df('SELECT alias_id FROM identity_map')['alias_id'].tolist())
    requests=load_df(
        """SELECT request_key,match_source_id,match_target_id,status
           FROM mdm_requests WHERE match_source_id IS NOT NULL
           ORDER BY id DESC"""
    )
    approvals={}
    for item in requests.itertuples(index=False):
        key=(item.match_source_id,item.match_target_id)
        if key not in approvals or approvals[key][0] in ('Rejected','Created'):
            approvals[key]=(item.status,item.request_key)

    def qty(cid,window):
        data=volumes.get(cid)
        return int(data.loc[data.index.isin(window),'units'].sum()) if data is not None else 0

    def lines(cid):
        data=volumes.get(cid)
        if data is None:return 0
        return int(data.loc[data.index>=DISPLAY_START,'po_lines'].sum())

    def growing(prev,recent):
        if prev==0:return None
        return round(100*(recent-prev)/prev,1)

    result=[]
    for item in pairs.itertuples(index=False):
        primary_before=qty(item.target_id,PREV3)
        primary_after=qty(item.target_id,LAST3)
        alias_before=qty(item.alias_id,PREV3)
        alias_after=qty(item.alias_id,LAST3)
        combined_before=primary_before+alias_before
        combined_after=primary_after+alias_after
        p= growth_category(primary_before,primary_after)
        c= growth_category(combined_before,combined_after)
        category_change=(p!='Insufficient history' and c!='Insufficient history' and p!=c)
        alias_units=qty(item.alias_id,list(pd.period_range(
            start=DISPLAY_START,periods=12,freq='M').astype(str)))
        exposure=lines(item.alias_id)
        # An explainable prioritization aid, not a probability of duplication.
        score=min(100,30 + (45 if category_change else 0) +
                  (15 if alias_units>=150 else 8 if alias_units>0 else 0) +
                  (10 if exposure>=8 else 5 if exposure else 0))
        priority=('Critical' if category_change else
                  'High' if score>=55 else 'Medium')
        status='Resolved' if item.alias_id in linked else 'Unreviewed'
        key=None
        workflow=approvals.get((item.alias_id,item.target_id))
        if status!='Resolved' and workflow:
            status,key=workflow
            if status=='In Approval':status='In review'
            elif status=='Approved':status='Awaiting MDM'
            elif status=='Rejected':status='Needs revision'
            elif status=='Created':status='Resolved'
        result.append({
            'alias_id':item.alias_id,'alias_name':item.alias_name,
            'country':item.country,'entity':item.entity,
            'registration_number':item.registration_number,
            'target_id':item.target_id,'target_name':item.target_name,
            'prior_primary':primary_before,'recent_primary':primary_after,
            'prior_combined':combined_before,'recent_combined':combined_after,
            'current_growth':growing(primary_before,primary_after),
            'potential_growth':growing(combined_before,combined_after),
            'category_change':category_change,
            'alias_12m_units':alias_units,'exposed_po_lines':exposure,
            'risk_score':score,'priority':priority,'status':status,
            'request_key':key,
        })
    output=pd.DataFrame(result,columns=columns)
    return output.sort_values(
        ['category_change','risk_score','alias_12m_units'],
        ascending=[False,False,False],kind='stable'
    ).reset_index(drop=True)


def quality_summary(cases=None):
    """Count distinct open candidate pairs and linked-order exposure."""
    df=quality_cases() if cases is None else cases
    remaining=df[df['status']!='Resolved']
    return {
        'candidates':len(df),
        'unresolved':len(remaining),
        'awaiting_review':int(remaining['status'].isin(['In review','Awaiting MDM']).sum()),
        'decision_changers':int(remaining['category_change'].sum()),
        'units_attribution_exposure':int(remaining['alias_12m_units'].sum()),
    }
