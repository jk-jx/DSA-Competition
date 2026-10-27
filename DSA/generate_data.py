"""Create reproducible, clearly synthetic data for a 36-month, 5-country demonstration."""
import argparse
from datetime import date
import numpy as np
import pandas as pd
from config import COUNTRIES, ENTITIES, DB_PATH, settings
from database import conn, init_schema, audit, utcnow

END_PERIOD = '2026-09'

def seed(reset=False):
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    if reset and DB_PATH.exists(): DB_PATH.unlink()
    rng = np.random.default_rng(20261027)
    months = pd.period_range(end=END_PERIOD, periods=36, freq='M').astype(str).tolist()
    with conn() as c:
        init_schema(c)
        if c.execute('SELECT COUNT(*) FROM customers').fetchone()[0]: return
        customer_rows = []
        by_country = {}
        for cc in COUNTRIES:
            for i in range(1,61):
                cid = f'{cc}-C{i:03d}'
                name = ('Hospital ABC' if cid == 'SG-C001' else f'{COUNTRIES[cc]} Health Account {i:03d}')
                reg = f'{cc}-REG-{i:06d}'
                ent = ENTITIES[(i-1)%3]
                customer_rows.append((cid,name,cc,ent,reg,cid))
                by_country.setdefault(cc,[]).append(cid)
            for j in range(1,6):
                base_id = f'{cc}-C{j:03d}'
                aid = f'{cc}-A{j:03d}'
                alias_name = 'ABC Hospital' if (cc,j)==('SG',1) else f'{COUNTRIES[cc]} Healthcare Acct {j:03d}'
                alias_entity = 'QTS' if (cc,j)==('SG',1) else ENTITIES[j%3]
                customer_rows.append((aid,alias_name,cc,alias_entity,f'{cc}-REG-{j:06d}',base_id))
                by_country[cc].append(aid)
        c.executemany('INSERT INTO customers VALUES(?,?,?,?,?,?)',customer_rows)
        # 5 countries x 3 products x 36 months. Exactly 6,000 genuine PO lines (including hero).
        rows=[]
        tx_id = 1
        for idx in range(5988):
            cc = list(COUNTRIES)[idx%5]
            mo = months[(idx//5 + int(rng.integers(0,36)))%36]
            pr = 'ABC'[int(rng.integers(0,3))]
            cust = str(rng.choice([i for i in by_country[cc] if i not in {'SG-C001','SG-A001'}]))
            ent = next(a[3] for a in customer_rows if a[0]==cust)
            season = 1.27 if int(mo[-2:]) in (3,9,12) else 1.0
            qty = max(1,int(rng.poisson((12+(idx%3)*4)*season)))
            rows.append((tx_id,cust,cc,ent,pr,mo,qty,'PO')); tx_id+=1
        # Carefully controlled hero: primary falls 100 -> 60; alias contributes 60 in latest 3 months.
        previous = [('2026-04',33),('2026-05',33),('2026-06',34)]
        latest = [('2026-07',20),('2026-08',20),('2026-09',20)]
        for mo,q in previous+latest:
            rows.append((tx_id,'SG-C001','SG','SPD','A',mo,q,'PO')); tx_id+=1
        for mo,q in latest:
            rows.append((tx_id,'SG-A001','SG','QTS','A',mo,q,'PO')); tx_id+=1
        # Three additional historical orders outside the 6-month comparison.
        for mo in ['2026-01','2026-02','2026-03']:
            rows.append((tx_id,'SG-C001','SG','SPD','A',mo,15,'PO')); tx_id+=1
        for record_type,total in [('Enquiry',700),('Customer Request',300)]:
            for i in range(total):
                cc = list(COUNTRIES)[i%5]
                cust = str(rng.choice(by_country[cc]))
                ent = next(a[3] for a in customer_rows if a[0]==cust)
                mo = months[int(rng.integers(0,36))]
                rows.append((tx_id,cust,cc,ent,'ABC'[int(rng.integers(0,3))],mo,int(rng.integers(1,40)),record_type))
                tx_id += 1
        c.executemany('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)',rows)
        conf = settings()['domains']
        for cc in COUNTRIES:
            for ent in ENTITIES:
                for domain in ('Customer','Item'):
                    for steward in conf[domain]['stewards']:
                        c.execute('INSERT INTO approval_matrix(entity,domain,country,steward,delegate,sla_days) VALUES(?,?,?,?,?,?)',
                                  (ent,domain,cc,steward,'MDM Steward',2))
        # Seed a real actionable match-and-merge request to make the hero demo fast.
        key='RQ-0001'; now=utcnow()
        payload={'name':'ABC Hospital','registration_number':'SG-REG-000001','description':'Review potential duplicate with Hospital ABC'}
        c.execute('''INSERT INTO mdm_requests(request_key,domain,record_name,country,entity,requested_by,payload,status,match_source_id,match_target_id,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(key,'Customer','ABC Hospital','SG','QTS','Alex Sales',__import__('json').dumps(payload),'In Approval','SG-A001','SG-C001',now))
        for steward in conf['Customer']['stewards']:
            c.execute('INSERT INTO approval_tasks(request_key,steward,state) VALUES(?,?,?)',(key,steward,'Pending'))
        audit(c,key,'Submitted','Alex Sales','Seeded synthetic identity-resolution request')
        audit(c,key,'In Approval','System','Finance and BU steward tasks created')
        c.commit()
    return {'customers':325,'canonical_customers':300,'purchase_order_lines':6000,'enquiries':700,'customer_requests':300}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--reset',action='store_true')
    args=parser.parse_args(); print(seed(reset=args.reset))
