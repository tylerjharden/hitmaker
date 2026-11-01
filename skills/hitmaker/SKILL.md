---
name: hitmaker
description: "Use when recreating a hit's feel in Suno: original first, then remix. Analyzes tempo/stems/flow, renders a demo, writes original lyrics and the Suno config."
version: 1.0.0
author: Tyler (Suno power user) + Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [music, suno, production, songwriting, remix, hip-hop, bass-music, audio-analysis]
    related_skills: [songwriting-and-ai-music]
---

# Hitmaker

Turn a reference hit into a Suno track that captures its sound and structure without copying it. The track can be a rap song, a bass banger, or a bootleg of a remix.
The method: **measure the reference, render an instrumental demo that carries its riffs, groove and
arrangement, write original lyrics to its flow statistics, then let Suno re-produce it through Cover.**
Text-only prompts hit Suno's genre prior and come out generic. An audio anchor plus a measured brief works.

## When to use
- "Make a Suno song like <track>", "reverse-engineer <track> into a prompt", "write lyrics that flow like <rapper>"
- "Make a bootleg/remix of <remix>": **go back to the ORIGINAL song first** (see Phase order)
- Any time Suno outputs keep coming back generic for a reference-driven request

## Phase order (do not skip)
1. **Original → song.** If the target is a remix of a song, run the pipeline on the *original* first and build
   your own full song (verses, hook, skits, ad-libs, signature sounds) in Suno. Iterate with the user until it's great.
   A remix is made from a song; one built on a demo with nobody performing comes out as "generic bass with someone rapping the whole way".
2. **User picks the best take** and sends it back as audio.
3. **Remix phase.** Analyze the target remix (drop structure, lead sound design, how it chops the vocal),
   then remix the user's song with Suno **Sample → Chop** / Mashup / Cover. See `references/remix-bootleg.md`.

## Setup (once)
`bash scripts/setup.sh [venv_path]` installs: demucs, basic-pitch (ONNX), librosa, pretty_midi, faster-whisper,
yt-dlp, soundfile, scipy, numba. Needs ffmpeg and about 3 GB of disk. CPU is fine: stems take about 2 min per track, Whisper about 10 min.
Run every stage with that venv's python: `PY=<venv>/bin/python; HM=scripts/hitmaker.py`.

## Pipeline: one project folder, one command per stage
```
$PY $HM fetch   proj --query "Artist Title"        # list candidates; pick the OFFICIAL upload
$PY $HM fetch   proj --url <url>                   # saves proj/original.mp3, checks duration
$PY $HM stems   proj                               # demucs -> proj/stems/{drums,bass,other,vocals}.wav
$PY $HM tempo   proj --bpm <looked-up BPM>         # grid lock + aliases + fine tempo + downbeat + swing
$PY $HM analyze proj [--k 14 | --sections a,b,..]  # section map, vocal map, key, tuning per stem
$PY $HM notes   proj --stem bass  --start 41 --bars 4   # riff / hook notes + chord colour
$PY $HM notes   proj --stem other --start 9  --bars 4   # piano/keys loop
$PY $HM voices  proj                               # flow stats per phrase + voice register (kids/female/male), hooks
$PY $HM transcribe proj                            # reference.mid (bass, keys, lead, drums). No original vocal
$PY $HM render  proj --palette hiphop|bass [--drops 3,5]   # reference_demo.mp3 (instrumental) + stems
$PY $HM validate proj                              # harmony, arrangement and tempo-lock scores vs the original
$PY $HM check --style style.txt --lyrics lyrics.txt --original-words proj/.private/vocal_words.json
```
Stage details, thresholds and how to read each output: `references/pipeline.md`.
Files: `scripts/hitmaker.py` (all stages), `scripts/hm_render.py` (synth palettes used by `render`), `scripts/setup.sh`.

## Rules that matter most
1. **Tempo: look it up online first, then verify by grid lock.** Databases are often off by 0.5 BPM or list a
   double-time alias (GodLovesUgly is listed at 183 and 91.5; it locks at 91.04). `tempo` sweeps the aliases and then a
   ±0.15 BPM fine sweep, keeping the tempo whose kick/snare phase drifts least from start to end (under about 25 ms = locked).
2. **Check the downbeat against the feel.** Hip-hop and bass at 85-100 BPM: kick on 1 and 3, snare on 2 and 4 (`--feel backbeat`).
   Halftime: snare on 3 (`--feel halftime`). A one-beat-off downbeat wrecks the drum transcription.
3. **Don't trust vision-model reads of spectrograms for structure.** Use `analyze` numbers.
4. **Never print, quote or reuse the original lyrics.** `voices` keeps the transcript in `.private/` and prints
   only statistics. `check` must show **0 shared 4-grams** before you deliver lyrics.
5. **The reference demo is instrumental.** Your lyrics replace the original vocal; Suno performs them.
6. **Style field ≤ 1000 chars** (Suno truncates silently); lyrics ≤ about 3000. `check` counts both.
7. **Variety Off** with an engineered brief. Any other setting lets Suno rewrite your style text on every take.
8. **No artist names in Suno fields.** Describe the sound: tempo, key, riff in plain musical words, drum mechanics, vocal persona.
9. **Lead with the hook/riff, then groove, then arrangement devices, then mix.** A list of 20 sound-design items averages out to generic.
10. **Measure before writing lyrics.** Syllables per beat, where lines start, phrase length, who speaks where (`voices`).
    Remixes often chop the acapella down to about 3 words a bar. Originals may have skits, kids, sung hooks. Copy the *shape*.

## Writing the lyrics
Build a lyric spec from `voices` + `analyze` (per section: bars, syllables per bar, phrase starts, hook positions,
extra voices), then write original words in the artist's *lane*, not their lines. Procedure, persona questions and
devices (skits, call-and-response, ad-libs in parentheses, spoken intros): `references/lyrics-in-style.md`.

## Building the Suno config
Template: `templates/suno_song_config.md`. Sliders, Cover vs Add Vocals vs Sample, exclude lists, the tuning table, and
the iteration loop with the user: `references/suno-playbook.md`.

## Pitfalls
- YouTube bot-walls servers ("Sign in to confirm you're not a bot") and some SoundCloud uploads are DRM-protected.
  Try the artist's Bandcamp (`<artist>.bandcamp.com/track/<slug>` streams the full track) or ask the user for a file.
- Whisper loops on chants and sung hooks and invents text (124 "repeats" in 30 s). `voices` transcribes in 6-bar
  chunks with anti-hallucination settings and flags back-to-back repeats. Check flagged spans by ear.
- Onset envelopes peak a few ms off the true hit, and swung hats drag a 16th-grid fit. `tempo` re-centres the grid
  on kick/snare hits. A swing reading of 75% or more almost always means the grid phase is wrong.
- Drum stems in bass music carry growl/vocal bleed in the snare bands. The main snares come from the verified feel;
  only the top 2 other hits are kept as ghosts.
- `project.json` writes are atomic, but if a stage crashes, rerun that stage. Don't hand-edit half a file.
- Full list with the reasons behind each: `references/lessons.md`.

## Verification before you hand anything over
- `validate`: harmony ≥ 0.85, arrangement ≥ 0.6, and the demo locks hardest at the project BPM.
- `check`: PASS (style ≤ 1000, lyrics ≤ 3000, 0 shared 4-grams).
- Tell the user what was measured and what was guessed (e.g. polyphonic chord voicings are approximate).
- Don't redistribute the original audio. Send links to official uploads instead.
