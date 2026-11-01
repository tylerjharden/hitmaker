# Pipeline stages: what each one does and how to read it

All stages read/write one project folder. `project.json` accumulates: `bpm, downbeat, feel, swing, sections, key,
tuning_cents, midi_shift`. Rerun any stage after fixing an upstream value. Downstream stages read the new numbers.

## fetch
- `--query` lists YouTube + SoundCloud candidates with uploader and duration. Pick the **official** upload
  (artist or label channel, album-length duration). Remix/extended/fan uploads have different arrangements.
- Blocked sources: YouTube bot wall on servers, DRM on some SoundCloud tracks. Artist Bandcamp
  (`https://<artist>.bandcamp.com/track/<slug>`) streams the full track as 128k MP3, which is plenty for analysis.
- Never send the downloaded audio to the user or publish it. Link the official page.

## stems
demucs `htdemucs`. About 2 min CPU for a 4 min song. Bass music: formant growls can land in `vocals.wav`, and vocal bleed
can land in `drums.wav`. The later stages are built to tolerate that.

## tempo   (the most important stage)
1. Seed with the BPM you looked up (`--bpm 91 183`). Every seed also tests ×2, ×½, ×⅔, ×1.5 within ±span.
2. Coarse grid lock: score = mean onset strength on a 16th grid ÷ overall mean. The right tempo wins clearly
   (GodLovesUgly: 91.0 → 1.80, 183.5 → 1.26). Close top two = check by ear or `--force`.
3. Downbeat from kick/snare beat profiles: backbeat = kick 1 and 3, snare 2 and 4. Halftime = snare on 3.
4. **Fine tempo**: sweep ±0.15 BPM in 0.01 steps and take the tempo whose kick/snare phase is flattest across 4 windows.
   Report under 25 ms = locked. GodLovesUgly: 91.00 drifted 67 ms, 91.04 drifted 2 ms. Without this, late sections
   transcribe with kicks on odd 16ths.
5. Swing = histogram peak of off-beat hat positions within each 8th: 50% straight, 58-62% MPC lazy, 66% triplet.
   Readings of 75% or more mean the grid phase is wrong. Fix the phase first.

## analyze
- Sections: agglomerative segmentation on chroma+MFCC (`--k` = number of sections, 12-16 for a 3-4 min song), snapped to bar lines.
  Override with `--sections` when you know the boundaries.
- Per section: RMS per stem, sub share (<100 Hz), vocal_on fraction. How to read them:
  drums near 0 = intro/break/stop. Bass up and sub up = drop. vocal_on ≥ 0.75 = rapped verse.
  vocal_on about 0.3 with a normal mix = hook, skit or sparse ad-libs.
- Vocal map: one character per bar. Shows where vocals sit relative to the beat sections.
- Key: Krumhansl profile on bass+other. Cross-check with the top pitch classes (flat-2 or raised-7 colours show up there).
- Tuning per stem (cents vs A440): a vocal 20+ cents away from the instruments = pitched or sped acapella.
  Sampled-piano hip-hop often sits 20-40 cents sharp or flat as a whole.

## notes
pyin on the harmonic part of one stem, one row per bar at `--step` beats. Use it on the **bass** for the riff and on
**other** for the piano/keys loop. Chord colour = top 3 chroma pitch classes per half bar. Polyphonic voicings are
approximate. Describe them as colours ("minor, then a tense diminished passing chord, then a dominant with a flat 9").

## voices
- faster-whisper `small.en` on the vocal stem in 6-bar chunks, VAD off, anti-hallucination thresholds,
  words with probability under 0.25 dropped, back-to-back 3-gram repeats collapsed and flagged.
- Output per phrase: section, time, bar.beat where it starts, syllables, syllables per beat, voice register
  (median f0: under 165 Hz low male, 165-240 mid, over 240 high = child or female; children often 350-500 Hz).
- Per section totals and hook candidates (repeated 3-grams by time). Text is withheld. Transcript is saved to `.private/`.
- Typical rap: 3-4 syllables per beat at 85-95 BPM (12-16 per bar). A remix chop: 1-2 per beat with long gaps.

## transcribe
basic-pitch on bass (28-300 Hz) and other (keys below MIDI 79, lead at 79 and above). Notes are quantized to the swung 16th grid and
shifted so the first downbeat is a bar line. Drums: per-section 2-bar templates. The main snares come from the verified
feel, plus 2 ghost notes and the top kick/hat steps. Sections with near-silent drum stems get no drums. **No vocal MIDI.**

## render
- `hiphop`: piano with inharmonic partials + hammer noise, warm round bass, dusty kit, vinyl crackle, 12-bit crunch.
- `bass`: 5-voice reese + formant growl with per-drop LFO rates (`--drops` = section indexes), lead, risers into drops.
The demo only has to carry riffs, groove and arrangement into Suno Cover. It's meant to sound plain.

## validate
Compares the original's instrumental (drums+bass+other) with the demo:
harmony (chroma cosine per 2 s) median ≥ 0.85, arrangement (5 s energy contour correlation) ≥ 0.6,
and the demo grid-locks hardest at the project BPM. Earlier results: Chromatek 0.93 / 0.62, GodLovesUgly remix 0.90 / 0.78.

## compose  (the demo you upload)
Plan file (see `templates/plan_example.json`): bpm, key, mode, swing, loop_bars, chords (one per half bar: i9, VImaj7,
iiø, viio7, V7b9, bII, ...), comp rhythm, melody/bass/hook as [step, length, semitones], 2-bar drum steps, and sections with
drums full/light/none, bass/keys/hook on or off, fade in/out. Write the sections to fit YOUR lyrics (one rap line = one bar).
Voicings use smooth voice leading. Notes sit on the swung grid.

## similarity  (copy-risk proxy)
Beat-synchronous chroma (tempo-invariant), 8-beat windows, best match over every original window and all 12 keys.
Calibration on GodLovesUgly: the rejected transcription scored 0.92, unrelated tracks 0.79-0.81, and the composed demo 0.80 (accepted target).
It's a proxy: Suno's fingerprint check is unknown. Ship at 0.82 or below, and if Suno still rejects, change the loop more.

## check
Style ≤ 1000 chars, lyrics ≤ 3000, syllables per line by section, shared 3/4-grams with the original transcript.
Exit code 1 on failure, so it works as a gate.
