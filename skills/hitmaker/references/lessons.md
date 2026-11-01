# Lessons (each one cost real takes)

## Process
- **The goal is an inspired work, never a clone.** The user: "what's the point if it's just a copy?" Measure the reference
  for feel and devices, then write new notes and words. The upload demo is always a fresh composition.
- **Remix of a remix → start from the original song.** Building the remix first gave "generic dubstep with rapping on
  top". The user's correction: make the song great in Suno first, then chop and remix it.
- **Text-only prompts hit the genre prior.** 10+ takes of a careful 950-char prompt for a Bassnectar/G Jones track all
  came back with the same stock pluck, growl and kit (spectral flux 0.39-0.57 vs 1.94 for the reference). A rendered MIDI
  recreation used as Cover audio fixed it, and the user said "Fire, that's what I want".
- **Measure the user's takes when feedback is "generic".** Compare spectral flux, high-band share and timbre cosine with the reference.
  Takes more similar to each other than to the reference = the model's prior. Change the anchor; more words won't help.
- **The user expects you to look the tempo up.** Then verify, because databases are often 0.5 BPM off or list a
  double-time alias.

- **Suno rejects uploads that match its catalog.** The transcribed GodLovesUgly demo (similarity 0.92) was rejected as
  "matches a song in our catalog". The Chromatek transcription got through, but don't rely on that. Compose the upload demo from
  measured facts (new key, tempo, notes) and gate it with `similarity`.

## Analysis
- Chromatek read 107.7 BPM in every librosa estimate. It's 160 BPM halftime (107.7 is the 2:3 alias). Grid-lock the drum stem.
- GodLovesUgly: databases said 183 and 91.5; a coarse lock said 91.0; the fine drift sweep found 91.04 (2 ms drift vs 67 ms at 91.0).
- A downbeat one beat off, and a grid phase 30-40 ms late, both happen. The backbeat check and the kick/snare re-centring fix them.
- Swing ≥ 75% = phase error. Real MPC hip-hop swing measured 65%.
- Vision models invent textbook structures from spectrograms. Use the numbers.
- Whisper hallucinates loops on hooks and chants. Use chunked transcription + loop flags.
- A remix's vocal density is nothing like the original's: chopped to about 3 words/bar vs about 13 syllables/bar.

## Suno
- The style field silently truncates at 1000 chars (a prompt cut off at "vinyl spinbacks").
- Variety above Off rewrites your style per take. Personalize only acts when Variety > Off.
- Genre words pull priors: "dubstep" at 108 BPM gave jazz/blues with acoustic drums. Use the tag Suno knows for that
  tempo and feel, plus the right Exclude list.
- Audio Influence 70-75% with a plain demo: Suno re-produces the sound while keeping the riffs and arrangement.

## Ethics / safety
- Don't redistribute copyrighted audio. Analyze it locally and link the official upload.
- Never quote or reuse original lyrics. Transcripts stay private, and new lyrics share 0 4-grams with the original.
- Don't put artist names in Suno fields. Describe the sound.
