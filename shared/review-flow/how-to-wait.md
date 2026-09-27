
When you run out of grounding work and the agents are still going, **block in the foreground**: `perl -e 'sleep <n>'` with a matching tool timeout. One call, one turn, `<n>` seconds of real waiting.

**Size the first block to the fan-out, then drop to short ones.** A flat 300 costs up to five minutes of dead time after the last agent has already reported, on every run. Block once for about as long as you expect the slowest agent to still need — 240s on a large diff, 120s on a small one — and after that **block in 30s steps, not 60s**. The cost being avoided is the turn, not the second: a handful of short calls at the tail is cheap, and it is the difference between finishing when the agents finish and finishing minutes later.

**The tail is where this is actually lost.** Sleeping past the end of the fan-out happens on runs that sized their first block correctly, inside a long block sized for agents that have already returned. Once you are past your estimate of the slowest agent, every further block is a coin flip on dead time proportional to its own length; 30s bounds the loss at 30s.

**Calibrate the first block against the slowest agent, not the diff.** On this roster the security reviewer is the long pole, at roughly eleven to thirteen minutes from its own dispatch against four to eleven for the rest. So the useful first block is roughly *that, minus however long you have already spent grounding*, and grounding usually covers most of it. If grounding has run past it, do not open with a long block at all — go straight to 30s steps.

Do **not** wait by backgrounding a sleep. A backgrounded command returns the turn to you immediately, so `sleep 300 &` waits zero seconds and costs one full turn — and by this point in the flow a turn re-reads a 150–250k context. A run that backgrounds its sleeps burns prompt tokens by the million and produces no wall-clock delay at all; a single foreground `perl` call does the whole job.

The same applies to any "let me check if they're done yet" poll — `TaskList`, listing the tasks directory, stat-ing output files. Agent completions arrive as notifications on their own; polling for them buys nothing and costs a turn each time. Block, and let the notification wake you.
