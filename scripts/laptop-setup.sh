#!/usr/bin/env bash
# One-time setup on the Kubuntu laptop. Safe to run again: each step checks first.
#
#   cd ~/OW-Undetectable && bash scripts/laptop-setup.sh
#
# What it does:
#   1. apt packages: tmux, Python venv, PortAudio (mic), espeak-ng (speech), gh (GitHub)
#   2. Claude Code (official installer) and ~/.local/bin on your PATH
#   3. GitHub login for git, so Claude's "teleport" can fetch branches without prompts
#   4. Python virtualenv in .venv with the app's requirements + test tools
#   5. The Vosk speech model in models/
#   6. Claude-friendly tmux settings in ~/.tmux.conf (backed up first)
#   7. Runs the test suite
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL=vosk-model-small-en-us-0.15
say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
cd "$REPO"

say "1/7 System packages (asks for your password)"
PKGS=(git curl unzip tmux python3-venv python3-pip libportaudio2 espeak-ng gh)
MISSING=()
for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
if ((${#MISSING[@]})); then
  sudo apt-get update
  sudo apt-get install -y "${MISSING[@]}" || {
    echo "Some packages failed. 'gh' may need GitHub's apt repo on older Ubuntu:"
    echo "  https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
  }
else
  echo "all installed"
fi

say "2/7 Claude Code"
if command -v claude >/dev/null 2>&1 || [ -x "$HOME/.local/bin/claude" ]; then
  echo "already installed: $("$HOME/.local/bin/claude" --version 2>/dev/null || claude --version)"
else
  curl -fsSL https://claude.ai/install.sh | bash
fi
if ! grep -qs 'HOME/.local/bin' "$HOME/.bashrc"; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
  echo "added ~/.local/bin to PATH in ~/.bashrc"
fi
export PATH="$HOME/.local/bin:$PATH"

say "3/7 GitHub login (lets git fetch without password prompts)"
if GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="ssh -o BatchMode=yes" \
   git ls-remote origin >/dev/null 2>&1; then
  echo "git can already reach GitHub without prompts; skipped"
elif command -v gh >/dev/null 2>&1; then
  if ! gh auth status >/dev/null 2>&1; then
    echo "Choose: GitHub.com -> HTTPS -> Login with a web browser."
    gh auth login
  fi
  gh auth setup-git
  echo "ok"
else
  echo "gh isn't installed; skipped. Teleport needs git fetch to work without prompts."
fi

say "4/7 Python environment (.venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt -r requirements-dev.txt
echo "ok: $(.venv/bin/python --version)"

say "5/7 Speech model ($MODEL)"
if [ -d "models/$MODEL" ]; then
  echo "already there"
else
  mkdir -p models
  curl -fL -o "models/$MODEL.zip" "https://alphacephei.com/vosk/models/$MODEL.zip"
  unzip -q "models/$MODEL.zip" -d models && rm "models/$MODEL.zip"
  echo "ok"
fi

say "6/7 tmux settings for Claude Code"
MARK="# claude-code settings (added by OW-Undetectable setup)"
if grep -qsF "$MARK" "$HOME/.tmux.conf"; then
  echo "already there"
else
  [ -f "$HOME/.tmux.conf" ] && cp "$HOME/.tmux.conf" "$HOME/.tmux.conf.bak.$(date +%s)"
  cat >> "$HOME/.tmux.conf" <<EOF

$MARK
set -g allow-passthrough on
set -g focus-events on
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
set -g mouse on
set -g history-limit 50000
EOF
  echo "added (old file backed up if there was one)"
  tmux info >/dev/null 2>&1 && tmux source-file "$HOME/.tmux.conf" || true
fi

say "7/7 Tests"
.venv/bin/python -m pytest -q

say "Done"
cat <<EOF
Next:
  1. Open a NEW Konsole tab (so PATH is updated) and run:   claude auth login
     (use the same claude.ai account as the phone app)
  2. Start everything:   bash $REPO/scripts/ow-tmux.sh
     The first time, it pulls the cloud session onto this laptop ("teleport").
     After that it reopens the last local session.

Wayland note: push-to-talk can't see global key/mouse presses under Wayland
(Kubuntu's default). Pick "Plasma (X11)" at the login screen, or leave
push_to_talk off in data/settings.json.
EOF
