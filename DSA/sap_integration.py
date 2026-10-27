"""Opt-in SAP Business One Service Layer adapter (never active without explicit config).

This adapter deliberately separates simulated payloads from live record creation.
Use test tenants only until a business owner validates field mappings and controls.
"""
import json
import requests
from intake_parser import setting
from database import conn, utcnow

class SAPIntegrationError(RuntimeError):
    pass

def configured():
    return all(setting(k) for k in ("SAP_B1_SERVICE_LAYER_URL","SAP_B1_COMPANY_DB","SAP_B1_USERNAME","SAP_B1_PASSWORD"))

def map_payload(payload):
    """Minimal mapping for CREATE; identity links require an SAP-specific update plan."""
    if payload.get("Action") != "CreateMasterRecord":
        raise SAPIntegrationError("Identity link requires manual ERP reconciliation; a local alias map is not a live SAP merge.")
    kind=payload["Object"]
    values=payload.get("Values") or {}
    if kind == "BusinessPartners":
        return "BusinessPartners", {
            "CardName": payload["Name"],
            "CardType": "cCustomer",
            "FederalTaxID": values.get("registration_number") or "",
        }
    if kind == "Items":
        return "Items", {"ItemName":payload["Name"]}
    raise SAPIntegrationError(f"No verified Service Layer mapping for {kind}")

def send_live(request_key, confirm=False):
    """Explicitly dispatched by authorized operator; never called automatically at finalization.

    No automatic retry on network ambiguity: reconcile in SAP first to prevent duplicates.
    """
    if not confirm:
        raise SAPIntegrationError("Explicit confirmation required for live ERP writes.")
    if not configured():
        raise SAPIntegrationError("SAP test connection credentials are not configured.")
    with conn() as c:
        r=c.execute("SELECT s.payload_json,m.status FROM sap_records s JOIN mdm_requests m ON s.request_key=m.request_key WHERE s.request_key=?",(request_key,)).fetchone()
        if not r or r["status"]!="Created":
            raise SAPIntegrationError("Final MDM approval and mock payload required first.")
        prior=c.execute("SELECT status,external_id FROM outbound_integrations WHERE request_key=?",(request_key,)).fetchone()
        if prior:
            raise SAPIntegrationError(f"Already dispatched or pending reconciliation ({prior['status']}); do not retry blindly.")
        payload=json.loads(r["payload_json"])
        endpoint, body=map_payload(payload)
        c.execute("INSERT INTO outbound_integrations(request_key,provider,status,checked_at) VALUES(?,?,?,?)",
                  (request_key,"SAP B1","Pending reconciliation",utcnow()))
        c.commit()
    base=setting("SAP_B1_SERVICE_LAYER_URL").rstrip("/")
    if not base.startswith("https://"):
        raise SAPIntegrationError("Service Layer URL must use HTTPS.")
    session=requests.Session()
    try:
        response=session.post(base+"/Login",json={
            "CompanyDB":setting("SAP_B1_COMPANY_DB"),
            "UserName":setting("SAP_B1_USERNAME"),
            "Password":setting("SAP_B1_PASSWORD")
        },timeout=15)
        response.raise_for_status()
        response=session.post(base+"/"+endpoint,json=body,timeout=20)
        response.raise_for_status()
        returned=response.json()
        external_id=str(returned.get("CardCode") or returned.get("ItemCode") or "")
        with conn() as c:
            c.execute("UPDATE outbound_integrations SET status='Created',external_id=?,checked_at=? WHERE request_key=?",
                      (external_id,utcnow(),request_key))
            c.commit()
        return {"status":"Created","external_id":external_id,"object":endpoint}
    except (requests.RequestException,ValueError) as exc:
        # Retain pending reconciliation: a timeout could follow a successful SAP creation.
        raise SAPIntegrationError(f"Check SAP before retry; request kept pending reconciliation ({type(exc).__name__}).") from exc
    finally:
        try: session.post(base+"/Logout",timeout=5)
        except requests.RequestException: pass
        session.close()
