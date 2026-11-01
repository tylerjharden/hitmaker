# hitmaker: a Hermes Agent skill for making Suno hits from reference tracks

Measure a reference track, render an instrumental demo that carries its riffs, groove and arrangement, write
original lyrics to its measured flow, and get a counted, ready-to-paste Suno config. Remixes too: build the
song first, then chop it.

## Install (Hermes Agent)
```
hermes skills tap add <owner>/hitmaker
hermes skills install hitmaker
bash ~/.hermes/skills/hitmaker/scripts/setup.sh      # one-time: audio/ML venv (CPU), needs ffmpeg
```
Then ask your agent: "use hitmaker to make a Suno song in the style of <artist - track>".

## What it does
`scripts/hitmaker.py` stages: fetch, stems (demucs), tempo (grid lock, alias sweep, fine drift sweep, downbeat,
swing), analyze (sections, vocal map, key, tuning), notes (riffs, piano loop), voices (flow stats, who speaks
where, hook positions; transcript kept private), transcribe (MIDI), render (hiphop/bass palettes), validate
(harmony/arrangement/tempo vs the original), check (Suno character limits, 0 shared 4-grams with the original).

Results on real tracks: the GodLovesUgly (Atmosphere) demo scored harmony 0.93, arrangement 0.95 and locked at
91.04 BPM. Chromatek (Bassnectar and G Jones) scored 0.93 / 0.62 at 160 BPM halftime.

## Rules it enforces
Never redistribute the original audio. Never quote or reuse original lyrics. No artist names in Suno fields.

MIT license.
