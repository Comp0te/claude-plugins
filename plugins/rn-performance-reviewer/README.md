# rn-performance-reviewer

A React Native performance reviewer for the `review-flow` review commands. It does nothing on
its own — it is an agent definition that `review-flow`'s `pr-review` and `branch-review`
commands can dispatch as one of the reviewers in a session's roster.

It reports statically-provable defects only — code that is wrong on its own terms whether or
not a profiler is running — never speculative optimization advice. Covered areas: lists,
effects and subscriptions, animations, Skia usage, memoization, bundle size and image
rendering. It carries stack-conditional guidance for MobX (`mobx-react-lite` / `mobx-react`),
Skia (`@shopify/react-native-skia`), Redux and TanStack Query.

## Installing

Install this in React Native repositories only. A repository that is not React Native gains
nothing from it — the agent's description never matches a non-RN diff, so it is simply never
dispatched.

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install rn-performance-reviewer@compote --scope project   # from inside the repository
```

## No configuration needed

`review-flow`'s reviewer selection is dynamic: it matches each installed agent's description
against the diff, not by name. Once this plugin is installed, its reviewer joins the roster
automatically — there is nothing to wire up.
