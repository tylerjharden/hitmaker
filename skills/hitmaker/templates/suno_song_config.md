# <TITLE>: Suno config

Reference: <Artist - Track> (measured: <BPM> BPM, <key>, <feel/swing>)
Upload: reference_demo.mp3 (instrumental; same arrangement as the reference)

## Settings (Cover, all in one)
- Create → Upload audio → reference_demo.mp3 → Cover
- Model v6 · Audio Influence 70% · Style Influence 75% · Weirdness 30%
- Variety Off · Personalize Off · Max Mode On · Instrumental Off

## Title
<title>

## Style (≤ 1000 chars, counted: <n>)
<tempo + genre + key>. <hook/riff in plain musical words>. <groove + drum mechanics>. <arrangement devices:
intro, stops, breaks, where the hook returns>. <vocal persona: who, register, delivery, pocket, density>. <mix words>.

## Exclude
<the genre priors you keep getting>, <singing/autotune/melodic rap for rap songs>

## Lyrics (≤ 3000 chars, counted: <n>; 0 shared 4-grams with the original)
[Vocal: <persona line>]

[Intro: <what plays, who talks>]
...

## If a take misses
| Symptom | Change |
|---|---|
| riff/groove lost | Audio Influence +5 |
| sounds like the demo synths | Audio Influence −5 |
| sings instead of raps | `[Rapped]` in verse tags |
| fills every gap | cut lines, "leave space" in tags |
