#!/usr/bin/env python3
"""Repeats the QA agent cannot see in a cleaned transcript (the creator's v9 review, 2026-10-03 : 7 repeats missed).
  python3 tools/redites.py <slug>   -> work/qa/redites.json
1. n-grams (3 to 5 words) said more often in the edit than in the teleprompter script (« pour pouvoir bénéficier » 2 vs 1) ;
2. words whose voiced time is far longer than the word (a false start Whisper merged into the next word) ;
3. voiced stretches with no word at all (an untranscribed retake).
Each item has an output time ; the agent only judges these, by ear."""
import json, os, re, sys
from collections import Counter
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import prompteur as PR

slug = sys.argv[1]
Q = PR.P(slug, "work", "qa")
norm = lambda s: re.sub(r"[^\w']", " ", s.lower()).split()
ow = json.load(open(PR.P(slug, "assets", "out_words.json")))["words"]
toks = [(norm(w["text"]), w) for w in ow]
flat = [(t, w) for ts, w in toks for t in ts]
script = norm(open(os.path.join(Q, "script.txt")).read()) if os.path.exists(os.path.join(Q, "script.txt")) else []
out = []
for n in (5, 4, 3):
    ce = Counter(tuple(x[0] for x in flat[i:i + n]) for i in range(len(flat) - n + 1))
    cs = Counter(tuple(script[i:i + n]) for i in range(len(script) - n + 1))
    for g, c in ce.items():
        if c > max(cs.get(g, 0), 1) or (c >= 2 and cs.get(g, 0) == 0 and len(set(g)) > 1):
            at = [round(flat[i][1]["start"], 2) for i in range(len(flat) - n + 1) if tuple(x[0] for x in flat[i:i + n]) == g]
            if any(b - a < 20 for a, b in zip(at, at[1:])):  # the same group twice within 20 s
                out.append({"kind": "ngram", "text": " ".join(g), "edit": c, "script": cs.get(g, 0), "at": at})
seen, uniq = set(), []
for o in out:  # keep the longest n-gram per place
    key = tuple(o["at"])
    if not any(set(key) & s for s in seen):
        uniq.append(o); seen.add(frozenset(key))
x, sr = sf.read(PR.P(slug, "work", "base.wav"), always_2d=True); x = x.mean(1)
hop = sr // 100
db = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop) / hop, "same")[::hop]) + 1e-9)
voiced = db > -40
for w in ow:
    a, b = int(w["start"] * 100), int(w["end"] * 100)
    v = voiced[a:b].sum() / 100
    letters = len(re.sub(r"\W", "", w["text"]))
    if v > 0.45 and letters <= 4:
        uniq.append({"kind": "long-word", "text": w["text"], "at": [round(w["start"], 2)], "voiced_s": round(v, 2)})
starts = sorted((w["start"], w["end"]) for w in ow)
for (a0, b0), (a1, b1) in zip(starts, starts[1:]):
    gap = voiced[int(b0 * 100):int(a1 * 100)].sum() / 100
    if gap > 0.3:
        uniq.append({"kind": "untranscribed-speech", "at": [round(b0, 2)], "voiced_s": round(gap, 2)})
json.dump(sorted(uniq, key=lambda o: o["at"][0]), open(os.path.join(Q, "redites.json"), "w"), ensure_ascii=False, indent=1)
print(len(uniq), "suspects ->", os.path.join(Q, "redites.json"))
