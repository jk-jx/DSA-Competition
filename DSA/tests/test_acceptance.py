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
    key=submit_request('Item',{'name':'Diagnostic Tubes','country':'SG','entity':'NEWBU','item_category':'Consumables',
                               'regulatory_class':'Not regulated'})
    routed=load_df('SELECT steward FROM approval_tasks WHERE request_key=?',(key,))
    assert set(routed.steward)=={'Quality Steward'}
    decide(key,'Quality Steward','Nadia Quality','Approved')
    payload=finalize(key,'Priya MDM')['payload']
    assert payload['Action']=='CreateMasterRecord'
    assert payload['Object']=='Items'


ITEM={'name':'Lab Reagent Kit','country':'SG','entity':'QTS','item_category':'Reagents'}

def test_item_without_regulatory_class_is_blocked():
    with pytest.raises(WorkflowError,match='regulatory_class'):
        submit_request('Item',dict(ITEM))
    assert load_df("SELECT 1 FROM mdm_requests WHERE domain='Item'").empty

def test_regulated_item_requires_licence_number():
    with pytest.raises(WorkflowError,match='licence_number'):
        submit_request('Item',{**ITEM,'regulatory_class':'Class B'})
    key=submit_request('Item',{**ITEM,'regulatory_class':'Class B','licence_number':'DE0012345'})
    assert status_for(key)['status']=='In Approval'

def test_unregulated_item_does_not_need_licence_number():
    key=submit_request('Item',{**ITEM,'regulatory_class':'Not regulated'})
    assert status_for(key)['status']=='In Approval'

def test_regulatory_class_must_be_a_listed_value():
    with pytest.raises(WorkflowError,match='listed value'):
        submit_request('Item',{**ITEM,'regulatory_class':'Probably fine','licence_number':'X1'})


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

def test_quality_exception_queue_tracks_governance_and_exposure():
    from quality_monitor import quality_cases, quality_summary
    cases=quality_cases()
    assert len(cases)==25
    hero=cases.set_index("alias_id").loc["SG-A001"]
    assert hero.target_id=="SG-C001"
    assert hero.category_change
    assert hero.priority=="Critical"
    assert hero.current_growth==-40.0
    assert hero.potential_growth==20.0
    assert hero.status=="In review"
    assert hero.request_key=="RQ-0001"
    summary=quality_summary(cases)
    assert summary["unresolved"]==25
    assert summary["decision_changers"]>=1
    assert summary["units_attribution_exposure"]>0
    decide("RQ-0001","Finance Steward","Wei Jie Finance","Approved")
    decide("RQ-0001","BU Steward","Daniel BU Head","Approved")
    assert quality_cases().set_index("alias_id").loc["SG-A001"].status=="Awaiting MDM"
    finalize("RQ-0001","Priya MDM")
    after=quality_cases()
    assert after.set_index("alias_id").loc["SG-A001"].status=="Resolved"
    assert quality_summary(after)["unresolved"]==24

def test_3d_identity_network_reflects_actual_approval_state():
    from quality_monitor import quality_cases
    from network_view import build_identity_network
    cases=quality_cases()
    fig=build_identity_network(cases,highlighted_alias="SG-A001")
    assert len(fig.data)>=3
    assert any(trace.name=="Proposed link" for trace in fig.data)
    decide("RQ-0001","Finance Steward","Wei Jie Finance","Approved")
    decide("RQ-0001","BU Steward","Daniel BU Head","Approved")
    finalize("RQ-0001","Priya MDM")
    approved=build_identity_network(quality_cases())
    assert any(trace.name=="Approved alias" for trace in approved.data)

def test_three_models_and_filtered_ablation_share_genuine_po_holdout():
    from forecast import backtest,forward_plan
    summary,detail=backtest()
    expected={'6-month moving average','Holt-Winters',
              'Pooled gradient boosting','Unfiltered training (ablation)'}
    assert set(summary.model)==expected
    assert (summary.held_out_points==45).all()
    assert (summary['WAPE %']>=0).all()
    for model in expected:
        part=detail[detail.model==model]
        assert len(part)==45
        assert (part.actual>=0).all()
    clean=detail[detail.model=='Pooled gradient boosting'].sort_values(['country','product','test_month'])
    dirty=detail[detail.model=='Unfiltered training (ablation)'].sort_values(['country','product','test_month'])
    assert clean.actual.tolist()==dirty.actual.tolist()
    future=forward_plan('SG','A',6,'Pooled gradient boosting')
    assert len(future)==6
    assert (future['Forecast units']>=0).all()


def test_hidden_demand_is_transparently_assumption_driven():
    from hidden_demand import hidden_demand_model
    x=hidden_demand_model(18,1800,.35)
    assert x['pending_setups']==1
    assert round(x['estimated_blocked_order_equivalents'],3)==.21
    assert x['illustrative_delayed_value_sgd']==pytest.approx(378)
    assert hidden_demand_model(0,1800,.35)['illustrative_delayed_value_sgd']==0


def test_email_intake_simulates_grace_period_and_routing_without_sending():
    from email_routing import route_inbound_email
    message='Set up new customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001'
    grace=route_inbound_email(message,grace_period=True)
    assert grace['record_type']=='MDM Setup'
    assert grace['sent'] is False
    assert 'Grace-period' in grace['route']
    assert not grace['approval_notification_preview']['contains_sensitive_fields']
    strict=route_inbound_email(message,grace_period=False)
    assert strict['route']=='Form required'
    override=route_inbound_email(message,mdm_override=True)
    assert override['route']=='MDM manual override'
    po=route_inbound_email('Purchase order PO 12345 for Product A')
    assert po['record_type']=='PO'
    assert po['route']=='Purchasing / commercial inbox'

def test_reference_backtest_values_are_reproducible():
    """Detect changes in seeded data, model libraries or evaluation methodology."""
    from forecast import backtest
    summary, rows=backtest()
    results=dict(zip(summary.model,summary["WAPE %"]))
    assert results["6-month moving average"]==22.07
    assert results["Holt-Winters"]==30.55
    assert results["Pooled gradient boosting"]==21.46
    assert results["Unfiltered training (ablation)"]==22.86
    assert (summary.held_out_points==45).all()
    assert rows.groupby("model").actual.sum().nunique()==1

def test_regional_chart_and_summary_share_entity_filter():
    from insights import monthly,transactions
    expected=transactions(True)
    expected=expected[(expected.period>='2025-10')&(expected.entity=='QTS')&(expected.country=='SG')&(expected['product']=='A')]
    observed=monthly(country='SG',product='A',entity='QTS')
    assert int(observed.qty.sum())==int(expected.qty.sum())
    all_units=int(monthly(country='SG',product='A').qty.sum())
    assert int(observed.qty.sum())<=all_units


SENSITIVE_CUSTOMER={'name':'Riverside Medical Centre','country':'MY','entity':'SPD','registration_number':'MY-REG-777',
                    'credit_terms':'Net 60','credit_limit':'50000','bank_account':'5140012345678'}

def test_sensitive_customer_fields_are_masked_for_other_roles():
    from workflow import masked_payload,can_view_sensitive
    shown=masked_payload('Customer',SENSITIVE_CUSTOMER)
    assert shown['bank_account']=='••••5678'
    assert shown['credit_limit']=='••••' and shown['credit_terms']=='••••'
    assert shown['name']=='Riverside Medical Centre'
    assert can_view_sensitive('Customer','Finance Steward') and can_view_sensitive('Customer','MDM Steward')
    assert not any(can_view_sensitive('Customer',r) for r in ('Requestor','BU Steward','Admin'))

def test_finance_reveal_is_audited_and_others_are_refused():
    from workflow import reveal_sensitive
    key=submit_request('Customer',dict(SENSITIVE_CUSTOMER))
    with pytest.raises(WorkflowError):
        reveal_sensitive(key,'BU Steward','Daniel BU Head')
    assert reveal_sensitive(key,'Finance Steward','Wei Jie Finance')['bank_account']=='5140012345678'
    log=load_df("SELECT actor,event,details FROM audit_log WHERE request_key=? AND event='Sensitive fields viewed'",(key,))
    assert list(log.actor)==['Wei Jie Finance']
    assert 'bank_account' in log.details.iloc[0] and '5140012345678' not in log.details.iloc[0]

def test_credit_terms_must_be_a_listed_value():
    with pytest.raises(WorkflowError,match='listed value'):
        submit_request('Customer',{**SENSITIVE_CUSTOMER,'credit_terms':'Whenever'})
