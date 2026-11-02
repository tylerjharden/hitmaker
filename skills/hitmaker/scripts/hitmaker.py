#!/usr/bin/env python3
"""hitmaker: reverse-engineer a reference track into a Suno-ready reference demo + prompt facts.

Every subcommand reads/writes one PROJECT folder:
  original.mp3          the reference audio (you supply it, or `fetch` downloads it)
  stems/*.wav           demucs stems (drums, bass, other, vocals)
  project.json          tempo, downbeat, swing, sections, key  (grows as stages run)
  analysis.json         section stats, vocal map, riffs
  reference.mid         transcription (bass, keys, lead, drums; NO original vocal)
  reference_demo.wav/mp3  rendered instrumental reference for Suno Cover
  .private/             transcripts used only for statistics; never publish

Stages:  fetch -> stems -> tempo -> analyze -> voices -> transcribe -> render -> validate
         check (style/lyrics gate) can run anytime.
"""
import argparse, json, re, subprocess, sys, os
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np

NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']
SR_A = 22050


# ------------------------------------------------------------------ helpers
def P(project): return Path(project).expanduser().resolve()

def load_proj(d):
    f = d/'project.json' if Path(d).is_dir() else Path(str(d)+'.json')
    return json.load(open(f)) if f.exists() else {}

def _py(o):
    if isinstance(o, dict): return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_py(v) for v in o]
    if isinstance(o, np.generic): return o.item()
    return o

def save_proj(d, **kw):
    p = load_proj(d); p.update(_py(kw))
    tmp = d/'project.json.tmp'
    json.dump(p, open(tmp, 'w'), indent=1); tmp.replace(d/'project.json')   # atomic: a crash can't leave half a file
    return p

def need(d, key, stage):
    p = load_proj(d)
    if key not in p: sys.exit(f'project.json has no "{key}". Run `{stage}` first.')
    return p

def audio(d, name='original', sr=SR_A):
    import librosa
    f = d/'original.mp3' if name == 'original' else d/'stems'/f'{name}.wav'
    if not f.exists(): sys.exit(f'missing {f}')
    return librosa.load(str(f), sr=sr, mono=True)[0]

def onset_env(y, sr=SR_A, hop=128):
    import librosa
    o = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    return o, librosa.frames_to_time(np.arange(len(o)), sr=sr, hop_length=hop)

def band_rise(y, lo, hi, sr=SR_A, hop=128):
    import librosa
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop)); f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    e = np.log1p(S[(f >= lo) & (f < hi)].sum(0)); d = np.maximum(0, np.diff(e, prepend=e[0]))
    return d/(np.percentile(d, 99.5)+1e-9), librosa.frames_to_time(np.arange(len(d)), sr=sr, hop_length=hop)

def env_at(env, t, x, w=2):
    i = np.searchsorted(t, x)
    return float(env[max(0, i-w):i+w+1].max()) if 0 < i < len(env)-1 else 0.0


# ------------------------------------------------------------------ fetch
def cmd_fetch(a):
    d = P(a.project); d.mkdir(parents=True, exist_ok=True)
    if a.query:
        for src in ('ytsearch8', 'scsearch8'):
            print(f'--- {src}')
            subprocess.run([sys.executable, '-m', 'yt_dlp', '--no-warnings', '--flat-playlist', '--print',
                            '%(id)s | %(title)s | %(uploader)s | %(duration)s s | %(url)s', f'{src}:{a.query}'])
        print('\nPick the OFFICIAL upload (artist/label channel, right duration) and rerun with --url.')
        return
    subprocess.run([sys.executable, '-m', 'yt_dlp', '--no-warnings', '-f', 'bestaudio', '-x', '--audio-format', 'mp3',
                    '-o', str(d/'original.%(ext)s'), a.url], check=True)
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                                         'default=nw=1:nk=1', str(d/'original.mp3')]))
    save_proj(d, source_url=a.url, duration=round(dur, 2))
    print(f'saved original.mp3 ({dur:.1f} s). Check this matches the official duration.')


# ------------------------------------------------------------------ stems
def cmd_stems(a):
    d = P(a.project)
    subprocess.run([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '-j', str(a.jobs), '-o', str(d/'sep'),
                    str(d/'original.mp3')], check=True)
    (d/'stems').mkdir(exist_ok=True)
    for f in (d/'sep'/'htdemucs'/'original').glob('*.wav'):
        f.replace(d/'stems'/f.name)
    print('stems:', sorted(x.name for x in (d/'stems').glob('*.wav')))


# ------------------------------------------------------------------ tempo
def grid_score(o, t, bpm, sub=4):
    spb = 60/bpm; best = (0, 0)
    for off in np.arange(0, spb, 0.003):
        g = np.arange(off, t[-1], spb/sub); i = np.searchsorted(t, g); i = i[i < len(o)]
        s = o[i].mean()/o.mean()
        if s > best[0]: best = (s, off)
    return best

def cmd_tempo(a):
    """Grid-lock: the right tempo puts drum onsets ON a 16th grid. Aliases (x2, /2, x2/3, x3/2) score lower."""
    import librosa
    d = P(a.project)
    y = audio(d, 'drums') if (d/'stems'/'drums.wav').exists() else audio(d)
    _, perc = librosa.effects.hpss(y)
    o, t = onset_env(perc)
    cands = set()
    for b in a.bpm:
        for m in (1, 2, 0.5, 2/3, 1.5):
            for dlt in np.arange(-a.span, a.span+1e-9, a.step):
                x = round(b*m+dlt, 2)
                if 60 <= x <= 200: cands.add(x)
    res = sorted(((float(grid_score(o, t, b)[0]), float(b)) for b in sorted(cands)), reverse=True)
    print('top grid locks (score: higher = drum hits sit on the 16th grid)')
    for s, b in res[:8]: print(f'  {b:7.2f} BPM  {s:.3f}')
    bpm = a.force or res[0][1]
    if not a.force and abs(res[0][1]-res[1][1]) > 0.6 and res[0][0]-res[1][0] < 0.05:
        print('WARNING: top two candidates are close. Check by ear or pass --force.')
    spb = 60/bpm; bar = 4*spb
    _, off = grid_score(o, t, bpm, sub=1)
    # downbeat: backbeat feel = snare on 2 & 4, halftime = snare on 3
    K, tk = band_rise(y, 40, 90); Sb, _ = band_rise(y, 160, 300); Sc, _ = band_rise(y, 2000, 5000)
    Sn = np.sqrt(Sb*Sc)
    prof_k, prof_s = [], []
    for k in range(4):
        g = np.arange(off+k*spb, t[-1]-1, bar)
        prof_k.append(np.mean([env_at(K, tk, x) for x in g])); prof_s.append(np.mean([env_at(Sn, tk, x) for x in g]))
    prof_k, prof_s = np.array(prof_k), np.array(prof_s)
    scores = []
    for r in range(4):           # r = which beat is the downbeat
        kk, ss = np.roll(prof_k, -r), np.roll(prof_s, -r)
        if a.feel == 'halftime': sc = kk[0] + ss[2] - ss[0] - 0.5*kk[2]
        else: sc = kk[0] + kk[2] + ss[1] + ss[3] - ss[0] - ss[2] - kk[1] - kk[3]
        scores.append(sc)
    r = int(np.argmax(scores)); db = (off + r*spb) % bar
    # fine tempo + phase: a few hundredths of a BPM drift a 16th by the end of the song.
    # Pick the tempo whose kick/snare phase stays flattest across 4 windows, then centre the grid on it.
    E = K + Sn
    pk = librosa.util.peak_pick(E, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=0.3, wait=5); pt = tk[pk]
    edges = np.linspace(min(10, pt[0]+1), pt[-1], 5)
    def drift(b, d0):
        sp = 60/b; row = []
        for w0, w1 in zip(edges[:-1], edges[1:]):
            x = pt[(pt > w0) & (pt < w1)]; ph = ((x-d0)/sp) % 1; ph = np.where(ph > 0.5, ph-1, ph); ph = ph[np.abs(ph) < 0.25]
            row.append(np.median(ph)*sp if len(ph) else np.nan)
        return np.array(row)
    best_fine = (1e9, bpm)
    if not a.force:
        for b in np.arange(bpm-0.15, bpm+0.151, 0.01):
            r_ = drift(b, db)
            if np.isnan(r_).any(): continue
            sprd = r_.max()-r_.min()
            if sprd < best_fine[0]: best_fine = (sprd, round(float(b), 2))
        bpm = best_fine[1]; spb = 60/bpm; bar = 4*spb
    r_ = drift(bpm, db); db = (db + float(np.nanmean(r_))) % bar
    print(f'fine tempo {bpm} BPM: kick/snare phase drift start-to-end {1000*(np.nanmax(r_)-np.nanmin(r_)):.0f} ms (under ~25 ms = locked)')
    # swing: where do the off-16th hat hits land between straight (50%) and triplet (66%)?
    H, th = band_rise(y, 6000, 12000)
    pk = librosa.util.peak_pick(H, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=0.15, wait=3)
    ph = (((th[pk]-db)/(spb/2)) % 1.0)
    late = ph[(ph > 0.45) & (ph < 0.8)]
    if len(late) > 20:                       # histogram peak, not median: stray hits drag the median
        hcount, edges = np.histogram(late, bins=np.arange(0.4, 0.81, 0.02))
        swing = float(edges[np.argmax(hcount)]+0.01)
    else: swing = 0.5
    print(f'\nBPM {bpm}  beat offset {off:.3f}s  downbeat {db:.3f}s  feel {a.feel}')
    print('kick by beat', np.round(np.roll(prof_k, -r)/prof_k.max(), 2), ' snare by beat', np.round(np.roll(prof_s, -r)/prof_s.max(), 2))
    print(f'swing (8th-note position of off-beat hats): {swing*100:.0f}%  (50 = straight, 66 = triplet swing)')
    save_proj(d, bpm=bpm, downbeat=round(db, 4), feel=a.feel, swing=round(swing, 3), grid_top=[[b, round(s, 3)] for s, b in res[:5]])


# ------------------------------------------------------------------ analyze
def cmd_analyze(a):
    import librosa
    d = P(a.project); p = need(d, 'bpm', 'tempo')
    spb = 60/p['bpm']; bar = 4*spb; db = p['downbeat']
    mix = audio(d); dur = len(mix)/SR_A
    st = {n: audio(d, n) for n in ('drums', 'bass', 'other', 'vocals')}
    hop = 2048
    if a.sections:
        bt = [float(x) for x in a.sections.split(',')]+[dur]
    else:
        C = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(mix), sr=SR_A, hop_length=hop)
        M = librosa.feature.mfcc(y=mix, sr=SR_A, hop_length=hop, n_mfcc=13)
        F = np.vstack([librosa.util.normalize(C), librosa.util.normalize(M)])
        bt = list(librosa.frames_to_time(librosa.segment.agglomerative(F, a.k), sr=SR_A, hop_length=hop))+[dur]
        bt = [db + round((x-db)/bar)*bar if a.snap and 0 < x < dur else x for x in bt]   # snap to bar lines
        bt = sorted(set([0.0]+[round(max(0, x), 2) for x in bt]))
    Sf = np.abs(librosa.stft(mix, n_fft=4096, hop_length=hop)); ff = librosa.fft_frequencies(sr=SR_A, n_fft=4096)
    R = {n: librosa.feature.rms(y=y, hop_length=hop)[0] for n, y in st.items()}
    vthr = np.percentile(R['vocals'], 60)*0.5
    print(f'SECTIONS  (bar = {bar:.3f}s, downbeat {db:.3f}s)')
    secs = []
    for x0, x1 in zip(bt[:-1], bt[1:]):
        i, j = int(x0*SR_A/hop), max(int(x0*SR_A/hop)+1, int(x1*SR_A/hop))
        s = dict(start=round(x0, 2), end=round(x1, 2), bars=round((x1-x0)/bar, 1),
                 sub=round(float(Sf[ff < 100, i:j].sum()/(Sf[:, i:j].sum()+1e-9)), 3),
                 vocal_on=round(float((R['vocals'][i:j] > vthr).mean()), 2),
                 **{n: round(float(R[n][i:j].mean()), 3) for n in R})
        secs.append(s)
        print(f"  {s['start']:6.1f}-{s['end']:6.1f}s {s['bars']:5.1f} bars | drums {s['drums']:.3f} bass {s['bass']:.3f} "
              f"other {s['other']:.3f} vocals {s['vocals']:.3f} | sub {s['sub']:.3f} vocal_on {s['vocal_on']:.2f}")
    nb = int((dur-db)/bar); vm = ''
    for b in range(nb):
        x = db+b*bar; i, j = int(x*SR_A/hop), int((x+bar)*SR_A/hop)
        vm += '#' if (R['vocals'][i:j] > vthr).mean() > 0.35 else '.'
    print('\nVOCAL MAP (# = vocal in bar), 16 bars per row')
    for k in range(0, len(vm), 16): print(f'  bar {k+1:3d}: {vm[k:k+16]}')
    h = librosa.effects.harmonic(st['other']+st['bass'])
    Ch = librosa.feature.chroma_cqt(y=h, sr=SR_A).mean(1)
    maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    mi = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    res = []
    for r in range(12):
        q = np.roll(Ch, -r); q = (q-q.mean())/q.std()
        res += [(np.corrcoef(q, maj)[0, 1], NAMES[r]+' major'), (np.corrcoef(q, mi)[0, 1], NAMES[r]+' minor')]
    res.sort(reverse=True)
    tun = {n: round(float(librosa.estimate_tuning(y=librosa.effects.harmonic(st[n]), sr=SR_A, bins_per_octave=60))*100)
           for n in ('other', 'bass', 'vocals')}
    print('\nKEY', [(n, round(c, 3)) for c, n in res[:3]], ' top pitch classes', [NAMES[i] for i in np.argsort(Ch)[::-1][:7]])
    print('TUNING (cents vs A440)', tun, ' <- a vocal far from the instruments = pitched/sped acapella')
    json.dump(dict(sections=secs, vocal_map=vm), open(d/'analysis.json', 'w'), indent=1)
    save_proj(d, sections=[s['start'] for s in secs], key=res[0][1], tuning_cents=tun)


def cmd_notes(a):
    """Monophonic note grid for a stem window: riffs, hooks, piano top line."""
    import librosa
    d = P(a.project); p = need(d, 'bpm', 'tempo'); spb = 60/p['bpm']; bar = 4*spb
    y = librosa.effects.harmonic(audio(d, a.stem))
    t0 = p['downbeat'] + np.ceil((a.start-p['downbeat'])/bar)*bar
    seg = y[int(t0*SR_A):int((t0+a.bars*bar)*SR_A)]
    lo, hi = (30, 250) if a.stem == 'bass' else (90, 1400)
    f0, vf, _ = librosa.pyin(seg, fmin=lo, fmax=hi, sr=SR_A, frame_length=4096 if a.stem == 'bass' else 2048, hop_length=256)
    tt = librosa.times_like(f0, sr=SR_A, hop_length=256); out = []
    for s in np.arange(0, a.bars*bar-1e-6, a.step*spb):
        m = (tt >= s) & (tt < s+a.step*spb) & vf
        if m.sum() < 2: out.append('--'); continue
        n = int(round(np.median(librosa.hz_to_midi(f0[m])))); out.append(f'{NAMES[n % 12]}{n//12-1}')
    per = int(round(4/a.step))
    print(f'{a.stem} from {t0:.2f}s, {a.bars} bars, one row per bar, step {a.step} beat')
    for i in range(0, len(out), per): print('  ', ' '.join(f'{x:>4s}' for x in out[i:i+per]))
    C = librosa.feature.chroma_cqt(y=seg, sr=SR_A, hop_length=512); tc = librosa.times_like(C, sr=SR_A, hop_length=512)
    print('chord colour per half bar (top 3 pitch classes):')
    print('  ', ' | '.join('/'.join(NAMES[i] for i in np.argsort(C[:, (tc >= h*bar/2) & (tc < (h+1)*bar/2)].mean(1))[::-1][:3])
                          for h in range(int(a.bars*2))))


# ------------------------------------------------------------------ voices
def cmd_voices(a):
    """Vocal flow statistics + who is speaking (register), from word timestamps. Transcript stays private."""
    import librosa
    from faster_whisper import WhisperModel
    d = P(a.project); p = need(d, 'bpm', 'tempo'); spb = 60/p['bpm']; bar = 4*spb; db = p['downbeat']
    priv = d/'.private'; priv.mkdir(exist_ok=True)
    m = WhisperModel(a.model, device='cpu', compute_type='int8')
    vo = audio(d, 'vocals')
    # Transcribe in bar-aligned chunks: one long pass makes Whisper loop on hooks/chants and invent text.
    import soundfile as sf
    chunk = a.chunk_bars*bar; words = []; flagged = []
    x = 0.0
    while x < len(vo)/SR_A:
        seg = vo[int(x*SR_A):int((x+chunk)*SR_A)]
        if np.sqrt(np.mean(seg**2)) > 0.003:
            tmp = priv/'_chunk.wav'; sf.write(tmp, seg, SR_A)
            ss, _ = m.transcribe(str(tmp), word_timestamps=True, vad_filter=False, beam_size=5, condition_on_previous_text=False,
                                 compression_ratio_threshold=2.0, log_prob_threshold=-1.0, no_speech_threshold=0.6,
                                 hallucination_silence_threshold=1.0)
            ws = [(w.start+x, w.end+x, w.word.strip(), w.probability) for sg in ss for w in sg.words]
            ws = [w for w in ws if w[3] >= 0.25]
            toks = [re.sub(r'[^a-z]', '', w[2].lower()) for w in ws]
            # loop detector: any 1-6 word cycle repeated back to back more than 3 times = chant or hallucination.
            keep = [True]*len(ws); i = 0
            while i < len(toks):
                hit = False
                for per in range(1, 7):
                    g = toks[i:i+per]; r = 1
                    if len(g) < per: break
                    while toks[i+per*r:i+per*r+per] == g: r += 1
                    if r > 3:
                        flagged.append((ws[i][0], r, per))
                        for k in range(i+per, i+per*r): keep[k] = False
                        i += per*r; hit = True; break
                if not hit: i += 1
            words += [w[:3] for w, k in zip(ws, keep) if k]
        x += chunk
    json.dump(words, open(priv/'vocal_words.json', 'w'))
    if not words: sys.exit('no words recognised')
    if flagged: print('LOOPS (same phrase back to back; chant or hallucination, check by ear):',
                      ', '.join(f'{t:.0f}s ({p}-word cycle x{r})' for t, r, p in flagged))
    def syl(w):
        w = re.sub(r'[^a-z]', '', w.lower()); n = len(re.findall(r'[aeiouy]+', w))
        if w.endswith('e') and n > 1 and not w.endswith('le'): n -= 1
        return max(1, n) if w else 0
    lines, cur = [], [words[0]]
    for x, y_ in zip(words, words[1:]):
        if y_[0]-x[1] > a.gap or y_[1]-cur[0][0] > 2*bar: lines.append(cur); cur = [y_]
        else: cur.append(y_)
    lines.append(cur)
    p_ = load_proj(d); sect = p_.get('sections', [0.0])
    sec_of = lambda x: int(np.searchsorted(sect, x, side='right'))-1
    print(f'{len(words)} words, {len(lines)} phrases (split on pauses > {a.gap}s)\n')
    print('PHRASES  [section, start, bar.beat, syllables, syl/beat, voice register]  (text withheld)')
    rows = []
    for L in lines:
        x0, x1 = L[0][0], L[-1][1]
        seg = vo[int(x0*SR_A):int(x1*SR_A)]
        reg = '?'
        if len(seg) > 2048:
            f0, vf, _ = librosa.pyin(seg, fmin=70, fmax=600, sr=SR_A, frame_length=2048, hop_length=256)
            if vf.sum() > 5:
                med = float(np.median(f0[vf])); reg = f'{med:4.0f}Hz ' + ('LOW male' if med < 165 else 'mid' if med < 240 else 'HIGH (child/female)')
        sy = sum(syl(w) for *_, w in L); beats = max((x1-x0)/spb, 0.25)
        b = (x0-db)/bar; rows.append(dict(sec=sec_of(x0), t=x0, syl=sy, rate=sy/beats, reg=reg))
        print(f'  s{sec_of(x0):<2d} {x0:6.1f}s  bar {int(b)+1:3d}.{int((b % 1)*4)+1}  {sy:3d} syl  {sy/beats:4.1f}/beat  {reg}')
    print('\nPER SECTION')
    for s in sorted(set(r['sec'] for r in rows)):
        rr = [r for r in rows if r['sec'] == s]
        print(f"  section {s} @ {sect[s]:.1f}s: phrases {len(rr):2d}  syllables {sum(r['syl'] for r in rr):4d}  median syl/beat {np.median([r['rate'] for r in rr]):.1f}")
    toks = [re.sub(r'[^a-z]', '', w.lower()) for *_, w in words]
    grams = Counter(tuple(toks[i:i+3]) for i in range(len(toks)-2))
    print('\nREPEATED 3-WORD PHRASES = hook candidates (count: times)  [text withheld]')
    seen = set()
    for gm, c in sorted(grams.items(), key=lambda x: -x[1]):
        if c < 3 or gm in seen: continue
        seen.add(gm)
        occ = [words[i][0] for i in range(len(toks)-2) if tuple(toks[i:i+3]) == gm]
        print(f'  x{c}: ' + ', '.join(f'{x:.0f}s' for x in occ))
        if len(seen) >= 8: break
    def rk(w):
        w = re.sub(r'[^a-z]', '', w.lower()); mm = re.search(r'[aeiouy]+[^aeiouy]*$', w); return mm.group(0) if mm else w
    lab = {}; scheme = ''
    for L in lines:
        k = rk(L[-1][2]); lab.setdefault(k, chr(65+len(lab) % 26)); scheme += lab[k]
    print('\nEND-RHYME LETTERS per phrase:', scheme)


# ------------------------------------------------------------------ transcribe
def bp_notes(path, lo, hi, onset=0.5, frame=0.3):
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
    _, _, ev = predict(str(path), ICASSP_2022_MODEL_PATH, onset_threshold=onset, frame_threshold=frame,
                       minimum_note_length=60, minimum_frequency=lo, maximum_frequency=hi)
    return [(s, e, int(pt), float(v)) for s, e, pt, v, *_ in ev]

def cmd_transcribe(a):
    import librosa, pretty_midi
    d = P(a.project); p = need(d, 'sections', 'analyze')
    bpm, db, feel = p['bpm'], p['downbeat'], p.get('feel', 'backbeat'); spb = 60/bpm; bar = 4*spb; q = spb/4
    sw = p.get('swing', 0.5) if a.swing else 0.5
    shift = (bar - db) % bar           # move first downbeat to a bar line in the MIDI
    sect = p['sections']+[p.get('duration', 1e9)]
    def qt(x):                          # quantize to (swung) 16th grid
        k = round((x-db)/q); base = db + k*q
        if k % 2 == 1: base = db + (k-1)*q + 2*q*sw
        return base + shift
    def mono(notes):
        notes = sorted(notes, key=lambda n: (n[0], -n[3])); out = []
        for n in notes:
            if out and n[0] < out[-1][1]-0.02:
                if n[3] > out[-1][3]*1.2 and n[0]-out[-1][0] > q*0.5: out[-1] = (out[-1][0], n[0], out[-1][2], out[-1][3])
                else: continue
            out.append(n)
        return out
    def inst(notes, name, prog, mono_=False):
        ins = pretty_midi.Instrument(program=prog, name=name)
        for s, e, pt, v in (mono(notes) if mono_ else notes):
            s2 = qt(s); e2 = max(s2+q*0.9, qt(e))
            ins.notes.append(pretty_midi.Note(velocity=int(np.clip(40+87*v, 30, 127)), pitch=pt, start=s2, end=e2))
        return ins
    print('basic-pitch: bass ...'); bass = bp_notes(d/'stems'/'bass.wav', 28, 300, 0.5, 0.35)
    print('basic-pitch: other ...'); oth = bp_notes(d/'stems'/'other.wav', 60, 2000, 0.5, 0.3)
    keys = [n for n in oth if n[2] < 79]; lead = [n for n in oth if n[2] >= 79]
    pm = pretty_midi.PrettyMIDI(initial_tempo=bpm)
    pm.instruments += [inst(bass, 'Bass', 38, True), inst(keys, 'Keys', 0), inst(lead, 'Lead', 81, True)]
    # drums: per-section 2-bar templates; snare main hits from the feel (verified at beat level by `tempo`)
    y = audio(d, 'drums')
    K, t = band_rise(y, 40, 90); Sb, _ = band_rise(y, 160, 300); Sc, _ = band_rise(y, 2000, 5000); H, _ = band_rise(y, 7000, 12000)
    Sn = np.sqrt(Sb*Sc)
    dr = pretty_midi.Instrument(program=0, is_drum=True, name='Drums'); rng = np.random.default_rng(3)
    main_sn = (4, 12, 20, 28) if feel == 'backbeat' else (8, 24)
    for x0, x1 in zip(sect[:-1], sect[1:]):
        seg = y[int(x0*SR_A):int(min(x1, len(y)/SR_A)*SR_A)]
        if len(seg) == 0 or np.sqrt(np.mean(seg**2)) < a.silence:
            print(f'  {x0:6.1f}-{x1:6.1f}s  no drums'); continue
        c0 = int(np.ceil((x0-db)/(2*bar))); c1 = int(np.floor((x1-db)/(2*bar)))
        if c1 <= c0: c1 = c0+1
        T = {k: np.zeros(32) for k in 'KSH'}
        for c in range(c0, c1):
            for s in range(32):
                x = db+c*2*bar+s*q
                T['K'][s] += env_at(K, t, x); T['S'][s] += env_at(Sn, t, x); T['H'][s] += env_at(H, t, x)
        for k in T: T[k] /= (T[k].max()+1e-9)
        kth = lambda v, n: np.sort(v)[::-1][n-1]
        kick_steps = [s for s in range(32) if T['K'][s] >= max(0.6, kth(T['K'], 6))]
        ghosts = [s for s in np.argsort(T['S'])[::-1] if s not in main_sn][:2]
        hats = [s for s in range(32) if T['H'][s] >= kth(T['H'], 10)]
        print(f'  {x0:6.1f}-{x1:6.1f}s  K {kick_steps}  S {list(main_sn)} ghost {sorted(ghosts)}  H {hats}')
        cyc = db + c0*2*bar
        while cyc < x1:
            for s in range(32):
                x = cyc + s*q
                if not (x0 <= x < x1): continue
                tt = qt(x)
                if s in kick_steps: dr.notes.append(pretty_midi.Note(int(90+30*T['K'][s]), 36, tt, tt+0.1))
                if s in main_sn: dr.notes.append(pretty_midi.Note(112, 38, tt, tt+0.1))
                elif s in ghosts: dr.notes.append(pretty_midi.Note(int(40+15*rng.random()), 38, tt, tt+0.08))
                if s in hats: dr.notes.append(pretty_midi.Note(int(55+50*T['H'][s]*(0.7+0.3*rng.random())), 42, tt, tt+0.05))
            cyc += 2*bar
    pm.instruments.append(dr)
    pm.write(str(d/'reference.mid'))
    save_proj(d, midi_shift=round(shift, 4))
    print('wrote reference.mid  (no original vocal: your lyrics replace it)',
          {i.name: len(i.notes) for i in pm.instruments})


# ------------------------------------------------------------------ render
def cmd_render(a):
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    import hm_render
    hm_render.render(P(a.project), a.palette, a.drops)


# ------------------------------------------------------------------ validate
def cmd_validate(a):
    import librosa
    d = P(a.project); p = need(d, 'midi_shift', 'transcribe')
    o = sum(audio(d, n) for n in ('drums', 'bass', 'other'))
    r = librosa.load(str(d/'reference_demo.wav'), sr=SR_A, mono=True)[0][int(p['midi_shift']*SR_A):]
    L = min(len(o), len(r)); o, r = o[:L], r[:L]
    Co = librosa.feature.chroma_cqt(y=o, sr=SR_A, hop_length=2048); Cr = librosa.feature.chroma_cqt(y=r, sr=SR_A, hop_length=2048)
    k = 21; seg = lambda C: np.array([C[:, i:i+k].mean(1) for i in range(0, C.shape[1]-k, k)])
    cs = [float(np.dot(x, y)/(np.linalg.norm(x)*np.linalg.norm(y)+1e-9)) for x, y in zip(seg(Co), seg(Cr))]
    h = SR_A*5
    ro = [np.sqrt(np.mean(o[i:i+h]**2)) for i in range(0, L-h, h)]; rr = [np.sqrt(np.mean(r[i:i+h]**2)) for i in range(0, L-h, h)]
    oe, t = onset_env(r)
    locks = {b: round(grid_score(oe, t, b)[0], 2) for b in sorted({p['bpm'], round(p['bpm']*2/3, 1), round(p['bpm']*1.5, 1), p['bpm']+1, p['bpm']-1})}
    print(f'harmony (chroma cosine per 2s, original instrumental vs demo): median {np.median(cs):.2f}, 25th pct {np.percentile(cs, 25):.2f}')
    print(f'arrangement (5s energy-contour correlation): {np.corrcoef(ro, rr)[0, 1]:.2f}')
    print('grid lock of the demo:', locks)
    print('targets: harmony >= 0.85, arrangement >= 0.6, demo locks hardest at the project BPM')


# ------------------------------------------------------------------ compose (original demo from facts)
def cmd_compose(a):
    here = Path(__file__).resolve().parent; sys.path.insert(0, str(here))
    import hm_compose
    d = P(a.project); d.mkdir(parents=True, exist_ok=True)
    plan = json.load(open(a.plan))
    info = hm_compose.compose(plan, d/'reference.mid')
    save_proj(d, **info, composed=True)
    print(f"wrote reference.mid: ORIGINAL composition, {info['bpm']} BPM, {info['key']}, {len(info['sections'])} sections, {info['duration']:.0f}s")
    print('next: render --palette ..., then similarity --original <analyzed original project>')


# ------------------------------------------------------------------ similarity (copy-risk proxy)
def beat_chroma(path, bpm, downbeat, sr=SR_A):
    import librosa
    y = librosa.load(str(path), sr=sr, mono=True)[0]
    C = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(y), sr=sr, hop_length=512)
    t = librosa.times_like(C, sr=sr, hop_length=512); spb = 60/bpm
    beats = np.arange(downbeat, t[-1]-spb, spb)
    B = np.array([C[:, (t >= b) & (t < b+spb)].mean(1) for b in beats]).T
    keep = B.sum(0) > 1e-6
    return B[:, keep] / (np.linalg.norm(B[:, keep], axis=0)+1e-9)

def _sim(demo_dir, orig_dir, instrumental=False):
    p = load_proj(demo_dir); po = load_proj(orig_dir)
    A = beat_chroma(demo_dir/'reference_demo.wav', p['bpm'], 0.0)   # rendered demos start on a bar line
    src = orig_dir/'original.mp3' if orig_dir.is_dir() else orig_dir
    if 'bpm' not in po:                 # a bare audio file or unanalyzed control: estimate the beat grid
        import librosa
        y = librosa.load(str(src), sr=SR_A, mono=True)[0]
        tempo, beats = librosa.beat.beat_track(y=y, sr=SR_A, units='time')
        po = {'bpm': float(np.atleast_1d(tempo)[0]), 'downbeat': float(beats[0]) if len(beats) else 0.0}
    if instrumental and (orig_dir/'stems').exists():
        import librosa, soundfile as sf
        mix = sum(librosa.load(str(orig_dir/'stems'/f'{n}.wav'), sr=SR_A)[0] for n in ('bass', 'other'))
        src = orig_dir/'.private'/'_inst.wav'; (orig_dir/'.private').mkdir(exist_ok=True); sf.write(src, mix, SR_A)
    B = beat_chroma(src, po['bpm'], po.get('downbeat', 0.0))
    W = 8
    def wins(X): return np.array([X[:, i:i+W].flatten() for i in range(0, X.shape[1]-W, 2)])
    wa = wins(A); wa = wa/np.linalg.norm(wa, axis=1, keepdims=True)
    best = np.zeros(len(wa))
    for r in range(12):
        wb = wins(np.roll(B, r, axis=0)); wb = wb/np.linalg.norm(wb, axis=1, keepdims=True)
        best = np.maximum(best, (wa @ wb.T).max(1))
    return float(np.median(best)), float(np.percentile(best, 90))

def cmd_similarity(a):
    """Copy-risk check. Absolute similarity depends on texture (a loud minor-key bassline scores ~0.83-0.89 against ANY
    bass-heavy track), so what counts is the MARGIN: similarity to the source minus the highest similarity to unrelated
    control tracks (each an analyzed project with original.mp3 + bpm/downbeat). A transcription has a clearly positive
    margin. An original piece in the same style has a margin of 0 or below. This is a proxy; Suno's real check is unknown."""
    d = P(a.project)
    t_med, t_p90 = _sim(d, P(a.original), a.instrumental)
    print(f'source  {a.original}: median {t_med:.3f} (90th pct {t_p90:.3f})')
    ctrl = []
    for c in (a.controls or []):
        m, _ = _sim(d, P(c)); ctrl.append(m); print(f'control {c}: median {m:.3f}')
    out = dict(similarity_median=t_med, similarity_p90=t_p90)
    if ctrl:
        margin = t_med - max(ctrl); out['similarity_margin'] = margin
        print(f'MARGIN (source minus closest control): {margin:+.3f}  -> ' + ('OK: no closer to the source than to unrelated music' if margin <= 0.0
              else 'RISK: closer to the source than to unrelated music; change the riff/bass/harmony'))
    else:
        print('no --controls given: absolute value only (unreliable for bass-heavy demos)')
    save_proj(d, **out)

# ------------------------------------------------------------------ groove (does the demo carry the reference's drive?)
def _bass_stats(bass, mix, bpm, db, a, b):
    import librosa
    spb = 60/bpm; q = spb/4
    seg = bass[int(a*SR_A):int(b*SR_A)]; mseg = mix[int(a*SR_A):int(b*SR_A)]
    lvl = 20*np.log10(np.sqrt(np.mean(seg**2))/(np.sqrt(np.mean(mseg**2))+1e-9)+1e-9)
    o = librosa.onset.onset_strength(y=seg, sr=SR_A, hop_length=128); t = librosa.frames_to_time(np.arange(len(o)), sr=SR_A, hop_length=128)
    pk = librosa.util.peak_pick(o, pre_max=3, post_max=3, pre_avg=10, post_avg=10, delta=0.5*o.std(), wait=4)
    hist = np.bincount(np.round(((t[pk]+a-db)/q)).astype(int) % 16, minlength=16)
    env = librosa.feature.rms(y=seg, hop_length=256)[0]
    return dict(level_db=lvl, notes_per_bar=len(pk)/((b-a)/(4*spb)), sustain=float((env > 0.3*np.percentile(env, 95)).mean()), hist=hist)

def cmd_groove(a):
    """Compare bass drive (level vs mix, notes per bar, sustain, rhythm) between the reference and the demo.
    Both are measured through demucs so the levels are comparable. Run demucs on the demo first via --separate."""
    import librosa
    d = P(a.project); o = P(a.original); pd_, po = load_proj(d), load_proj(o)
    sep = d/'demo_sep'/'htdemucs'/'reference_demo'
    if not sep.exists():
        subprocess.run([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '-o', str(d/'demo_sep'), str(d/'reference_demo.wav')],
                       check=True, capture_output=True)
    ob, om = audio(o, 'bass'), audio(o)
    dbass = librosa.load(str(sep/'bass.wav'), sr=SR_A)[0]; dmix = librosa.load(str(d/'reference_demo.wav'), sr=SR_A)[0]
    oa, ob_ = a.orig_window; da, db_ = a.demo_window
    for lab, st in (('reference', _bass_stats(ob, om, po['bpm'], po['downbeat'], oa, ob_)),
                    ('demo', _bass_stats(dbass, dmix, pd_['bpm'], 0.0, da, db_))):
        print(f"{lab:9s} bass {st['level_db']:5.1f} dB vs mix | {st['notes_per_bar']:4.1f} notes/bar | sustain {st['sustain']:.0%} | "
              f"16th histogram {' '.join(str(x) for x in st['hist'])}")
    print('aim: notes/bar within ~1 of the reference; sustain under 75% for a funky line; bass no quieter than the reference')

# ------------------------------------------------------------------ check
def cmd_check(a):
    bad = False
    if a.style:
        s = Path(a.style).read_text().strip()
        print(f'style: {len(s)} chars (Suno cap 1000, silently truncates)'); bad |= len(s) > 1000
        names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', s)
        if names: print('  possible artist/proper names (Suno ignores or blocks them):', sorted(set(names)))
    if a.lyrics:
        L = Path(a.lyrics).read_text()
        print(f'lyrics: {len(L)} chars (Suno cap ~3000)'); bad |= len(L) > 3000
        def syl(w):
            w = re.sub(r'[^a-z]', '', w.lower()); n = len(re.findall(r'[aeiouy]+', w))
            if w.endswith('e') and n > 1 and not w.endswith('le'): n -= 1
            return max(1, n) if w else 0
        sec = None; per = defaultdict(list)
        for ln in L.splitlines():
            if ln.startswith('['): sec = ln.split(':')[0].strip('[]'); continue
            if ln.strip() and not ln.strip().startswith('('): per[sec].append(sum(syl(w) for w in ln.split()))
        for k, v in per.items(): print(f'  {k:14s} lines {len(v):2d}  syllables/line median {np.median(v):.0f} (range {min(v)}-{max(v)})')
        if a.original_words:
            W = [re.sub(r"[^a-z']", '', w[2].lower()) for w in json.load(open(a.original_words))]
            T = [re.sub(r"[^a-z']", '', w.lower()) for ln in L.splitlines() if not ln.startswith('[') for w in ln.split()]
            g = lambda X, n: {tuple(X[i:i+n]) for i in range(len(X)-n+1)}
            sh3, sh4 = g(W, 3) & g(T, 3), g(W, 4) & g(T, 4)
            print(f'  overlap with original vocal: {len(sh3)} shared 3-grams, {len(sh4)} shared 4-grams (keep 4-grams at 0; 3-grams only for common phrases)')
            bad |= len(sh4) > 0
    print('FAIL' if bad else 'PASS')
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    s = sp.add_parser('fetch'); s.add_argument('project'); s.add_argument('--query'); s.add_argument('--url'); s.set_defaults(f=cmd_fetch)
    s = sp.add_parser('stems'); s.add_argument('project'); s.add_argument('--jobs', type=int, default=4); s.set_defaults(f=cmd_stems)
    s = sp.add_parser('tempo'); s.add_argument('project'); s.add_argument('--bpm', type=float, nargs='+', required=True,
                    help='published BPM(s) from a lookup; aliases are tested automatically')
    s.add_argument('--span', type=float, default=1.5); s.add_argument('--step', type=float, default=0.5)
    s.add_argument('--feel', choices=['backbeat', 'halftime'], default='backbeat'); s.add_argument('--force', type=float)
    s.set_defaults(f=cmd_tempo)
    s = sp.add_parser('analyze'); s.add_argument('project'); s.add_argument('--k', type=int, default=12)
    s.add_argument('--sections', help='comma list of section start times (s) to override auto segmentation')
    s.add_argument('--no-snap', dest='snap', action='store_false'); s.set_defaults(f=cmd_analyze)
    s = sp.add_parser('notes'); s.add_argument('project'); s.add_argument('--stem', default='bass')
    s.add_argument('--start', type=float, required=True); s.add_argument('--bars', type=int, default=4)
    s.add_argument('--step', type=float, default=0.5); s.set_defaults(f=cmd_notes)
    s = sp.add_parser('voices'); s.add_argument('project'); s.add_argument('--model', default='small.en')
    s.add_argument('--chunk-bars', type=int, default=6)
    s.add_argument('--gap', type=float, default=0.35); s.set_defaults(f=cmd_voices)
    s = sp.add_parser('transcribe'); s.add_argument('project'); s.add_argument('--silence', type=float, default=0.01)
    s.add_argument('--no-swing', dest='swing', action='store_false'); s.set_defaults(f=cmd_transcribe)
    s = sp.add_parser('render'); s.add_argument('project'); s.add_argument('--palette', choices=['hiphop', 'grit', 'bass'], default='hiphop')
    s.add_argument('--drops', default='', help='comma list of section indexes that are drops (bass palette)'); s.set_defaults(f=cmd_render)
    s = sp.add_parser('validate'); s.add_argument('project'); s.set_defaults(f=cmd_validate)
    s = sp.add_parser('compose'); s.add_argument('project'); s.add_argument('--plan', required=True); s.set_defaults(f=cmd_compose)
    s = sp.add_parser('similarity'); s.add_argument('project'); s.add_argument('--original', required=True)
    s.add_argument('--instrumental', action='store_true', help='compare against the original bass+other stems only')
    s.add_argument('--controls', nargs='*', help='UNRELATED tracks: analyzed project folders or plain audio files (beat grid estimated)')
    s.set_defaults(f=cmd_similarity)
    s = sp.add_parser('groove'); s.add_argument('project'); s.add_argument('--original', required=True)
    s.add_argument('--orig-window', type=float, nargs=2, default=[45, 95]); s.add_argument('--demo-window', type=float, nargs=2, default=[30, 55])
    s.set_defaults(f=cmd_groove)
    s = sp.add_parser('check'); s.add_argument('--style'); s.add_argument('--lyrics'); s.add_argument('--original-words')
    s.set_defaults(f=cmd_check)
    a = ap.parse_args(); a.f(a)

if __name__ == '__main__':
    main()
