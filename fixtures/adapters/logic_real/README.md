# logic_real — a REAL Logic Pro session (evidence capture)

"Lincoln's Come in Fives" — a real Berklee coursework session. Evidence:
four genuinely exported stems (Bass, Heavy Kit, Mellotron Strings & Flute,
Rhythm Guitar; ~72 s each) plus the project's real MIDI export. The
`.logicx` project itself exists but is unparsed by design — its state is
reported as hidden, which is the point.

Produced by LogicSessionStateExplorer `feat/full-pipeline-demo` @ 34ecb11:

    logic_session_evidence_explorer export-canonical-bundle <staged-evidence-dir> --out <dir>

(run from the staging dir for portable relative paths; descriptors on).

Real-data behaviors this capture demonstrates (all by honest design):
- role inference: Bass/Strings/Guitar inferred; "Heavy Kit 1" ABSTAINS
  (real Logic drummer-kit naming outside the keyword vocabulary)
- MIDI linking: the real MIDI's internal "Mellotron Strings & Flute"
  tracks link to the matching stem; its "Drummer" tracks match nothing
  and are left unlinked rather than forced onto "Heavy Kit"
- no mixdown was exported, so there is no stem-sum reconciliation —
  absence of evidence, stated as such

The audio itself is NOT committed (course material; ~65 MB); this bundle
is metadata + descriptors only. Source audio lives outside the repo at
"Berklee Media Files Skim/Logic" on the local machine.
