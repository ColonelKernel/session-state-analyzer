"""The workbench's two P3 pages, dispatched as tabs from ``app.py``.

These are plain modules with ``render(...)`` functions — not Streamlit
multipage scripts. ``app.py`` stays the single entry point (the repo's
``.streamlit/config.toml`` disables sidebar auto-navigation so this
directory's name does not conscript it into st.pages).
"""
