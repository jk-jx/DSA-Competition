"""Small reproducible labelled synthetic benchmark for rules-first message typing.

This is a smoke-test/illustrative test set, not independently collected
production email validation. Accuracy should never be presented as expected
real-world precision.
"""
import pandas as pd
from intake_parser import classify_message

EXAMPLES=[
    ("Please create a customer record for North Health", "MDM Setup"),
    ("Set up a new item for laboratory testing", "MDM Setup"),
    ("Please register vendor Acme Supply", "MDM Setup"),
    ("New customer onboarding request for a hospital", "MDM Setup"),
    ("Please update customer master data", "MDM Setup"),
    ("Confirmed purchase order PO 124566 attached", "PO"),
    ("Purchase order 99881 for product A", "PO"),
    ("PO #987654 for diagnostic kits", "PO"),
    ("Attached PO 123456 for September supply", "PO"),
    ("Our purchase order PO 70001 is confirmed", "PO"),
    ("Could you send a price quotation?", "Enquiry"),
    ("Enquiry about laboratory materials", "Enquiry"),
    ("Please check item availability", "Enquiry"),
    ("Request a quote for Product B", "Enquiry"),
    ("I have a general product inquiry", "Enquiry"),
    ("We would like to purchase 25 kits", "Customer Request"),
    ("Customer purchase request for 10 units", "Customer Request"),
    ("We are planning to order product A", "Customer Request"),
    ("Request to purchase 50 units", "Customer Request"),
    ("We would like to buy diagnostic supplies", "Customer Request"),
]


def classifier_benchmark():
    frame=pd.DataFrame(EXAMPLES,columns=["Message","Expected category"])
    frame["Predicted category"]=frame.Message.map(classify_message)
    frame["Correct"]=frame["Expected category"]==frame["Predicted category"]
    return {
        "accuracy":round(100*float(frame.Correct.mean()),1),
        "count":len(frame),
        "correct":int(frame.Correct.sum()),
        "details":frame,
    }
