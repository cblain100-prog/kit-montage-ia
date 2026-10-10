#!/usr/bin/env python3
"""Synthesised stings (original sounds, free of any rights) and music helpers for the montage chain.

  python3 music.py sting <out.wav> <drop_seconds> [a|b|c]   render a sting alone (preview)
"""
import os, subprocess, sys
import numpy as np

SR = 48000


def _env(n, a, d, peak=1.0):
    e = np.ones(n) * peak
    a, d = min(a, n), min(d, n)
    if a:
        e[:a] = np.linspace(0, peak, a)
    if d:
        e[-d:] *= np.linspace(1, 0, d)
    return e


def _lowpass(x, cutoff):
    # one-pole low-pass, enough for a soft pad
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def make_sting(drop, tail=2.8, seed=7):
    """Stereo float array: soft pad intro (0..drop), noise riser into the drop, 808 drop at `drop`."""
    rng = np.random.default_rng(seed)
    n = int((drop + tail) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    # --- intro pad: D minor 9 (D F A C E), detuned saws, low-passed, gentle swell ---
    ni = int(drop * SR)
    if ni > 0:
        ti = t[:ni]
        pad = np.zeros(ni)
        for f in (146.83, 174.61, 220.0, 261.63, 329.63):
            for det in (-0.004, 0.004):
                ph = 2 * np.pi * f * (1 + det) * ti
                pad += (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.06
        pad = _lowpass(pad, 900) * 1.8
        # soft pluck arpeggio on top (A5 C6 E6), every quarter note at 90 bpm
        q = 60 / 90 / 2
        for k, f in enumerate([880.0, 1046.5, 1318.5, 1046.5] * 8):
            s0 = int(k * q * SR)
            if s0 >= ni:
                break
            ln = min(int(0.35 * SR), ni - s0)
            tt = np.arange(ln) / SR
            pad[s0:s0 + ln] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9) * 0.09
        pad *= _env(ni, int(min(0.6, drop / 2) * SR), 0, 1.0)
        out[:ni, 0] += pad
        out[:ni, 1] += np.roll(pad, 120)  # tiny stereo width
    # --- riser: filtered noise swelling over the last 0.7s before the drop ---
    rl = int(min(0.7, drop) * SR)
    if rl > 0:
        noise = rng.standard_normal(rl)
        noise = noise - _lowpass(noise, 1500)  # high-passed hiss
        noise *= np.linspace(0, 1, rl) ** 2.5 * 0.22
        out[ni - rl:ni, 0] += noise
        out[ni - rl:ni, 1] += noise[::-1] * 0.9
    # --- 808 drop: sine with fast pitch dive then a slow glide down, saturated ---
    nd = n - ni
    td = np.arange(nd) / SR
    f = 50 + 150 * np.exp(-td * 38)                     # 200 Hz -> 50 Hz attack
    f = f * (1 - 0.18 * np.clip(td - 0.4, 0, None) / tail)  # slow glide down (the "slide")
    ph = 2 * np.pi * np.cumsum(f) / SR
    boom = np.sin(ph) * np.exp(-td * 1.25)
    boom = np.tanh(boom * 2.6) * 0.62                    # saturation = the 808 growl
    click = rng.standard_normal(nd) * np.exp(-td * 180) * 0.35  # transient
    clap = (rng.standard_normal(nd) - _lowpass(rng.standard_normal(nd), 700)) * np.exp(-td * 22) * 0.18
    drop_sig = boom + click + clap
    out[ni:, 0] += drop_sig
    out[ni:, 1] += drop_sig
    out *= _env(n, 0, int(0.4 * SR), 1.0)[:, None]
    return out / max(1e-9, np.abs(out).max()) * 0.89


def _saw(f, t):
    return 2 * ((f * t) % 1) - 1


def _808(nd, rng, glide=True, drive=2.6, decay=1.25):
    td = np.arange(nd) / SR
    f = 50 + 150 * np.exp(-td * 38)
    if glide:
        f = f * (1 - 0.18 * np.clip(td - 0.4, 0, None) / max(td[-1], 1e-3))
    boom = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-td * decay) * drive) * 0.62
    click = rng.standard_normal(nd) * np.exp(-td * 180) * 0.35
    return boom + click, td


def make_sting_rhythmic(drop, tail=2.8, seed=11):
    """B: rhythmic chord stabs (16ths at 100 bpm) + accelerating snare roll, tape-stop gap, big 808 drop."""
    rng = np.random.default_rng(seed)
    n, ni = int((drop + tail) * SR), int(drop * SR)
    out = np.zeros(n)
    step = 60 / 100 / 4
    chord = (146.83, 174.61, 220.0, 293.66)
    k = 0
    while k * step < drop - 0.25:
        if k % 4 in (0, 3) or k % 8 == 6:
            s0, ln = int(k * step * SR), int(0.11 * SR)
            tt = np.arange(ln) / SR
            stab = sum(_saw(f, tt) for f in chord) * np.exp(-tt * 28) * 0.05
            out[s0:s0 + ln] += _lowpass(stab, 2200)
        k += 1
    # snare roll accelerating over the last second, hitting 32nds
    t0 = max(0, drop - 1.0)
    t, gap = t0, 0.16
    while t < drop - 0.12:
        s0, ln = int(t * SR), int(0.07 * SR)
        tt = np.arange(ln) / SR
        nz = rng.standard_normal(ln)
        out[s0:s0 + ln] += (nz - _lowpass(nz, 1200)) * np.exp(-tt * 45) * (0.08 + 0.18 * (t - t0))
        t += gap; gap = max(0.035, gap * 0.8)
    # 120 ms of silence (the "tape stop" gasp) then the drop
    out[max(0, ni - int(0.12 * SR)):ni] *= 0
    d, td = _808(n - ni, rng, glide=True, drive=3.2, decay=1.1)
    clap = (rng.standard_normal(n - ni) - _lowpass(rng.standard_normal(n - ni), 900)) * np.exp(-td * 18) * 0.25
    out[ni:] += d + clap
    out *= _env(n, 0, int(0.4 * SR))
    st = np.stack([out, np.roll(out, 90)], 1)
    return st / max(1e-9, np.abs(st).max()) * 0.89


def make_sting_cinematic(drop, tail=3.2, seed=5):
    """C: warm synth arpeggio (synthwave), reverse cymbal swell, deep impact without glide + shimmer."""
    rng = np.random.default_rng(seed)
    n, ni = int((drop + tail) * SR), int(drop * SR)
    out = np.zeros((n, 2))
    notes = [146.83, 220.0, 293.66, 349.23, 440.0, 349.23, 293.66, 220.0]  # D minor arpeggio
    step = 60 / 110 / 4
    k = 0
    while k * step < drop:
        s0, ln = int(k * step * SR), int(0.22 * SR)
        ln = min(ln, ni - s0)
        if ln <= 0:
            break
        tt = np.arange(ln) / SR
        f = notes[k % len(notes)]
        v = (_saw(f, tt) + _saw(f * 1.005, tt)) * np.exp(-tt * 7) * 0.05
        v = _lowpass(v, 1400 + 1800 * min(1, k * step / max(drop, 0.1)))  # filter opens up
        pan = 0.3 if k % 2 else -0.3
        out[s0:s0 + ln, 0] += v * (1 - pan)
        out[s0:s0 + ln, 1] += v * (1 + pan)
        k += 1
    rl = int(min(1.4, drop) * SR)
    nz = rng.standard_normal(rl)
    cym = (nz - _lowpass(nz, 4000)) * np.linspace(0, 1, rl) ** 3 * 0.3
    out[ni - rl:ni, 0] += cym
    out[ni - rl:ni, 1] += cym[::-1] * 0.95
    nd = n - ni
    td = np.arange(nd) / SR
    sub = np.sin(2 * np.pi * (42 + 60 * np.exp(-td * 20)) * td) * np.exp(-td * 0.9) * 0.7
    hit = rng.standard_normal(nd) * np.exp(-td * 12) * 0.25
    hit = _lowpass(hit, 600)
    shimmer = sum(np.sin(2 * np.pi * f * td) for f in (1174.66, 1760.0, 2349.3)) * np.exp(-td * 1.6) * 0.03
    imp = np.tanh((sub + hit) * 1.8) * 0.7 + shimmer
    out[ni:, 0] += imp
    out[ni:, 1] += imp
    out *= _env(n, 0, int(0.6 * SR))[:, None]
    return out / max(1e-9, np.abs(out).max()) * 0.89


STINGS = {"a": make_sting, "b": make_sting_rhythmic, "c": make_sting_cinematic}
DEFAULT_STING = "c"
STING_TRIM_DB = {"a": 0.0, "b": 0.4, "c": -1.1}  # same loudness (measured LUFS) for a fair comparison


def write_wav(path, x):
    import wave
    x16 = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(x16.tobytes())


def loop_track(path, need, xfade=3.0):
    """A track long enough for `need` seconds: when the video is longer than the song, the song starts again
    from the beginning with a crossfade instead of leaving the end silent."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True).stdout)
    if dur >= need:
        return path
    n = 2
    while n * dur - (n - 1) * xfade < need:
        n += 1
    import hashlib, tempfile
    out = os.path.join(tempfile.gettempdir(), f"loop-{hashlib.md5(path.encode()).hexdigest()[:10]}-{n}.wav")
    if not os.path.exists(out):
        fc = "".join(f"[{i}:a]" for i in range(2)) + f"acrossfade=d={xfade}[x1];"
        for i in range(2, n):
            fc += f"[x{i - 1}][{i}:a]acrossfade=d={xfade}[x{i}];"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ["-i", path] * n + ["-filter_complex", fc.rstrip(";"), "-map", f"[x{n - 1}]", out], check=True)
    return out


if __name__ == "__main__":
    if len(sys.argv) > 3 and sys.argv[1] == "sting":
        write_wav(sys.argv[2], STINGS[sys.argv[4] if len(sys.argv) > 4 else "c"](float(sys.argv[3])))
        print("sting written", sys.argv[2])
    else:
        print(__doc__)
