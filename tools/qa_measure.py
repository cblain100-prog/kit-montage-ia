#!/usr/bin/env python3
"""Stage 1 of the editing checks (no agent, no render, seconds) : every voice joint measured on the rush from
assets/edl.json, against the grid validated by the creator. Agents only judge what this flags.

  breath   : >= 0.15 s of silence after the last word, 0.30 to 0.55 s in total around a joint (v2 : cuts too soon ; 2026-10-03 : 0.75 s « trop d'espace »)
  cut word : sound still above -30 dB in the last 50 ms of a piece (a word cut short)
  clipped  : sound above -35 dB in the first 30 ms of the next piece (an attack cut)

  python3 tools/qa_measure.py <slug> [--json out.json]
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import montage as M
import prompteur as PR

slug = sys.argv[1]
db = PR.energy(slug)
e = M.load(M.P(slug, "assets", "edl.json")); fps = e["fps"]; P = e["pieces"]
SPEECH = -40
def lvl(a, b): return float(np.max(db[int(a * 100):max(int(a * 100) + 1, int(b * 100))]))
out, bad = [], 0
for p, q in zip(P, P[1:]):
    if abs(p["src"][1] - q["src"][0]) <= 1:
        continue
    a1, b2 = p["src"][1] / fps, q["src"][0] / fps
    k = int(a1 * 100); back = 0
    while back < 150 and db[k - back - 1] < SPEECH: back += 1
    k2 = int(b2 * 100); fwd = 0
    while fwd < 150 and db[k2 + fwd] < SPEECH: fwd += 1
    r = dict(out=round(p["out"][1] / fps, 2), rush_end=round(a1, 2), rush_next=round(b2, 2), after_word=back / 100, before_word=fwd / 100,
             end_db=round(lvl(a1 - .02, a1), 1), start_db=round(lvl(b2, b2 + .03), 1))
    flags = []
    if r["after_word"] < 0.15: flags.append("breath-after")  # less is fine when the next take starts later (total below)
    if r["after_word"] + r["before_word"] < 0.30: flags.append("breath-total")
    if r["after_word"] + r["before_word"] > 0.55: flags.append("too-long")
    if r["end_db"] > -30: flags.append("cut-word")
    if r["start_db"] > -35: flags.append("clipped-attack")
    r["flags"] = flags; bad += bool(flags); out.append(r)
for i, r in enumerate(out, 1):
    if r["flags"]:
        print(f"{i:3d} out {r['out']:7.2f}  rush {r['rush_end']:7.2f}|{r['rush_next']:7.2f}  after {r['after_word']:.2f} before {r['before_word']:.2f}  end {r['end_db']} start {r['start_db']}  {','.join(r['flags'])}")
print(f"{len(out)} joints, {bad} flagged")
if "--json" in sys.argv:
    json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
