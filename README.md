# OW Assist: voice cooldown tracker (prototype)

You call out enemy abilities as you see them used ("nade", "suzu", "grav").
The app times them and plays a short tone in your headset when each one is
about to come back and when it's back.

**It never reads, hooks, or draws over the game.** The only input is your
microphone. Recognition runs offline and audio is never saved.

## Setup (Windows)

1. Install Python 3.11+ and run `pip install -r requirements.txt`.
2. Download the small English Vosk model (`vosk-model-small-en-us-0.15`, ~40 MB)
   from the Vosk models page (alphacephei.com/vosk/models) and unzip it to `models/`.
3. Run: `python -m ow_assist --model models/vosk-model-small-en-us-0.15`

Other options:
- `--list-devices` / `--device N` to pick your mic
- `--no-ui` for audio only
- `--text` to type commands instead of speaking

## Commands

| Say | Effect |
|---|---|
| `nade`, `sleep`, `suzu`, `lamp`, `grip`, `cryo` | starts that cooldown timer |
| `nano`, `kitsune`, `amp matrix`, `beat`, `trans`, `grav`, `shatter`, `blade` | marks the ult as used, then counts up the time since |
| `enemy <alias>` | same as the alias alone |
| `cancel <alias>` | removes that timer |
| `undo` | reverts your last call |
| `reset` / `new round` | clears everything |

## Sounds

- **Tick:** your call was heard.
- **One beep at the ability's pitch:** it's back in about 3 seconds.
- **Two beeps:** it's back now.

Every ability has its own pitch. Sleep Dart is spoken as "sleep up" instead,
because it's the biggest threat to a dive DPS.

## Why these abilities

The defaults are picked for Tracer, Sojourn, Genji and Cassidy: the enemy
cooldowns that stop your dive (sleep, cryo) or save your target (suzu, lamp,
grip, nade's anti-heal decides duels). Edit `data/abilities.json` to change
them. Add or remove abilities and aliases, and set `"speak": true` on any
ability you want announced by voice.

> **The cooldown numbers are unverified estimates.** Check each one against the
> current patch and fix it in `data/abilities.json`.

## Settings (`data/settings.json`)

- `warn_before_seconds`: how early the heads-up beep plays.
- `call_lag_seconds`: how many seconds are subtracted from each timer,
  because you speak after the ability is used.
- `fire_on_partial`: acts on a call before you finish speaking, which is
  faster. Set it to `false` if you get misfires.
- `buzz_on_unknown`: plays a low buzz when speech isn't understood. Only useful
  with push-to-talk, because with an always-on mic it buzzes on normal comms.

## Prototype test plan

Play about 5 matches and track only 1 or 2 abilities, starting with `sleep`.
Then check three things:
- Did calling feel natural?
- Did the recognizer misfire?
- Did the tones help or get in the way?

## Tests

`python -m pytest`
