# Deploying the workbench to Streamlit Community Cloud

The repo is deploy-ready: `requirements.txt` (editable installs of the schema
package and the app with `ui`/`audio`/`midi`/`score` extras), `packages.txt`
(`libsndfile1` for audio loading), and `.streamlit/config.toml` are all in
place, and the four example bundles under `fixtures/` auto-load on first visit.
Verified locally: the app boots headless and serves HTTP 200.

## One-time deploy (about 2 minutes, needs a browser + GitHub login)

1. Go to <https://share.streamlit.io> and sign in with the **ColonelKernel**
   GitHub account. Authorize Streamlit if prompted.
2. Click **Create app → Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `ColonelKernel/session-state-analyzer`
   - **Branch:** `main`
   - **Main file path:** `src/session_explorer/workbench/app.py`
4. (Optional) Under **Advanced settings**, set Python version to **3.11**.
5. Click **Deploy**. First build takes a few minutes (it compiles the editable
   installs and installs `libsndfile1`). When it finishes you'll get a public
   URL like `https://<something>.streamlit.app`.

## After it's live

- Put the URL in the CV / proposal (replace the GitHub link, or add it next to
  it) — a live demo beats a repo link for a first-time reviewer.
- Add a badge to the top of `README.md`:
  `[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://YOUR-APP.streamlit.app)`

## If the build fails

- **Import error on `canonical_snapshot`** — confirm the `-e packages/canonical_snapshot`
  line is first in `requirements.txt`.
- **`libsndfile` / audio load error** — confirm `packages.txt` contains
  `libsndfile1`; add `ffmpeg` if any bundle ships non-WAV renders.
- **Editable install rejected** — as a fallback, replace the two `-e` lines with
  non-editable installs (`./packages/canonical_snapshot` and `.[ui,audio,midi,score]`)
  and set `PYTHONPATH=src` under Advanced settings so the fixture paths still
  resolve to this checkout.

## Alternative host

Hugging Face Spaces (Streamlit SDK) also works and likewise needs a browser
login; point it at the same entry file and `requirements.txt`.
