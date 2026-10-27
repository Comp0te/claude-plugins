**Capture the gate's real exit status.** If you pipe its output through `tail` or `head` to keep the transcript short, the status you see belongs to the pager, not to the gate — a suite that crashed will report success. Do not rely on remembering this. Run it in this shape:

```bash
set -o pipefail
<the repo's own check/test gate command> 2>&1 | tee <scratch>/gate.log | tail -40
echo "GATE EXIT=$?"
```

`tee` keeps the whole log, so when a sub-step fails you can read *which* one without re-running the suite; `pipefail` is what makes `$?` the gate's own status rather than the pager's, since without it a pipeline reports only its last command and `tail` always succeeds.

**Use `$?` with `pipefail`, never `${PIPESTATUS[0]}`.** `PIPESTATUS` is a bash array and this environment's shell is zsh, where it is simply unset: the line prints `GATE EXIT=` — an empty string, which reads as "nothing to see" rather than as a broken check. Lowercasing it is not the repair either, because zsh's `pipestatus` is 1-indexed, so `${pipestatus[0]}` is empty too and `${pipestatus[1]}` is the value bash calls `[0]`. `pipefail` plus `$?` is identical in both shells and preserves the exact code — measured: a sub-step exiting 2 reports 2, not 1.

The stakes are the reason this is spelled out: the block exists to stop a crashed suite from being read as a pass, and an empty `GATE EXIT=` is the same failure wearing the check's own clothes. If you split the gate into its sub-steps — which is what an environment artifact of the kind below can force — every one of them needs its own `set -o pipefail` and its own `$?` read *immediately* after the pipeline, before any other command overwrites it. A step whose only evidence is *empty output* is reported as "no diagnostics printed", never as "exit 0" — and a step whose exit status came back empty is reported as "status not captured", never as green.

If the gate is red for a reason that is not an environment artifact, stop and ask: verdicts about code that does not build are verdicts about nothing. Environment artifacts — a test runner that needs a flag to start, stale or missing dependencies, a missing native module — are things you can name and re-run past, using that second result. A failure you have merely decided to be relaxed about is not one.
