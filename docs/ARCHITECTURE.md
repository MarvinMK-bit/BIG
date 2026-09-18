# BIG — Bitcoin Incentivized Grading

**Architecture and design rationale**

Author: Maali Marvin Kenneth
Status: Draft v0.1
Date: 13 September 2026
Licence: Apache-2.0

---

## 1. What BIG is

BIG is an automated grading system for handwritten student scripts that is designed to
need less artificial intelligence over time, not more.

It grades a script two ways. The first path sends the script to a large language model,
which is what every automated grading product does today. The second path runs the script
against a **mark scheme** — a versioned, human-readable, deterministic set of grading rules
held in this repository as code.

Both paths write their results into the same table. That makes them directly comparable,
question by question, so the system can measure exactly where deterministic grading has
caught up with the model and where it has not.

The work of moving questions from the first path to the second is done by people: teachers
who spot grading errors, and contributors who write and improve mark schemes. BIG pays them
in bitcoin over Lightning for doing it.

---

## 2. The thesis

### 2.1 The bottleneck

Several companies now grade handwritten scripts automatically — iFLYTEK in China, The
Marking App in South Africa, and others. The technology works well enough to be useful.
The constraint is cost: every script graded is tokens spent, and token cost scales linearly
with the number of scripts. For a school in Uganda marking 600 candidates across nine
subjects, that arithmetic does not close.

Cheaper models are the obvious answer, and they grade worse. So the question becomes:
under what conditions does a cheap model grade as well as an expensive one?

### 2.2 The evidence

There is a directional answer in the literature.

Lee, Jung et al., *Is GPT-4 Alone Sufficient for Automated Essay Scoring? A Comparative
Judgment Approach Based on Rater Cognition* (arXiv:2407.05733), compared GPT-3.5 and GPT-4
against human raters using quadratic weighted kappa. On Essay Set 7, with a basic rubric,
GPT-3.5 achieved 0.263. Given an elaborated rubric containing explicit descriptors, the
same model rose to 0.449 — a 71% relative improvement, and the only statistically
significant difference the authors found (Wilcoxon signed-rank, p < .000). Under GPT-4, the
elaborated rubric produced no improvement, and on some traits a decrease. Human raters
scored 0.741 on the same set; GPT-4 ranged from 0.267 to 0.557 across traits.

The finding is not that a marking guide makes a weak model equal to a strong one. On these
numbers it does not. The finding is more specific and more useful:

> **Encoding the answer key benefits the weak model substantially and the strong model not
> at all.**

That is the entire economic argument for BIG. Every increment of grading knowledge moved
out of the model and into an explicit scheme reduces what you need to pay the model for.
The gains accrue exactly at the cheap end.

**Two caveats, stated plainly.** This study concerns essay scoring, not mathematics. We
expect bounded mathematical marking to respond *better* to encoded answers than essays do,
but that is a hypothesis, not a result. And it is one study on one dataset. BIG treats this
as directional evidence supporting a hypothesis the project exists to test — not as
settled fact.

### 2.3 The chess engine analogy

In the 1990s, chess engines were enormous brute-force search machines. Deep Blue weighed
over a tonne, drew serious power, and still only narrowly beat Kasparov. The approach was:
search more positions than the human can.

Today a chess engine running on a phone, drawing a few amps of battery, beats any human
alive. The search space it explores is far shallower. What changed was the quality of the
evaluation function — better heuristics, and after AlphaZero, learned position evaluation
that made deep search largely unnecessary.

The knowledge moved out of the search and into the evaluation.

Automated grading is at its Deep Blue moment. We are throwing enormous general-purpose
models at a task, and paying for that generality on every single script. High school
subjects are a bounded domain — far larger than chess, but bounded. Ugandan secondary
schools still teach from *Pure Mathematics* by J.K. Backhouse through more than three
curriculum changes and several decades of newer textbooks, because the mathematics has not
changed. A quadratic equation is marked the same way it was marked in 1980.

BIG is built on the assumption that the same transition is available here: move the
knowledge out of the model and into explicit, testable, versioned mark schemes.

### 2.4 What "deterministic" does and does not mean

A deterministic grader is **consistent, reproducible, auditable, and free to run**. Given
the same input it produces the same output, every time, at zero marginal cost.

It is **not** automatically accurate. A badly written mark scheme will be wrong in exactly
the same way on every script, which is arguably more dangerous than a model that is
erratically wrong, because nobody notices a consistent error.

The honest claim is that deterministic graders are *verifiable* in a way that model output
is not. You can read the rule. You can test it against past scripts. You can prove what it
does. That property — not accuracy per se — is what makes the incentive layer possible,
because you cannot pay people to improve something you cannot measure.

---

## 3. Architecture

### 3.1 Four load-bearing decisions

**Decision 1 — Per-question results are the spine of the system.**

Every grading run, by either path, writes one row per question: the session, the question
number, the extracted answer, the mark awarded, the maximum mark, which path graded it,
which mark scheme version was used, and a confidence value.

This is the foundation everything else rests on. Feedback attaches to a specific question
result. A mark scheme's performance is measured against accumulated question results. A
sats payout is justified by pointing at a measurable change in them. Without this table
there is no corpus, no measurement, and no defensible reason to pay anybody anything.

*Rationale:* the predecessor system (GradeScript) discards per-question results from its
grading metadata — they survive only inside a rendered Markdown report and cannot be
reconstructed from the database. That is a missing feature there. It would be fatal here.

**Decision 2 — Both grading paths write the same result shape.**

The LLM path and the mark-scheme path produce identical `question_result` rows. They differ
only in a `grader_type` field and the scheme version referenced.

*Rationale:* this is what turns the chess-engine story from rhetoric into a measurement. It
becomes possible to query the exact point at which deterministic grading overtakes the model
on a given question type, and to plot cost against accuracy over time. If the two paths wrote
different shapes, the central claim of the project would be permanently unfalsifiable.

**Decision 3 — Mark schemes are versioned artifacts in the repository, not database blobs.**

A mark scheme is a file. It is reviewed, diffed, and merged through pull requests, and
attributed to whoever wrote it.

*Rationale:* this inherits GitHub's entire review apparatus for free — which is what the
feedback system would otherwise have to reimplement badly. It also means a sats payout maps
to a merged commit with a named author, which is a far cleaner audit trail than an
administrator upvoting a comment.

**Decision 4 — Feedback is data with provenance.**

A feedback record points at the `question_result` it concerns. A mark scheme version points
back at the feedback that motivated it. Feedback carries a stable public identifier
(`Feedback 0010a` — user, date, what was being graded) and optional contributor context
("Teacher of S3 Mathematics", "undergraduate mathematics student").

*Rationale:* this closes the loop. A scheme can be traced to the observation that produced
it, and a contributor can be paid for an observation whose effect is visible in the data.

### 3.2 The OCR boundary

OCR is the one component that stays a model for now. Mapping handwritten human symbols to
machine-readable text is exactly what large multimodal models are good at and what rules are
bad at.

But it sits **behind an interface**, not hard-wired into the pipeline. Handwriting
recognition is moving quickly, and a local open-weights model may be adequate within a
couple of years. Costing nothing to design for now and saving a rewrite later, the OCR
engine is a swappable component with a defined contract: script image in, structured
Markdown out.

Everything downstream of that boundary operates on machine-readable text, which is precisely
why the grader can be deterministic.

An open question worth stating: OCR makes errors, and a deterministic grader is less
forgiving of them than a model is. Part of what BIG must establish empirically is whether
mark schemes can be written to see past OCR noise, or whether the OCR contract needs to
carry per-token confidence for the grader to use.

### 3.3 Component overview

```
           ┌─────────────────────────────────────────┐
           │              Script upload               │
           └────────────────────┬────────────────────┘
                                │
           ┌────────────────────▼────────────────────┐
           │        OCR engine (swappable)            │
           │   image/docx ──► structured Markdown     │
           └────────────────────┬────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
   ┌──────────▼──────────┐          ┌─────────────▼─────────────┐
   │   Path A: LLM        │          │  Path B: Mark scheme      │
   │   grader             │          │  (deterministic)          │
   └──────────┬──────────┘          └─────────────┬─────────────┘
              │                                   │
              └─────────────────┬─────────────────┘
                                │
           ┌────────────────────▼────────────────────┐
           │      question_result  (shared shape)     │
           └────────────────────┬────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
   ┌──────────▼──────────┐          ┌─────────────▼─────────────┐
   │  Marked script /     │          │   Feedback + sats         │
   │  Mask of Marks       │          │   (Blink / Lightning)     │
   └─────────────────────┘          └───────────────────────────┘
```

### 3.4 Scope of the first deterministic grader

Start narrow and provable: **arithmetic**. Test it against OCR output from both `.docx`
inputs and photographed scripts. Expand to algebraic manipulation, then to the structured
parts of physics, before touching anything resembling free text.

The reason for starting this small is that the first mark scheme has to demonstrate the
measurement machinery works — that a deterministic result can be compared to an LLM result
on the same question and shown to be equal or better. That demonstration matters more than
coverage.

### 3.5 Data ownership and visibility

BIG holds two very different kinds of data, and they are governed differently.

**Student scripts are private.** Uploaded scripts, extracted answers, and per-question
results belong to the school or teacher who submitted them and are visible only to that
owner. This is not a configuration option. It is in accordance with data
protection and privacy laws in most countries.

**Mark schemes are public.** Schemes are the artifact the project exists to accumulate.
They live in this repository, are reviewed through pull requests, and carry no student data
— a scheme encodes how a question is marked, not who answered it. Public schemes can be
shared, forked, and improved by anyone.

**Aggregate measurements are public.** Accuracy by question type, cost per script, the
convergence between the two grading paths — these are the evidence for or against the
project's central claim, and publishing them is the point. They are derived from private
scripts but contain none of their content.

**Consequences for the data model:**

- Ownership is recorded at the row level. A `QuestionResult` belongs to an owner, and
  queries are scoped by that owner.
- Mark schemes carry a visibility flag, defaulting to public.
- Contributor attribution on a public scheme is opt-in. Some contributors will want credit
  for work they were paid sats for; others will not.

**On administrator access.** BIG is Apache-2.0, so anyone may run their own instance and
will be administrator of it. Administrator credentials govern a deployment, not the
codebase, and live in environment variables — never in this repository. On any given
instance, administrators can read the data held there; deployments handling student work
should say so plainly to their users.

### 3.6 The assessment loop

Grading is only half of assessment. A mark that never reaches the student changes nothing.

BIG's loop is designed to close on paper:

1. **Capture on mobile.** A teacher photographs scripts with the phone already in their
   pocket. No scanner exists in most Ugandan schools, and none needs to.
2. **Grade and review.** Results are reviewed on whichever device is to hand.
3. **Print back onto the scripts.** The annotated output — including the Mask of Marks —
   is printed and returned to students on their own paper.

This splits the system across two surfaces with different requirements: capture is mobile,
printing is desktop. The backend serves data rather than presentation so both are first-class,
and the frontend is responsive from the start. Retrofitting a desktop-only interface for
phones is expensive; designing for both from the beginning is not.

**Printer performance is tracked as data.** Which printer models produce legible, correctly
scaled annotated scripts — and which do not — is operational knowledge worth accumulating.
It informs what schools should buy, and in time it is the evidence base for purpose-built
hardware. iFLYTEK's dedicated grading device followed exactly this path: software first,
then hardware shaped by what the software learned.

### 3.7 Mark schemes: format, generation, and transparency

A mark scheme is the artifact this project exists to accumulate. Its format determines who
can write one, so the format is a product decision, not an implementation detail.

**Schemes are YAML files, versioned in this repository.** YAML is readable and writable by a
teacher who does not program, diffs cleanly in a pull request, and — unlike a scheme
expressed as code — cannot execute anything. That last property matters for a public project
that accepts contributions from strangers.

A scheme carries, at minimum: a name, a semantic version, the subject it covers, and a list
of questions with their maximum marks and expected answers. Matching is declared rather than
programmed — `exact`, `numeric`, and similar matcher names — so the vocabulary of what a
scheme can express grows deliberately rather than by contributors writing arbitrary logic.

**Schemes can be generated from marking guides.** Teachers already write marking guides for
every set exam. Requiring them to re-express that work as YAML is a needless barrier, so BIG
accepts a marking guide and produces a draft scheme from it.

Guides are accepted as **DOCX only, never as photographs**. A marking guide is an authored
document that already exists as text; photographing it introduces an OCR error class into
material that never needed one. This is a deliberate asymmetry with student scripts, which
must be photographed because no text version exists.

**Generation is free.** BIG sells nothing. Running a model against your own marking guide
costs what it costs, and users arrange that themselves. Sats flow outward from this project
to contributors and never inward from users — charging for model assistance would mean BIG
earned more when schemes stayed weak, which inverts the incentive the whole system rests on.

**Generated schemes are drafts until reviewed.** A model reading a marking guide will
misread some answers, and a wrong scheme applied to six hundred scripts is worse than no
scheme. Generated schemes therefore enter review rather than service, and each scheme records
its provenance — hand-written, generated from a guide, or derived from feedback — because
those carry different levels of trust.

**Both representations are visible.** A user can see the YAML and the form it compiles to
before trusting a scheme with real scripts. This follows directly from section 2.4: the claim
for deterministic grading is that you can read the rule and prove what it does. A scheme that
cannot be inspected at both levels does not deliver that property.

Improving a scheme — by hand, with a model, by any means the contributor chooses — is
rewarded under section 4.2. The work is what earns sats, not the tooling used to do it.

---

## 4. The incentive layer

### 4.1 Why incentives are necessary

Writing good mark schemes is unglamorous work that requires subject expertise. The people
who have that expertise — practising teachers — have no reason to donate it to an
open-source project, and the usual open-source motivations (scratching your own itch,
portfolio building) do not apply to a secondary school mathematics teacher in Jinja.

Bitcoin rewards, paid in sats over Lightning, make the work worth doing for the people
best placed to do it. This is the mechanism that makes the whole thesis operable rather
than merely plausible.

### 4.2 Reward structure

| Contribution | Reward floor |
|---|---|
| Useful feedback on a grading result (upvoted) | 100 sats |
| A new mark scheme, or a material improvement to one | 500 sats |

Feedback is public, threaded like a discussion, and moderated. Spam and bad-faith
contributions are downvoted, and repeat offenders can be muted or blocked.

Payouts run over the Blink API. Contributors register a Blink wallet address against their
account.

### 4.3 Open design questions

These are deliberately unresolved and are good places for contributors to weigh in:

- **Reward calibration.** Fixed floors are simple but crude. Should a scheme that measurably
  improves accuracy across many scripts earn more than one that does not?
- **Gaming resistance.** Any reward system attracts people optimising for the reward rather
  than the goal. Admin upvoting is the initial defence; it will not scale.
- **Thread depth.** One reply level to a top-level feedback comment is the conservative
  option if hosting constraints bite; deeper threading is preferred otherwise.
- **Payout timing.** Immediate on upvote, or batched?

---

## 5. Relationship to GradeScript

BIG is a research and development project. It is owned by Maali Marvin Kenneth and will be
held by GradeScript UG on that company's incorporation. It is licensed to the public under
Apache-2.0: ownership and licence are separate, and publishing under an open licence grants
the public permission to use and modify the work without transferring who owns it.

BIG will not necessarily be sold as a GradeScript UG product. It is a testbed for a thesis
about how automated grading should evolve, and its output — schemes, measurements, and
findings — is public regardless of what commercial form, if any, follows.

**BIG is a clean-room redesign. It shares no code with GradeScript.** What crosses over is
design judgement: having read a production system that grades scripts at scale, we know
which of its structural choices to repeat and which to avoid. Those judgements are recorded
below so that contributors understand why BIG is built the way it is, and do not spend
effort re-proposing approaches that were considered and rejected.

A revised GradeScript v0.2, aligned more closely with the requirements of Ugandan schools,
is separately in development.

**Inherited deliberately:**

- **Layering:** routers call repositories and services; repositories own every query. This
  is a clean separation and it works.
- **The server-side API proxy.** The browser calls only its own origin; a server-side
  rewrite forwards to the backend, so no backend URL is ever client-visible and there are no
  public environment variables. This matters more for BIG than it did for GradeScript,
  because BIG holds wallet addresses and payout endpoints.
- **The Mask of Marks printing path**, which is fully built and works well.

**Deliberately not inherited:**

- **Migrations as raw SQL in the application entry point**, guarded by an advisory lock, with
  backfills keyed to hardcoded dates. Workable for a team who knows the quirks; hostile to
  outside contributors, which defeats the purpose of an open project. BIG uses Alembic from
  the first commit.
- **Client-side-only route protection.** Without middleware, protected page shells render
  before the sign-in check completes. Cosmetic in a grading tool. Unacceptable in a system
  where an administrator releases bitcoin payments.
- **A prompt registry of subject stubs that all resolve to one shared prompt.** BIG's
  per-subject behaviour lives in mark schemes, which are real artifacts, not in prompt
  variants that do not differ.

---

## 6. What would falsify this

A design document that cannot be wrong is not a design, it is an advertisement. BIG's
central claim fails if:

- Deterministic mark schemes plateau well below LLM accuracy on bounded mathematical
  questions, and the gap does not close as schemes accumulate.
- OCR error rates prove high enough that no rule set can be written to see past them, making
  a model's error tolerance indispensable.
- The incentive layer fails to attract sustained contribution, leaving too few schemes to
  test the thesis at all.

Each of these is measurable with the data model described in section 3. That is the point of
building it this way.

---

## 7. Status

This document describes intent, not implementation. Nothing in section 3 is built yet.
It is published at the start of the project so that the reasoning is on the record and can
be argued with.

Contributions, objections, and corrections are welcome. See `CONTRIBUTING.md`.
