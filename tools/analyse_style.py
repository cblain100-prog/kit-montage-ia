#!/usr/bin/env python3
"""Measures the editing style of one of the creator's OWN edited videos, to seed their look (« style-de-montage » skill).

  python3 tools/analyse_style.py <video> [--out folder] [--name mon-style] [--demucs]

Measures, all local :
  cuts         every cut (ffmpeg scene detection, low threshold so same-camera reframes count) : shot length (mean, median),
               cuts per minute, for the whole video and the first 60 s (the intro is often faster)
  framing      face size on one frame per shot (Apple Vision) : wide / tight / very tight, how often the framing changes,
               shots without a face (full-screen visuals) and their share of the time
  zooms        face size at the start and the end of each shot : slow push-ins / pull-outs inside shots
  text         on-screen text per shot (Apple Vision OCR), static text (a logo seen everywhere) ignored
  sound        loudness (LUFS, range, true peak) ; music under the voice estimated from the quietest moments, or measured
               exactly with --demucs (needs `pip install demucs`, slow)
Writes <out>/style-sheet.jpg (one frame per shot, labelled) and <out>/style.json (measures + suggested look values).
Default <out> : projects/_styles/<name>/ . Never use another creator's video : the point is YOUR style."""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(v):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", v]).stdout)


def scene_cuts(v, thr):
    err = run(["ffmpeg", "-hide_banner", "-i", v, "-an", "-vf", f"scale=320:-2,select='gt(scene,{thr})',showinfo", "-f", "null", "-"]).stderr
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", err)]


def grab(v, t, out, w=640):
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", v, "-frames:v", "1", "-vf", f"scale={w}:-2", out])
    return out


def facebox_bin():
    b = os.path.join(HERE, "tools", "bin", "facebox")
    if not os.path.exists(b):
        os.makedirs(os.path.dirname(b), exist_ok=True)
        run(["swiftc", "-O", "-o", b, os.path.join(HERE, "tools", "facebox.swift")])
    return b if os.path.exists(b) else None


def vision(paths, text=False):
    fb = facebox_bin()
    if not fb or not paths:
        return [None] * len(paths)
    out = []
    for k in range(0, len(paths), 40):
        r = run([fb] + (["--text"] if text else []) + paths[k:k + 40]).stdout
        out += [json.loads(l) for l in r.splitlines() if l.strip()]
    return out


def loudness(path):
    err = run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"]).stderr
    g = lambda k: float(re.findall(k + r":\s+(-?[0-9.]+)", err)[-1]) if re.findall(k + r":\s+(-?[0-9.]+)", err) else None
    return {"lufs": g("I"), "range_lu": g("LRA"), "true_peak_db": g("Peak")}


def short_term(path):
    """Loudness every 0.4 s (LUFS-like, from RMS of a K-weighting-free mono mix : enough to compare levels)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32)
    h = int(0.4 * 16000)
    n = len(x) // h
    return 20 * np.log10(np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)


def music_estimate(v, tmp, use_demucs):
    if use_demucs:
        try:
            run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-o", tmp, v])
            d = next(os.path.join(r, "") for r, _, f in os.walk(tmp) if "vocals.wav" in f)
            vo, mu = loudness(d + "vocals.wav")["lufs"], loudness(d + "no_vocals.wav")["lufs"]
            if vo is not None and mu is not None:
                return {"method": "demucs", "music_under_voice_lu": round(vo - mu, 1), "music_present": mu > -45}
        except Exception as e:  # demucs missing or failed : the estimate below
            print("  demucs unavailable :", str(e)[:120])
    st = short_term(v)
    if not len(st):
        return {"method": "none"}
    speech, floor = np.percentile(st, 90), np.percentile(st, 8)
    present = floor > -50 and speech - floor < 30
    return {"method": "estimate (quietest 8 % of the video vs speech)", "speech_db": round(float(speech), 1), "floor_db": round(float(floor), 1),
            "music_present": bool(present), "music_under_voice_lu": round(float(speech - floor), 1) if present else None}


def framing_of(h):
    """Face height / frame height -> framing name."""
    if h is None:
        return "visuel"
    return "large" if h < 0.30 else "serré" if h < 0.45 else "très serré"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--out"); ap.add_argument("--name", default="mon-style")
    ap.add_argument("--threshold", type=float, default=0.22, help="scene threshold (lower = more cuts found)")
    ap.add_argument("--demucs", action="store_true")
    A = ap.parse_args()
    v = os.path.abspath(os.path.expanduser(A.video))
    out = A.out or os.path.join(HERE, "projects", "_styles", A.name)
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="style-")
    dur = duration(v)
    cuts = [c for c in scene_cuts(v, A.threshold) if 0.2 < c < dur - 0.2]
    # two detections closer than 4 frames are one cut (a flash, a dissolve)
    merged = []
    for c in cuts:
        if not merged or c - merged[-1] > 0.13:
            merged.append(c)
    bounds = [0.0] + merged + [dur]
    shots = [(a, b) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]
    lens = np.array([b - a for a, b in shots])
    intro = [b - a for a, b in shots if a < 60]
    # one frame per shot (middle) + start / end frames for zooms, at most 120 shots sampled evenly
    idx = list(range(len(shots))) if len(shots) <= 120 else list(np.linspace(0, len(shots) - 1, 120).astype(int))
    mids, starts, ends = [], [], []
    for i in idx:
        a, b = shots[i]
        mids.append(grab(v, (a + b) / 2, os.path.join(tmp, f"m{i:04d}.jpg")))
        if b - a > 1.2:
            starts.append((i, grab(v, a + 0.15, os.path.join(tmp, f"s{i:04d}.jpg"), 480)))
            ends.append((i, grab(v, b - 0.15, os.path.join(tmp, f"e{i:04d}.jpg"), 480)))
    faces = vision(mids)
    texts = vision(mids, text=True)
    fs = vision([p for _, p in starts]); fe = vision([p for _, p in ends])
    zooms = []
    for (i, _), s, e in zip(starts, fs, fe):
        if s and e and "h" in s and "h" in e and s["h"] > 0.05:
            zooms.append(e["h"] / s["h"] - 1)
    zin = sum(1 for z in zooms if z > 0.04); zout = sum(1 for z in zooms if z < -0.04)
    # static text (a logo, a watermark) is in most shots : ignored
    seen = {}
    for t in texts:
        for w in (t or {}).get("text", "").split(" | "):
            if w:
                seen[w] = seen.get(w, 0) + 1
    static = {w for w, n in seen.items() if n > max(3, 0.4 * len(texts))}
    # small text (a label on a microphone, a sign in the room) is noise : at least 1.2 % of the frame
    text_shots = [i for i, t in zip(idx, texts) if t and t.get("area", 0) > 0.012 and any(w and w not in static for w in t.get("text", "").split(" | "))]
    rows = []
    for k, i in enumerate(idx):
        f = faces[k] if k < len(faces) else None
        h = f.get("h") if f and "h" in f else None
        rows.append({"shot": i, "start": round(shots[i][0], 2), "len": round(shots[i][1] - shots[i][0], 2), "framing": framing_of(h),
                     "face_h": h, "text": (texts[k] or {}).get("text", "") if k < len(texts) else ""})
    face_rows = [r for r in rows if r["framing"] != "visuel"]
    changes = sum(1 for x, y in zip(face_rows, face_rows[1:]) if x["framing"] != y["framing"])
    vis_time = sum(r["len"] for r in rows if r["framing"] == "visuel") * (len(shots) / max(1, len(idx)))
    count = lambda name: sum(1 for r in rows if r["framing"] == name)
    sound = loudness(v)
    music = music_estimate(v, tmp, A.demucs)
    # contact sheet : one labelled frame per sampled shot, 6 columns, at most 48 tiles
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(os.path.join(HERE, "assets", "fonts", "Poppins-Medium.ttf"), 13)  # accents (« serré ») need a real font
    tiles = []
    for r, p in list(zip(rows, mids))[:48]:
        im = Image.open(p).convert("RGB").resize((320, 180))
        d = ImageDraw.Draw(im)
        lab = f"{int(r['start'] // 60)}:{r['start'] % 60:04.1f}  {r['len']:.1f}s  {r['framing']}" + ("  T" if r["shot"] in text_shots else "")
        d.rectangle([0, 158, 320, 180], fill=(0, 0, 0))
        d.text((6, 160), lab, fill=(255, 220, 120), font=font)
        tiles.append(im)
    cols = 6
    sheet = Image.new("RGB", (cols * 320, max(1, -(-len(tiles) // cols)) * 180), (10, 10, 10))
    for k, im in enumerate(tiles):
        sheet.paste(im, ((k % cols) * 320, (k // cols) * 180))
    sheet_path = os.path.join(out, "style-sheet.jpg")
    sheet.save(sheet_path, quality=85)
    med = float(np.median(lens)) if len(lens) else 0
    res = {
        "video": os.path.basename(v), "duration_s": round(dur, 1),
        "cuts": {"count": len(shots) - 1, "per_minute": round((len(shots) - 1) / dur * 60, 1), "mean_shot_s": round(float(lens.mean()), 2),
                 "median_shot_s": round(med, 2), "intro_mean_shot_s": round(float(np.mean(intro)), 2) if intro else None,
                 "shortest_s": round(float(lens.min()), 2), "longest_s": round(float(lens.max()), 2)},
        "framing": {"sampled_shots": len(idx), "large": count("large"), "serré": count("serré"), "très serré": count("très serré"),
                    "visuel (no face)": count("visuel"), "framing_changes_between_face_shots": changes,
                    "visual_share_of_time": round(vis_time / dur, 2)},
        "zooms_inside_shots": {"measured": len(zooms), "push_in": zin, "pull_out": zout,
                               "mean_change_pct": round(float(np.mean(np.abs(zooms))) * 100, 1) if zooms else None},
        "text": {"shots_with_text": len(text_shots), "share": round(len(text_shots) / max(1, len(idx)), 2), "static_ignored": sorted(static)[:10],
                 "examples": [r["text"] for r in rows if r["shot"] in text_shots][:8]},
        "sound": sound, "music": music,
        "sheet": sheet_path,
    }
    # suggestions for look.json (the skill shows them, the creator decides)
    res["suggested_look"] = {
        "cut.shot_target": round(min(max(med, 1.5), 4.0), 1),
        "cut.min_shot": round(min(max(float(np.percentile(lens, 15)) if len(lens) else 1.4, 1.0), 2.0), 1),
        "cut.max_shot": round(min(max(float(np.percentile(lens, 85)) if len(lens) else 3.4, 2.5), 6.0), 1),
        "intro faster": bool(intro and np.mean(intro) < 0.8 * lens.mean()),
        "zoom.default": "push / pull inside shots" if zooms and (zin + zout) > 0.4 * len(zooms) else "cuts only, few zooms",
        "music.body.under_lu": music.get("music_under_voice_lu"),
        "keywords.frequency": f"text on {round(len(text_shots) / max(1, len(idx)) * 100)} % of shots",
    }
    json.dump(res, open(os.path.join(out, "style.json"), "w"), ensure_ascii=False, indent=1)
    c, fr = res["cuts"], res["framing"]
    print(f"{res['video']} : {dur:.0f} s, {c['count']} coupes, {c['per_minute']} par minute, plan moyen {c['mean_shot_s']} s (médian {c['median_shot_s']} s)"
          + (f", intro {c['intro_mean_shot_s']} s" if c["intro_mean_shot_s"] else ""))
    print(f"cadrages : {fr['large']} larges, {fr['serré']} serrés, {fr['très serré']} très serrés, {fr['visuel (no face)']} visuels sans visage "
          f"({round(fr['visual_share_of_time'] * 100)} % du temps), {fr['framing_changes_between_face_shots']} changements de cadrage")
    z = res["zooms_inside_shots"]
    print(f"zooms dans les plans : {z['push_in']} avancées, {z['pull_out']} reculs sur {z['measured']} plans mesurés")
    print(f"texte à l'écran : {res['text']['shots_with_text']} plans ({round(res['text']['share'] * 100)} %)")
    print(f"son : {sound['lufs']} LUFS, musique : " + (f"oui, environ {music.get('music_under_voice_lu')} LU sous la voix ({music['method']})" if music.get("music_present") else f"pas détectée ({music['method']})"))
    print("planche :", sheet_path)
    print("mesures :", os.path.join(out, "style.json"))


if __name__ == "__main__":
    main()
