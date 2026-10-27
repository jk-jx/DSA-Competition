import pytest
from database import conn,load_df
from generate_data import seed
from insights import hero_customer,decision_impact,regional_summary,record_type_counts
from dedup import find_matches,normalize
from workflow import decide,finalize,submit_request,status_for,WorkflowError,add_approval_rule
import database,generate_data

@pytest.fixture(autouse=True)
def clean_database(tmp_path,monkeypatch):
    path=tmp_path/'test_demo.sqlite'
    monkeypatch.setattr(database,'DB_PATH',path)
    monkeypatch.setattr(generate_data,'DB_PATH',path)
    seed(reset=True)

def test_seed_has_expected_volume_and_separate_record_types():
    assert record_type_counts()=={'PO':6000,'Enquiry':700,'Customer Request':300}
    assert len(load_df('SELECT customer_id FROM customers'))==325
    assert status_for('RQ-0001')['status']=='In Approval'

def test_hero_approval_changes_customer_not_region_totals():
    before=hero_customer(); totals_before=regional_summary()['Latest 12 months'].sum()
    assert before['raw']['growth']==-40.0
    assert before['cleaned']['growth']==-40.0
    assert decision_impact()['changed']==0
    decide('RQ-0001','Finance Steward','Wei Jie Finance','Approved')
    decide('RQ-0001','BU Steward','Daniel BU Head','Approved')
    assert status_for('RQ-0001')['status']=='Approved'
    result=finalize('RQ-0001','Priya MDM')
    assert result['payload']['Action']=='LinkExistingIdentity'
    after=hero_customer()
    assert after['raw']['growth']==-40.0
    assert after['cleaned']['growth']==20.0
    assert after['cleaned']['category']=='Growing'
    assert decision_impact()['changed']==1
    assert regional_summary()['Latest 12 months'].sum()==totals_before
    assert finalize('RQ-0001','Priya MDM')['already_created']
    assert int(load_df('SELECT COUNT(*) AS n FROM sap_records').iloc[0]['n'])==1
    assert int(load_df('SELECT COUNT(*) AS n FROM identity_map').iloc[0]['n'])==1

def test_maker_checker_and_no_unapproved_finalization():
    with pytest.raises(WorkflowError):decide('RQ-0001','Finance Steward','Alex Sales','Approved')
    with pytest.raises(WorkflowError):finalize('RQ-0001','Priya MDM')

def test_rejection_and_audit_append_only():
    decide('RQ-0001','Finance Steward','Wei Jie Finance','Rejected')
    assert status_for('RQ-0001')['status']=='Rejected'
    with pytest.raises(WorkflowError):finalize('RQ-0001','Priya MDM')
    with pytest.raises(Exception):
        with conn() as c: c.execute("DELETE FROM audit_log WHERE request_key='RQ-0001'")

def test_duplicate_normalization_and_tier():
    assert normalize('Natl Univ Hosp Pte Ltd')=='national university hospital'
    matches=find_matches('ABC Hospital',country='SG')
    assert any(m['customer_id']=='SG-C001' and m['score']==100 and m['tier']=='Review required' for m in matches)

def test_new_item_request_and_configurable_approvals():
    add_approval_rule('NEWBU','Item','SG','Quality Steward',sla_days=2)
    key=submit_request('Item',{'name':'Diagnostic Tubes','country':'SG','entity':'NEWBU','item_category':'Consumables'})
    routed=load_df('SELECT steward FROM approval_tasks WHERE request_key=?',(key,))
    assert set(routed.steward)=={'Quality Steward'}
    decide(key,'Quality Steward','Nadia Quality','Approved')
    payload=finalize(key,'Priya MDM')['payload']
    assert payload['Action']=='CreateMasterRecord'
    assert payload['Object']=='Items'


def test_invalid_canonical_mapping_is_blocked_at_intake():
    with pytest.raises(WorkflowError):
        submit_request('Customer',{'name':'Healthcare Alias','country':'SG','entity':'SPD','registration_number':'FAKE'},
                       merge_source='SG-C002',merge_target='SG-C003')


def test_fresh_submitted_identity_resolution_changes_dashboard():
    key=submit_request('Customer', {'name':'ABC Hospital','country':'SG','entity':'QTS',
        'registration_number':'SG-REG-000001'}, requester='Alex Sales',
        merge_source='SG-A001',merge_target='SG-C001')
    req=status_for(key)
    assert (req['match_source_id'],req['match_target_id'])==('SG-A001','SG-C001')
    assert hero_customer()['cleaned']['growth']==-40.0
    decide(key,'Finance Steward','Wei Jie Finance','Approved')
    decide(key,'BU Steward','Daniel BU Head','Approved')
    result=finalize(key,'Priya MDM')
    assert result['payload']['Action']=='LinkExistingIdentity'
    assert hero_customer()['cleaned']['growth']==20.0
    assert decision_impact()['changed']==1


def test_partial_merge_request_is_rejected():
    with pytest.raises(WorkflowError):
        submit_request('Customer', {'name':'ABC Hospital','country':'SG','entity':'QTS',
            'registration_number':'SG-REG-000001'}, merge_source='SG-A001')


def test_merge_requires_matching_submitted_identifier():
    with pytest.raises(WorkflowError):
        submit_request('Customer', {'name':'ABC Hospital','country':'SG','entity':'QTS',
            'registration_number':'FAKE'}, merge_source='SG-A001',merge_target='SG-C001')

def test_identity_case_evidence_is_a_preview_until_approved():
    from insights import identity_case_evidence
    first=identity_case_evidence()
    assert first['primary_previous']==100
    assert first['primary_latest']==60
    assert first['combined_previous']==100
    assert first['combined_latest']==120
    assert first['primary_growth']==-40.0
    assert first['combined_growth']==20.0
    assert not first['approval_applied']
    original=first['total_po_units']
    decide('RQ-0001','Finance Steward','Wei Jie Finance','Approved')
    decide('RQ-0001','BU Steward','Daniel BU Head','Approved')
    finalize('RQ-0001','Priya MDM')
    after=identity_case_evidence()
    assert after['approval_applied']
    assert after['total_po_units']==original
    assert after['monthly'].equals(first['monthly'])

def test_forward_purchasing_plan_is_reproducible_and_po_only():
    from forecast import forward_plan
    for horizon in (6,12):
        for model in ('6-month moving average','Holt-Winters'):
            result=forward_plan('SG','A',horizon,model)
            assert len(result)==horizon
            assert result.iloc[0]['Month']=='2026-10'
            assert result.iloc[-1]['Month']==('2027-03' if horizon==6 else '2027-09')
            assert (result['Low planning scenario']<=result['Forecast units']).all()
            assert (result['Forecast units']<=result['High planning scenario']).all()
            assert (result['Forecast units']>=0).all()
    with pytest.raises(ValueError):
        forward_plan('SG','A',18)
