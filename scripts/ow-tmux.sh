#!/usr/bin/env bash
# Start (or reattach to) the "ow" tmux session for working on this project.
#
#   bash scripts/ow-tmux.sh
#
# Windows:
#   1 claude  Claude Code. The first run teleports the cloud session that built this
#             project onto the laptop; later runs reopen your last local session.
#   2 shell   a terminal in the repo with the Python venv active
#   3 app     ready to run the app (text mode by default)
#
# Detach with Ctrl+b then d. Run this script again to come back.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION=ow
CLOUD_SESSION=session_01FUw99vXpLAzWcmeob5MhFT
export PATH="$HOME/.local/bin:$PATH"

if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code isn't installed yet. Run: bash $REPO/scripts/laptop-setup.sh"
  exit 1
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  # Claude stores local sessions under ~/.claude/projects/<path with / turned into ->
  local_dir="$HOME/.claude/projects/$(printf '%s' "$REPO" | sed 's#[/.]#-#g')"
  if ls "$local_dir"/*.jsonl >/dev/null 2>&1; then
    CLAUDE_CMD="claude --continue"
  else
    CLAUDE_CMD="claude --teleport $CLOUD_SESSION || claude"
  fi

  tmux new-session -d -s "$SESSION" -c "$REPO" -n claude
  tmux send-keys -t "$SESSION:claude" "cd '$REPO' && $CLAUDE_CMD" C-m

  tmux new-window -t "$SESSION" -n shell -c "$REPO"
  tmux send-keys -t "$SESSION:shell" "source .venv/bin/activate && git status -sb" C-m

  tmux new-window -t "$SESSION" -n app -c "$REPO"
  tmux send-keys -t "$SESSION:app" "source .venv/bin/activate && python -m ow_assist --text"

  tmux select-window -t "$SESSION:claude"
fi

if [ -n "${TMUX:-}" ]; then
  tmux switch-client -t "$SESSION"
else
  tmux attach -t "$SESSION"
fi
