# Application bundle — status and remaining steps

**Deadline: July 16, 2026** · Apply to: **mtg-info@upf.edu**

## What's ready (in this folder, all gitignored)

| File | Status |
|---|---|
| `thesis_proposal.md` / `.pdf` | Ready to send |
| `motivation_letter.md` / `.pdf` | **3 `[TODO]` biography blocks to fill**, then re-render PDF |
| `cv_notes.md` | Tailoring guide — CV itself must come from you |
| `email_draft.md` | Ready; insert video link, attach PDFs |
| `../demo/walkthrough_base.mp4` | 90s silent screen capture, paced to `docs/demo_script.md` |
| `../demo/walkthrough_narrated_DRAFT.mp4` | Same video with **synthetic TTS narration** — a timing draft. Strongly consider re-recording narration in your own voice for the actual submission. |

## Remaining steps (in order)

1. Fill the three `[TODO]` blocks in `motivation_letter.md`, then re-render:
   `python3 <scratchpad>/md2pdf.py docs/application/motivation_letter.md`
   (or any Markdown→PDF tool).
2. Produce your CV per `cv_notes.md`.
3. Publish the repository (from your terminal — this is deliberately left to you):
   `gh repo create AbletonSessionStateExplorer --public --source . --push && git push origin --tags`
4. Record narration over `walkthrough_base.mp4` (QuickTime screen-record or
   any editor; the TTS draft shows the timing), upload it unlisted, and put
   the link in `email_draft.md`.
5. Run the checklist at the bottom of `email_draft.md` and send.
