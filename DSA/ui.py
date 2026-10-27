"""Minimal presentation helpers shared by the four pages."""
import streamlit as st

STEPS = [
    "01 · Submit a request",
    "02 · Review & approve",
    "03 · See regional impact",
    "04 · Forecast & take action",
]

def next_step(step, label="Continue to next step"):
    if st.button(label, type="primary", key=f"go_step_{step}"):
        st.session_state["nav_step"] = STEPS[step]
        st.rerun()

def demo_note():
    st.caption("Illustrative synthetic data • This is a workflow demonstration, not a live enterprise system.")
