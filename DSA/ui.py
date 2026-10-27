"""Consistent product UI for the company operations portal."""
from html import escape
import streamlit as st

STEPS = [
    "01 · Submit a request", "02 · Review & approve",
    "03 · See regional impact", "04 · Forecast & take action",
]


def style():
    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');
:root{
  --ink:#14253b;--ink-2:#2b415c;--muted:#75849b;--line:#e3e9f0;
  --bg:#f6f8fb;--accent:#3369c7;--navy:#101f35;--teal:#138b83;
}
html,body,[class*="css"],.stApp{font-family:"DM Sans",system-ui,-apple-system,sans-serif}
.stApp{background:var(--bg);color:var(--ink)}
.block-container{max-width:1360px;padding:2.05rem 2.45rem 6.4rem}
h1,h2,h3,h4{font-family:"Manrope","DM Sans",sans-serif;color:var(--ink);letter-spacing:-.04em;font-weight:800!important}
h2{font-size:1.59rem!important;line-height:1.25!important}
h3{font-size:1.09rem!important;line-height:1.4!important}
p{line-height:1.6}
[data-testid="stSidebar"]{
 background:linear-gradient(180deg,#12263d 0%,#0f2138 54%,#0b192b 100%)!important;
 border-right:1px solid #243b55!important;
 min-width:245px;
}
[data-testid="stSidebar"]>div:first-child{padding-top:1.4rem}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,[data-testid="stSidebar"] h3{
 color:#dbe6f1!important;
}
[data-testid="stSidebar"] hr{border-color:#294058!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p{
 color:#9ab0c8!important;font-size:.75rem!important
}
[data-testid="stSidebar"] [data-testid="stRadio"] > label p{
 font-size:.65rem!important;letter-spacing:.14em!important;font-weight:800!important;
 color:#9ab0c8!important
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"]{
 gap:3px!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label{
 padding:10px 12px!important;border-radius:9px!important;margin:2px 0;
 transition:background .18s ease;min-height:43px;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover{
 background:#223d58!important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked){
 background:#254868!important;box-shadow:inset 3px 0 0 #71d4c8!important;
}
[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"]>div{
 background:#1d3854!important;border-color:#37526d!important;color:#edf5ff!important;
}
[data-testid="stSidebar"] .stButton button {
 background:#1b3854!important;color:#e7f1fc!important;border:1px solid #385471!important;
}
[data-testid="stSidebar"] .stButton button:hover{
 background:#2a4a69!important;border-color:#70a8d1!important
}
.portal-brand{display:flex;align-items:center;gap:12px;padding:5px 0 1px}
.portal-logo{width:39px;height:39px;background:linear-gradient(140deg,#63d6cb,#6c96dc);
 color:#0b2742;border-radius:12px;display:grid;place-items:center;
 font:800 23px "Manrope",sans-serif;box-shadow:0 7px 20px #060e1b44}
.portal-brand-name{font:800 .86rem "Manrope",sans-serif;color:white;letter-spacing:.055em}
.portal-brand-sub{font-size:.69rem;color:#9fb6cf;margin-top:2px}
.portal-side-rule{height:1px;background:#294058;margin:17px 0}
.portal-eyebrow{letter-spacing:.13em;font-size:.67rem;font-weight:800;color:#8293a9;margin-bottom:7px}
.portal-header-row{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:3px 0 16px}
.portal-header-row h1{margin:0!important;font-size:1.84rem!important}
.portal-header-row p{margin:6px 0 0;color:#728299;font-size:.92rem}
.portal-status{font-size:.64rem;font-weight:800;color:#116e61;white-space:nowrap;
 display:inline-flex;align-items:center;gap:7px;border-radius:99px;
 border:1px solid #d5e9e3;background:#eaf7f2;padding:9px 12px;letter-spacing:.055em}
.status-dot{display:inline-block;width:7px;height:7px;background:#18a488;border-radius:50%;box-shadow:0 0 0 3px #b5e8db}
.portal-section-label{display:flex;align-items:center;justify-content:space-between;gap:10px;
 margin:29px 0 12px}
.portal-section-label h3{margin:0!important;font-size:1.04rem!important}
.portal-section-label span{font-size:.78rem;color:#8a98aa}
.portal-banner{
 border-radius:18px;padding:30px 33px;margin:28px 0 30px;
 color:#fff;background:
 radial-gradient(ellipse at 93% 18%,#2d7590 0%,transparent 34%),
 linear-gradient(115deg,#172f4e 3%,#1a4865 100%);
 box-shadow:0 13px 32px rgba(14,37,64,.11);
}
.portal-banner .tag{font-size:.68rem;letter-spacing:.16em;font-weight:800;color:#87d8d0;margin:0 0 10px}
.portal-banner h2{font-size:1.48rem!important;color:#fff!important;max-width:780px;margin:0 0 7px!important}
.portal-banner p{color:#d3e5f0;font-size:.89rem;margin:0;max-width:650px}
.kpi-card{background:#fff;border:1px solid var(--line);border-radius:13px;
 padding:19px 20px 16px;box-shadow:0 4px 18px rgba(27,51,82,.028);min-height:122px}
.kpi-icon{height:31px;width:31px;border-radius:9px;background:#e7effd;color:#305ea9;
 display:grid;place-items:center;font-weight:800;font-size:.9rem;margin-bottom:12px}
.kpi-icon.teal{background:#e1f4f0;color:#138b83}
.kpi-icon.amber{background:#fff1d9;color:#bb7a22}
.kpi-icon.slate{background:#eaf0f5;color:#576b82}
.kpi-label{font-size:.78rem;color:#718299;font-weight:700;line-height:1.3}
.kpi-value{font:800 1.75rem "Manrope",sans-serif;letter-spacing:-.055em;
 color:#172d46;line-height:1.35;margin:4px 0 0}
.kpi-foot{font-size:.72rem;color:#9ba8b6;margin-top:6px}
.panel-lead{font:800 1rem "Manrope",sans-serif;color:#1b2f49;margin:0 0 4px}
.panel-sub{font-size:.86rem;color:#7b8ca2;line-height:1.5;margin:0 0 17px}
.card-icon{display:grid;place-items:center;width:37px;height:37px;border-radius:11px;
 background:#e8effe;color:#3669bb;font-weight:800;font-size:1.12rem;margin-bottom:12px}
.card-icon.teal{background:#e4f5f0;color:#168a7e}
.card-icon.violet{background:#eeeafa;color:#7062b1}
.card-description{color:#77879a;font-size:.82rem;line-height:1.55;min-height:43px;margin:5px 0 14px}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;
 padding:15px 16px;box-shadow:0 3px 15px rgba(20,46,74,.026)}
[data-testid="stMetricLabel"] p{color:#75869a!important;font-size:.82rem!important;font-weight:700}
[data-testid="stMetricValue"]{font:800 1.65rem "Manrope",sans-serif!important;letter-spacing:-.06em!important;color:#172b44!important}
[data-testid="stVerticalBlockBorderWrapper"]:has(>[data-testid="stVerticalBlock"]) {
 border-color:#e3e9f0!important;background:#fff!important;
 border-radius:13px!important;box-shadow:0 4px 16px rgba(26,49,77,.027)
}
div[data-testid="stVerticalBlockBorderWrapper"]>div[data-testid="stVerticalBlock"]{
 border-radius:13px
}
[data-testid="stDataFrame"]{border-radius:9px;overflow:hidden}
[data-testid="stExpander"]{border:1px solid #e4eaf1!important;border-radius:10px!important;background:#fff}
[data-testid="stAlert"]{border-radius:10px!important}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{
 border-radius:9px!important;background:#fff!important;border-color:#d9e1eb!important
}
[data-baseweb="select"]>div{border-radius:9px!important}
button[data-testid="stBaseButton-primary"],.stButton button[kind="primary"]{
 border-radius:9px!important;border:1px solid #285fa9!important;
 background:#285fa9!important;color:#fff!important;font-weight:800!important;
 box-shadow:0 5px 12px #285fa91c!important
}
button[data-testid="stBaseButton-primary"]:hover,.stButton button[kind="primary"]:hover{
 background:#1e4e91!important;border-color:#1e4e91!important
}
.stButton button,.stDownloadButton button{
 border-radius:9px!important;font-weight:700!important;border-color:#dae3ed
}
.stButton button:hover,.stDownloadButton button:hover{border-color:#9db7d8!important;color:#245a9f}
hr{border-color:#e3e9f0!important}
div[data-testid="stRadio"]:not([data-testid="stSidebar"] *) [role="radiogroup"]{
 padding:4px;background:#ebf0f6;border-radius:10px;gap:3px
}
.ui-hero{background:linear-gradient(110deg,#1a3958,#23667c);border:1px solid #245a78;
 color:#fff;padding:25px 28px;border-radius:15px;margin:4px 0 22px}
.ui-hero .kicker{color:#a2e0da;font-weight:800;font-size:.7rem;letter-spacing:.13em}
.ui-hero h2{color:white!important;margin:5px 0 7px!important}
.ui-hero p{color:#d8e8ef;margin:0}
.ui-pill{display:inline-block;background:#eaf2ff;color:#2256a8;padding:6px 11px;border-radius:99px;
 font-size:.77rem;font-weight:800}
.ui-pill.green{background:#e3f7ee;color:#0b7057}
.ui-pill.amber{background:#fff3d9;color:#8e5a08}
.ui-pill.gray{background:#eaf0f5;color:#43566c}
.ui-panel{background:#fff;border:1px solid var(--line);border-radius:13px;padding:17px 19px;
 margin:9px 0 15px}
.ui-panel-title{font-weight:800;font-size:1rem;margin-bottom:5px}
.ui-panel p{font-size:.86rem;color:#63758a;margin:0}
.ui-timeline{display:flex;gap:8px;margin:2px 0 18px;flex-wrap:wrap}
.ui-step{background:white;border:1px solid #e1e8f2;border-radius:999px;padding:8px 14px;
 font-size:.78rem;font-weight:800;color:#667991}
.ui-step.current{background:#dfeaff;border-color:#9fbbec;color:#2154ad}
.ui-step.done{background:#e0f4ed;border-color:#bbdfd4;color:#0b7057}
.account-badge{display:inline-flex;align-items:center;gap:7px;background:#e9f6f1;
 border:1px solid #c9e8da;border-radius:99px;padding:7px 11px;color:#1b765f;
 font-size:.73rem;font-weight:800}
.account-badge.muted{background:#f0f3f7;color:#62748a;border-color:#e2e8ef}
.guide-underlay{color:#75869b;font-size:.75rem}
@media(max-width:850px){
 .block-container{padding:1.3rem 1.1rem 5.8rem}
 .portal-header-row{flex-wrap:wrap}
 .portal-banner{padding:24px 20px;margin:22px 0 26px}
 .portal-banner h2{font-size:1.25rem!important}
 .kpi-card{padding:15px}
}
</style>""", unsafe_allow_html=True)


def metric_tile(label, value, icon="◈", tone="blue", foot=""):
    tone = tone if tone in ("teal", "amber", "slate") else ""
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-icon {tone}">{escape(icon)}</div>'
        f'<div class="kpi-label">{escape(str(label))}</div>'
        f'<div class="kpi-value">{escape(str(value))}</div>'
        f'<div class="kpi-foot">{escape(str(foot))}</div></div>',
        unsafe_allow_html=True,
    )


def section_label(title, note=""):
    st.markdown(
        f'<div class="portal-section-label"><h3>{escape(title)}</h3>'
        f'<span>{escape(note)}</span></div>',
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
    st.markdown(
        f'<span class="ui-pill {tone}">{escape(str(text))}</span>', unsafe_allow_html=True,
    )


def workflow_progress(active):
    captions = ["Intake", "Approvals", "Regional impact", "Business actions"]
    parts = [
        f'<div class="ui-step {"current" if i == active else "done" if i < active else ""}">'
        f'{i+1:02d} · {escape(label)}</div>'
        for i, label in enumerate(captions)
    ]
    st.markdown('<div class="ui-timeline">' + "".join(parts) + '</div>', unsafe_allow_html=True)


def _navigate(index):
    st.session_state["nav_step"] = STEPS[index]


def next_step(step, label="Continue"):
    st.button(label, type="primary", key=f"go_step_{step}",
              on_click=_navigate, args=(step,), use_container_width=False)


def demo_note():
    st.caption("Synthetic case data · Simulated roles · No production ERP records")
