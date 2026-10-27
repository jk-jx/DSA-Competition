"""Working-day SLAs, auditable reminder/escalation events and optional Teams delivery."""
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from database import conn, audit, utcnow
from intake_parser import setting

def business_due(start, days):
    date=start.date()
    remain=int(days)
    while remain:
        date+=timedelta(days=1)
        if date.weekday()<5:
            remain-=1
    return datetime.combine(date, datetime.min.time(), tzinfo=start.tzinfo)+timedelta(hours=17)

def _parse_time(value):
    dt=datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def sla_snapshot(now=None):
    now=now or datetime.now(timezone.utc)
    with conn() as c:
        rows=c.execute("""SELECT t.request_key,t.steward,t.state,r.created_at,
            r.country,r.entity,r.domain,m.sla_days,m.delegate
            FROM approval_tasks t JOIN mdm_requests r ON r.request_key=t.request_key
            LEFT JOIN approval_matrix m ON m.country=r.country AND m.entity=r.entity
             AND m.domain=r.domain AND m.steward=t.steward
            WHERE t.state='Pending' AND r.status='In Approval'
            ORDER BY r.created_at,t.id""").fetchall()
    out=[]
    for r in rows:
        days=int(r["sla_days"] or 2)
        due=business_due(_parse_time(r["created_at"]), days)
        secs=(due-now).total_seconds()
        status="Overdue" if secs<0 else ("Due soon" if secs<=24*3600 else "On track")
        out.append({"request_key":r["request_key"],"steward":r["steward"],
                    "delegate":r["delegate"] or "MDM Steward","sla_days":days,
                    "due_at":due.isoformat(),"hours_remaining":round(secs/3600,1),
                    "sla_status":status})
    return out

def _teams_message(payload):
    """Send only nonsensitive request ID/status, never customer fields or credentials."""
    webhook=setting("TEAMS_WEBHOOK_URL")
    if not webhook:
        return False
    if not webhook.startswith("https://"):
        raise ValueError("Teams webhook must be HTTPS.")
    response=requests.post(webhook,json={"text":
        f"MDM {payload['event']} · request {payload['request_key']} · "
        f"steward {payload['steward']} · delegate {payload['delegate']} · "
        f"due {payload['due_at']}"},timeout=10)
    response.raise_for_status()
    return True

def process_sla(now=None, notify=False):
    """Idempotently record first due-soon/overdue escalations, optionally notify Teams.

    Call from a scheduled job/production Power Automate or manually from the app.
    """
    outcomes=[]
    for task in sla_snapshot(now):
        if task["sla_status"]=="On track":
            continue
        event="Escalated" if task["sla_status"]=="Overdue" else "Reminder"
        with conn() as c:
            prior=c.execute("SELECT 1 FROM sla_events WHERE request_key=? AND steward=? AND event=?",
                            (task["request_key"],task["steward"],event)).fetchone()
            if prior:continue
            c.execute("INSERT INTO sla_events(request_key,steward,event,delegate,created_at,delivery) VALUES (?,?,?,?,?,?)",
                      (task["request_key"],task["steward"],event,task["delegate"],utcnow(),"Pending" if notify else "Demo"))
            audit(c,task["request_key"],event,"SLA Monitor",
                  f"{task['steward']} / {task['delegate']} / deadline {task['due_at']}")
            c.commit()
        outcome={**task,"event":event,"teams_sent":False}
        if notify:
            try:
                outcome["teams_sent"]=_teams_message(outcome)
                status="Sent" if outcome["teams_sent"] else "Not configured"
            except (requests.RequestException,ValueError) as exc:
                status=f"Delivery failed: {type(exc).__name__}"
            with conn() as c:
                c.execute("UPDATE sla_events SET delivery=? WHERE request_key=? AND steward=? AND event=?",
                          (status,task["request_key"],task["steward"],event))
                c.commit()
            outcome["delivery"]=status
        outcomes.append(outcome)
    return outcomes
