## Receiving Review

Review feedback — from me, a review report, or a reviewer agent — is a set of claims about the
code. A decision I made is carried out once understood; a claim about the code is checked first.

- **Clarify every unclear item before changing anything.** Items are often related, and a fix
  built on half the list is built on a guess.
- **Check each claim against the code**: that the problem exists here, and that the change breaks
  no caller. When it is wrong, say so with the evidence — the caller, the test, the constraint.
- **Before building what a reviewer calls "done properly", check that it is used.** If nothing
  calls it, propose removing it instead.
- **Answer with the fix or the objection, not with agreement.** Blocking items first, then simple
  ones, then structural; run the checks after each.
