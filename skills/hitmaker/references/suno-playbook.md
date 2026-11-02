# Suno playbook (v6, Nov 2026)

## Fields and limits
- Style: **1000 chars max, truncates silently**. Natural-language brief, 600-950 chars. Order: tempo + genre + key →
  the hook/riff in plain musical words → groove/drum mechanics → arrangement devices → vocal persona → mix.
- Lyrics: about 3000 chars. Section tags carry descriptors: `[Drop 2: heaviest bass, single chopped words only]`.
- Exclude: the genre priors you keep getting (e.g. `jazz, blues, rock guitar, acoustic drums, four on the floor,
  house, trance, pop, lo-fi`), plus `singing, autotune, melodic rap` for rap songs.
- No artist names anywhere. Describe the sound.

## Settings by workflow
| Workflow | When | Settings |
|---|---|---|
| **Cover, all in one** (default) | demo + lyrics → finished song | v6, Audio Influence 70, Style Influence 75, Weirdness 30, Variety Off, Personalize Off, Max Mode On, Instrumental Off |
| Cover, instrumental only | want the beat first | same, Instrumental On |
| Add Vocals (Pro/Premier) | keep an instrumental exactly, add a performance | lyrics + vocal persona only, Audio Strength about 80 |
| **Sample → Chop** | remix: slice a section of a song and rebuild around it | select region; Chop = rearranges slices through the song; As-is = no instruments on top; Blend = mixed with new parts; keep pitch+speed On for vocal chops |
| Mashup | combine two songs (e.g. your song + your bass demo) | pick both and describe what to take from each |
| Replace Section | fix one part, keep the rest | highlight 15-20 s, rewrite tag/lyrics for that part |
| v6 Simple mode | multi-step edits in plain words | "Sample the hook at 1:12, chop it, build a riddim drop under it at 150 BPM halftime" |

**Variety must be Off** with an engineered brief. Normal/High/Extra/Max rewrite your style text on every take.
Weirdness: the audio already carries the character, so keep it low (20-35). Change one slider per round.

## Tuning table (what you hear → what to change)
| Symptom | Fix |
|---|---|
| Riff/groove lost, generic beat | Audio Influence +5 |
| Sounds like the plain demo synths | Audio Influence −5 or Style Influence +10 |
| Feels slower/faster than the reference | BPM first in style text; Weirdness ≤ 30; check the demo locks at that BPM |
| Rapper sings | `[Rapped]` in verse tags; add "melodic rap, singing" to Exclude |
| Rapper fills every gap | fewer lines; "leave space between lines" in tags; blank lines between couplets |
| Leans soft, jazzy, introspective | name era and edge ("hardcore 90s, grimy, menacing"); Exclude jazz, jazzy, smooth, soft, mellow, lo-fi, chillhop, neo-soul, R&B, conscious rap; make the focal bass loud in the demo |
| Wrong genre (jazz, rock, house) | add it to Exclude; name the genre Suno knows ("boom bap", "midtempo bass", "riddim") |
| Hook doesn't stick | shorter hook line; repeat it more often; put it at section ends |
| Style ignored after the 1000th char | count characters; cut adjectives, keep the musical facts |

## Iteration loop with the user
1. Give one config. The user makes 4-6 takes. Ask for the best 1-2 as audio files plus blunt notes.
2. Measure the takes against the reference when the notes are vague: tempo lock, spectral flux (static vs evolving),
   high-band share, vocal density from `voices`. Compare numbers, not impressions.
3. Change one or two things at a time and say exactly what changed and why.
4. If takes are more similar to each other (timbre cosine 0.93-0.97) than to the reference (0.85), the genre prior is the
   ceiling. Strengthen the audio anchor (better demo, higher influence); more adjectives won't help.
