"""Cross-page AppTest helpers for the st.navigation workbench.

The AppTest element tree cannot see ``st.navigation`` (no nav elements exist
in ``element_tree``), and ``AppTest.switch_page`` rejects callable pages. The
supported way to drive a non-default page is therefore the page-hash channel
the frontend itself uses: a page's script hash is ``calc_hash(url_path)``
(streamlit/navigation/page.py), and ``AppTest`` forwards ``self._page_hash``
into every run's ``RerunData``.

``goto`` pins that private-attribute workaround in exactly one place;
``test_goto_private_api_canary`` fails loudly if a Streamlit upgrade changes
either half of the contract.
"""

from __future__ import annotations

from streamlit.util import calc_hash


def goto(at, slug: str):
    """Point ``at``'s next ``run()`` at the page whose url_path is ``slug``.

    An empty slug returns to the current mode's default page (the app root).
    The hash persists on the AppTest instance, so subsequent runs — including
    mode switches — stay on this page while a page with that slug exists.
    """
    at._page_hash = calc_hash(slug) if slug else ""
    return at
