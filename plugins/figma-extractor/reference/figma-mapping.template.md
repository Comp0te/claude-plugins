# Figma → code mapping

A human maintains this file; `figma-extractor` reads it but never edits it. When the agent's
memory surfaces a mapping that has proved itself, promote it here yourself.

Delete every instruction line in *italics* once the section is filled in — they exist to say
what belongs in the section, not to ship as content.

Optional: name the Figma file(s) this document was derived from, so a reader knows which design
file the tables below are the source of truth for.

## Theme access

*The import idiom for reaching a token — a hook, a plain object, a context. Name anything that
looks like it should work but doesn't (a deprecated hook, a broken alias).*

## Colours

*A table: design tool name/style → code token → hex. Then, if the codebase has tokens with no
design-tool counterpart, list them so they aren't mistaken for a gap.*

*The gap policy — what should happen when a colour has no entry in the table above. The two
policies seen in practice: **halt** ("flag it as a blocker, don't add a one-off token"), or
**approximate** ("pick the nearest existing token by hex, and say which one and how close"). Pick
one. If this is left blank, the agent's own default applies: halt.*

**Gap policy for an unmapped colour:**

## Typography

*A table: design tool text style → family/size/line-height/spacing → code variant. Note whether
there's a shared text component or a raw platform primitive, and whether the code's type scale
and the design's have already drifted (and the recipe for reporting that drift when it happens).*

## Components

*A table: design tool node name → component → import path. Note whether imports go through a
barrel or a direct path, and any rule for deriving a prop from a visual property (for example,
a fill colour choosing a variant).*

*The gap policy — what should happen when a node has no mapped component. The two policies seen
in practice: **halt** ("flag it as a blocker, propose an option, don't compose ad hoc"), or
**compose** ("build it inline from these named primitives, and halt only if that would require a
new *shared* component"). Pick one. If this is left blank, the agent's own default applies: halt.*

**Gap policy for an unmapped component:**

## Spacing

*Does the project have a spacing/radius token scale? If yes, a table: design tool value → token.
If no, say so explicitly — the agent then reports raw spacing and radius numbers instead of
inventing a scale that doesn't exist.*

## Icons

*Storage format (separate files vs. generated components), the import mechanism, and a table:
design tool name → file. Note where a new icon goes and the naming convention it follows.*

## Assets

*Where bitmaps land, the density-set convention if any, and whether vector assets are saved as
files at all or always reported as path data instead.*

## Screen-level state

*Where screens live, the wrapper a screen is expected to use (an observer, a provider, none),
how a screen reaches shared state versus local state, and how a new screen gets registered.*

## Forms

*Only if the project has a form abstraction: the wrapper component, where forms live, how values
and validation flow in and out.*

## Known-stale rows

*A live list of rows in this document that are known to be wrong or out of date, so the agent
reports the contradiction instead of trusting a stale mapping. One bullet per correction: what
the table says, what's actually true, and why.*

## Open questions

*Known gaps this document doesn't yet resolve — one bullet each, kept as a live list rather than
buried in history.*
