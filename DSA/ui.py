"""Minimal presentation helpers shared by the four pages."""
import streamlit as st

STEPS = [
    "01 · Submit a request",
    "02 · Review & approve",
    "03 · See regional impact",
    "04 · Forecast & take action",
]

def _navigate(index):
    st.session_state["nav_step"] = STEPS[index]

def next_step(step, label="Continue to next step"):
    # Callback runs before widgets are instantiated on the next rerun.
    # Directly writing radio state after construction raises a Streamlit exception.
    st.button(label, type="primary", key=f"go_step_{step}",
              on_click=_navigate, args=(step,))

def demo_note():
    st.caption("Illustrative synthetic data • This is a workflow demonstration, not a live enterprise system.")
