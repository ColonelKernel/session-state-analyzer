# logic_real — a REAL Logic Pro session (complete evidence capture)

"Lincoln's Come in Fives" — a real Berklee coursework session (151 BPM, 5/4,
E minor). This capture demonstrates every evidence class the system has, on
real material:

- **OBSERVED** — four genuinely exported stems (Bass, Heavy Kit, Mellotron
  Strings & Flute, Rhythm Guitar; Jan 2025) + a stereo bounce rendered from
  the real project in Logic Pro 12.3 (offline, normalize off, Jul 2026) + the
  project's real MIDI export
- **INFERRED** — roles from real names (Bass/Strings/Guitar inferred;
  "Heavy Kit 1" honestly ABSTAINS — drummer-kit naming outside the
  vocabulary); MIDI's "Mellotron Strings & Flute" tracks link to their stem,
  its "Drummer" tracks correctly match nothing
- **ANNOTATED** — channel-strip notes transcribed from the open project's
  mixer (insert chains, sends, buses, faders/pans), incl. tracks that have
  NO exported stem (Drummer ×2, JUPITER-8 + Arpeggiator, B3 organ) and four
  Space Designer aux returns fed by Bus 1/2/6/8
- **HIDDEN** — the .logicx itself stays unparsed (automation/routing
  INACCESSIBLE on the project entity); several Pedalboard#NN.aif take files
  are missing from the media folder (skipped at load — recorded here)
- **OBSERVATION** — stem-sum reconciliation: fitted gain 0.026, correlation
  0.06, residual −0.02 dB ⇒ the stems barely explain the bounce. TRUE and
  detected: the mix contains four more instrument tracks, bus reverbs, and a
  mastering chain absent from the stems — and the stems predate the project
  version by five weeks. The honest negative result is the demonstration.

Produced by LogicSessionStateExplorer feat/full-pipeline-demo @ 5f5f05c:

    logic_session_evidence_explorer export-canonical-bundle <staging-dir> --out <dir>

Audio is NOT committed (course material, ~100 MB); this bundle is metadata +
descriptors only. Source material lives locally under
"Berklee Media Files Skim/Logic". The .logicx was opened read-only to bounce
and transcribe the mixer; the project bundle's mtime is unchanged (Mar 2025).
