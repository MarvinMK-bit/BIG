# BIG — Bitcoin Incentivized Grading

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

Scripts are graded two ways, writing into the same table.

| | **Path A — LLM grader** | **Path B — Mark scheme** |
|---|---|---|
| How it grades | Sends the script to a model | Runs versioned deterministic rules |
| Marginal cost | Tokens, per script | Zero |
| Auditable | No | Yes — read the rule |
| Coverage today | Broad | Narrow, growing |

Identical per-question results make the two directly comparable: you can see exactly where
deterministic grading has caught up with the model, and where it hasn't.

OCR stays a model for now, behind a swappable interface — image in, structured Markdown out.
Everything downstream runs on machine-readable text, which is why the grader can be
deterministic.

## Where the bitcoin comes in

Writing good mark schemes takes subject expertise. The people who have it — practising
teachers — have no reason to donate it to an open-source project.

So BIG pays them, in sats, over Lightning.

| Contribution | Reward floor |
|---|---|
| Useful feedback on a grading result | 100 sats |
| A new mark scheme, or a material improvement | 500 sats |

Mark schemes are files in this repo, reviewed through pull requests. A payout maps to a
merged commit with a named author.

## What would prove this wrong

Deterministic schemes plateauing below LLM accuracy and never closing the gap. OCR too noisy
for any rule set to see past. Or an incentive layer that fails to attract contributors. Each
is measurable — that's the point of building it this way.

## Status

**Design stage. Nothing is built yet.**

The [architecture document](docs/ARCHITECTURE.md) has the data model, the full rationale, and
the open design questions. Objections welcome — especially from teachers. Spotting where a
grader marks wrongly is the input this whole system runs on. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[Apache-2.0](LICENSE). Copyright 2026 Maali Marvin Kenneth.
