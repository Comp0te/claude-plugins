# pr-tickets

Triages the findings a PR review deliberately left unposted — pre-existing problems and
deferred work — and turns the ones worth tracking into Jira issues, after verifying each
against the base branch.

## What it consumes

The `/pr-tickets:jira` command reads `.claude/reviews/pr-<N>-findings.md` and
`.claude/reviews/pr-<N>-deferred.md` from the repository root. Both are written by
`review-flow`'s `/pr-review` command. This plugin is useless without `review-flow` installed
and a review already run for the PR: there is nothing to triage otherwise, and the command
stops rather than reconstructing findings on its own.

## Requirements

- **`review-flow` installed.** The preflight checks for a verification agent that confirms
  findings against the base branch before any ticket is filed; without it, the command stops
  and says so.
- **Jira tooling that exposes issue creation** in the session. Without it, the command stops
  before triage begins and writes nothing — it never simulates a created ticket.

## Configuration

Every repository this command runs in files tickets into a different Jira project, so the
project's conventions are read from a config file rather than assumed. Copy
`reference/pr-tickets.config.example.json` to `.claude/pr-tickets.json` in the repository root
and commit it:

```json
{
  "site": "your-org.atlassian.net",
  "project": "PROJ",
  "component": "Component Name",
  "issueType": "Bug",
  "summaryPrefix": "PROJ | ",
  "labels": [],
  "dedupeJql": "project = PROJ AND component = \"Component Name\" AND statusCategory != Done"
}
```

| Key | Meaning |
| --- | --- |
| `site` | The Jira Cloud site the issue is created on, e.g. `your-org.atlassian.net`. |
| `project` | The Jira project key tickets are filed into. |
| `component` | The component value set on every created ticket. |
| `issueType` | The default issue type — `Bug` for a defect, `Task` for a missing test, cleanup, or design change. |
| `summaryPrefix` | Prepended to every ticket's summary, e.g. `PROJ \| `. |
| `labels` | Labels applied to every created ticket. May be empty. |
| `dedupeJql` | The JQL used to search for an existing open ticket before filing a new one. Falls back to a search by component and substance when omitted — never by the summary prefix, since more than one repository can file into the same project. |

If `.claude/pr-tickets.json` is missing, the command falls back to a ticket this repository has
already filed (a `promoted:` key in a deferred log) and offers to write the config from what it
infers. With neither a config nor a prior ticket, it asks for these values and stops until they
are answered — it never invents a project key.

## Installing

```bash
claude plugin marketplace add Comp0te/claude-plugins
claude plugin install review-flow@compote --scope user
claude plugin install pr-tickets@compote --scope user
```
