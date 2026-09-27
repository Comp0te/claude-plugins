
Deleted lines are the blind spot every other check shares: reviewers read what was added. Nothing else in this flow looks at what left.

**Keep it context-free either way.** Do not pass this reviewer the requirement or the author's stated intent. A rationale explains why the author believed the removal was safe, and this is the one check whose value depends on establishing that independently.

**This reviewer is the only owner of comment rot, which is why its trigger is two-part.** Its second half re-reads the comments and docs the change left *unchanged* around code it touched — the claim a change silently invalidated. That is a separate blind spot from deleted lines and it does not require any deletion to open: a purely additive hunk falsifies the comment above it just as reliably. Dispatching this reviewer only when something was removed would leave a whole class of diff with nobody re-reading a single surviving comment. If the session offers a *separate* comment or documentation reviewer as well, dispatch it only when comments or docs are a substantial part of the diff — otherwise the two are a duplicate dispatch rather than extra coverage.
