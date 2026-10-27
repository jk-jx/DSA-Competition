"""Assumption-driven visibility of potential demand delayed by pending setups."""
from database import load_df


def hidden_demand_model(days_per_request=18,typical_order_value=1800,
                        monthly_request_fraction=.35,days_in_month=30):
    """Scenario estimate, not observed delayed/lost orders or realized revenue.

    Pending setups × assumed fraction needing a purchase order × fraction of
    month delayed × illustrative order value. No transactional linkage exists.
    """
    pending=load_df("""SELECT request_key,domain,status FROM mdm_requests
        WHERE status IN ('Submitted','In Approval','Approved')""")
    count=len(pending)
    assumed_order_equivalents=count*float(monthly_request_fraction)*min(1.,max(0.,days_per_request/days_in_month))
    return {
        "pending_setups":count,
        "estimated_blocked_order_equivalents":assumed_order_equivalents,
        "illustrative_delayed_value_sgd":assumed_order_equivalents*typical_order_value,
        "days_per_request":days_per_request,
        "typical_order_value":typical_order_value,
        "fraction_with_order":monthly_request_fraction,
    }
