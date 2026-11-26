# OW Assist: voice cooldown tracker (prototype)

You call out enemy abilities as you see them used ("nade", "suzu", "grav").
The app times them and says "nade is up" in your headset when each one is back.
Nothing plays when you make a call. Your confirmation is the callout arriving later.

**It never reads, hooks, or draws over the game.** The only input is your
microphone. Recognition runs offline and audio is never saved.

## When you get home: first-run checklist

1. **Install.** Install Python 3.11+ (tick "Add to PATH"), open a terminal in
   this folder and run `pip install -r requirements.txt`.
2. **Get the speech model.** Download `vosk-model-small-en-us-0.15` from the
   Vosk models page (alphacephei.com/vosk/models) and unzip it to `models/`.
3. **Dry run without the mic:** `python -m ow_assist --text`. Type `nade`, and
   about 10 seconds later you should hear "nade is up". Then type `gg win`.
   That checks speech output without the game or mic involved.
4. **Pick your mic:** run `python -m ow_assist --list-devices` and note your
   headset mic's number. Use the one marked `MME`. Put the number itself after
   `--device` (for example `--device 9`), not the letter N.
5. **Set push-to-talk** (optional but recommended): set `"push_to_talk": "mouse:x2"`
   (or whichever button is free) in `data/settings.json`.
6. **Run it for real:** `python -m ow_assist --model models/vosk-model-small-en-us-0.15 --device N --phone`
   Open the printed address on your phone and allow the Windows network prompt.
7. **Check the cooldowns.** In a custom game, time each tracked ability and fix
   the numbers in `data/abilities.json`.
8. **Play about 5 matches** calling only `sleep`, then see the test plan at the bottom.

If anything fails, copy the full error text and send it to me.

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

## Push-to-talk

By default the mic is always listening. To listen only while you hold a button,
set `push_to_talk` in `data/settings.json`:

- `"mouse:x2"` or `"mouse:x1"`: mouse side buttons (recommended)
- `"mouse:middle"`
- `"key:f13"`, `"key:caps_lock"`, `"key:v"` and so on: any key
- `null`: always listening

Hold the button, say the call, let go. It catches the word even if you start
talking a moment before pressing.

The button still reaches the game, so **bind one the game doesn't use**. It
watches the button the same way Discord's push-to-talk does.

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
| `nade`, `sleep`, `sue zoo` (or `suzy`), `lamp`, `grip`, `cryo` | starts that cooldown timer |
| `nano`, `fox`, `amp matrix`, `beat`, `trans`, `gravity` (or `graviton`), `shatter`, `blade` | marks the ult as used, then counts up the time since |
| `enemy <alias>` | same as the alias alone |
| `cancel <alias>` | removes that timer |
| `undo` | reverts your last call |
| `reset` / `new round` | clears everything |

The speech model only knows real English words. At startup it lists any alias it
can't hear (`suzu`, `kitsune`, `grav`), so use the alternatives above instead.
If you add your own alias, check that it isn't on that list.

## What you hear

- **"sleep is up", "nade is up"...:** that cooldown is back. Set a different
  phrase with `"callout"` on an ability in `data/abilities.json`.
- **"undone" / "cleared":** after `undo`, `cancel` or `new round`, so you know
  the correction worked.
- **Nothing else.** Calls are silent and ults have no callout, since there's no
  "ready" moment to announce.

## Tilt tracker

It runs automatically alongside the cooldown tracker.

| Say (in the lobby) | Effect |
|---|---|
| `gg win` / `gg loss` / `gg draw` | logs the result and says it back ("Loss logged. 2 losses in a row.") |
| `gg loss tilted` | logs a loss and marks that you're frustrated |
| `goal four games` (one to ten) / `goal off` | sets or clears a session goal |
| `record` | reads back your session ("3 wins, 2 losses") |
| `undo` | undoes the most recent action, whether that was a result or a cooldown call |

- **Sessions are automatic.** A session starts when Overwatch opens, and ends
  2 minutes after it closes, so a quick restart doesn't count as a new session.
  It only checks whether the game is running; it never reads the game. If that
  check isn't available, the session starts at your first `gg`.
- **It speaks up only when it matters.** It says "2 losses in a row", then at
  3 "Consider calling it." It also tells you when you reach your goal, and once
  when you pass 2 hours.
- **The phone view shows the session** at the top: a status dot (green, yellow
  or red), your record, and the last 10 results.
- **See your stats:** `python -m ow_assist --stats` shows your win rate by
  game number in a session, after 2+ losses in a row, and after "tilted"
  losses. Treat it as rough until you have about 30 games.
- **It can't know about games you forget to log.** Saying `record` in the lobby
  is a quick check.
- Results are stored only on your PC, in `userdata/history.sqlite3`.
- The thresholds can be changed in settings: `warn_after_losses`,
  `stop_after_losses`, `long_session_minutes`, `session_end_grace_seconds`,
  `session_gap_minutes` (a gap this long between results starts a new session),
  and `game_process`.

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
- `push_to_talk`: see above. `ptt_tail_seconds` is how long it keeps listening after you release.

## Prototype test plan

Play about 5 matches and track only 1 or 2 abilities, starting with `sleep`.
Then check three things:
- Did calling feel natural?
- Did the recognizer misfire?
- Did the callouts help or get in the way?

## Tests

`python -m pytest`
