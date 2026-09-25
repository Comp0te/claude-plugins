# Reusable route scripts

Recording the route from launch to the screen under test once, then replaying it, is the cheapest
win available to a verification run. This file holds the rules that keep a recorded script from
replaying green while quietly mis-tapping. `agent-device help scripting` is the authority on
command shapes — read it before your first recording; where it disagrees with this file, it wins.

## Where scripts live

`.agent-device/<screen>.ad` at the repository root, named after the destination, unless the
project's `.claude/docs/ui-verification.md` names another location. The directory should be
gitignored — a `.ad` file is a machine-local convenience, not a reviewed artifact, and its
identity annotations are bound to the device and language it was recorded on.

## When not to record at all

**Do not record a route whose launch path necessarily passes through a screen that can only be
driven by raw coordinate presses on every launch** — most commonly a lock/PIN/passcode screen with
no accessible focus. A recorded coordinate step replays blind with no identity check, so a layout
shift silently mis-taps and still reports success; and if the screen's coordinates encode a
credential, the script encodes the credential too. Drive that portion live on every run.

If the gate is biometric rather than numeric, `agent-device settings faceid|touchid <match>`
clears it without coordinates, and the route is safe to record from there.

## Recording

Arm the recording on the first `open`, walk the journey, guard the destination, then publish
without closing:

```
agent-device open <app-id> --relaunch --save-script=.agent-device/<screen>.ad
agent-device press 'id="continue"' --settle
agent-device wait 'role="heading" label="Screen X"'
agent-device session save-script
```

`session save-script` publishes the recorded open through the guard, omits the close, and leaves
the session active — so you record and then run the checklist in one session. A second successful
`open` aborts publication; start a fresh session to author again.

- **The destination guard must be a selector wait on a labeled or id-bearing landmark.** Its
  identity is captured while armed and re-verified at replay time, so a reshuffled screen with the
  same label elsewhere fails closed instead of false-passing. A duration wait, `wait stable`,
  `wait absent`, `wait @ref`, or a selector wait on an unlabeled element **is not a guard** and buys
  you nothing. A guard that finds the label but not the recorded identity fails with
  `wait_landmark_identity_mismatch` — that is route drift, not an app defect.
- **Prefer a stable landmark over a localized string.** If only a translated label is available,
  the script is bound to the language it was recorded in — say so in the script's name.
- **Record only the route to the screen, never the checklist itself.** Much of the interaction in
  a React Native app is coordinate presses (icon-only controls, chip/remove buttons, picker
  wheels), and those replay blind — a recorded coordinate silently hits the wrong control after
  any layout shift, while a selector step fails closed on an identity mismatch instead of
  mis-tapping.
- **A credential in the route needs `--record-as`, or its literal text is written to the `.ad`
  file.** Keep the live value in an env var and name its replay placeholder:

  ```
  export AD_VAR_PASSWORD='<secret>'
  agent-device fill 'id="password"' "$AD_VAR_PASSWORD" --record-as PASSWORD
  ```

  The app receives the real value; the published script contains only `${PASSWORD}`. Replay with
  `AD_VAR_PASSWORD` still set, or pass `--env PASSWORD=<value>`. `--record-as` is fill-only and
  requires an armed recording.
- **An authentication step that opens a system web view outside the accessibility tree** (an
  OAuth/SSO flow) cannot be recorded around. Sign in live without recording armed, then start the
  recording from the already-authenticated screen.

## Replaying

```
agent-device replay .agent-device/<screen>.ad --keep-session
```

`--keep-session` suppresses exactly the authored terminal close and returns the surviving session,
so the checklist runs in it directly.

## When a replay diverges

A failing step returns `REPLAY_DIVERGENCE` with a screen digest, ranked selector suggestions, a
`repairHint`, and a resume field. **Read the hint before deciding what to do** — the two common
cases need opposite responses:

- `state-repair` — the script is correct, the app state is not. Fix state with `--no-record`
  actions, then `replay --from <n> --plan-digest <sha256>` to re-run the unchanged step.
- `record-and-heal` — the script is stale. Arm `replay <file>.ad --save-script[=<out>]` before
  step 1, press the correct control via a blessed `@ref` from the divergence's `screen.refs`, then
  `replay --from <n+1> --plan-digest <sha256>`. End with `close --save-script`, which writes
  `<stem>.healed.ad` by default. **Review the healed diff before promoting it over the original.**
  Read-only commands you run to find the repair target stay out of the healed script unless you
  pass `--record` on them.
- `caution` means a blind re-press may repeat the mistake; `manual` means no safe automated repair
  could be proven. Re-record the route from scratch in both cases.

Resume never re-executes skipped steps, so app state at the resume point is your responsibility.

Two rules hold regardless of hint:

- **Never hand-edit a `.ad` file.** An edited script replays green while its identity annotations
  are stale or invented, defeating the exact protection the script exists to provide. The
  supervised repair path above is not hand-editing; a text editor is. (`--update`/`-u` is a no-op,
  by design — every divergence already carries the ranked suggestions it would have applied.)
- **Never delete a failing `wait` to make a replay pass.** It will pass warm and fail cold, and a
  failing wait means the timing actually changed.

**A replay failure while a build or bundler runs in parallel on the same machine** can be a false
alarm from host load rather than real drift. Re-run it on a quiet machine before reporting it.
