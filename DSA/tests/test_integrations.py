"""Offline acceptance tests for optional email, Teams and SAP connectors."""
from datetime import datetime, timedelta, timezone
import pytest
from database import load_df
from generate_data import seed
from intake_parser import classify_message, rule_extract, extract_message
from sla import sla_snapshot, process_sla, business_due
from sap_integration import map_payload, SAPIntegrationError, send_live
import database, generate_data


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    db = tmp_path / "test.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(generate_data, "DB_PATH", db)
    seed(reset=True)


def test_email_mdm_prefill_and_correct_type():
    r = rule_extract("Hi MDM, please create customer ABC Hospital under QTS in Singapore. Registration number: SG-REG-000001.")
    assert r["record_type"] == "MDM Setup"
    assert r["domain"] == "Customer"
    assert r["fields"]["name"] == "ABC Hospital"
    assert r["fields"]["country"] == "SG"
    assert r["fields"]["entity"] == "QTS"
    assert r["fields"]["registration_number"] == "SG-REG-000001"
    assert extract_message("Please create customer ABC Hospital under QTS in Singapore.")["method"] == "rules"


def test_document_types_stay_distinct():
    assert classify_message("Purchase order PO #123456, confirmed delivery") == "PO"
    assert classify_message("Please send a price quotation enquiry") == "Enquiry"
    assert classify_message("We would like to purchase 20 units") == "Customer Request"
    assert classify_message("Please set up a new item, new part") == "MDM Setup"


def test_working_day_sla_and_idempotent_escalation():
    start = datetime(2026, 10, 23, 9, tzinfo=timezone.utc)  # Friday
    assert business_due(start, 2).date().isoformat() == "2026-10-27"
    snapshot = sla_snapshot(now=datetime.now(timezone.utc))
    assert len(snapshot) >= 2
    events = process_sla(now=datetime.now(timezone.utc) + timedelta(days=14), notify=False)
    assert len(events) == 2
    assert all(e["event"] == "Escalated" for e in events)
    assert process_sla(now=datetime.now(timezone.utc) + timedelta(days=14), notify=False) == []
    assert int(load_df("SELECT COUNT(*) AS n FROM sla_events").iloc[0]["n"]) == 2


def test_sap_mapping_only_supported_operations():
    obj, body = map_payload({"Action": "CreateMasterRecord", "Object": "BusinessPartners",
                              "Name": "Acme Health", "Values": {"registration_number": "UEN-123"}})
    assert obj == "BusinessPartners" and body["CardName"] == "Acme Health"
    with pytest.raises(SAPIntegrationError):
        map_payload({"Action": "LinkExistingIdentity", "Object": "BusinessPartners"})
    with pytest.raises(SAPIntegrationError):
        send_live("RQ-0001", confirm=False)

def test_synthetic_message_benchmark_matches_all_four_purchasing_types():
    from classifier_evaluation import classifier_benchmark
    result=classifier_benchmark()
    assert result["count"]==20
    assert result["accuracy"]>=90
    assert set(result["details"]["Expected category"])=={
        "PO","Customer Request","Enquiry","MDM Setup"
    }
