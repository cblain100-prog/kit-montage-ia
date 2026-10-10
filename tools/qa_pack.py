#!/usr/bin/env python3
"""Evidence pack for the verification agents (kit-montage-*). Everything a checker needs, measured once, in work/qa/ :

  script.txt        the teleprompter text (what he meant to say)
  edited.txt        the edited voice, transcribed, one line per ~sentence with output times
  joints.json       every voice joint : text before / after / across, sound level at the cut, silence kept around it
  inserts.json      every visual : id, kind, out times, the words he says during it, its strip image
  strips/<id>.jpg   6 frames : just before, start, 1/3, 2/3, end, just after
  sheets/NN.jpg     the whole video, one frame every 2 s, 48 per sheet, time-stamped

  python3 tools/qa_pack.py <slug> <render name> [<script : .html, .md or .txt>]
"""
import html, json, os, re, subprocess, sys
import numpy as np, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import montage as M, fastwhisper
import prompteur as PR
from PIL import Image, ImageDraw

slug, name = sys.argv[1], sys.argv[2]
tp = sys.argv[3] if len(sys.argv) > 3 else None
Q = M.P(slug, "work", "qa"); os.makedirs(f"{Q}/strips", exist_ok=True); os.makedirs(f"{Q}/sheets", exist_ok=True)
video = M.P(slug, "renders", f"{name}.mp4")

# script
if tp:
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", open(os.path.expanduser(tp)).read(), flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", s)) if tp.endswith((".html", ".htm")) else s
    open(f"{Q}/script.txt", "w").write("\n".join(l.strip() for l in t.splitlines() if l.strip()))

# edited voice
W = M.load(M.P(slug, "assets", "out_words.json"))["words"]
lines, cur = [], []
for w in W:
    cur.append(w)
    if w["text"].rstrip().endswith((".", "?", "!")) or len(cur) > 28:
        lines.append(f"[{cur[0]['start']:7.2f}-{cur[-1]['end']:7.2f}] " + " ".join(x["text"] for x in cur)); cur = []
if cur:
    lines.append(f"[{cur[0]['start']:7.2f}-{cur[-1]['end']:7.2f}] " + " ".join(x["text"] for x in cur))
open(f"{Q}/edited.txt", "w").write("\n".join(lines))

# joints
e = M.load(M.P(slug, "assets", "edl.json")); fps = e["fps"]; P = e["pieces"]
y, sr = sf.read(PR.voice(slug, True))
yo, _ = sf.read(M.P(slug, "work", "base16.wav"))
m = fastwhisper.load_model("medium")
def T(a):
    a = np.concatenate([np.zeros(int(.25 * sr)), a, np.zeros(int(.25 * sr))]).astype(np.float32)
    return " ".join(w["word"].strip() for s in m.transcribe(a, language=PR.lang(slug), word_timestamps=True, condition_on_previous_text=False, temperature=0)["segments"] for w in s["words"])
def db(a): return float(20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-9)) if len(a) else -99.0
J = []
for n, (p, q) in enumerate(zip(P, P[1:])):
    if abs(p["src"][1] - q["src"][0]) <= 1:
        continue
    a1, b2, t_out = p["src"][1] / fps, q["src"][0] / fps, p["out"][1] / fps
    before, after = y[int((a1 - 1.8) * sr):int(a1 * sr)], y[int(b2 * sr):int((b2 + 1.8) * sr)]
    k = int(t_out * sr); h = sr // 100
    back = 0
    while k - (back + 1) * h > 0 and db(yo[k - (back + 1) * h:k - back * h]) < -40: back += 1
    fwd = 0
    while k + (fwd + 1) * h < len(yo) and db(yo[k + fwd * h:k + (fwd + 1) * h]) < -40: fwd += 1
    J.append(dict(n=len(J) + 1, out=round(t_out, 2), rush_end=round(a1, 2), rush_next=round(b2, 2),
                  before=T(before), after=T(after), across=T(np.concatenate([before, after])),
                  level_last_50ms_db=round(db(before[-int(.05 * sr):]), 1), silence_kept_s=round((back + fwd) / 100, 2),
                  silence_after_last_word_s=round(back / 100, 2), silence_before_next_word_s=round(fwd / 100, 2)))
    print("joint", len(J), flush=True)
json.dump(J, open(f"{Q}/joints.json", "w"), ensure_ascii=False, indent=1)

# inserts
plan = M.load(M.P(slug, "plan.json")); times = M.load(M.P(slug, "work", "insert-times.json"))
plan["inserts"] = [i for i in plan["inserts"] if i["id"] in times]  # keywords dropped by cmd_inserts
I = []
for ins in plan["inserts"]:
    s0, e0 = times[ins["id"]][0], times[ins["id"]][1]
    ts = [max(0, s0 - 0.1), s0 + 0.05, s0 + (e0 - s0) / 3, s0 + 2 * (e0 - s0) / 3, e0 - 0.1, e0 + 0.1]
    frames = []
    for i, t0 in enumerate(ts):
        f = f"{Q}/strips/_{i}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-i", video, "-frames:v", "1", "-vf", "scale=400:225", f])
        im = Image.open(f).convert("RGB"); ImageDraw.Draw(im).text((6, 4), f"{t0:.2f}", fill=(255, 255, 0)); frames.append(im)
    strip = Image.new("RGB", (2400, 225)); [strip.paste(im, (i * 400, 0)) for i, im in enumerate(frames)]
    strip.save(f"{Q}/strips/{ins['id']}.jpg", quality=80)
    said = " ".join(w["text"] for w in W if s0 - 0.6 <= w["start"] <= e0 + 0.3)
    desc = {k: v for k, v in ins.items() if k in ("kind", "src", "title", "label", "n", "items", "rows", "type")}
    I.append(dict(id=ins["id"], kind=ins["kind"], out_start=round(s0, 2), out_end=round(e0, 2), said=said, strip=f"strips/{ins['id']}.jpg",
                  desc=json.dumps(desc, ensure_ascii=False)[:600]))
json.dump(I, open(f"{Q}/inserts.json", "w"), ensure_ascii=False, indent=1)

# sheets
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video], capture_output=True, text=True).stdout)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", "fps=1/2,scale=320:180", f"{Q}/sheets/f%04d.png"])
fs = sorted(x for x in os.listdir(f"{Q}/sheets") if x.startswith("f"))
for n in range(0, len(fs), 48):
    sh = Image.new("RGB", (320 * 8, 180 * 6))
    for k, f in enumerate(fs[n:n + 48]):
        im = Image.open(f"{Q}/sheets/{f}").convert("RGB"); ImageDraw.Draw(im).text((6, 4), f"{(n + k) * 2}s", fill=(255, 255, 0))
        sh.paste(im, ((k % 8) * 320, (k // 8) * 180))
    sh.save(f"{Q}/sheets/{n // 48 + 1:02d}.jpg", quality=80)
for f in fs: os.remove(f"{Q}/sheets/{f}")
print("pack ok", len(J), "joints", len(I), "inserts")
