#!/usr/bin/env python3
"""Writes the default sound effects of the kit into assets/sfx/, synthesised from scratch (original sounds, no licence
issue, nothing to credit). Every name the engine and the look use is covered ; replace any file by a sound you prefer
(same name, WAV), for example from Mixkit or Pixabay (see assets/README.md).

  python3 tools/make_sfx.py [--force]      (an existing file is kept unless --force)
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "assets", "sfx")
SR = 48000
rng = np.random.default_rng(2026)


def t_(d):
    return np.arange(int(d * SR)) / SR


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def bandnoise(d, lo, hi):
    n = rng.standard_normal(int(d * SR))
    return highpass(lowpass(n, hi), lo)


def env(n, a, r, curve=2.0):
    e = np.ones(n)
    a, r = int(a * SR), int(r * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** curve
    return e


def norm(x, peak=0.8):
    return x / (np.abs(x).max() + 1e-9) * peak


def stereo(x, width=0.0):
    d = int(width * SR)
    r = np.roll(x, d) if d else x
    return np.stack([x, r], 1)


def pop():
    t = t_(0.09)
    f = 900 * np.exp(-t * 40) + 320
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 55)
    x += bandnoise(0.09, 2000, 6000) * np.exp(-t * 300) * 0.25
    return norm(x, 0.7)


def whoosh(d=0.45, lo=300, hi=5000, peak_at=0.6):
    n = int(d * SR)
    x = rng.standard_normal(n)
    # sweeping band : the filter opens towards the peak then closes
    k = np.linspace(0, 1, n)
    shape = np.where(k < peak_at, (k / peak_at) ** 2, ((1 - k) / (1 - peak_at)) ** 1.5)
    out = np.zeros(n)
    blk = 512
    for i in range(0, n, blk):
        c = lo + (hi - lo) * shape[min(i + blk // 2, n - 1)]
        seg = lowpass(x[max(0, i - 2048):i + blk], c)[-len(x[i:i + blk]):]
        out[i:i + blk] = seg
    out = highpass(out, 150) * shape
    return norm(out, 0.6)


def click(soft=True):
    t = t_(0.04)
    x = bandnoise(0.04, 1500 if soft else 2500, 7000 if soft else 11000) * np.exp(-t * (260 if soft else 380))
    x += np.sin(2 * np.pi * (1800 if soft else 2600) * t) * np.exp(-t * 400) * 0.4
    return norm(x, 0.55 if soft else 0.7)


def key_press():
    t = t_(0.06)
    x = bandnoise(0.06, 1200, 8000) * np.exp(-t * 180) + np.sin(2 * np.pi * 180 * t) * np.exp(-t * 90) * 0.3
    return norm(x, 0.6)


def typing(d=2.4):
    out = np.zeros(int(d * SR))
    t = 0.03
    while t < d - 0.08:
        k = key_press() * rng.uniform(0.5, 1.0)
        i = int(t * SR)
        out[i:i + len(k)] += k[:len(out) - i]
        t += rng.uniform(0.06, 0.16)
    return norm(out, 0.6)


def sparkle():
    t = t_(0.6)
    x = np.zeros(len(t))
    for j, f in enumerate((2093, 2637, 3136, 4186)):
        s0 = int(j * 0.06 * SR)
        tt = t[:len(t) - s0]
        x[s0:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt * 9) * 0.25
    return norm(x, 0.5)


def riser(d):
    n = int(d * SR)
    k = np.linspace(0, 1, n)
    x = highpass(rng.standard_normal(n), 800) * k ** 2.2 * 0.5
    f = 200 + 900 * k ** 2
    x += np.sin(2 * np.pi * np.cumsum(f) / SR) * k ** 2 * 0.25
    x *= env(n, 0, 0.02)
    return norm(x, 0.6)


def impact(sub=48, bright=0.25, d=1.6):
    t = t_(d)
    f = sub + 90 * np.exp(-t * 25)
    x = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2) * 2.0) * 0.8
    x += lowpass(rng.standard_normal(len(t)), 900) * np.exp(-t * 14) * 0.5
    x += bandnoise(d, 3000, 9000) * np.exp(-t * 30) * bright
    return norm(x, 0.85)


def reverse_cymbal(d=1.6):
    t = t_(d)
    x = bandnoise(d, 4000, 15000) * np.exp(-t * 2.8)
    x += sum(np.sin(2 * np.pi * f * t) for f in (3521, 4699, 6271)) * np.exp(-t * 3.5) * 0.04
    return norm(x[::-1] * env(len(t), 0.0, 0.01), 0.7)


SOUNDS = {
    "pop.wav": lambda: stereo(pop()),
    "whoosh-short.wav": lambda: stereo(whoosh(0.32, 400, 6000, 0.55), 0.004),
    "whoosh.wav": lambda: stereo(whoosh(0.5, 250, 5000, 0.6), 0.006),
    "click-soft.wav": lambda: stereo(click(True)),
    "click.wav": lambda: stereo(click(False)),
    "key-press.wav": lambda: stereo(key_press()),
    "typing.wav": lambda: stereo(typing(), 0.002),
    "sparkle.wav": lambda: stereo(sparkle(), 0.008),
    "riser-0.6s.wav": lambda: stereo(riser(0.6), 0.005),
    "riser-1.0s.wav": lambda: stereo(riser(1.0), 0.005),
    "hook-riser-1.wav": lambda: stereo(riser(1.4), 0.006),
    "hook-impact-1.wav": lambda: stereo(impact(46, 0.2)),
    "hook-impact-2.wav": lambda: stereo(impact(52, 0.3, 1.3)),
    "hook-impact-3.wav": lambda: stereo(impact(42, 0.15, 1.9)),
    "impact-bass-1.wav": lambda: stereo(impact(40, 0.05, 1.2)),
    "impact-bass-2.wav": lambda: stereo(impact(36, 0.08, 1.5)),
    "hook-reverse-1.wav": lambda: stereo(reverse_cymbal(1.4), 0.004),
    "hook-reverse-2.wav": lambda: stereo(reverse_cymbal(1.8), 0.004),
}


def main():
    import soundfile as sf
    os.makedirs(OUT, exist_ok=True)
    force = "--force" in sys.argv
    n = 0
    for name, make in SOUNDS.items():
        f = os.path.join(OUT, name)
        if os.path.exists(f) and not force:
            continue
        sf.write(f, make().astype(np.float32), SR, subtype="PCM_16")
        n += 1
    print(f"{n} sound effects written to {OUT} ({len(SOUNDS)} in the set)")


if __name__ == "__main__":
    main()
