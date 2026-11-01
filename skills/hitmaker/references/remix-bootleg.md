# Remix / bootleg phase

## Why the original comes first
A remix of a famous song works because the song is already strong: verses, a hook, signature vocal moments, a
recognisable loop. Zeds Dead x Subtronics' GodLovesUgly remix keeps Slug's best lines, the hook and the mood.
Then it rebuilds the beat into bass-music drops. Remix a demo with no song in it and you get "generic dubstep
bass with someone rapping on top the whole way". So: build and polish your own song first (Phase 1), then remix it.

## What a remix keeps vs replaces (measured on GodLovesUgly → ZD x Subtronics)
| | Original (Atmosphere) | Remix |
|---|---|---|
| Tempo / key | 91.04 BPM, G minor, 65% swing | 95 BPM straight, G minor (sped about 4%) |
| Beat | MPC boom bap, backbeat | backbeat kept, dubstep/riddim drops |
| Vocal | full dense verses (~3.3 syllables/beat), skit with kids, hook | chopped to about 3 words/bar in verses, 1-3 single words/bar in drop 2 |
| Hook | repeated title phrase in the hook section | the same hook dropped at the end of drop 1, end of verse 2, inside drop 2 |
| Arrangement | intro skit → verses/hooks | intro → verse → build → drop (stop, 1 bar) → verse → drop (stop) → outro |
| Harmony | piano loop: minor → diminished passing → dominant b9 | bass riff built from the same flat-2/chromatic colours |

## Remix procedure
1. Run `tempo`/`analyze`/`voices` on the **target remix** to get its section map, chop density per section and hook placements.
2. Run the same on **the user's best Phase-1 take** (their song) to find the hook timestamp, the strongest 1-2 bar vocal
   phrases, the kids/skit lines and the piano loop bars.
3. Measure the remix's drop sound design (bass stem, drop windows):
   - LFO rate: amplitude-modulation spectrum of the bass stem → rate in beats (1/4, 1/8, 1/8 triplet, 1/16).
   - Whistle/sine lead: spectral peak tracking 1-5 kHz; note the pitch range and any pitch-LFO (vibrato rate/depth).
   - Riddim-ness: how many distinct bass notes per 4 bars (riddim = 1-2 notes, rhythm carries it), and gaps per bar.
   - Stops: 1-bar silences before the bass re-enters.
4. In Suno, on the user's song:
   - **Sample → Chop** the hook phrase (keep pitch+speed On), with a style brief for the remix and the remix lyrics map
     (verse = sparse chopped phrases, drop = single words / hook).
   - Or **Cover** a bass-palette demo (`render --palette bass --drops ...`) with the remix lyrics map. Use Mashup to blend
     the user's song with that demo when Cover loses the vocal identity.
   - v6 Simple mode can do it in one request: "Sample the hook at 1:12 and the kids at 0:05, chop them, rebuild at 95
     BPM with riddim drops: sine-whistle lead with fast LFO, one-note wobble bass, one-bar stops before each drop."
5. Iterate with the user (`references/suno-playbook.md`). Keep the vocal identity, replace the beat.

## Sound vocabulary Suno responds to (bass remixes)
riddim (repetitive one-note bass, rhythm carries it), sine whistle lead, pitch LFO, LFO wobble at 1/8 triplets,
formant growl, reese, talking bass, tearout, metallic screech, sub drop, one-bar stop, tape stop, reverse vocal
into the drop, vocal chop stutter, halftime, backbeat. Name the rate and the role ("one-note riddim bass wobbling in
1/8 triplets under a whistling sine lead"). A pile of adjectives won't get you there.
