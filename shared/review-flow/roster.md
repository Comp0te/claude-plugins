
**Size the roster to the diff, then trim by trigger.** The value of another reviewer is another lens on the same files, and it runs out fast on a small change — five agents on a three-file diff produce five readings of the same forty lines and a classification pass that costs more than the findings are worth.

- **≤10 changed files → 3 slots**, filled in this order: the test-coverage reviewer, the security-focused reviewer, and **the one remaining agent whose declared trigger this diff satisfies most strongly** — the error-handling reviewer when the diff touches try/catch, error callbacks, fallbacks or retries, the type reviewer when it reshapes types. Nothing beyond the three, **except the deletion check, which is a standing dispatch outside this cap** — see *Deletion check* below.
  **The third slot is a slot, not a fixed name.** Hardcoding the deletion check there would leave a small diff whose entire subject is error handling with no error-handling reviewer at all — and most diffs land in this bucket. Say in the report which matched agent you dropped.
  **Where the error-handling and type triggers are both satisfied, take the type reviewer** — on this repository's reviews it returns materially more findings no other agent found.

  **Two things this does not license.** The tiebreak settles *ties only*: on a diff whose subject is error handling the error-handling reviewer still wins the slot on the "most strongly satisfied" test above, which is decided first. And the gap is smaller than it looks per token: the type reviewer runs on opus and the error-handling reviewer on sonnet, so a tie broken toward type buys the unique findings at a materially higher price. Where the diff is large enough that both fit, take both rather than choosing.

  Keep recording `found-by:` on every review, so this can be re-decided on data rather than on memory.
- **11-30 files → up to 5.**
- **>30 files → the full matched set.**

Where more matched than the cap allows, drop by marginal yield and by how much of the trigger the diff actually satisfies: an agent whose subject appears in one file of thirty is a wasted dispatch, and you can tell which those are before sending them. **Say in the report which matched agents you dropped and why** — a silently trimmed roster reads as full coverage. The security-focused reviewer and the test-coverage reviewer are never the ones dropped.

**Issue every dispatch in one message.** Compose all the briefs, then send the agent calls together as parallel tool uses in a single turn — never one call per turn. A brief runs to six or eight thousand characters, so each turn spent emitting one costs twenty to thirty seconds of pure wall clock before the *next* agent has started, and the whole fan-out is waiting on the last one. Measured on two real reviews, the gap between the first agent's dispatch and the fifth's was **99 and 141 seconds**, all of it the flow standing still. Nothing is gained by staggering them: the agents share nothing, the roster is already decided, and this is the one place in the command where parallelism is free.
