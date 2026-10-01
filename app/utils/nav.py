"""
Page registry so any page can jump to another with context.

main.py registers the st.Page objects on every run; pages call goto() with
the registry key and optional session-state values to carry across.
"""

from __future__ import annotations

import streamlit as st

_PAGES: dict = {}


def register(key: str, page) -> None:
    _PAGES[key] = page


def page(key: str):
    return _PAGES.get(key)


def goto(key: str, **state) -> None:
    for k, v in state.items():
        st.session_state[k] = v
    target = _PAGES.get(key)
    if target is not None:
        st.switch_page(target)


def link(key: str, label: str, icon: str | None = None, **kwargs) -> None:
    target = _PAGES.get(key)
    if target is not None:
        st.page_link(target, label=label, icon=icon, **kwargs)
