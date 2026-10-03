<p align="center">
  <img src="docs/assets/big-logo.png" alt="BIG — Bitcoin Incentivized Grading logo" width="420">
</p>

# BIG — Bitcoin Incentivized Grading

### *Mark like a Chess Engine*

**An automated grading system designed to need less AI over time, not more.**

---

## The problem

Companies already grade handwritten scripts automatically — iFLYTEK in China, The Marking
App in South Africa. The technology works. The cost doesn't: every script graded is tokens
spent, scaling linearly. For a Ugandan school marking 600 candidates across nine subjects,
the arithmetic never closes.

The obvious fix is a cheaper model. Cheaper models grade worse.

## The idea

In the 1990s, chess engines were brute-force search machines. Deep Blue weighed over a
tonne, drew serious power, and only narrowly beat Kasparov. Today an engine on a phone
battery beats any human alive — while searching a far shallower tree. What changed wasn't
the search. It was the evaluation.

The knowledge moved out of the search and into the heuristics.

Automated grading is at its Deep Blue moment. We throw enormous general-purpose models at
the task and pay for that generality on every script. But high school subjects are bounded.
Ugandan schools still teach from Backhouse's *Pure Mathematics* through three curriculum
changes and decades of newer textbooks, because the mathematics hasn't changed. A quadratic
is marked today the way it was marked in 1980.

So: move the knowledge out of the model and into explicit, versioned **mark schemes**.

## Does it work?

Lee, Jung et al. ([arXiv:2407.05733](https://arxiv.org/abs/2407.05733)) scored essays with
GPT-3.5 and GPT-4 against human raters. Given a basic rubric, GPT-3.5 managed 0.263
(quadratic weighted kappa). Given an elaborated rubric with explicit descriptors, it rose to
**0.449** — the only statistically significant improvement in the study. Under GPT-4, the
same elaborated rubric produced nothing.

> **Encoding the answer key benefits the weak model substantially and the strong model not
> at all.**

Every increment of grading knowledge moved out of the model reduces what you must pay the
model for. That's the whole economic argument.

It's essay scoring, not mathematics, and it's one study. We expect bounded mathematical
marking to respond *better* — but that's the hypothesis this project exists to test.

## How BIG works

A script is photographed, read by OCR into Markdown, then graded two ways — writing results
into the same table so the two can be compared question by question.

| | **LLM grader** | **Mark scheme** |
|---|---|---|
| How it grades | Sends the script to a model | Runs versioned deterministic rules |
| Marginal cost | Tokens, per script | Zero |
| Auditable | No | Yes — read the rule |
| Coverage today | Broad | Narrow, growing |

**Schemes mark working, not just answers.** A scheme can name a *procedure* — code in this
repository — that reads a student's own first line, extracts the problem, and verifies each
subsequent step. Marking stops at the first wrong step, as a human marker would stop
trusting the rest. Current procedures cover collection of like terms, linear equations,
quadratic equations, and simultaneous equations in two unknowns, with a dispatcher that
chooses the route from the student's working.

**Marks are awarded per step**, using four codes: **T** a correct first step, **M** a
subsequent step, **A** the answer, **D** a concluding statement. Each is displayed as
`T - 1` when earned or `T - 0` when not.

**Results come back on paper.** BIG renders the marked script, and a *Mask of Marks* — the
same annotations on white — so the student's original paper can be fed back through a
printer and keep their own handwriting, with only the marks added.

OCR stays a model for now, behind a swappable interface. Everything downstream runs on
machine-readable text, which is why the grader can be deterministic. Line positions for
annotation are found by image analysis, not by a model.

## Where the bitcoin comes in

Writing good mark schemes takes subject expertise. The people who have it — practising
teachers — have no reason to donate it to an open-source project.

So BIG pays them, in sats, over Lightning.

| Contribution | Reward floor |
|---|---|
| Useful feedback on a grading result or a scheme | 100 sats |
| A well-designed mark scheme, or a material improvement | 500 sats |

Schemes are public, readable as YAML, and reviewed before entering the repository. Feedback
is threaded and moderated. Anyone may publish a **performance report** claiming how a scheme
performed on their own scripts — and anyone may publish a conflicting report disputing it.
Reports carry no student data; disputes stand alongside what they dispute.

## What would prove this wrong

Deterministic schemes plateauing below LLM accuracy and never closing the gap. OCR too noisy
for any rule set to see past. Or an incentive layer that fails to attract contributors. Each
is measurable — that's the point of building it this way.

## Status

**Working, early, and not yet proven.** The pipeline runs end to end: upload, OCR, both
grading paths, per-question comparison, human verdicts, accuracy over time, annotated
scripts and printable masks. Schemes can be uploaded, reviewed and exported. Rewards are
recorded and paid over Lightning.

What it does **not** yet have is evidence. Accuracy figures mean nothing until many scripts
have been graded and judged, and that work is only beginning.

The hosted instance is invite-only, because it handles student work. The code is open source
— run your own.

## Contributing

The most valuable contribution here is knowing where a grader marks wrongly. That's subject
expertise, not programming.

See [CONTRIBUTING.md](CONTRIBUTING.md), the [architecture
document](docs/ARCHITECTURE.md) for the full reasoning and data model, and
[docs/MARK-CODES.md](docs/MARK-CODES.md) for how marks are awarded.

## Licence

[Apache-2.0](LICENSE). Copyright 2026 Maali Marvin Kenneth.
