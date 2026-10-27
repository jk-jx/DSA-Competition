"""SQLite-backed demonstration store. Never use this demo's role switcher as production authentication."""
import sqlite3, json
from datetime import datetime, timezone
from config import DB_PATH

def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=10000')
    return c

def init_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS customers(
        customer_id TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL, entity TEXT NOT NULL,
        registration_number TEXT, canonical_truth_id TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS transactions(
        transaction_id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id),
        country TEXT NOT NULL, entity TEXT NOT NULL, product TEXT NOT NULL,
        period TEXT NOT NULL, qty INTEGER NOT NULL, record_type TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_tx ON transactions(period,country,product,record_type);
    CREATE TABLE IF NOT EXISTS identity_map(
        alias_id TEXT PRIMARY KEY REFERENCES customers(customer_id),
        canonical_id TEXT NOT NULL REFERENCES customers(customer_id),
        approved_by TEXT NOT NULL, request_id TEXT NOT NULL, approved_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS mdm_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_key TEXT UNIQUE NOT NULL,
        domain TEXT NOT NULL, record_name TEXT NOT NULL, country TEXT NOT NULL,
        entity TEXT NOT NULL, requested_by TEXT NOT NULL, payload TEXT NOT NULL,
        status TEXT NOT NULL, match_source_id TEXT, match_target_id TEXT,
        created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS approval_tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_key TEXT NOT NULL REFERENCES mdm_requests(request_key),
        steward TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'Pending',
        decision_by TEXT, decision_at TEXT,
        UNIQUE(request_key,steward));
    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_key TEXT NOT NULL, event TEXT NOT NULL, actor TEXT NOT NULL,
        details TEXT NOT NULL, happened_at TEXT NOT NULL);
    CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(FAIL,'audit log is append-only'); END;
    CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(FAIL,'audit log is append-only'); END;
    CREATE TABLE IF NOT EXISTS approval_matrix(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity TEXT NOT NULL, domain TEXT NOT NULL, country TEXT NOT NULL,
        steward TEXT NOT NULL, delegate TEXT, sla_days INTEGER NOT NULL DEFAULT 2,
        UNIQUE(entity,domain,country,steward));
    CREATE TABLE IF NOT EXISTS sla_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_key TEXT NOT NULL,
        steward TEXT NOT NULL,
        event TEXT NOT NULL,
        delegate TEXT,
        created_at TEXT NOT NULL,
        delivery TEXT NOT NULL,
        UNIQUE(request_key,steward,event));
    CREATE TABLE IF NOT EXISTS outbound_integrations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_key TEXT NOT NULL UNIQUE,
        provider TEXT NOT NULL,
        external_id TEXT,
        status TEXT NOT NULL,
        checked_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sap_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT, request_key TEXT NOT NULL UNIQUE,
        sap_object TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL);
    ''')
    c.commit()

def audit(c, key, event, actor, details=''):
    c.execute('INSERT INTO audit_log(request_key,event,actor,details,happened_at) VALUES(?,?,?,?,?)',
              (key,event,actor,details,utcnow()))

def load_df(query, params=()):
    import pandas as pd
    with conn() as c:
        return pd.read_sql_query(query, c, params=params)

def is_initialized():
    with conn() as c:
        init_schema(c)
        return c.execute('SELECT COUNT(*) FROM customers').fetchone()[0] > 0
