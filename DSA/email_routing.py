"""Deterministic email intake routing demonstration for the MDM shared mailbox.

No Outlook or Teams access occurs here. Returns the proposed response and a
nonsensitive approval card; production Power Automate owns delivery, grace
period configuration and MDM override authorization.
"""
from intake_parser import classify_message, rule_extract

def route_inbound_email(message,grace_period=True,mdm_override=False):
    parsed=rule_extract(message)
    record_type=parsed["record_type"]
    domain=parsed["domain"]
    eligible=record_type=="MDM Setup"
    if eligible:
        subject="Master data setup — structured submission required"
        if mdm_override:
            reply="Urgent setup accepted for MDM manual triage. An authorized MDM analyst will validate required fields and approvals."
            route="MDM manual override"
        elif grace_period:
            reply="Please complete the structured master-data form. During the launch grace period, your request will also be manually triaged."
            route="Grace-period manual triage + prefilled form"
        else:
            reply="Please submit this setup using the structured portal form. Email alone does not initiate SAP master-data creation."
            route="Form required"
    else:
        subject="Purchasing message classified"
        reply={
            "PO":"Confirmed purchase order identified; route to the purchasing workflow, not master-data setup.",
            "Customer Request":"Customer purchasing request identified; awaiting confirmed order before inclusion in PO forecasts.",
            "Enquiry":"General enquiry received; no purchase order or master-data record has been created.",
        }[record_type]
        route="Purchasing / commercial inbox"
    card={
        "title":"MDM approval notification",
        "record_type":record_type,
        "domain":domain,
        "approval_action":"Approver signs in to the governed approval inbox; no auto-approval",
        "contains_sensitive_fields":False,
    }
    return {"record_type":record_type,"domain":domain,"route":route,
            "reply_subject":subject,"reply_body":reply,"extracted_fields":parsed["fields"],
            "approval_notification_preview":card,"sent":False}
