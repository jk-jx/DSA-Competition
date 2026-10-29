"""UI smoke test: exercise the actual Streamlit app rather than only domain logic."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import database
import generate_data

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def isolated_app(tmp_path, monkeypatch):
    db = tmp_path / "ui_smoke.sqlite"
    monkeypatch.setattr(database, "DB_PATH", db)
    monkeypatch.setattr(generate_data, "DB_PATH", db)
    at = AppTest.from_file(APP, default_timeout=100)
    at.run()
    assert not at.exception, [str(e.message) for e in at.exception]
    return at


def test_portal_views_render_without_uncaught_errors(isolated_app):
    app = isolated_app
    sections = [
        "Overview", "Master Data", "Regional Performance",
        "Insights & Forecasts", "Administration",
    ]
    for section in sections:
        app.session_state["portal_section"] = section
        app.run()
        assert not app.exception, (
            section, [str(e.message) for e in app.exception]
        )


def test_master_data_subviews_render_for_each_role(isolated_app):
    app = isolated_app
    app.session_state["portal_section"] = "Master Data"
    for view in ("Request tracker", "Create request", "Approval inbox"):
        app.session_state["workspace_view"] = view
        app.run()
        assert not app.exception, (
            view, [str(e.message) for e in app.exception]
        )
    for role in ("Requestor", "Finance Steward", "BU Steward", "MDM Steward"):
        app.session_state["portal_role"] = role
        app.run()
        assert not app.exception, (
            role, [str(e.message) for e in app.exception]
        )


def test_prepare_customer_review_click_prefills_form(isolated_app):
    app=isolated_app
    app.session_state["portal_section"]="Master Data"
    app.session_state["workspace_view"]="Quality exceptions"
    app.run()
    assert not app.exception
    app.button(key="prepare_case").click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    assert app.session_state["workspace_view"]=="Create request"
    assert app.session_state["req_domain"]=="Customer"
    assert app.session_state["prepared_alias"]
    assert app.session_state["prepared_target"]
    assert app.session_state["req_Customer_registration_number"]


def _item_form(app, **fields):
    app.session_state["portal_section"] = "Master Data"
    app.session_state["workspace_view"] = "Create request"
    app.session_state["req_domain"] = "Item"
    for key, value in {"name": "Lab Reagent Kit", "item_category": "Reagents", **fields}.items():
        app.session_state[f"req_Item_{key}"] = value
    app.session_state["req_ack"] = True
    app.run()
    assert not app.exception, [str(e.message) for e in app.exception]
    return next(b for b in app.button if b.label == "Submit for approval")


def test_item_form_blocks_submit_until_regulatory_class_chosen(isolated_app):
    submit = _item_form(isolated_app)
    assert submit.disabled
    assert any("Regulatory class" in w.value for w in isolated_app.warning)


def test_item_form_requires_licence_for_regulated_class(isolated_app):
    submit = _item_form(isolated_app, regulatory_class="Class B")
    assert submit.disabled
    assert any("licence number" in i.value for i in isolated_app.info)
    submit = _item_form(isolated_app, regulatory_class="Class B", licence_number="DE0012345")
    assert not submit.disabled


def test_email_extracted_class_text_maps_to_option(isolated_app):
    _item_form(isolated_app, regulatory_class="class b")
    assert isolated_app.session_state["req_Item_regulatory_class"] == "Class B"


def _inbox_as(app, role, key):
    app.session_state["portal_section"] = "Master Data"
    app.session_state["workspace_view"] = "Approval inbox"
    app.session_state["portal_role"] = role
    app.session_state["chosen_request"] = key
    app.run()
    assert not app.exception, [str(e.message) for e in app.exception]


def _detail_values(app):
    table = next(df.value for df in app.dataframe if "Field" in df.value.columns)
    return dict(zip(table.Field, table.Value))


def test_inbox_masks_bank_details_and_logs_finance_reveal(isolated_app):
    from workflow import submit_request
    from database import load_df
    key = submit_request("Customer", {
        "name": "Riverside Medical Centre", "country": "MY", "entity": "SPD",
        "registration_number": "MY-REG-777", "credit_terms": "Net 60", "bank_account": "5140012345678"})
    app = isolated_app

    _inbox_as(app, "BU Steward", key)
    assert _detail_values(app)["Bank account number (restricted)"] == "••••5678"
    assert not any(b.label.startswith("Reveal") for b in app.button)

    _inbox_as(app, "Finance Steward", key)
    assert _detail_values(app)["Bank account number (restricted)"] == "••••5678"
    next(b for b in app.button if b.label.startswith("Reveal")).click().run()
    assert not app.exception, [str(e.message) for e in app.exception]
    assert _detail_values(app)["Bank account number (restricted)"] == "5140012345678"
    views = load_df("SELECT actor FROM audit_log WHERE request_key=? AND event='Sensitive fields viewed'", (key,))
    assert list(views.actor) == ["Wei Jie Finance"]


def test_erp_export_masks_bank_details_for_non_finance_roles(isolated_app):
    from workflow import submit_request, decide, finalize
    key = submit_request("Customer", {
        "name": "Riverside Medical Centre", "country": "MY", "entity": "SPD",
        "registration_number": "MY-REG-777", "bank_account": "5140012345678"})
    decide(key, "Finance Steward", "Wei Jie Finance", "Approved")
    decide(key, "BU Steward", "Daniel BU Head", "Approved")
    finalize(key, "Priya MDM")
    app = isolated_app

    _inbox_as(app, "BU Steward", key)
    assert app.get("download_button")
    assert "masked in this export" in " ".join(c.value for c in app.caption)

    _inbox_as(app, "MDM Steward", key)
    assert "masked in this export" not in " ".join(c.value for c in app.caption)
