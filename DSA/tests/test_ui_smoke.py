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
