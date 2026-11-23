# OW Assist: voice cooldown tracker (prototype)

You call out enemy abilities as you see them used ("nade", "bell", "gravity").
The app times them and says "nade is up" in your headset when each one is back.
For ults it estimates when each one may be back ("gravity may be up"), and after
each fight it tells you what they used and what they may still have.
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
   headset mic's number.
5. **Set push-to-talk** (optional but recommended): set `"push_to_talk": "mouse:x2"`
   (or whichever button is free) in `data/settings.json`.
6. **Mic test (10 minutes):** `python -m ow_assist --mic-test --model models/vosk-model-small-en-us-0.15 --device N`
   It shows each call word; say it into your headset as you would in a match. At the
   end it lists the words it misheard. **WRONG** (heard as a different call) means
   change that word; **MISSED** means try it again. Send me the report: it's saved
   to `userdata/mic_test.txt`.
7. **Run it for real:** `python -m ow_assist --model models/vosk-model-small-en-us-0.15 --device N --phone`
   Open the printed address on your phone and allow the Windows network prompt.
8. **Read the startup output.** If it says the speech model doesn't know some words,
   those calls can't be heard. Pick another word for them. Optional: after changing
   a call word, run `python tools/check_speech.py models/vosk-model-small-en-us-0.15`
   (needs espeak-ng and numpy) to see how reliably each call is heard.
9. **Check the cooldowns.** In a custom game, time each tracked ability and fix
   the numbers in `data/abilities.json`.
10. **Play about 5 matches**, then run `python -m ow_assist --review 5` and send me
    the output. See the test plan at the bottom.

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

- Each enemy ult you've called gets a row: orange for 15 seconds after it was used,
  then a countdown to "may be up in", then **yellow "may be up"**, then
  **red "likely up"**. The bar shows the estimated charge.
- The strip at the top shows recent fights: green won, red lost, with the number
  of ults they used in each.
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
| `nade`, `sleep`, `bell` (Suzu), `lamp`, `grip`, `cryo` | starts that cooldown timer |
| any enemy ult: `gravity`, `nano`, `blade`, `trans`, `beat`, `pulse`, `noon`... (every hero, see `data/abilities.json`) | marks the ult as used and starts its estimate |
| `enemy <alias>` | same as the alias alone |
| `swap <ult>` | they just switched to that hero: starts its ult at 15% |
| `<ult> ten` … `<ult> ninety`, `<ult> full` | the kill cam showed their real charge (e.g. `gravity eighty`). Sets the estimate and teaches the charge rate |
| `won fight` / `lost fight` | ends the fight and reads the summary: what they used, then what they may still have |
| `status` | reads out what they may have right now |
| `cancel <alias>` | removes that timer |
| `undo` | reverts your last call |
| `new round` | ult charge back to 0 for every hero you're tracking (sides swapped, or the next Control round). Keeps the enemy comp |
| `reset` / `new match` | clears everything, comp included |

## What you hear

- **"sleep is up", "nade is up"...:** that cooldown is back. Set a different
  phrase with `"callout"` on an ability in `data/abilities.json`.
- **"gravity may be up":** an engage or kill ult has reached its earliest likely
  return. Ults due within 10 seconds of each other are grouped: "gravity and nano may
  be up". Change which tiers speak with `ult_callout_tiers`, or set it to `[]`.
- **Fight summary**, after `won fight` / `lost fight`: "They used gravity and nano.
  May have blade. Watch for nano blade." Or "No enemy ults. Nothing likely up.
  trans in about 40 seconds." "Watch for …" names a known combo when all its parts
  may be up. The combo list is in `data/abilities.json`.
- **"undone" / "cleared" / "new round":** after `undo`, `cancel`, `reset` or
  `new round`, so you know the correction worked.
- **Nothing else.** Calls themselves are silent.

## Ult tracking

Built from coaching guides and patch data. **[docs/ult-tracking.md](docs/ult-tracking.md)**
has the research and sources. In short:

- **Every ult has a cost and a tier** (engage, kill, save, minor). The estimate is
  `cost / 16` seconds to "may be up" and `cost / 11` to "likely up", since real
  matches charge at about 2-3× the 5 points/s passive rate.
- **It learns your games.** Each time you call the same ult again, the gap between
  calls tunes the rates. They are saved in `userdata/ult_rates.json`, and the phone
  footer shows how many samples it has.
- **It's an estimate, never a fact.** It knows when you saw the ult, not their damage.
  If an enemy is getting fed, assume earlier.
- **How to use it, as coaches teach it:**
  - Start by calling only 1-3 ults: your mirror, then one engage, one kill and one
    save ult.
  - Say `won fight` / `lost fight` at the end of every fight.
  - Say `new round` when sides swap.
  - Call `swap <ult>` when you see a swap.
  - When you die, glance at the kill cam's ult % and call it, e.g. `gravity eighty`.
    It's the only real number you'll get.
  - Expect about the same number of ults as last fight, plus one or two.

## Mic test

`python -m ow_assist --mic-test --model <model> --device N` asks for every call word, one
at a time. It uses the same recognizer, grammar and push-to-talk as a match.

- `--mic-test gravity nano blade` tests only those words, e.g. after you change one.
- `--rounds 2` asks for each word twice, to catch words that only sometimes fail.
- Ctrl+C stops early and still prints the report.
- `--text --mic-test` lets you type instead, to try it out without a mic.

Only the recognized text is kept, never audio.

## Match review

Every call is logged with what the tool was estimating at that moment, in
`userdata/match_log.jsonl` (turn it off with `"match_log": false`). After playing:

`python -m ow_assist --review` (last match), `--review 5`, or `--review all`

It shows:
- **Each ult that was used again**, how long after the last time, against the tool's
  "may be up" and "likely" times. It's marked **EARLY** (came back before "may be
  up"), *in the window*, or later. Later usually means they held it, or a call was
  missed.
- **Each kill-cam call:** the real % next to what the tool estimated.
- **Enemy ults per fight.**
- **A verdict:** whether the estimates run fast or slow, and what to change.

Undone calls are left out. A match starts when the app starts, on `reset` /
`new match`, and on `gg ...`, so say `gg win` / `gg loss` after each game.

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
cooldowns that stop your dive (sleep, cryo) or save your target (Suzu, lamp,
grip, nade's anti-heal decides duels). Edit `data/abilities.json` to change
them. Add or remove abilities and aliases.

> **The cooldown numbers are unverified estimates.** Check each one against the
> current patch and fix it in `data/abilities.json`.

## Settings (`data/settings.json`)

- `ult_possible_rate` / `ult_likely_rate`: points per second used for "may be up" and
  "likely up" (defaults 16 and 11). `ult_learn_rates`: tune them from your games.
- `ult_swap_kept_fraction`: charge kept on a hero swap (0.15).
- `ult_repeat_ignore_seconds`: the same ult called again within this many seconds
  counts as one call (8).
- `ult_callout_tiers`: which tiers get "may be up" callouts (`["engage", "kill"]`).
- `call_lag_seconds`: how many seconds are subtracted from each timer,
  because you speak after the ability is used.
- `fire_on_partial`: acts on a call before you finish speaking, which is
  faster. Set it to `false` if you get misfires.
- `speech_rate`: how fast callouts are spoken.
- `window_topmost`: keeps the optional window above other windows.
- `phone_port`: the port the phone view uses.
- `match_log`: log every call for `--review` (on by default).
- `push_to_talk`: see above. `ptt_tail_seconds` is how long it keeps listening after you release.

## Prototype test plan

Play about 5 matches and track only 1 or 2 abilities, starting with `sleep`.
Then check three things:
- Did calling feel natural?
- Did the recognizer misfire?
- Did the callouts help or get in the way?

Then do the mic test, and 5 matches calling 2-3 enemy ults plus `won fight` /
`lost fight`, the kill-cam % when you die, and `gg win` / `gg loss` at the end:
- Run `python -m ow_assist --review 5`. Were most repeat ults "in the window"?
  Lots of EARLY means the estimates are too slow.
- Did anything get misheard mid-match that the mic test didn't catch?
- Was the fight summary short enough to hear mid-game?

## Tests

`python -m pytest`
