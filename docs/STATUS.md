# Status (last updated 2026-11-24)

Branch: `claude/pensive-bell-oeo7ri`. Started as a cloud session
(`session_01FUw99vXpLAzWcmeob5MhFT`, "Ult tracking tool research"), continued on the
Kubuntu laptop.

## Done

- **Ult estimates.** Each enemy ult goes charging -> "may be up" -> "likely up".
  - Rates: 22 / 15 points/s for a median hero, times each hero's `charge_factor`.
    They come from Overwatch League 2018–20 stats: pros charged at about 4x the
    5 pts/s passive rate and held a full ult about 26 s.
  - It learns from repeat calls and kill-cam calls, subtracting the hero's hold time.
- **Calls:**
  - `<ult>`, `swap <ult>`, `<ult> fed`, `<ult> ten…ninety/full` (kill cam)
  - `won fight` / `lost fight`, giving a summary of what they used, what they may
    have, and "Watch for <combo>"
  - `status`, `new round`, `reset`, `undo`, `cancel`
- **Call words.** Every one was checked against vosk-model-small-en-us-0.15 and
  tested with synthetic speech: 97.5% across 6 voice and noise conditions.
- **Ult costs** were checked against the wiki and Blizzard's patch notes up to
  November 2026.
- **Mic test** (`--mic-test`) and **match review** (`--review`) are built.
- **Laptop setup:** `scripts/laptop-setup.sh` (one-time) and `scripts/ow-tmux.sh`
  (tmux with Claude, a shell and the app). The first run of ow-tmux.sh teleports
  this cloud session; later runs use `claude --continue`. The user already has
  tmux and a GitHub account. Setup instructions are in the README section "Working
  on it from the Kubuntu laptop".
- **Research** sources and their limits are in `docs/ult-tracking.md`.
  - Unreachable from the cloud: YouTube, Reddit, the Internet Archive.
  - These should work from the laptop's home internet.

## Next

1. **The user runs the mic test** with their own voice and headset and shares
   `userdata/mic_test.txt`. Change any WRONG words in `data/abilities.json`.
2. **The user plays 5 matches** with the app, then runs
   `python -m ow_assist --review 5`. Tune `ult_possible_rate` / `ult_likely_rate`
   from the verdict.
3. **Go through the callout list with the user.** They want to review every call
   word. The current list is in `data/abilities.json`.
4. **Optional research now that the laptop has normal internet:**
   - YouTube transcripts of coaches the user picks (`youtube-transcript-api` or
     `yt-dlp --write-auto-subs --skip-download`);
   - Reddit r/OverwatchUniversity ult-tracking guides;
   - more Blizzard forum threads (rate-limited, so go slowly).

   Fold anything new into `docs/ult-tracking.md` and the tool.

## Open questions

- Ranked charge rates vs pro rates: the defaults sit a little under pro play. The
  match review will tell.
- D.Mon's ult cost isn't published anywhere (set to 0, so only time since use is shown).
- Running on Linux: push-to-talk uses pynput, which can't see global keys or mouse
  buttons under Wayland (Kubuntu's default). Use an X11 session or leave
  `push_to_talk` off.
