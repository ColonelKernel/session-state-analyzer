"""The Streamlit workbench: the analyzer's read-only research UI (P3).

Entry point: ``streamlit run src/session_explorer/workbench/app.py``.

Exactly two pages ship in P3 — the canonical graph and the entity inspector —
per the hard fence in the pivot plan. The workbench presents; it never
acquires: everything on screen arrives through ``loaders.load_bundle``.
"""
