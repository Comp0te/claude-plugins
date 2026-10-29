#!/usr/bin/env bash
set -eu
mkdir -p prompts
cat > CLAUDE.md <<'SCAFFOLD_EOF'
# support-agent

- The agent's behavior is defined by the prompt files in `prompts/`.
- Adding a dependency needs the owner's approval.
SCAFFOLD_EOF
cat > prompts/retry.md <<'SCAFFOLD_EOF'
# Tool-call retries

When a tool call fails, tell the user what failed and carry on with the rest of the task.
SCAFFOLD_EOF
