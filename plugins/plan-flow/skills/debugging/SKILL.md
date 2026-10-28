---
name: debugging
description: Use when a bug, a failing or flaky test, a build failure, or behavior nobody expected needs fixing — before proposing a fix, and again when a fix already tried did not hold.
---

# Debugging

Find the cause before changing anything that could hide it. A fix for a symptom you do not
understand moves the bug somewhere else, and whoever meets it next starts with less than you had.

## The order of work

1. **Read the whole failure.** The full stack trace, the warnings printed above the error, the
   exit code, the file and line. The message often names the cause outright.
2. **Reproduce it on demand.** A reproduction is something anyone can rerun: a test, a script with
   an exit code, or exact steps in the running app. If you cannot make it happen again, gather
   evidence (below) rather than guessing — a fix for a bug you never saw cannot be checked.
3. **Turn the reproduction into a failing test before touching the suspect code,** and run it to
   watch it fail for the reason you expect. From then on the test is the target: when it later
   disagrees with your fix, the fix is wrong, never the expectation. Where no test framework
   reaches the failure — a build step, a native layer — the script or the app steps stand in.
4. **Locate the cause** with the techniques below, starting from the cheapest that applies.
5. **State one hypothesis and test it with the smallest change:** "X causes this because Y; if so,
   changing Z makes the reproduction pass." One variable per run, so a result means one thing.
6. **Fix it where the bad state originates,** not where it surfaced. Then run the reproduction and
   the project's own checks. A bug someone could see on screen is verified on screen too — a green
   test only proves the test.
7. **Remove the instrumentation you added.**
8. **Report** the cause, the evidence that shows it, the fix, and the test that now guards it.

## Locating the cause

- **What changed.** `git log` and `git diff` since the last known-good state; lockfile and
  dependency bumps; config and environment; build caches (Metro, CocoaPods, Gradle, Xcode derived
  data). A clean rebuild is an experiment — record its result like any other.
- **Bisect when a known-good commit exists.** `git bisect run <reproduction command>` names the
  commit that introduced the bug in a handful of runs, before any reading.
- **Compare with what works.** Find the nearest working path in the same codebase and list every
  difference, including the ones that "cannot matter".
- **Trace backward.** When the error surfaces deep in a call chain, follow the bad value up to where
  it was made — see `root-cause-tracing.md`.
- **Instrument the boundaries.** In a chain of components (CI → build → signing, API → service →
  store), log what enters and leaves each boundary, run once, and read where the data goes wrong.
  When the output is large, hand reading it to a helper agent if one is available and keep the
  conclusion.
- **Timing and flaky tests:** `condition-based-waiting.md`. **A test that leaves state behind**
  (a stray file, a polluted directory): `scripts/find-polluter.sh` finds which test file does it.

## Keep a hypothesis log

Write each hypothesis, the experiment and its result in the conversation as you go, one line each.
It keeps you from re-running an experiment you already ran, and the count of failed fixes below
has to survive a long session.

## When fixes keep failing

After three fixes that did not hold — or after two, when each revealed a problem in a different
place — stop changing code. Bring the user the log, what each attempt showed, and the question of
whether the design itself is the problem. A fourth patch on a wrong structure is the most expensive
step available.

## When the cause is out of reach

If the evidence points outside the code — the network, the device, a third-party service — say
what you ruled out and how. Then add handling (a retry, a timeout, a clear error) and logging that
would catch it next time, and call it a mitigation, not a fix.

## After the fix

When the bad value could have entered through more than one path, offer to add validation at the
other layers it passes — `hardening.md`. Offer it; do not add it unasked.

## Signs you have drifted

- You are about to change code "to see if it helps".
- You changed several things before one run.
- You are explaining the bug without having reproduced it.
- The fix is ready and you cannot say why the bug happened.
- The user asks "is that actually happening?" or "stop guessing".

Each of these means returning to step 2.
