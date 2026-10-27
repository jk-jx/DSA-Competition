"""Shared interface components for a polished, accessible Streamlit case study."""
from html import escape

import streamlit as st

STEPS = [
    "01 · Submit a request",
    "02 · Review & approve",
    "03 · See regional impact",
    "04 · Forecast & take action",
]


def style():
    st.markdown(
        """<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
:root {--navy:#132941;--muted:#64748b;--blue:#245ac5;--line:#e4ebf3;--bg:#f6f8fc;--green:#087e67}
html, body, [class*="css"], .stApp {font-family:"DM Sans",system-ui,sans-serif}
.stApp {background:var(--bg); color:var(--navy)}
.block-container {max-width:1240px; padding:1.55rem 2.2rem 4rem}
[data-testid="stSidebar"] {background:#f8faff;border-right:1px solid #e4ebf3}
[data-testid="stSidebar"] .block-container{padding-top:1rem}
[data-testid="stSidebar"] div[role="radiogroup"] label{
  border-radius:10px; padding:10px 9px; margin:3px 0; transition:background .15s ease
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {background:#eaf0fb}
h1,h2,h3 {color:var(--navy);letter-spacing:-.033em}
h1 {font-weight:800!important;font-size:2rem!important;line-height:1.18!important}
h3{font-size:1.13rem!important}
.stButton button[kind="primary"], button[data-testid="stBaseButton-primary"] {
  background:#245ac5!important;border:1px solid #245ac5!important;
  color:white!important;border-radius:10px!important;font-weight:700!important
}
.stButton button, .stDownloadButton button {
  border-radius:10px!important;font-weight:650!important
}
div[data-testid="stVerticalBlockBorderWrapper"]>div[data-testid="stVerticalBlock"] {
  border-radius:12px;
}
[data-testid="stMetric"] {
  background:#fff; padding:16px 17px; border:1px solid var(--line);
  border-radius:13px; box-shadow:0 3px 13px rgba(17,39,66,.035)
}
[data-testid="stMetricLabel"] {color:#5a6f87}
[data-testid="stMetricValue"] {font-size:1.9rem}
[data-testid="stAlert"] {border-radius:11px}
[data-testid="stDataFrame"] {border-radius:10px;overflow:hidden}
[data-testid="stExpander"]{border-radius:10px;background:#fff;border:1px solid var(--line)}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
  border-radius:10px;
}
hr {border-color:#e9eff5!important}
.ui-hero {background:linear-gradient(110deg,#102e53 0%,#194a79 63%,#1c638b 100%);
border:1px solid #1b5085;color:#fff;padding:26px 30px;border-radius:17px;
box-shadow:0 13px 30px rgba(18,45,84,.12); margin:8px 0 24px}
.ui-hero .kicker {font-size:.74rem;font-weight:800;letter-spacing:.13em;color:#a8d6fb;margin-bottom:8px}
.ui-hero h2 {font-size:1.64rem;line-height:1.17;color:white!important;margin:2px 0 9px!important;font-weight:800}
.ui-hero p {color:#d6e7f8;margin:0;font-size:.95rem;max-width:750px}
.ui-pill {display:inline-block;background:#eaf2ff;color:#2256a8;padding:6px 11px;
border-radius:99px;font-size:.77rem;font-weight:800;white-space:nowrap}
.ui-pill.green{background:#e3f7ee;color:#0b7057}
.ui-pill.amber{background:#fff3d9;color:#8e5a08}
.ui-pill.gray{background:#eaf0f5;color:#43566c}
.ui-panel {background:white;border:1px solid var(--line);border-radius:13px;
padding:17px 19px;margin:9px 0 15px;box-shadow:0 3px 13px rgba(17,39,66,.03)}
.ui-panel-title {font-weight:800;font-size:1.04rem;margin-bottom:5px}
.ui-panel p {font-size:.89rem;color:#63758a;margin:0}
.ui-timeline {display:flex;gap:8px;margin:2px 0 18px;flex-wrap:wrap}
.ui-step {background:white;border:1px solid #e1e8f2;border-radius:999px;
padding:8px 14px;font-size:.78rem;font-weight:800;color:#667991}
.ui-step.current {background:#dfeaff;border-color:#9fbbec;color:#2154ad}
.ui-step.done {background:#e0f4ed;border-color:#bbdfd4;color:#0b7057}
.ui-muted {font-size:.85rem;color:#64748b}
.ui-brand {font-size:.8rem;font-weight:800;letter-spacing:.11em;color:#59718e}
@media(max-width:750px) {.block-container{padding:1.1rem .8rem 3rem}
 .ui-hero{padding:21px 17px}.ui-hero h2{font-size:1.3rem}}
</style>""",
        unsafe_allow_html=True,
    )


def hero(kicker, title, subtitle):
    st.markdown(
        f'<div class="ui-hero"><div class="kicker">{escape(kicker)}</div>'
        f'<h2>{escape(title)}</h2><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def panel(title, body):
    st.markdown(
        f'<div class="ui-panel"><div class="ui-panel-title">{escape(title)}</div>'
        f'<p>{escape(body)}</p></div>',
        unsafe_allow_html=True,
    )


def pill(text, tone="blue"):
    tone = tone if tone in ("green", "amber", "gray") else ""
    st.markdown(f'<span class="ui-pill {tone}">{escape(str(text))}</span>',
                unsafe_allow_html=True)


def workflow_progress(active):
    captions = ["Intake", "Approvals", "Regional impact", "Business actions"]
    parts = [
        f'<div class="ui-step {"current" if i == active else "done" if i < active else ""}">'
        f'{i+1:02d} · {escape(label)}</div>'
        for i, label in enumerate(captions)
    ]
    st.markdown('<div class="ui-timeline">' + "".join(parts) + "</div>",
                unsafe_allow_html=True)


def _navigate(index):
    st.session_state["nav_step"] = STEPS[index]


def next_step(step, label="Continue"):
    st.button(label, type="primary", key=f"go_step_{step}",
              on_click=_navigate, args=(step,), use_container_width=False)


def demo_note():
    st.caption("Synthetic competition scenario · Simulated roles · No live production records")
