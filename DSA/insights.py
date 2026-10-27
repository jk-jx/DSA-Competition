"""Purchasing analytics and decision impact calculated from actual seeded SQLite rows."""
import numpy as np
import pandas as pd
from database import load_df

LATEST = pd.Period('2026-09',freq='M')
DISPLAY_START = str(LATEST-11)
YOY_START = str(LATEST-23)
PREV3 = [str(LATEST-i) for i in (5,4,3)]
LAST3 = [str(LATEST-i) for i in (2,1,0)]

def transactions(po_only=True):
    q='''SELECT t.*, c.name AS source_name, c.canonical_truth_id, 
                 COALESCE(m.canonical_id,t.customer_id) AS cleaned_customer_id
          FROM transactions t JOIN customers c ON t.customer_id=c.customer_id
          LEFT JOIN identity_map m ON t.customer_id=m.alias_id'''
    df=load_df(q)
    return df[df.record_type=='PO'].copy() if po_only else df

def enriched(cleaned=True):
    df=transactions(True)
    df['resolved_id']=df.cleaned_customer_id if cleaned else df.customer_id
    return df

def growth_category(previous,current):
    if previous<=0: return 'Insufficient history'
    pct=(current-previous)/previous*100
    return 'Growing' if pct>5 else ('Declining' if pct<-5 else 'Stable')

def customer_growth(cleaned=True):
    df=enriched(cleaned)
    df=df[df.period.isin(PREV3+LAST3)]
    df=df.assign(window=np.where(df.period.isin(PREV3),'previous','latest'))
    pivot=df.pivot_table(index='resolved_id',columns='window',values='qty',aggfunc='sum',fill_value=0)
    for col in ('previous','latest'):
        if col not in pivot:pivot[col]=0
    pivot=pivot.reset_index()
    pivot['growth_pct']=np.where(pivot.previous>0,(pivot.latest-pivot.previous)/pivot.previous*100,np.nan)
    pivot['category']=[growth_category(p,l) for p,l in zip(pivot.previous,pivot.latest)]
    return pivot

def decision_impact():
    raw=customer_growth(False).set_index('resolved_id')
    clean=customer_growth(True).set_index('resolved_id')
    mapping=load_df('SELECT customer_id,canonical_truth_id FROM customers')
    # Compare the sales-facing primary record for every canonical entity with its cleaned identity.
    primary=set(mapping.customer_id)&set(mapping.canonical_truth_id)
    eligible=changed=0
    details=[]
    for key in sorted(primary):
        if key not in raw.index or key not in clean.index: continue
        before=raw.loc[key]; after=clean.loc[key]
        if before['category']=='Insufficient history' or after['category']=='Insufficient history': continue
        eligible+=1
        if before['category']!=after['category']:
            changed+=1
            details.append({'customer_id':key,'before':before['category'],'after':after['category'],
                           'raw_growth':round(float(before['growth_pct']),1),'cleaned_growth':round(float(after['growth_pct']),1)})
    return {'changed':changed,'eligible':eligible,'percent':(changed/eligible*100 if eligible else 0), 'examples':details}

def hero_customer():
    raw=customer_growth(False).set_index('resolved_id')
    clean=customer_growth(True).set_index('resolved_id')
    key='SG-C001'
    def extract(df):
        r=df.loc[key]
        return {'previous':int(r.previous),'latest':int(r.latest),'growth':float(r.growth_pct),'category':r.category}
    return {'raw':extract(raw),'cleaned':extract(clean),'resolved':bool(load_df('SELECT * FROM identity_map WHERE alias_id=?',('SG-A001',)).shape[0])}

def hero_preview():
    """Illustrative post-link view from the synthetic source records; never a committed merge.

    Shows what Hospital ABC's trend would be if stewards approve the seeded
    alias SG-A001 -> SG-C001. Source transaction rows remain untouched.
    """
    source=load_df(
        """SELECT t.period,t.qty FROM transactions t
           WHERE t.record_type='PO' AND t.customer_id IN (?,?)""",
        ('SG-C001','SG-A001'),
    )
    previous=int(source.loc[source.period.isin(PREV3),'qty'].sum())
    latest=int(source.loc[source.period.isin(LAST3),'qty'].sum())
    growth=(latest-previous)/previous*100 if previous else float('nan')
    return {'previous':previous,'latest':latest,'growth':growth,
            'category':growth_category(previous,latest)}


def identity_case_evidence():
    """Auditable source split for the seeded identity-resolution case.

    The preview includes only confirmed PO quantities for SG-C001 and SG-A001.
    It does not modify identity_map or any transaction. Even after approval the
    raw source rows remain identical.
    """
    ids=('SG-C001','SG-A001')
    rows=load_df(
        """SELECT customer_id,period,qty FROM transactions
           WHERE record_type='PO' AND customer_id IN (?,?)""", ids)
    months=PREV3+LAST3
    monthly=rows[rows.period.isin(months)].pivot_table(
        index='period',columns='customer_id',values='qty',aggfunc='sum',fill_value=0
    ).reindex(months,fill_value=0)
    for customer_id in ids:
        if customer_id not in monthly: monthly[customer_id]=0
    monthly=monthly.reset_index().rename(columns={
        'period':'Month','SG-C001':'Primary record','SG-A001':'Duplicate alias'
    })
    monthly['Combined identity']=monthly['Primary record']+monthly['Duplicate alias']
    primary_prior=int(monthly.iloc[:3]['Primary record'].sum())
    primary_recent=int(monthly.iloc[3:]['Primary record'].sum())
    merged_prior=int(monthly.iloc[:3]['Combined identity'].sum())
    merged_recent=int(monthly.iloc[3:]['Combined identity'].sum())
    def pct(prior,recent):
        return round((recent-prior)/prior*100,1) if prior else None
    return {
        'monthly':monthly,
        'primary_previous':primary_prior,'primary_latest':primary_recent,
        'combined_previous':merged_prior,'combined_latest':merged_recent,
        'primary_growth':pct(primary_prior,primary_recent),
        'combined_growth':pct(merged_prior,merged_recent),
        'po_rows':int(len(rows)),
        'total_po_units':int(rows.qty.sum()),
        'approval_applied':bool(load_df(
            'SELECT 1 FROM identity_map WHERE alias_id=? AND canonical_id=?',
            ids[::-1],
        ).shape[0]),
    }


def regional_summary(country=None,product=None,entity=None):
    df=enriched(True)
    df=df[(df.period>=YOY_START)&(df.period<=str(LATEST))]
    if country:df=df[df.country==country]
    if product:df=df[df['product']==product]
    if entity:df=df[df.entity==entity]
    window=np.where(df.period>=DISPLAY_START,'Latest 12 months','Prior 12 months')
    df=df.assign(window=window)
    piv=df.pivot_table(index=['country','product'],columns='window',values='qty',aggfunc='sum',fill_value=0).reset_index()
    for col in ('Latest 12 months','Prior 12 months'):
        if col not in piv:piv[col]=0
    base=piv['Prior 12 months']
    piv['YoY growth %']=np.where(base>0,100*(piv['Latest 12 months']-base)/base,np.nan)
    return piv

def monthly(country=None,product=None,entity=None):
    """Latest twelve months of confirmed POs under all selected filters."""
    df=transactions(True)
    if country:df=df[df.country==country]
    if product:df=df[df['product']==product]
    if entity:df=df[df.entity==entity]
    df=df[df.period>=DISPLAY_START]
    return df.groupby(['period','product'],as_index=False)['qty'].sum()

def cross_sell(limit=10):
    df=enriched(True)
    df=df[df.period>=DISPLAY_START]
    grp=df.groupby(['resolved_id','product'])['qty'].sum().unstack(fill_value=0)
    for x in 'ABC':
        if x not in grp: grp[x]=0
    picks=grp[(grp.A>0)&(grp.B>0)&(grp.C==0)].copy()
    picks['action']='Review Product C opportunity (already purchases A and B)'
    return picks.sort_values(['A','B'],ascending=False).head(limit).reset_index()

def dropoff(limit=10):
    df=customer_growth(True)
    return df[(df.category=='Declining')&(df.previous>=10)].sort_values('growth_pct').head(limit)

def record_type_counts():
    df=load_df('SELECT record_type,COUNT(*) AS lines FROM transactions GROUP BY record_type')
    return dict(zip(df.record_type,df.lines))
