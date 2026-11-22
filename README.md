# OW Assist: voice cooldown tracker (prototype)

You call out enemy abilities as you see them used ("nade", "suzu", "grav").
The app times them and says "nade is up" in your headset when each one is back.
Nothing plays when you make a call. Your confirmation is the callout arriving later.

**It never reads, hooks, or draws over the game.** The only input is your
microphone. Recognition runs offline and audio is never saved.

## Setup (Windows)

1. Install Python 3.11+ and run `pip install -r requirements.txt`.
2. Download the small English Vosk model (`vosk-model-small-en-us-0.15`, ~40 MB)
   from the Vosk models page (alphacephei.com/vosk/models) and unzip it to `models/`.
3. Run: `python -m ow_assist --model models/vosk-model-small-en-us-0.15`

Other options:
- `--list-devices` / `--device N` to pick your mic
- `--window` to show the status window. Off by default; its only real use is
  seeing how long ago each ult was used.
- `--text` to type commands instead of speaking, and `--mute` to turn off speech

## Phone view (ult timers)

Run with `--phone`. The app prints an address like `http://192.168.1.20:8765`.
Open it on your phone, which must be on the same Wi-Fi as your PC.

- Each enemy ult you've called shows a live "time since used" counter.
  It's highlighted orange for the first 15 seconds, so fresh ults stand out.
- Rows keep a fixed order, so they don't jump around while you glance.
- "new round" clears the list. "disconnected" means the phone lost the PC.
- **Windows will ask to allow network access the first time.** Allow it on
  private networks only.
- **Set your phone's auto-lock to "never" while playing.** The page can't keep
  the screen awake by itself, because browsers only allow that on https pages.
- The page is read-only. It can show the ult timers but can't change anything.
  Anyone on your Wi-Fi who opens the address could see them too.
- Change the port with `phone_port` in `data/settings.json`.

## Commands

| Say | Effect |
|---|---|
| `nade`, `sleep`, `suzu`, `lamp`, `grip`, `cryo` | starts that cooldown timer |
| `nano`, `kitsune`, `amp matrix`, `beat`, `trans`, `grav`, `shatter`, `blade` | marks the ult as used, then counts up the time since |
| `enemy <alias>` | same as the alias alone |
| `cancel <alias>` | removes that timer |
| `undo` | reverts your last call |
| `reset` / `new round` | clears everything |

## What you hear

- **"sleep is up", "nade is up"...:** that cooldown is back. Set a different
  phrase with `"callout"` on an ability in `data/abilities.json`.
- **"undone" / "cleared":** after `undo`, `cancel` or `new round`, so you know
  the correction worked.
- **Nothing else.** Calls are silent and ults have no callout, since there's no
  "ready" moment to announce.

## Why these abilities

The defaults are picked for Tracer, Sojourn, Genji and Cassidy: the enemy
cooldowns that stop your dive (sleep, cryo) or save your target (suzu, lamp,
grip, nade's anti-heal decides duels). Edit `data/abilities.json` to change
them. Add or remove abilities and aliases.

> **The cooldown numbers are unverified estimates.** Check each one against the
> current patch and fix it in `data/abilities.json`.

## Settings (`data/settings.json`)

- `call_lag_seconds`: how many seconds are subtracted from each timer,
  because you speak after the ability is used.
- `fire_on_partial`: acts on a call before you finish speaking, which is
  faster. Set it to `false` if you get misfires.
- `speech_rate`: how fast callouts are spoken.
- `window_topmost`: keeps the optional window above other windows.
- `phone_port`: the port the phone view uses.

## Prototype test plan

Play about 5 matches and track only 1 or 2 abilities, starting with `sleep`.
Then check three things:
- Did calling feel natural?
- Did the recognizer misfire?
- Did the callouts help or get in the way?

## Tests

`python -m pytest`
