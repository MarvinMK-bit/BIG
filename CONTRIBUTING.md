# Contributing to BIG

BIG is at design stage. Nothing is built yet, which makes this the most useful
moment to argue with it.

## You don't need to write code

The most valuable contribution to this project is knowing where a grader marks
wrongly. That is subject expertise, not programming, and it is the input the
entire system runs on.

If you teach — or have ever marked a stack of scripts at midnight — your
judgement about what a correct mark looks like is worth more here than a pull
request.

## Ways to contribute

**Argue with the design.** Read docs/ARCHITECTURE.md and open an issue where
you disagree. Section 4.3 lists design questions that are deliberately
unresolved. Section 6 lists what would prove the whole thesis wrong. Both are
invitations.

**Report a grading error.** Once the system runs, feedback attaches to the
specific question result it concerns and is public.

**Write or improve a mark scheme.** Mark schemes are files in this repository,
reviewed through pull requests like any other code.

**Improve the documentation.** If something here is unclear, that is a defect.

## Rewards

Contributors are paid in bitcoin over the Lightning Network.

| Contribution | Reward floor |
|---|---|
| Useful feedback on a grading result | 100 sats |
| A new mark scheme, or a material improvement | 500 sats |

These are floors, not fixed amounts, and the calibration is an open question —
see architecture section 4.3. Payouts run over the Blink API; contributors
register a wallet address against their account.

Spam and bad-faith contributions are downvoted and may be muted.

## Pull requests

- Open an issue first for anything substantial, so effort is not wasted on an
  approach that has already been considered.
- One logical change per pull request.
- Explain why, not just what. The reasoning is the part future contributors
  need.
- Mark schemes should state what they cover, what they deliberately do not
  cover, and how they handle OCR noise.

## Licensing of contributions

BIG is licensed under Apache-2.0. By contributing, you agree that your
contribution is licensed under the same terms. You retain copyright in what you
write.

There is no contributor licence agreement. This is deliberate — a CLA would
deter exactly the teachers this project needs.

## Conduct

Be decent. Disagree with the argument, not the person. Teachers contributing
here are doing so outside the hours they are paid for, and the tone should
reflect that.
