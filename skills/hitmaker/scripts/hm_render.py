"""hitmaker renderer: MIDI -> instrumental reference demo for Suno Cover.

Palettes
  hiphop : dusty sampled-piano feel, warm round bass, boom bap kit, vinyl crackle, 12-bit crunch
  grit   : 90s hardcore: hard dry drums with a cracking snare, LOUD funky saturated bass with mid-range bite
           (audible on laptop speakers), bright detuned piano, short room, 12-bit crunch
  bass   : reese/formant growl bass with per-section LFO rates, screaming lead, plucks, risers into drops
The demo only has to carry riffs, groove and arrangement. Suno re-produces the sound.
"""
import json
import numpy as np, soundfile as sf, pretty_midi
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100

def m2f(m): return 440.0*2**((np.asarray(m, float)-69)/12)
def _f(x, fc, kind, o=2): return sosfilt(butter(o, fc, kind, fs=SR, output='sos'), x)
def hp(x, fc, o=2): return _f(x, fc, 'hp', o)
def lp(x, fc, o=2): return _f(x, fc, 'lp', o)
def bp(x, lo, hi, o=2): return _f(x, [lo, hi], 'bp', o)

def svf(x, cut, res, mode):
    """state-variable filter with per-sample cutoff (0 LP, 1 BP). numba if available."""
    try:
        from numba import njit
        global _svf
        if '_svf' not in globals():
            @njit(cache=True)
            def _svf(x, cut, res, mode):
                y = np.zeros_like(x); a = 0.0; b = 0.0; k = 2.0-2.0*res
                for n in range(len(x)):
                    g = np.tan(np.pi*min(cut[n], 18000.0)/44100.0)
                    a1 = 1.0/(1.0+g*(g+k)); a2 = g*a1; a3 = g*a2
                    v3 = x[n]-b; v1 = a1*a+a2*v3; v2 = b+a2*a+a3*v3
                    a = 2*v1-a; b = 2*v2-b
                    y[n] = v2 if mode == 0 else v1
                return y
        return _svf(x.astype(np.float64), np.asarray(cut, np.float64), res, mode)
    except ImportError:
        out = np.zeros_like(x); blk = 512
        for i in range(0, len(x), blk):
            c = float(np.mean(cut[i:i+blk])); c = min(max(c, 30), 18000)
            out[i:i+blk] = lp(x[i:i+blk], c) if mode == 0 else bp(x[i:i+blk], c*0.8, c*1.25)
        return out

def saw(ph): return 2.0*(ph-np.floor(ph))-1.0


def render(d, palette='hiphop', drops=''):
    p = json.load(open(d/'project.json'))
    pm = pretty_midi.PrettyMIDI(str(d/'reference.mid'))
    bpm = p['bpm']; spb = 60/bpm; shift = p.get('midi_shift', 0.0)
    sect = [0.0]+[x+shift for x in p['sections'][1:]]
    drop_ix = [int(x) for x in drops.split(',') if x.strip()]
    N = int((pm.get_end_time()+3)*SR); rng = np.random.default_rng(7)
    T = np.arange(N)/SR
    ins = {i.name: i for i in pm.instruments}
    sec_of = lambda x: np.searchsorted(sect, x, side='right')-1

    def mono_curves(notes, glide=0.03, tail=0.03):
        pitch = np.full(N, np.nan); gate = np.zeros(N); since = np.full(N, 10.0); vel = np.zeros(N)
        for n in sorted(notes, key=lambda n: n.start):
            a, b = int(n.start*SR), min(N, int((n.end+tail)*SR))
            pitch[a:b] = n.pitch; gate[a:b] = 1; vel[a:b] = n.velocity/127; since[a:b] = np.arange(b-a)/SR
        idx = np.where(~np.isnan(pitch), np.arange(N), 0); np.maximum.accumulate(idx, out=idx)
        pitch = pitch[idx]; pitch[np.isnan(pitch)] = 40
        al = 1-np.exp(-1/(glide*SR))
        pitch = sosfilt(np.array([[al, 0, 0, 1, -(1-al), 0]]), pitch-pitch[0])+pitch[0]
        return pitch, np.clip(lp(gate, 200, 1), 0, 1), since, vel

    det = p.get('piano_detune_cents', 0)/100.0
    def piano(notes, bright=3200):
        out = np.zeros(N)
        for n in notes:
            a = int(n.start*SR); L = min(int(min(n.end-n.start+1.2, 3.5)*SR), N-a)
            if L <= 0: continue
            tt = np.arange(L)/SR; f = m2f(n.pitch+det); s = np.zeros(L)
            for k in range(1, 9):
                fk = f*k*np.sqrt(1+0.0004*k*k)
                if fk > 9000: break
                s += np.sin(2*np.pi*fk*tt+rng.random())*np.exp(-tt*(0.9+0.55*k))/k**1.1
            hm = min(L, 1200); s[:hm] += 0.15*lp(rng.standard_normal(hm)*np.exp(-np.arange(hm)/120), 2500)
            out[a:a+L] += lp(s, bright)*(n.velocity/127)
        return out

    def warm_bass(notes):
        if not notes: return np.zeros(N)
        pitch, gate, since, vel = mono_curves(notes, glide=0.02, tail=0.05)
        f = m2f(pitch); ph = np.cumsum(f/SR)
        s = np.sin(2*np.pi*ph) + 0.25*lp(saw(ph*1.0+0.1), 600)
        env = 0.6+0.4*np.exp(-since/0.25)
        return np.tanh(1.6*s)*gate*env*(0.6+0.4*vel)

    def growl_bass(notes):
        if not notes: return np.zeros(N)
        pitch, gate, since, vel = mono_curves(notes, glide=0.035)
        sec = sec_of(T); rates = [0.5, 0.25, 1/3, 0.5, 0.25, 1/6]
        rate = np.array([rates[drop_ix.index(s) % len(rates)] if s in drop_ix else 1.0 for s in range(len(sect)+1)])[sec]
        lfo = 0.5+0.5*np.sin(2*np.pi*((T-shift)/spb)/rate)
        f = m2f(pitch)
        raw = sum(saw(np.cumsum(f*2**(dd/12)/SR)+rng.random()) for dd in (-0.18, -0.08, 0, 0.08, 0.18))/5
        raw += 0.35*np.sign(np.sin(2*np.pi*np.cumsum(2*f/SR)))
        talk = svf(raw, 120+3800*(0.25*np.exp(-since/0.18)+0.75*lfo**1.6), 0.82, 0)
        form = svf(raw, 300+430*lfo, 0.9, 1)+0.7*svf(raw, 840+1460*lfo, 0.9, 1)
        mid = hp(np.tanh(3.2*(0.8*talk+0.9*form)), 140)
        sub = lp(np.tanh(1.3*np.sin(2*np.pi*np.cumsum(np.where(pitch > 47, f/2, f)/SR))), 110)
        in_drop = np.isin(sec, drop_ix) if drop_ix else np.ones(N, bool)
        return (0.55*mid*in_drop+0.85*sub)*gate


    def funk_bass(notes):
        """saturated electric/synth bass: pluck filter envelope + drive gives mid-range bite; clean sub underneath"""
        if not notes: return np.zeros(N)
        out = np.zeros(N)
        for n in notes:
            a = int(n.start*SR); L = min(int((n.end-n.start+0.03)*SR), N-a)
            if L <= 0: continue
            tt = np.arange(L)/SR; f = m2f(n.pitch); ph = f*tt + rng.random()
            raw = 0.6*saw(ph) + 0.4*np.sign(np.sin(2*np.pi*ph*1.0))
            cut = 180 + 2600*np.exp(-tt/0.07)*(n.velocity/127)
            body = svf(raw, cut, 0.55, 0)
            sub = np.sin(2*np.pi*f*tt)
            env = np.minimum(1, tt/0.003)*np.minimum(1, (L/SR-tt)/0.012)
            out[a:a+L] += (np.tanh(2.8*body)*0.8 + 0.55*sub)*env*(n.velocity/127)
        return out

    def lead(notes, soft):
        if not notes: return np.zeros(N)
        pitch, gate, since, vel = mono_curves(notes, glide=0.05, tail=0.12)
        vib = 0.2*np.clip((since-0.15)/0.3, 0, 1)*np.sin(2*np.pi*5.4*T)
        f = m2f(pitch+vib); ph = np.cumsum(f/SR)
        if soft:   # rhodes-ish
            y = np.sin(2*np.pi*ph)+0.3*np.sin(2*np.pi*2*ph)*np.exp(-since/0.4)
            return lp(y, 2500)*gate*0.5
        raw = sum(saw(np.cumsum(f*2**(dd/12)/SR)+rng.random()) for dd in (-0.12, 0, 0.12))/3
        return hp(np.tanh(2.5*svf(raw, 900+6500*(0.35+0.65*np.exp(-since/0.35)), 0.55, 0))*gate, 250)

    def kit(dusty):
        def kick():
            L = int(0.45*SR); t = np.arange(L)/SR; f = (45 if dusty else 48)+170*np.exp(-t/(0.04 if dusty else 0.03))
            s = np.tanh(2.0*np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t/(0.28 if dusty else 0.22)))
            return lp(s, 4000) if dusty else s+hp(rng.standard_normal(L)*np.exp(-t/0.003), 3000)*0.5
        def snare():
            L = int(0.35*SR); t = np.arange(L)/SR
            body = np.sin(2*np.pi*(190+50*np.exp(-t/0.01))*t)*np.exp(-t/0.07)
            nz = bp(rng.standard_normal(L), 1200, 7000 if dusty else 9000)*np.exp(-t/(0.13 if dusty else 0.11))
            return np.tanh(1.8*(0.9*body+1.0*nz))
        def hat(o=False):
            L = int((0.3 if o else 0.06)*SR); t = np.arange(L)/SR
            s = sum(np.sign(np.sin(2*np.pi*400*r*t)) for r in (2, 3, 4.16, 5.43, 6.79, 8.21))
            s = hp(s, 6500, 4)*np.exp(-t/(0.1 if o else 0.016))*0.45
            return lp(s, 10000) if dusty else s
        return {36: kick(), 38: snare(), 42: hat(), 46: hat(True)}

    def drums(notes, dusty):
        K = kit(dusty); bus = {k: np.zeros(N) for k in K}
        for n in notes:
            s = K.get(n.pitch)
            if s is None: continue
            a = int(n.start*SR); L = min(len(s), N-a)
            bus[n.pitch][a:a+L] += s[:L]*(n.velocity/127)**1.3
        return bus

    def reverb(x, sec=1.6, mix=0.18):
        L = int(sec*SR); t = np.arange(L)/SR
        ir = rng.standard_normal(L)*np.exp(-t/(sec/6.9)); ir = lp(ir, 6000); ir /= np.sqrt(np.sum(ir**2))
        return x+mix*fftconvolve(x, ir)[:len(x)]

    dusty = palette == 'hiphop'; grit = palette == 'grit'
    keys = piano(ins['Keys'].notes if 'Keys' in ins else [], 2800 if dusty else 6000 if grit else 3600)
    if grit: bass = funk_bass(ins['Bass'].notes)
    elif dusty: bass = warm_bass(ins['Bass'].notes)
    else: bass = growl_bass(ins['Bass'].notes)
    ld = lead(ins['Lead'].notes if 'Lead' in ins else [], soft=(dusty or grit))
    dr = drums(ins['Drums'].notes if 'Drums' in ins else [], dusty)
    if grit:   # harder snare + punch: parallel saturation on the drum bus
        D = 1.15*dr[36]+1.0*dr[38]+0.45*dr[42]+0.35*dr[46]
        D = 0.6*D + 0.5*np.tanh(3.0*D)
    else:
        D = 1.0*dr[36]+0.8*dr[38]+0.5*dr[42]+0.4*dr[46]
    fx = np.zeros(N)
    if dusty or grit:
        crackle = np.zeros(N); pops = rng.random(N) < 6/SR
        crackle[pops] = rng.standard_normal(pops.sum())*0.5
        crackle = hp(crackle+0.004*rng.standard_normal(N), 1500)
        fx += (0.08 if dusty else 0.04)*crackle
        keys = reverb(keys, 1.4 if dusty else 0.7, 0.15 if dusty else 0.08)
        crunch = lambda x: np.round(x*2048)/2048                 # 12-bit sampler grit
        keys, D = crunch(lp(keys, 9000 if dusty else 12000)), crunch(D)
    else:
        for i in drop_ix:
            if i >= len(sect): continue
            L = int(8*spb*SR); a = int(sect[i]*SR)-L
            if a > 0:
                tt = np.arange(L)/L
                fx[a:a+L] += svf(rng.standard_normal(L), 400+9000*tt**2, 0.7, 1)*tt**2*0.35
        keys = reverb(keys, 1.8, 0.25); ld = reverb(ld, 2.2, 0.25)
    nrm = lambda x: x/(np.sqrt(np.mean(x**2))+1e-9)
    if grit: mix = 0.15*nrm(keys)+0.32*nrm(bass)+0.05*nrm(ld)+0.24*nrm(D)+fx
    else: mix = 0.55*keys+0.75*bass+0.35*ld+0.8*D+fx
    mix = hp(mix, 25)
    mix = np.tanh(1.3*mix/np.max(np.abs(mix)+1e-9)*1.6)
    mix *= 0.89/np.max(np.abs(mix))
    sf.write(d/'reference_demo.wav', mix.astype(np.float32), SR)
    import subprocess
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(d/'reference_demo.wav'), '-b:a', '320k', str(d/'reference_demo.mp3')])
    for nm, sig in (('keys', keys), ('bass', bass), ('lead', ld), ('drums', D)):
        sf.write(d/f'demo_stem_{nm}.wav', (sig/(np.max(np.abs(sig))+1e-9)*0.8).astype(np.float32), SR)
    print(f'wrote reference_demo.wav/.mp3 ({N/SR:.1f}s, palette {palette}) + demo_stem_*.wav')
