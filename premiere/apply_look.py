"""Apply the creator's look (looks/<look>/look.json) to the face track in Premiere Pro, then splice the result back.
  python3 premiere/apply_look.py <slug> <until_out_seconds>
Face track = work/base-v.mp4 (framings already cut by prompteur.py base). Premiere adds the zooms:
  B (default) : every shot pushes 100 -> 108 % over its length ;
  C (accent)  : on a strong word (impact sound or keyword of the plan), quick eased zoom +12 %, held to the cut.
Output : work/base-v-look.mp4 (same length as base-v), to set as plan.base_video before prompteur.py compose."""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import prompteur as PR
from ppclient import PP
import ppbatch as PB
import paths

FPS, F = 30, 1 / 30


def ease(t0, dur, v0, v1, steps=6):
    """Cubic ease-out drawn with keys (the MCP resets Premiere's interpolation to linear when it sets a value)."""
    return [(t0 + dur * k / steps, v0 + (v1 - v0) * (1 - (1 - k / steps) ** 3)) for k in range(steps + 1)]


def plan_keys(slug, until):
    plan = PR.load_plan(slug)
    look = PR.load_look(plan)
    zb, zc = look["zoom"]["default"], look["zoom"]["accent"]
    times = json.load(open(PR.P(slug, "work", "insert-times.json")))
    plan["inserts"] = [i for i in plan["inserts"] if i["id"] in times]
    full = [tuple(times[i["id"]][:2]) for i in plan["inserts"] if not PR.overlay_kind(i)]
    on_face = lambda t: not any(a - 0.1 <= t <= b + 0.1 for a, b in full)
    cuts = sorted({p["out"][0] / FPS for p in PR.edl(slug) if p["out"][0] / FPS < until} | {0.0})
    shots = list(zip(cuts, cuts[1:] + [until]))
    # strong words : impact sounds of the plan and keywords (1-2 giant words)
    cand = [PR.to_out(slug, PR.anchor(slug, t)) for f, t, db in plan.get("sfx", []) if f.startswith("impact") and isinstance(t, str)]
    cand += [times[i["id"]][0] for i in plan["inserts"] if i.get("kind") == "keyword"]
    # after the intro : spoken numbers and a few punch words (the body has no keyword cards)
    pieces = PR.edl(slug)
    kept = lambda t: any(p["src"][0] <= t * FPS < p["src"][1] and not p.get("cold") for p in pieces)
    punch = re.compile(r"\d|^(" + look["zoom"].get("accent_words", "jamais|attention|important|gratuit|surtout|fini|cher") + r")\b", re.I)
    cand += [PR.to_out(slug, w["start"], pieces) for w in PR.words(slug) if punch.search(w["text"].strip(" .,!?«»")) and kept(w["start"])]
    ca = (plan.get("music") or {}).get("close", {}).get("at", plan.get("intro_until", 45))
    intro_end = PR.to_out(slug, PR.anchor(slug, ca)) if isinstance(ca, str) else float(ca)
    acc, last = [], -99
    for w in sorted(c for c in cand if c < until):
        shot = next(((a, b) for a, b in shots if a <= w < b), None)
        gap = 5 if w < intro_end else 14  # « parfois le C », never on every shot
        if zc.get("enabled", True) and shot and on_face(w) and on_face(w + 1.0) and w - last >= gap and shot[1] - w >= 0.5:  # accent.enabled false : no punch-in
            acc.append(w); last = w
    # review 2026-10-05 : « tu fais beaucoup de zoom, des dézooms ça serait intéressant » : with zoom.default.alternate one shot
    # pushes in, the next pulls out ; with zoom.dezoom every other accent is a quick dezoom from the start of its shot
    zd, alt = look["zoom"].get("dezoom"), zb.get("alternate", False)
    if zd and zd.get("enabled") is False:
        zd = None
    keys = []
    for k, (a, b) in enumerate(shots):
        span = max(b - a, F)
        f0, f1 = (zb["to"], zb["from"]) if alt and k % 2 else (zb["from"], zb["to"])
        v = lambda t: f0 + (f1 - f0) * (t - a) / span
        w = next((x for x in acc if a <= x < b), None)
        if w is None:
            keys += [(a, f0), (b - F, f1)]
        elif zd and acc.index(w) % 2 and b - a >= zd["dur"] + 0.4:  # the dezoom needs room before the cut
            keys += ease(a, zd["dur"], zd["from"], zd["to"]) + [(b - F, zd["to"] + 3)]
        else:
            t0 = w - zc["lead"]
            v0 = v(t0)
            keys += [(a, f0), (t0 - F, v0)] + ease(t0, zc["dur"], v0, v0 + (zc["to"] - zc["from"]) * 0.8) + [(b - F, v0 + (zc["to"] - zc["from"]) * 0.8)]
    seen, out = set(), []
    for t, val in sorted(keys):
        t = round(max(t, 0), 3)
        if t not in seen and t < until:
            seen.add(t); out.append((t, round(val, 2)))
    return out, acc


def main(slug, until):
    work = PR.P(slug, "work")
    src = os.path.join(work, f"look-src-{int(until)}.mp4")  # a new name per length : Premiere caches an imported file
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(work, "base-v.mp4"), "-t", f"{until}", "-c", "copy", src], check=True)
    keys, acc = plan_keys(slug, until)
    print(f"{len(keys)} keys, accents C at {acc}")
    pp = PP()
    name = f"look-{slug}-{int(time.time())}"
    item = pp("import_media", filePath=src, binName="look")
    item = item.get("data", item)
    iid = item.get("id") or item.get("projectItemId") or next(x for x in pp("list_project_items")["items"] if x["name"] == os.path.basename(src))["id"]
    sid = pp("create_sequence_from_clips", projectItemIds=[iid], name=name)["data"]["sequenceId"]
    cid = pp("get_full_sequence_info", sequenceId=sid)["data"]["videoTracks"][0]["clips"][0]["nodeId"]
    PB.scale_keys(pp, sid, [(cid, keys)])  # Motion > Scale whatever the UI language
    mov = os.path.join(work, "look-premiere.mov")
    if os.path.exists(mov):
        os.remove(mov)
    pp("export_sequence", sequenceId=sid, outputPath=mov, presetPath=paths.prores_preset(), allowOverwrite=True)
    size, still = -1, 0
    for _ in range(1800):  # Adobe Media Encoder works asynchronously : done when the file stops growing for 20 s
        cur = os.path.getsize(mov) if os.path.exists(mov) else -1
        still = still + 1 if cur == size and cur > 0 else 0
        size = cur
        if still >= 10:
            break
        time.sleep(2)
    pp.close()
    # splice : Premiere's zoomed intro + the rest of the face track, frame exact
    out = os.path.join(work, "base-v-look.mp4")
    n = round(until * FPS)
    total = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.join(work, "base-v.mp4")],
                                       capture_output=True, text=True).stdout) * FPS)
    if n >= total:  # the whole video went through Premiere
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mov, "-vf", f"fps=30,trim=end_frame={total},scale=1920:1080,format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", "30", "-color_range", "tv", out], check=True)
    else:
      subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mov, "-i", os.path.join(work, "base-v.mp4"), "-filter_complex",
                    f"[0:v]fps=30,trim=end_frame={n},setpts=PTS-STARTPTS,scale=1920:1080,format=yuv420p[a];"
                    f"[1:v]trim=start_frame={n},setpts=PTS-STARTPTS,format=yuv420p[b];[a][b]concat=n=2:v=1:a=0[v]",
                    "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", "30", "-color_range", "tv", out], check=True)
    d = lambda f: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)
    print("base-v", d(os.path.join(work, "base-v.mp4")), "look", d(out))


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]))
