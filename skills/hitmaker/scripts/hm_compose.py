"""hitmaker compose: write an ORIGINAL demo (MIDI) from measured facts + a plan file.

Why: a transcription of a famous record is a copy, and Suno's upload check rejects it ("matches a song in our
catalog"). Keep what is style (tempo feel, swing, chord colours, arrangement, drum mechanics). Write new notes:
a different key (±2-3 semitones), a different tempo (±2-4%), a new melody, voicings and bass line.

Plan file (JSON), all keys optional except bpm/key/sections:
{
  "bpm": 89, "key": "A", "mode": "minor", "swing": 0.62,
  "loop_bars": 2,
  "chords": ["i9", "i9", "viio7", "V7b9"],                # one per half bar, cycles through the loop
  "comp": "x.....x...x.....",                              # piano rhythm per bar (16 steps)
  "melody": [[0,6,7],[6,2,3],[8,8,2], ...],                # [step in loop (16ths), length, semitones from tonic(+12 = octave)]
  "bass":   [[0,10,0],[10,2,3],[12,4,5], ...],             # same format, tonic in octave 2
  "hook":   [[0,3,10],[3,3,7],[6,10,3]],                   # motif for hook sections (soft lead), loops per 2 bars
  "drums":  {"kick": [0,6,10,16,22,26], "snare": [4,12,20,28], "ghost": [15,27], "hat": [0,2,4,...]},  # 2-bar 16th steps
  "sections": [{"name": "intro skit", "bars": 4, "drums": "none", "bass": false, "keys": true}, ...]
}
optional: "bass_gate" (0.5 = short funky notes, 0.95 = legato), "piano_detune_cents" (e.g. 30 = slightly sharp, uneasy),
          "comp": "" for no chords (riff-only piano)
section flags: drums = full | light (no kick ghosts, half hats) | none ; bass, keys, hook = true/false ; fade = in/out
"""
import json, numpy as np, pretty_midi

NOTE = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4, 'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8,
        'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
# chord symbols relative to the tonic of a minor (or major) key -> semitone stacks
CHORDS = {
    'i': [0, 3, 7], 'i7': [0, 3, 7, 10], 'i9': [0, 3, 7, 10, 14], 'iadd9': [0, 3, 7, 14],
    'ii0': [2, 5, 8, 12], 'iiø': [2, 5, 8, 12], 'bII': [1, 5, 8], 'III': [3, 7, 10], 'iv': [5, 8, 12], 'iv7': [5, 8, 12, 15],
    'v': [7, 10, 14], 'V': [7, 11, 14], 'V7': [7, 11, 14, 17], 'V7b9': [7, 11, 14, 17, 20], 'VI': [8, 12, 15],
    'VImaj7': [8, 12, 15, 19], 'VII': [10, 14, 17], 'viio7': [11, 14, 17, 20],
    'I': [0, 4, 7], 'Imaj7': [0, 4, 7, 11], 'IV': [5, 9, 12], 'vi': [9, 12, 16], 'ii': [2, 5, 9],
}

def voice(stack, prev, lo=52, hi=72, root=57):
    """choose an inversion/octave of the chord closest to the previous voicing (smooth voice leading)"""
    pcs = sorted(set((root + s) % 12 for s in stack))
    cands = []
    for base in range(lo, hi):
        if base % 12 not in pcs: continue
        v = [base]
        for pc in pcs:
            if pc == base % 12: continue
            n = v[-1] + ((pc - v[-1]) % 12 or 12)
            v.append(n)
        v = sorted(v)
        if v[-1] <= hi + 4: cands.append(v)
    if not cands: return [root + s for s in stack]
    if prev is None: return min(cands, key=lambda v: abs(np.mean(v) - (lo + hi) / 2))
    return min(cands, key=lambda v: sum(min(abs(a - b) for b in prev) for a in v))

def compose(plan, out_mid):
    bpm = plan['bpm']; spb = 60 / bpm; q = spb / 4; bar = 4 * spb
    sw = plan.get('swing', 0.5)
    tonic = NOTE[plan['key']]
    root_keys = 48 + tonic if 48 + tonic >= 52 else 60 + tonic
    loop_bars = plan.get('loop_bars', 2); loop_steps = 16 * loop_bars
    def t_of(step_abs):
        k = step_abs; base = k * q
        if k % 2 == 1: base = (k - 1) * q + 2 * q * sw
        return base
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    keys = pretty_midi.Instrument(0, name='Keys'); bass = pretty_midi.Instrument(33, name='Bass')
    lead = pretty_midi.Instrument(4, name='Lead'); drm = pretty_midi.Instrument(0, is_drum=True, name='Drums')
    rng = np.random.default_rng(5)
    chords = plan.get('chords', ['i', 'i', 'iv', 'V7'])
    comp = plan.get('comp', 'x.......x.......')
    D = plan.get('drums', {})
    kick, snare, ghost, hat = D.get('kick', [0, 10, 16, 26]), D.get('snare', [4, 12, 20, 28]), D.get('ghost', []), D.get('hat', list(range(0, 32, 2)))
    bar0 = 0; sect_starts = []; prev = None
    for s in plan['sections']:
        sect_starts.append(round(bar0 * bar, 3))
        nb = s['bars']
        for b in range(nb):
            gbar = bar0 + b; lb = gbar % loop_bars
            fade = 1.0
            if s.get('fade') == 'in': fade = 0.35 + 0.65 * b / max(1, nb - 1)
            if s.get('fade') == 'out': fade = 1.0 - 0.75 * b / max(1, nb - 1)
            # keys: chord comping + top-line melody
            if s.get('keys', True):
                for st in range(16):
                    if not comp or comp[st] != 'x': continue
                    half = (lb * 2 + st // 8) % len(chords)
                    v = voice(CHORDS[chords[half]], prev, root=root_keys); prev = v
                    t0 = gbar * bar + t_of(st)
                    nxt = next((k for k in range(st + 1, 16) if comp[k] == 'x'), 16)
                    dur = max(q, t_of(nxt) - t_of(st) - 0.02)
                    for i, n in enumerate(v):
                        keys.notes.append(pretty_midi.Note(int((62 + 10 * rng.random()) * fade), n, t0 + 0.004 * i, t0 + dur))
                for st0, ln, semi in plan.get('melody', []):
                    if st0 // 16 != lb: continue
                    t0 = gbar * bar + t_of(st0 % 16)
                    vel = 96 if st0 % 4 == 0 else 80
                    keys.notes.append(pretty_midi.Note(int(vel * fade), root_keys + 12 + semi, t0, t0 + ln * q * 0.95))
            if s.get('bass', True):
                for st0, ln, semi in plan.get('bass', [[0, 14, 0]]):
                    if st0 // 16 != lb: continue
                    t0 = gbar * bar + t_of(st0 % 16)
                    base = 36 + tonic if 36 + tonic <= 47 else 24 + tonic          # tonic in octave 2 (E2..D#3)
                    acc = 112 if st0 % 4 == 0 else 96                                 # accents on the beat: funk articulation
                    bass.notes.append(pretty_midi.Note(int(acc * fade), base + semi, t0, t0 + ln * q * plan.get('bass_gate', 0.95)))
            if s.get('hook', False):
                for st0, ln, semi in plan.get('hook', []):
                    if st0 // 16 != lb % 2: continue
                    t0 = gbar * bar + t_of(st0 % 16)
                    lead.notes.append(pretty_midi.Note(78, root_keys + 12 + semi, t0, t0 + ln * q * 0.95))
            dmode = s.get('drums', 'full')
            if dmode != 'none':
                for st in range(16):
                    s2 = (gbar % 2) * 16 + st
                    t0 = gbar * bar + t_of(st)
                    if s2 in kick and not (dmode == 'light' and s2 % 8 != 0): drm.notes.append(pretty_midi.Note(int(108 * fade), 36, t0, t0 + 0.1))
                    if s2 in snare: drm.notes.append(pretty_midi.Note(int(112 * fade), 38, t0, t0 + 0.1))
                    if s2 in ghost and dmode == 'full': drm.notes.append(pretty_midi.Note(int(40 + 12 * rng.random()), 38, t0, t0 + 0.06))
                    if s2 in hat and not (dmode == 'light' and st % 4 != 0):
                        drm.notes.append(pretty_midi.Note(int((60 + 30 * (st % 4 == 0) + 12 * rng.random()) * fade), 42, t0, t0 + 0.04))
        bar0 += nb
    pm.instruments += [keys, bass, lead, drm]
    pm.write(str(out_mid))
    return dict(bpm=bpm, sections=sect_starts, duration=round(bar0 * bar, 2), midi_shift=0.0, downbeat=0.0,
                key=f"{plan['key']} {plan.get('mode', 'minor')}", swing=sw, feel='backbeat',
                section_names=[s['name'] for s in plan['sections']], piano_detune_cents=plan.get('piano_detune_cents', 0))
