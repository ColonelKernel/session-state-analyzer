# Preliminary thesis proposal

**Interpretable DAW-State Graphs for Prediction and Explanation in AI-Assisted Music Production**

Preliminary thesis proposal for the PhD position at the Music Technology Group
(Universitat Pompeu Fabra) with Steinberg Media Technologies GmbH as industrial
partner.

Candidate: Zachary Scheffler · July 2026

---

## 1. Motivation and problem statement

Digital audio workstations are the central instrument of contemporary music
production, yet the knowledge they contain is largely invisible to current AI
music systems. A DAW session encodes a producer's craft as *state*: track
organization, routing topology, insert and send effect chains, parameter
settings, and the arrangement of clips and events. Most assistive technologies
for music production operate downstream of this state — on rendered audio — or
upstream of it, on isolated plugin parameters. The session itself, where
production decisions actually live, remains an unmodeled black box.

This thesis addresses the topic of the call directly: **representations of the
states of a DAW, such as audio effects or mixing details, and how they
influence the final acoustic outcome**, with the goal of providing and
evaluating **methods that allow prediction of such DAW states** to support the
creativity of musicians and producers.

The central claim is that DAW state should be modeled as a **typed, partially
observable graph** — a representation in which tracks, effect chains, sends,
returns, parameters, and their relations are explicit, nameable objects. Such
a representation supports three things that end-to-end audio models do not:
(i) *prediction at the level producers act on* (which device, which routing,
which setting — not which waveform), (ii) *explanation by construction* (a
predicted state change can cite the session structure that motivated it), and
(iii) *honest handling of partial observability* (proprietary formats and
plugin-internal state bound what any system can see, and the representation
should say so).

## 2. Research questions

**RQ1 — Representation.** What graph-structured representations of DAW session
state are expressive enough to capture production-relevant structure (chains,
routing, arrangement) while remaining DAW-agnostic — instantiable from
Cubase/VST3 session structures as well as other DAW paradigms — and honest
about unobserved state?

**RQ2 — Prediction.** Given a partial session state and optionally audio
descriptors of its material, how well can models predict withheld or future
DAW states: the composition of a device chain, likely parameter regions, the
next production action in an edit sequence? Which model classes (interpretable
probabilistic baselines, graph neural networks, sequence models over edit
histories) offer the best accuracy/interpretability trade-off?

**RQ3 — Outcome linkage.** How do DAW-state changes map to measurable acoustic
outcomes? Can models predict descriptor-space consequences of state edits
(e.g., the spectral and dynamic effect of an insert chain), and conversely,
infer plausible states from audio evidence?

**RQ4 — Human-centered explanation.** When state predictions are surfaced to
producers as suggestions, what explanation forms (graph citations, precedent
examples, counterfactuals) support appropriate trust, and how do such systems
affect producer agency and creative outcomes, measured through user studies?

## 3. Methodology and work plan

**Year 1 — Representation and data.**
Formalize the typed session-state graph schema (building on the preliminary
prototype below), define the Cubase/VST3 instantiation with Steinberg —
tracks, events, insert/send effects, and the VST3 parameter model give the
schema a concrete industrial grounding — and construct datasets. Three
complementary sources: (a) synthetic corpora generated from parameterized
production templates, useful for controlled prediction benchmarks; (b) open
multitrack resources (MedleyDB, the Cambridge-MT multitrack library, MUSDB18)
paired with reconstructed or annotated session structures; (c) in
collaboration with Steinberg, anonymized real session structures and edit
histories where feasible — the industrial partnership's distinctive
opportunity. Audio material is descriptor-encoded with Essentia; Freesound
provides loop/sample-level material with community metadata.

**Year 2 — Predictive models.**
Develop and compare models for the RQ2 tasks in increasing order of
complexity: interpretable probabilistic baselines (co-occurrence and
conditional models over chain composition), graph neural networks over the
typed session graph (masked-node and link prediction), and sequence models
over edit histories (next-action prediction). Evaluate against the RQ3
linkage: joint models of state and descriptor evidence. Every learned model is
paired with an explanation mechanism, and faithfulness of explanations is
evaluated alongside accuracy.

**Year 3 — Human-centered evaluation and synthesis.**
Integrate the best models into an assistive prototype (suggestion surfaces
inside or alongside a DAW workflow, with Steinberg's product context) and run
producer studies: explanation quality, trust calibration, perceived agency,
and effect on production outcomes. Synthesis, open releases, and thesis
writing.

Throughout: open-science practice — public code, documented schemas, released
datasets where licensing allows — consistent with MTG norms.

## 4. Preliminary work

I have built and released a working prototype, **Session State Explorer v0**
(github.com/colonelkernel/AbletonSessionStateExplorer), that implements the
representation-and-explanation half of this proposal at small scale:

- a typed, DAW-agnostic session-state model (tracks, clips, scenes, devices,
  parameters, sends, returns, master) instantiated in **two DAW dialects** —
  an Ableton-style demo (session grid) and a Cubase-style demo (linear
  arranger, wired FX-channel sends, dialect-supplied device families) — as
  direct evidence for the cross-DAW representation claim of RQ1;
- compilation of session state into a typed directed graph (11 node types, 12
  edge types) with graph-level statistics and explicit modeling of
  placeholder/uncertain elements;
- audio descriptor extraction (librosa; Essentia and pyloudnorm as optional
  backends) attached to graph entities;
- six rule-based recommendations that are explainable by construction — each
  cites the graph nodes it reasons over, states a confidence, and carries an
  explicit caveat preserving producer agency;
- a first learned proof-of-concept for RQ2: a masked device-family prediction
  baseline trained on a seeded synthetic session corpus, with honest
  reporting of its synthetic-data scope;
- a structural **session diff** between versions (devices, sends, returns,
  tempo, parameters) whose built-in demonstration enacts the system's own
  recommendations and verifies them as state changes — a working seed of
  RQ3's version-comparison methodology;
- a **Live extension** built on Ableton's public Extensions SDK that exports
  real session state from inside the DAW into the model's schema — the
  observation pathway the thesis proposes, working end-to-end on the
  Ableton side and mirroring what first-party Cubase instrumentation would
  provide with Steinberg;
- cautious surface inspectors for both Ableton `.als` files and Cubase Track
  Archive XML, and a documented export adapter — partial observability as a
  designed-for property on both DAW sides, rather than an afterthought.

The prototype is deliberately modest — its purpose is to make the research
object concrete and to establish the explanation contract that learned models
in the thesis must satisfy.

## 5. Fit with the supervisory team

The proposal is designed at the seam the supervisory team spans. Essentia
(Bogdanov) is the descriptor backbone for RQ3's state–outcome linkage;
Freesound and community audio data (Font) ground the loop/sample layer of
session material; the open, transparent AI-for-music agenda (Serra) is the
methodological frame for RQ4. On the Steinberg side, MIR-informed production
tooling (Wolff) and the VST3/SDK and product perspective (Rolland) make the
Cubase instantiation of RQ1 and the Year-3 integration realistic rather than
speculative.

## 6. Responsible and human-centered AI

Assistive production systems risk homogenizing style and eroding producer
agency. The design position of this thesis is that predictions are surfaced as
*inspectable options with stated evidence and stated limits*, never as
corrections; that models disclose the observability boundary they operate
within; and that evaluation includes agency and trust, not only accuracy. This
aligns with the MTG's stated commitment to trustworthy and transparent AI for
music.

## 7. Selected references

- B. De Man, R. Stables, J. D. Reiss, *Intelligent Music Production*,
  Routledge, 2019.
- D. Moffat, M. Sandler, "Approaches in intelligent music production," *Arts*,
  2019.
- J. D. Reiss, "Intelligent systems for mixing multichannel audio," *ICDSP*,
  2011.
- D. Bogdanov et al., "Essentia: an audio analysis library for music
  information retrieval," *ISMIR*, 2013.
- F. Font, G. Roma, X. Serra, "Freesound technical demo," *ACM MM*, 2013.
- R. Bittner et al., "MedleyDB: a multitrack dataset for annotation-intensive
  MIR research," *ISMIR*, 2014.
- Z. Rafii et al., "MUSDB18 — a corpus for music separation," 2017.
- M. A. Martínez-Ramírez et al., "Deep learning for black-box modeling of
  audio effects," *Applied Sciences*, 2020.
- C. J. Steinmetz, J. D. Reiss, "Steerable discovery of neural audio effects,"
  *NeurIPS Workshops*, 2021.
- J. Zhou et al., "Graph neural networks: a review of methods and
  applications," *AI Open*, 2020.

---

*This is a preliminary proposal; the work plan is expected to be refined with
the supervisory team during the first months of the PhD.*
