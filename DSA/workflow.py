"""Auditable maker-checker workflow and idempotent SAP handoff simulation."""
import json
import sqlite3
from config import settings, ROLE_ACTOR
from database import conn, audit, load_df, utcnow

class WorkflowError(ValueError): pass

def status_for(key):
    with conn() as c:
        r=c.execute('SELECT * FROM mdm_requests WHERE request_key=?',(key,)).fetchone()
        if not r: raise WorkflowError('Request does not exist.')
        return dict(r)

def approval_stewards(c, domain, entity, country):
    rows=c.execute('''SELECT steward FROM approval_matrix WHERE domain=? AND entity=? AND country=? ORDER BY steward''',
                   (domain,entity,country)).fetchall()
    return [r['steward'] for r in rows] or settings()['domains'][domain]['stewards']

def submit_request(domain,payload,requester='Alex Sales',merge_source=None,merge_target=None):
    cfg=settings()['domains'][domain]
    missing=[f for f in cfg['required'] if not str(payload.get(f,'')).strip()]
    if missing: raise WorkflowError('Required fields missing: '+', '.join(missing))
    country=payload['country']; entity=payload['entity']
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        k='RQ-'+str(c.execute('SELECT COALESCE(MAX(id),0)+1 FROM mdm_requests').fetchone()[0]).zfill(4)
        c.execute('''INSERT INTO mdm_requests(request_key,domain,record_name,country,entity,requested_by,payload,status,match_source_id,match_target_id,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                  (k,domain,payload['name'],country,entity,requester,json.dumps(payload),'Submitted',merge_source,merge_target,utcnow()))
        audit(c,k,'Submitted',requester,'Request passed required-field validation')
        for steward in approval_stewards(c,domain,entity,country):
            c.execute('INSERT INTO approval_tasks(request_key,steward,state) VALUES(?,?,?)',(k,steward,'Pending'))
        c.execute('UPDATE mdm_requests SET status=? WHERE request_key=?',('In Approval',k))
        audit(c,k,'In Approval','System','Domain data steward tasks routed in parallel')
        c.commit()
    return k

def decide(key,steward,actor,decision):
    if decision not in ('Approved','Rejected'): raise WorkflowError('Invalid decision')
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        req=c.execute('SELECT * FROM mdm_requests WHERE request_key=?',(key,)).fetchone()
        if not req or req['status']!='In Approval': raise WorkflowError('Request is not awaiting approval.')
        if req['requested_by']==actor: raise WorkflowError('Segregation of duties: requestor cannot self-approve.')
        task=c.execute('SELECT state FROM approval_tasks WHERE request_key=? AND steward=?',(key,steward)).fetchone()
        if task is None or task['state']!='Pending': raise WorkflowError('No pending approval for this steward.')
        c.execute('''UPDATE approval_tasks SET state=?,decision_by=?,decision_at=?
                     WHERE request_key=? AND steward=?''',(decision,actor,utcnow(),key,steward))
        audit(c,key,decision,actor,f'{steward} decision')
        if decision=='Rejected':
            c.execute('UPDATE mdm_requests SET status=? WHERE request_key=?',('Rejected',key))
        else:
            count=c.execute("SELECT COUNT(*) FROM approval_tasks WHERE request_key=? AND state='Pending'",(key,)).fetchone()[0]
            if count==0:
                c.execute('UPDATE mdm_requests SET status=? WHERE request_key=?',('Approved',key))
                audit(c,key,'Approved','System','All independent steward approvals completed')
        c.commit()

def _safe_merge(c, source, target, key,actor):
    if not source or not target: return
    if source==target: raise WorkflowError('Cannot merge a customer with itself.')
    a=c.execute('SELECT * FROM customers WHERE customer_id=?',(source,)).fetchone()
    b=c.execute('SELECT * FROM customers WHERE customer_id=?',(target,)).fetchone()
    if not a or not b: raise WorkflowError('Customer ID not found.')
    if a['country']!=b['country'] or not a['registration_number'] or a['registration_number']!=b['registration_number']:
        raise WorkflowError('Merge requires same country and matching verified business identifier.')
    old=c.execute('SELECT canonical_id FROM identity_map WHERE alias_id=?',(source,)).fetchone()
    if old and old['canonical_id']!=target: raise WorkflowError('Alias is already mapped to a different identity.')
    if c.execute('SELECT 1 FROM identity_map WHERE alias_id=?',(target,)).fetchone():
        raise WorkflowError('Target is itself an alias. Choose a canonical record.')
    c.execute('''INSERT OR IGNORE INTO identity_map(alias_id,canonical_id,approved_by,request_id,approved_at)
                 VALUES(?,?,?,?,?)''',(source,target,actor,key,utcnow()))
    audit(c,key,'Golden record mapping',actor,f'{source} mapped to {target}; source transactions retained')

def finalize(key,actor):
    """Final checker confirms golden-record mapping, then performs an idempotent mock SAP handoff."""
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        req=c.execute('SELECT * FROM mdm_requests WHERE request_key=?',(key,)).fetchone()
        if req is None: raise WorkflowError('Unknown request')
        if req['status']=='Created':
            return {'request_key':key,'already_created':True}
        if req['status']!='Approved': raise WorkflowError('All steward approvals are required first.')
        if actor==req['requested_by']: raise WorkflowError('Requestor cannot perform final check.')
        _safe_merge(c,req['match_source_id'],req['match_target_id'],key,actor)
        payload=json.loads(req['payload'])
        obj='BusinessPartners' if req['domain'] in ('Customer','Vendor') else ('Items' if req['domain']=='Item' else 'CostCenters')
        if req['match_source_id'] and req['match_target_id']:
            # Existing alias resolution is a linkage/update, NOT another BP creation.
            body={'Object':obj,'Action':'LinkExistingIdentity','RequestID':key,
                  'AliasSAPID':req['match_source_id'],'GoldenRecordSAPID':req['match_target_id'],
                  'Country':req['country'],'Entity':req['entity']}
        else:
            body={'Object':obj,'Action':'CreateMasterRecord','RequestID':key,
                  'Name':req['record_name'],'Country':req['country'],'Entity':req['entity'],'Values':payload}
        # UNIQUE(request_key) prevents duplicate SAP record on retry.
        c.execute('INSERT OR IGNORE INTO sap_records(request_key,sap_object,payload_json,created_at) VALUES(?,?,?,?)',
                  (key,obj,json.dumps(body),utcnow()))
        c.execute('UPDATE mdm_requests SET status=? WHERE request_key=?',('Created',key))
        audit(c,key,'Created',actor,'Idempotent SAP-ready payload created (not connected to SAP)')
        c.commit()
    return {'request_key':key,'already_created':False,'payload':body}

def add_approval_rule(entity,domain,country,steward,delegate='MDM Steward',sla_days=2):
    if not 1<=int(sla_days)<=30: raise WorkflowError('SLA must be between 1 and 30 working days.')
    with conn() as c:
        try:
            c.execute('INSERT INTO approval_matrix(entity,domain,country,steward,delegate,sla_days) VALUES(?,?,?,?,?,?)',
                      (entity,domain,country,steward,delegate,int(sla_days)))
            c.commit()
        except sqlite3.IntegrityError as ex: raise WorkflowError('The rule already exists.') from ex
