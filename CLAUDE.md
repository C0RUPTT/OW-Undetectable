# OW Assist: notes for Claude

A voice-driven Overwatch helper. The player says what they see ("gravity", "nano",
"won fight") and the app times enemy cooldowns, estimates when enemy ults are back,
and reads short callouts in their headset. It also has a phone view and a tilt tracker.

**Hard rule: it never reads, hooks, injects into, or draws over the game.** The only
inputs are the microphone, a push-to-talk button, and whether the game process is
running. Keep it that way. Don't add screen capture, memory reading, overlays or
anything that touches the game client.

## Layout

- `ow_assist/`: the app (`python -m ow_assist`)
  - `tracker.py`: pure timer and ult-estimate logic (time is passed in)
  - `estimate.py`: the charge model: rates, windows, calibration
  - `commands.py`: speech text -> commands, plus the recognizer grammar
  - `data.py`: loads `data/abilities.json` and `data/settings.json`
  - `__main__.py`: Controller and CLI (`--text`, `--mic-test`, `--review`, `--stats`)
  - `matchlog.py`: match log and `--review`; `mictest.py`: mic test
  - `voice.py`: Vosk; `ptt.py`: push-to-talk; `speech.py`: TTS
  - `phone.py`: phone web view; `ui.py`: Tk window
  - `tilt.py` / `stats.py` / `watcher.py`: tilt tracker
- `data/abilities.json`: every ability and ult: cost, tier, call words, `charge_factor`, `hold`
- `docs/ult-tracking.md`: the research behind the model, with sources
- `docs/STATUS.md`: **where the work is up to and what's next; read this first**
- `tools/check_speech.py`: synthetic-voice test of every call word
- `scripts/`: laptop setup and the tmux launcher

## Working on it

- Tests: `.venv/bin/python -m pytest -q` (run after every change; keep them passing).
- Try it without a mic: `.venv/bin/python -m ow_assist --text --mute`.
- Every call word must be in the Vosk model's vocabulary and should pass
  `tools/check_speech.py`. Several obvious words can't be heard; see
  `docs/ult-tracking.md` section 5.
- Ult costs change with patches. When updating, check the wiki and Blizzard's patch
  notes, and note the source in `docs/ult-tracking.md`.
- The user mostly reads replies on a phone: keep answers short and plain.
- The user is on Kubuntu for development. The game itself may run elsewhere.
