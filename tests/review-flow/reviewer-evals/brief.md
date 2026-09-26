Review this change.

Read the code at {workspace}.

Diff scope: `git diff HEAD~1...HEAD`, run in {workspace}.

Gate: not run in this evaluation.

The repo's full gate has already been settled for you — on CI or locally, as stated above with its result. Do not run the full test suite, and do not run a whole-project type-check: the answer is already established, and running them again in parallel with the other reviewers will exhaust the machine. Run only *targeted* checks that a specific finding needs: a single test file, a scoped grep, a small standalone probe. When you do invoke the test runner, bound its parallelism — several reviewers are running concurrently and a runner that fans out to one worker per core will take the machine down (on Jest that is `--maxWorkers=2`, plus `--watchman=false` where the file watcher is a known irritant).

**Executable checks may be run only in **none**, which is at commit `{head_sha}`. Run them nowhere else — not in the directory you happen to start in, not in the repository root, not in the tree you were given to read.** If that slot says **none**, no test runner can start anywhere this run: settle what you can by reading and mark it `grounded`, and never `verified`. A check run against a tree at another commit is not weaker evidence, it is evidence about different code, and nothing downstream can see which it was.
{author_block}
```diff
{diff}
```
