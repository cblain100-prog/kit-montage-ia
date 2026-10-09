#!/usr/bin/env python3
"""Hear a stretch of the edited voice (for the checking agents): words with times, and the sound level every 50 ms.
  python3 tools/hear.py <slug> <start s> <end s>      (output time of the edit, work/base16.wav)"""
import os, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import montage as M, fastwhisper
import prompteur as PR
slug, a, b = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
y, sr = sf.read(M.P(slug, "work", "base16.wav"))
seg = np.concatenate([np.zeros(int(.3 * sr)), y[int(a * sr):int(b * sr)], np.zeros(int(.3 * sr))]).astype(np.float32)
r = fastwhisper.load_model("medium").transcribe(seg, language=PR.lang(slug), word_timestamps=True, condition_on_previous_text=False, temperature=0)
print("words :", " ".join(f"{w['word'].strip()}@{a - .3 + w['start']:.2f}" for s in r["segments"] for w in s["words"]))
db = lambda t: 20 * np.log10(np.sqrt(np.mean(y[int(t * sr):int((t + .05) * sr)] ** 2)) + 1e-9)
print("level :", " ".join(f"{t:.2f}:{db(t):.0f}" for t in np.arange(a, b, .05)))
