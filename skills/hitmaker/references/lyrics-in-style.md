# Writing lyrics in an artist's style without copying them

Goal: Suno performs *your* words with the artist's flow, tone and song devices. You copy the shape (measured).
You never copy the words.

## 1. Build the lyric spec from measurements
From `analyze` + `voices`, fill one row per section:

| section | bars | who | syllables/bar | phrase starts | phrase length | rhyme | devices |
|---|---|---|---|---|---|---|---|
| intro (0:00-0:36) | 13 | 2 kids, high register | 8-12, chatty | anywhere | short | none | skit, overlaps the beat intro |
| verse 1 | 22 | rapper | 13 | beat 1 or a pickup | 1 bar | couplets + internal | storytelling |
| hook | 12 | rapper + sung voice | 6-8 | beat 2 | 2 bars | repeated title line | chant, call and response |

Measure the rate in syllables per **beat**, which carries across tempos. Count bars from `analyze`. Find hooks in the
repeated-3-gram times from `voices`, and who speaks from the register column.

## 2. Persona and lane (ask the user, or decide)
- Artist lane in plain words: e.g. "self-deprecating Midwestern storyteller, deadpan wit, specific everyday details,
  vulnerable underneath the jokes, conversational, dense internal rhyme, lines that land on a twist".
- Theme: never the original's theme verbatim. Find a sibling theme with the same emotional engine.
  (GodLovesUgly's engine: claiming worth because of your flaws. "Crooked Teeth" keeps the engine and changes the images.)
- Title/hook: short, concrete, singable, and repeatable 3-8 times without wearing out.

## 3. Devices to recreate (originals have them, generic Suno songs don't)
- **Skits / spoken intros**: write them as dialogue lines under a tag like
  `[Intro skit: two little girls teasing the rapper, playground voices, rain, no beat yet]`.
  Children's voices: Suno can do `[Child voices]` / `(kids laughing)`. Keep the lines short and chatty.
- **Call and response**: main line, then `(echo)` in parentheses. Suno renders parentheses as backing or ad-lib vocals.
- **Sung hook over a rap song**: `[Hook: sung by a soulful female voice, rapper answers]`.
- **Ad-libs and asides**: parentheses, at most 1 per 2 lines.
- **Stops and breaks**: `[Break: beat drops out for one bar, rapper keeps going a cappella]`.
- **Signature line placement**: the punchline lands on the last bar before a section change.

## 4. Writing rules that help Suno rap
- One line = one bar. Blank line between couplets in sparse sections only.
- Match the measured syllables per bar ±2. Dense verses: 12-16 at 85-95 BPM. Don't pad with filler words.
- Put stresses on the beats: read it aloud over the demo. Multi-syllable rhymes at line ends, internal rhymes mid-line.
- Spell out numbers and acronyms. Avoid odd proper nouns unless you've tested them.
- Put a vocal anchor at the top: `[Vocal: male rapper, <register>, <delivery>, <pocket>]`.
- Put `[Rapped]` or "rapped" in verse tags. Put "melodic rap, singing" in Exclude unless a sung hook is wanted, and if it is,
  tag only that section as sung.

## 5. Gate
`hitmaker.py check --lyrics lyrics.txt --original-words proj/.private/vocal_words.json` must show 0 shared 4-grams.
A 3-gram match is only OK for common phrases ("I don't know"). Remove anything that echoes a memorable original line.
