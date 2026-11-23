# Ult tracking: what coaches teach, and how this tool uses it

This sums up research done in November 2026 across coaching guides, Blizzard forum
threads, Reddit guides, patch notes, the Overwatch wiki and other trackers (LoL and
Dota timers, Overwatch tools). Sources are at the bottom.

What was read in full or tested directly:
- **ult costs**, against the wiki and Blizzard's 2026 patch notes;
- **call words**, against the speech model itself, including a recognition test;
- **Dignitas's ult tracking guide**, read in full; it shaped the fight summary and
  the kill-cam calls.

What couldn't be read, and why:
- **YouTube** sends this cloud server to Google's bot check, so no transcripts.
- **Reddit** requires a login for scripts.
- **The Blizzard forums** rate-limited after two threads.

Other coaching points in sections 1, 3 and 4 come from search summaries. Anything
marked **unverified** came from a single weak source. To add videos, paste their
transcripts into the chat.

## 1. How to practise

- **Start small.** Track your mirror first (if you have your ult, they probably have
  theirs). Then your duo partner's mirror, then the big ults. Trying to track all five
  from the start "is going to be a migraine".
- **Track three, one of each kind:**
  - one **engage** ult that starts fights (Grav, Shatter)
  - one **kill** ult that ends them (Blade, Pulse, Nano)
  - one **save** ult that stops your win condition (Trans, Beat)

  The tool tags every ult with one of these tiers, plus **minor**.
- **Count ults per fight.** If they used 2 last fight, expect 2 or 3 next fight.
- **After every fight, three steps (Dignitas):**
  1. what they used;
  2. what they still have;
  3. what they'll most likely use next.

  Their example: "Grav was used, Genji and Ana have ults, so expect Nano-Blade." The
  tool's fight summary follows this order: "They used gravity. May have nano and
  blade. Watch for nano blade." (the tool says "gravity", see section 5)
- **Don't narrate charge percentages.** Call only what changes a decision.
- **Review.** Watch replays in third person, where ult charge is visible, and check
  which ults you missed.

## 2. When does an ult come back?

| Fact | Value | Confidence |
|---|---|---|
| Passive charge | about 5 points/second for every hero, from when the doors open | wiki |
| Damage and healing | about 1 point per HP dealt or healed to enemy heroes; little or nothing from barriers and turrets | community testing |
| Tanks | damage or healing done to a tank gives 40% less charge (raised from 20% in July 2026) | patch notes |
| Tactician supports | can no longer bank charge past 100% (June 2026) | patch notes |
| Hero swap | keeps at most **15%** of the new hero's cost (30% → 25% → 15% since 2023) | patch notes |
| New round | everyone starts at **0**. That covers each Control round and the side swap on Escort/Hybrid | wiki |
| Same round | charge carries through checkpoints, deaths and overtime | standard behaviour |
| Coach rules of thumb | "decent damage in two fights → probably has ult"; fast ults every 1-2 fights, medium every 2-3; "if enough time passes, assume it's full" | forums, guides |

### Measured: Overwatch League charge rates

The league's official Stats Lab files (2018–2020, every player, hero and map) record
"Time Building Ultimate", "Ultimates Earned" and "Time Holding Ultimate". Combined
with each hero's cost at the time (wiki history) and the old passive rate of 4.46
points/s (confirmed from Dignitas's Tracer and Lúcio pure-passive times), they give
real charge rates. This is based on about 250,000 ults:

| | Charge rate as a multiple of passive |
|---|---|
| All heroes, median | **4.0×** (middle 60%: 3.3× to 4.9×) |
| Supports | 5.0× (constant healing) |
| Tanks / damage | 3.7× |
| Fastest | Moira 7×, Brigitte 6×, Zenyatta 5.5–6×, Baptiste 5.5× |
| Slowest | Orisa 2.8×, Winston 2.9–3.4×, Mei 3.1–3.3×, Reinhardt 3.2–3.7× |

Pros also **held a full ult for about 26 seconds** (median) before using it:
- the longest holders were Bastion (47 s), Roadhog (43 s), Pharah (40 s), Cassidy
  (37 s), Genji, Reaper and Zenyatta (35 s);
- the quickest were Moira (8 s), Widowmaker (10 s) and D.Va (13 s).

Limits of this data: it's pro play from the 6v6 era. Ranked has less constant
fighting, and today's tank penalty (−40% charge for hitting tanks) slows things
further. Heroes reworked since then (Orisa, Doomfist, Sombra, Symmetra, Bastion,
Roadhog, Moira) and heroes released after 2020 use their role's average.

### The tool's model

- An ult called at time T is **possible** again after `cost / (22 × factor)` seconds
  and **likely** after `cost / (15 × factor)`. 22 and 15 points/s are 4.4× and 3×
  passive, a little below the pro numbers above. `factor` is the hero's charge speed
  from the league data, capped to 0.75–1.4: Brigitte 1.4, Baptiste 1.38, Zenyatta
  1.36, … Winston 0.75; supports without data 1.2, others 0.95. For Grav (2500,
  factor 1.2) that is about 1:35 and 2:19.
- It always says "may be up", never "has". It knows when the ult was used, not how
  much damage the player has done since. An older Overwatch tracker, Visor, was
  criticised for presenting guesses as facts and changed its wording for that reason.
- `swap <ult>` starts that hero at 15% charge. `new round` puts everyone back to 0
  and keeps the comp, since it usually stays the same.
- **Self-calibration.** When you call the same ult twice, the gap between the calls
  shows how fast this player charged. The hero's typical hold time (from the league
  data) is subtracted first, since the gap includes time they sat on a full ult.
  Gaps under 20 s count as a double call. Gaps longer than 2.5× the "likely" time
  probably hide a missed call. Both are ignored.
  The rest are blended into the rates and saved in `userdata/ult_rates.json`.
  Because an enemy may hold an ult, observed gaps run slow. So the median sets the
  "likely" rate and the 80th percentile sets the "possible" rate.

## 3. Cues for seeing an ult you didn't watch happen

- **Voice lines.** Many heroes play a different line to enemies than to allies,
  often in their native language, so enemy ults cut through. Examples: D.Va says
  "Nerf this!" to enemies, Zarya's line is in Russian, Hanzo's and Genji's are in
  Japanese, Mei's in Mandarin, Mercy's in German, Mauga's in Samoan. Winston and
  Bastion make no words, only a roar or beeps. The details for each hero are
  partly **unverified**, so check them in a custom game.
- **Killfeed.** Ult kills show the ult's icon. An ult that kills nobody leaves no entry.
- **The kill cam** shows the enemy's real ult charge (not in tournaments or scrims).
  It's the only time you see the real number. Call `<ult> eighty` or `<ult> full`
  and the estimate jumps to it. When that ult was called before, the gap also
  teaches the tool this lobby's charge rate.
- **Mirror rule (Dignitas).** If you have your ult, your counterpart probably has
  theirs. If they're landing multi-hits and you aren't, they're ahead.
- **Tells (Dignitas, forums).**
  - Zarya pushes hard when she has Grav.
  - Genji plays unusually safe when he has Blade.
  - Expect panic ults from players about to die.
  - Teams tend to get ults around the same time.
- **Behaviour.** A player who suddenly takes aggressive angles usually has their ult.
  A player who goes passive is often close to it or holding it.

## 4. Ult economy (deciding what to do with the info)

- **Ult advantage.** If you're 2 ults up, take the fight. If you're down, stall or
  disengage.
- **Dry fights.** Fight without ults to make them spend. If they used nearly
  everything and you used nothing, the next fight is yours.
- **Win with one ult, hold the rest.** Over-ulting wins one fight and loses the next.
- **Combos and counters.** Kill the Genji to stop Nano-Blade. Hold Beat for Grav,
  and save stuns for Trance.
- **Don't feed charge.** After an early 2-3 player loss, regroup rather than trickle in.

## 5. Choosing callout words (speech recognition)

Every call was tested twice against `vosk-model-small-en-us-0.15`.

**1. Is the word in the model at all?** Vosk silently drops words it doesn't know.
It doesn't know these: grav, suzu, kitsune, deadeye, overclock, panopticon, railgun,
zarya, shion. The app re-checks at startup and warns about any alias you add.

**2. Is it heard correctly?** `tools/check_speech.py` speaks every call with a
synthetic voice, at 6 speeds, accents and noise levels. Each clip goes through the
app's real recognizer and parser. The first draft's misses:
- **valk** was heard as "bell" every time, which would log Kiriko's Suzu instead
  of Valkyrie.
- **spree** was heard as "three".
- **tectonic**, **hog**, **terra** and **e m p** were unreliable.

The final set scores 97.5%. The remaining misses are almost all in the heaviest-noise
runs, which push-to-talk avoids.

| Hero | Call | Instead of |
|---|---|---|
| Zarya | gravity | grav |
| Kiriko | bell (Suzu), fox rush | suzu, kitsune |
| Cassidy | noon / high noon | deadeye |
| Sojourn | sojourn | overclock |
| Domina | prison | panopticon |
| Mercy | valkyrie | valk |
| Venture | quake | tectonic |
| Roadhog | roadhog | hog |
| Sombra | blackout | EMP |
| Shion | slaughter | spree, satsuriku |
| Orisa | surge | terra |
| Illari | captive | captive sun (the second word was sometimes lost) |

Other rules:
- Avoid pairs that sound alike or clash: nano / nade, amp / lamp (so Baptiste's ult
  is "amp matrix"), blade (Genji vs Vendetta, who is "sunder").
- Team comms contain the same words as your commands, so use **push-to-talk**.
  Saying an ult twice within 8 seconds counts as one call.
- A synthetic voice isn't yours. Rerun `tools/check_speech.py` after changing a word,
  and trust real games over it.

## Ult costs used (points)

The costs live in `data/abilities.json`. They were checked on 2026-11-23, row by row,
against the wiki's ult table (revision 379906) and Blizzard's live patch notes for
June to November 2026. 49 of 54 matched the wiki.

The wiki is up to date through the June 16 patch, but it missed these changes, so
their costs are the wiki value times the patch %, rounded to 25:

| Hero | Wiki | Patch | Used |
|---|---|---|---|
| Hanzo | 1700 | −12% (June) | 1500 |
| Genji | 2125 | −6% (Aug 11) | 2000 |
| Venture | 1950 | −8% (Aug 11) | 1800 |
| Emre | 2750 | −6% (Aug 11) | 2575 |
| Hazard | 2150 | +7% (Aug 11) | 2300 |
| Winston | 2525 | −6% (Aug 11) | 2375 |
| Domina | 2200 | −6% (Sep 8) | 2075 |

D.Mon's cost isn't listed anywhere, so the tool shows only time since used for her.
To check a cost in game, use the Workshop code JZKVS below.

## Sources

Coaching and economy:
- Dignitas, "Be ready: a guide to ultimate tracking in Overwatch": https://dignitas.gg/articles/be-ready-a-guide-to-ultimate-tracking-in-overwatch
- Blizzard forums, "How to track enemy ults": https://us.forums.blizzard.com/en/overwatch/t/how-to-track-enemy-ults/381408
- Blizzard forums, "Ult tracking, how do you do it": https://us.forums.blizzard.com/en/overwatch/t/ult-tracking-how-do-you-do-it/344747
- Blizzard forums, "How do you shotcall effectively": https://us.forums.blizzard.com/en/overwatch/t/how-do-you-shotcall-effectively/584836
- Boostroom, "Ultimate economy 101": https://boostroom.com/blog/ultimate-economy-101-when-to-use-ults-and-when-not-to
- Boostroom, "Communication tips": https://boostroom.com/blog/communication-tips-for-overwatch-2-callouts-that-win-games
- Boosteria, "Ultimate economy": https://boosteria.org/guides/overwatch-2-ultimate-economy-track-trade-win-fights
- Heystacks, "Overwatch macro fundamentals": https://heystacks.com/doc/764/overwatch-macro-fundamentals
- r/OverwatchUniversity, "Skills guide: learning to ult track" (2018)
- Videos found but not transcribed:
  - https://www.youtube.com/watch?v=Pz_cvXznQSE
  - https://www.youtube.com/watch?v=8sC5D1dP6sU
  - https://www.youtube.com/watch?v=gKYMjs3R-bM
  - https://www.youtube.com/watch?v=TnlKqOPnARQ

Read in full this time:
- Dignitas, "Be ready! A guide to ultimate tracking in Overwatch"
- Blizzard forums, "How do you predict Zarya Grav?" (May 2026): https://us.forums.blizzard.com/en/overwatch/t/how-do-you-predict-zarya-grav/1020732
- Blizzard forums, "Ult Charge Decay" (Feb 2026): https://us.forums.blizzard.com/en/overwatch/t/ult-charge-decay/1000134. It confirms an ult is spent in full when cast, with no partial refund on death. Moira's Coalescence has been the exception since June 2026.

League data:
- Overwatch League Stats Lab, player-hero stats 2018, 2019 and 2020 (official files from Blizzard's asset server, read in full):
  - https://assets.blz-contentstack.com/v3/assets/blt321317473c90505c/bltc1b83b55692b42f4/5e4c1368de213a0dff736e29/phs_2018.zip
  - https://assets.blz-contentstack.com/v3/assets/blt321317473c90505c/blt034e0b484f2dae47/5e4c1369b6a7c40dd9c69e9f/phs_2019.zip
  - https://assets.blz-contentstack.com/v3/assets/blt321317473c90505c/blt7e0ffce2b617f0d2/5ecd3a75a84f2107d1775f56/phs_2020.zip
- Historical ult costs: Overwatch wiki "Ultimate ability" revisions of July 2018 and May 2019, read through the wiki API.
- How to find the files: https://github.com/rd11490/owl_tutorials (getting_data).

Mechanics and costs:
- Overwatch wiki, "Ultimate ability" (read through its API, revision 379906): https://overwatch.fandom.com/wiki/Ultimate_ability
- Blizzard live patch notes, June to November 2026 (read in full): https://overwatch.blizzard.com/en-us/news/patch-notes/live/2026/08/ and the months around it
- Blizzard patch notes, 2023/02 and 2023/12 (swap charge cap) and 2026/02, /08, /09, /10: https://overwatch.blizzard.com/en-us/news/patch-notes/
- Old OWL ult-rate analysis (2018): https://medium.com/@Cheraws/tracer-generates-a-blistering-6-pulse-bombs-per-10-minutes-d7067d9036bd
- Workshop code JZKVS, "Ultimate Charge Points Counter", useful for calibration: https://workshop.codes/JZKVS

Other trackers and voice design:
- Barrel Timer (offline Vosk voice timers for LoL): https://github.com/R3ner/Barrel-Timer
- TIMER.GG (voice timers with spoken lead-time reminders): https://github.com/samc/timergg
- dota_timer_assistant: https://github.com/vort3/dota_timer_assistant
- Visor's wording change to "may have ult": https://medium.com/visorgg/listening-to-feedback-and-building-for-you-489ef67287cf
- Disney Research on keyword spotting in multiplayer voice games: https://la.disneyresearch.com/wp-content/uploads/Multi-party-Language-Interaction-in-a-Fast-paced-Game-Using-Multi-keyword-Spotting-Paper.pdf
