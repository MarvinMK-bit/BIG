# Mark codes

Questions marked on their working (`matcher: procedure`) award their marks under BIG's own
mark codes. There are four, and they are BIG's: they are designed to mirror how method marking
works in practice — credit for the first step, for each correct step after it, for the answer,
and for saying what the answer means — but they are not any examination board's codes and
should not be read as such.

| Code | Awarded for                                             | Per question              |
|------|---------------------------------------------------------|---------------------------|
| `T`  | the correct first step                                  | exactly one, always first |
| `M`  | a subsequent correct step                               | one to four               |
| `A`  | the answer stated, e.g. `x = 2, x = 3`                  | at most one               |
| `D`  | the concluding statement, e.g. `the roots are 2 and 3`  | at most one               |

## Code and mark

A mark point is named by its code alone. The number written after it is the mark it was
awarded, not part of its name: a `T` that is earned reads `T - 1`, and one that is not reads
`T - 0`. There is no such thing as an unearned `M - 1`. Results and reasons always write the
mark this way, with a space either side of the hyphen.

## Declaring marks

A scheme declares a procedure question's marks by code, in this sequence: one `T`, then its
`M` marks, then `A` if it has one, then `D` if it has one. A scheme that breaks the sequence is
rejected when it is loaded or uploaded, with a message naming the rule — for example
`question '1' has A after D: marks must run in the order T then M then A then D`.

```yaml
questions:
  - number: "1"
    max_mark: 4
    matcher: procedure
    procedure: quadratic
    marks:
      - id: T
        description: Equation identified and coefficients extracted
      - id: M
        description: Correct factorisation or quadratic formula step
      - id: A
        description: Both roots stated correctly
      - id: D
        description: A concluding statement
```

## Several M marks

A question whose working has more than one step between the first step and the answer may
declare up to four `M` marks. Each is a distinct mark, earned or lost on its own: the first
for the first step after `T`, the second for the next, and so on. They keep the code `M`; in
output they are told apart by position only — "first M", "second M" — never renamed. Results
show every mark separately with its own tick or cross, e.g. `T - 1 ✓  M - 1 ✓  M - 0 ✗  A - 1 ✓`.

## Aligning the LLM grader

The LLM grader can be run against a scheme's mark structure, so its marks line up code for code
with the scheme grader's. It is told each question's number, total marks and ordered codes with
the generic meanings above — and nothing else: not the expected answers, the mark descriptions,
the parameters or the procedure. It works out the mathematics itself and returns 1 or 0 per
code; a response whose codes or order differ from what was asked for is rejected. Where both
runs share a structure, the comparison view sets them side by side, code by code.

## How a procedure applies them

Each procedure decides what counts as a correct step for its topic; the codes fix only the
shape of the marks. Every procedure also follows one rule: marking stops at the first clearly
wrong step, nothing after it is awarded, and the reason says so.

A quadratic has exactly one working step between identifying the equation and stating the
roots, so `quadratic-any` declares one each of `T`, `M`, `A` and `D`, out of 4. The quadratic
procedure awards:

- `T` for line 1, when it is a quadratic equation with its coefficients read correctly;
- `M` for line 2, when it is a correct factorisation or quadratic formula step;
- `A` for the first line from line 3 on that states every root correctly;
- `D` for a line after the answer that contains every root's value and a concluding word
  (`root`, `roots`, `solution`, `solutions`, `therefore`, `hence`, `thus`, `answer`, `so`,
  in any case). This is a pattern check, not a model's judgement, and `D` is awarded only
  when `A`'s answer was stated correctly.

The full rules are in the docstring of
`backend/app/services/grading/procedures/quadratic.py`.
