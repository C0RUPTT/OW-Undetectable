# OW Assist: voice cooldown tracker (prototype)

You call out enemy abilities as you see them used ("nade", "sleep", "gravity").
The app times them and says "nade is up" in your headset when each one is back.
Nothing plays when you make a call. Your confirmation is the callout arriving later.

**It never reads, hooks, or draws over the game.** The only input is your
microphone. Recognition runs offline and audio is never saved.

## Install (Windows, once)

1. Install **Python 3.11+** (tick "Add Python to PATH") and **Git for Windows**
   (git-scm.com, default options are fine).
2. Open a terminal on your Desktop and download the app:
   ```
   git clone -b claude/focused-babbage-t6gmsr https://github.com/C0RUPTT/OW-Undetectable.git ow-assist
   cd ow-assist
   pip install -r requirements.txt
   ```
   The first time, a browser window asks you to sign in to GitHub.
3. Get the speech model (about 130 MB) into `models/`:
   ```
   mkdir models
   curl -L -o lgraph.zip https://alphacephei.com/vosk/models/vosk-model-en-us-0.22-lgraph.zip
   tar -xf lgraph.zip -C models
   del lgraph.zip
   ```
4. Create **`my_settings.json`** in the `ow-assist` folder with your mic and the phone view:
   ```json
   {
     "device": 9,
     "phone": true
   }
   ```
   Find your mic's number with `run --list-devices` (use the `MME` one).
   You can use words from its name instead of the number, like `"device": "Yeti MME"`.
   That keeps working when plugging in other devices changes the numbers.

## Every day

- **Start it:** double-click **`run.bat`**.
- **Update it:** double-click **`update.bat`**. Your `my_settings.json`, models
  and game history are never touched by updates.

## Your settings: `my_settings.json`

Put anything you want to change in `my_settings.json`, not in
`data/settings.json`. Updates replace the files in `data/`, but never yours.
Anything you leave out uses the default. Example:

```json
{
  "device": 9,
  "phone": true,
  "require_enemy": true,
  "turn_on": ["hook", "emp", "teleport"],
  "turn_off": ["lamp"]
}
```

## Choosing which abilities to track

`python -m ow_assist --list-abilities` (or `run.bat --list-abilities`) lists
every ability, whether it's on, and what to say for it. To change one, put
any of its names in `turn_on` or `turn_off` in `my_settings.json`.

Keep the list short: every extra word is one more thing the recognizer can
confuse with what you or your team say. A good start is the few abilities that
decide fights for your heroes.

## Push-to-talk

By default the mic is always listening. To listen only while you hold a button,
set `push_to_talk` in `my_settings.json`:

- `"mouse:x2"` or `"mouse:x1"`: mouse side buttons (recommended)
- `"mouse:middle"`
- `"key:f13"`, `"key:caps_lock"`, `"key:v"` and so on: any key
- `null`: always listening

Hold the button, say the call, let go. It catches the word even if you start
talking a moment before pressing.

The button still reaches the game, so **bind one the game doesn't use**. It
watches the button the same way Discord's push-to-talk does.

## Phone view (ult timers)

Set `"phone": true` in `my_settings.json` (or run with `--phone`). At startup
the app prints an address like `http://192.168.1.20:8765`. Type it into your
phone's browser; the phone must be on the same Wi-Fi as your PC. Bookmark it or
add it to your home screen: the address stays the same unless your router
gives your PC a new one.

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
- Change the port with `phone_port` in `my_settings.json`.

## Commands

| Say | Effect |
|---|---|
| a cooldown's name (`nade`, `sleep`, `recall`...) | starts that cooldown timer |
| an ult's name (`nano`, `gravity`, `blade`...) | marks the ult as used, then counts up the time since |
| `no <alias>` / `enemy <alias>` | same as the alias alone ("no nade") |
| `cancel <alias>` | removes that timer |
| `undo` | reverts your last call |
| `reset` / `new round` | clears everything |

`--list-abilities` shows every name you can say. The speech model only knows
real words: at startup it lists any name it can't hear (like `suzu`), so use
another name for that ability (`sue zoo`).

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

## If it mishears you

Every phrase it hears is printed, like `heard: enemy nade (0.91)`, with the
recognizer's confidence from 0 to 1. Things to try, in order:

1. **Track fewer abilities.** Fewer words means fewer mix-ups.
2. **Turn on `require_enemy`** if chat sets off timers.
3. **Set `min_confidence`** above the numbers you see on wrong `heard:` lines.
4. **Check the mic level** in Windows Sound settings, under Recording. Speak
   at normal volume close to the mic.

## Why these abilities

The ones on by default are picked for Tracer and Sojourn: the enemy cooldowns
that stop your dive or kill you (sleep, cryo, magnet), save your target (suzu,
lamp, grip; nade's anti-heal decides duels), or let an enemy Tracer escape
(recall).

> **The cooldown numbers are unverified estimates.** Time them in a custom game
> and put the right ones in `my_settings.json`, by any of the ability's names:
> `"cooldowns": {"sleep": 15, "recall": 13}`.

## All settings

Set any of these in `my_settings.json`.

- `model`: the speech model folder. `device`: your mic's number. `phone`: `true` for the phone view.
- `turn_on`, `turn_off`, `cooldowns`: see above.

- `call_lag_seconds`: how many seconds are subtracted from each timer,
  because you speak after the ability is used.
- `fire_on_partial`: acts on a call before you finish speaking, which is
  faster but misfires more. Off by default.
- `min_confidence`: calls the recognizer is less sure of than this (0 to 1)
  are skipped. `0` keeps everything. Use the numbers on the `heard:` lines to
  pick a value.
- `require_enemy`: when `true`, only "no nade" or "enemy nade" starts a timer,
  never plain "nade". This stops chat with your team from setting off timers.
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
