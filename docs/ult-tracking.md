# Ult tracking: what coaches teach, and how this tool uses it

This sums up research done in November 2026 across coaching guides, Blizzard forum
threads, Reddit guides, patch notes, the Overwatch wiki and other trackers (LoL and
Dota timers, Overwatch tools). Sources are at the bottom. Anything marked
**unverified** came from a single weak source or from search snippets, because many
of these pages could not be opened directly.

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
- **Report what they still have, not only what they used.** Report it after the
  fight or in spawn, in short calls: "They used grav. Care nano."
- **Don't narrate charge percentages.** Call only what changes a decision.
- **Review.** Watch replays in third person, where ult charge is visible, and check
  which ults you missed.

## 2. When does an ult come back?

| Fact | Value | Confidence |
|---|---|---|
| Passive charge | about 5 points/second for every hero, from when the doors open | wiki |
| Damage and healing | about 1 point per HP dealt or healed to enemy heroes; little or nothing from barriers and turrets | community testing |
| Tanks | damage or healing done to a tank gives less charge (−40% as of the Feb 2026 sub-roles patch; sources conflict) | **unverified** |
| Hero swap | keeps at most **15%** of the new hero's cost (30% → 25% → 15% since 2023) | patch notes |
| New round | everyone starts at **0**. That covers each Control round and the side swap on Escort/Hybrid | wiki |
| Same round | charge carries through checkpoints, deaths and overtime | standard behaviour |
| Coach rules of thumb | "decent damage in two fights → probably has ult"; fast ults every 1-2 fights, medium every 2-3; "if enough time passes, assume it's full" | forums, guides |

Old OWL data (2018) put Tracer at about 6 pulses per 10 minutes, roughly 14 points/s
at today's cost. That is a pro game, though, and an upper bound.

### The tool's model

- An ult called at time T is **possible** again after `cost / 16` seconds and
  **likely** after `cost / 11` seconds (both rates are settings). For Grav (2500)
  that is about 2:36 and 3:47.
- It always says "may be up", never "has". It knows when the ult was used, not how
  much damage the player has done since. An older Overwatch tracker, Visor, was
  criticised for presenting guesses as facts and changed its wording for that reason.
- `swap <ult>` starts that hero at 15% charge. `new round` puts everyone back to 0
  and keeps the comp, since it usually stays the same.
- **Self-calibration.** When you call the same ult twice, the gap between the calls
  shows how fast this player charged. Gaps under 20 s count as a double call. Gaps
  longer than 2.5× the "likely" time probably hide a missed call. Both are ignored.
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
- **Death cam and kill cam** show the enemy's ult status.
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

- Vosk only hears words in its model's vocabulary and **silently drops the rest**.
  The tool now checks every alias at startup and warns you. Words likely missing
  from the small English model include grav, nade, suzu, cryo, kitsune, panopticon
  and nerf. Each of those has a plain-English second alias (gravity, grenade, bell,
  ice block, fox, prison, self destruct).
- Use distinct words. These pairs sound alike or clash:
  - nano / nade
  - amp / lamp (so Baptiste's ult is only "amp matrix")
  - surge (Zarya and Orisa)
  - blade (Genji and Vendetta: "sunder" for Vendetta)
  - bomb (D.Va, Tracer, Sierra)
  - matrix (also D.Va's Defense Matrix)

  Two-syllable words are recognized more reliably than one-syllable ones.
- Team comms contain the same words as your commands, so use **push-to-talk**.
  Saying an ult twice within 8 seconds is treated as one call.

## Ult costs used (points)

The costs live in `data/abilities.json`. Values come from the wiki table as of about
July 2026, adjusted for later patch notes:

- Hazard +7% (Aug 2026)
- Winston −6% (Aug 2026)
- Domina −6% (Sep 2026)

**Least sure:** Domina, Hazard, Winston, Mercy (raised in June 2026, amount
unclear), Roadhog (reworked Oct 2026), Reaper and Torbjörn (third-party source
only) and Doctrine. D.Mon is unknown, so it shows only time since used. Check any
of them in a custom game or on the wiki and edit the file.

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

Mechanics and costs:
- Overwatch wiki, "Ultimate ability": https://overwatch.fandom.com/wiki/Ultimate_ability
- Blizzard patch notes, 2023/02 and 2023/12 (swap charge cap) and 2026/02, /08, /09, /10: https://overwatch.blizzard.com/en-us/news/patch-notes/
- Old OWL ult-rate analysis (2018): https://medium.com/@Cheraws/tracer-generates-a-blistering-6-pulse-bombs-per-10-minutes-d7067d9036bd
- Workshop code JZKVS, "Ultimate Charge Points Counter", useful for calibration: https://workshop.codes/JZKVS

Other trackers and voice design:
- Barrel Timer (offline Vosk voice timers for LoL): https://github.com/R3ner/Barrel-Timer
- TIMER.GG (voice timers with spoken lead-time reminders): https://github.com/samc/timergg
- dota_timer_assistant: https://github.com/vort3/dota_timer_assistant
- Visor's wording change to "may have ult": https://medium.com/visorgg/listening-to-feedback-and-building-for-you-489ef67287cf
- Disney Research on keyword spotting in multiplayer voice games: https://la.disneyresearch.com/wp-content/uploads/Multi-party-Language-Interaction-in-a-Fast-paced-Game-Using-Multi-keyword-Spotting-Paper.pdf
