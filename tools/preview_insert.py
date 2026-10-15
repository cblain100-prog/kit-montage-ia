#!/usr/bin/env python3
"""Render ONE insert of a project module on its own (no plan.json write, no shared work/ins), to check it by eye.
  python3 tools/preview_insert.py <slug> <module> <insert-id> [--out DIR]
The insert comes straight from projects/<slug>/<module>.py ; times are computed like cmd_inserts (anchor + lead,
until + tail or dur) without the global adjustments (holds, snapping to cuts). Writes DIR/<id>.(mp4|webm) and a
contact sheet DIR/<id>-sheet.jpg (8 frames), composited over the real edited face cam when it is an overlay."""
import argparse, importlib, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import prompteur as PR
import prompteur_blocks as B


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("module"); ap.add_argument("iid")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    slug = a.slug
    sys.path.insert(0, PR.P(slug))
    mod = importlib.import_module(a.module)
    ins = next((i for i in mod.inserts() if i["id"] == a.iid), None)
    if not ins:
        raise SystemExit(f"{a.iid} not in {a.module}.inserts()")
    plan, pieces, ws = PR.load_plan(slug), PR.edl(slug), PR.words(slug)
    T = lambda x: PR.to_out(slug, PR.anchor(slug, x, ws), pieces)
    s = T(ins["at"]) + ins.get("lead", 0)
    e = T(ins["until"]) + ins.get("tail", 0) if "until" in ins else s + ins["dur"]
    s, e = round(s * PR.FPS) / PR.FPS, round(e * PR.FPS) / PR.FPS
    out = a.out or os.path.join("/tmp", "preview-insert")
    d = os.path.join(out, ins["id"])
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(f"{d}/assets/fonts", exist_ok=True)
    shutil.copy(os.path.join(HERE, "assets", "gsap.min.js"), f"{d}/assets/")
    B.set_brand((PR.load_look(plan) or {}).get("brand"))
    for f in B.fonts():
        shutil.copy(os.path.join(HERE, "assets", "fonts", f), f"{d}/assets/fonts/")
    for f in ins.get("files", []):
        shutil.copy(PR.P(slug, f), f"{d}/assets/")
    if ins.get("face"):
        shutil.copy(PR.face_clip(slug, plan, pieces, s, e + 0.5), f"{d}/assets/face.mp4")
    shutil.copy(os.path.join(HERE, "assets", "hyperframes.json"), f"{d}/hyperframes.json")
    rel = lambda x: max(0.0, T(x) - s)
    ow = PR.P(slug, "assets", "out_words.json")
    owords = PR.M.load(ow)["words"] if os.path.exists(ow) else []
    ins["_words"] = [[B._norm(w["text"]), round(w["start"] - s, 3)] for w in owords if s - 1 <= w["start"] <= e + 1 and B._norm(w["text"])]
    ins["_s"], ins["_e"] = s, e
    html, cues = B.build(ins, e - s, rel, PR.P(slug, "assets"))
    open(f"{d}/index.html", "w").write(html)
    lint = subprocess.run(["npx", "--yes", PR.HF, "lint"], cwd=d, capture_output=True, text=True).stdout
    errs = [l for l in lint.splitlines() if "✗" in l]
    print(f"{ins['id']}: out {s:.2f} -> {e:.2f} ({e - s:.2f}s), cues {[(c[0], round(c[1], 2)) for c in cues]}")
    if errs:
        print("LINT ERRORS:\n" + "\n".join(errs)); sys.exit(1)
    ov = PR.overlay_kind(ins)
    ext = "webm" if ov else "mp4"
    vid = os.path.join(out, f"{ins['id']}.{ext}")
    r = subprocess.run(["npx", "--yes", PR.HF, "render", "--format", ext, "--output", vid, "--quiet"], cwd=d, capture_output=True, text=True)
    if r.returncode or not os.path.exists(vid):
        print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(1)
    sheet = os.path.join(out, f"{ins['id']}-sheet.jpg")
    base = PR.P(slug, "work", "base-v.mp4")
    n, dur = 8, e - s
    if ov:  # over the real edited face cam
        fc = (f"[0:v]trim=start={s:.3f}:duration={dur:.3f},setpts=PTS-STARTPTS[b];[1:v]setpts=PTS-STARTPTS[o];[b][o]overlay=eof_action=pass,"
              f"fps={n / dur:.4f},scale=480:270,tile=4x2[v]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", base, "-c:v", "libvpx-vp9", "-i", vid, "-filter_complex", fc, "-map", "[v]", "-frames:v", "1", sheet]
    else:
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", vid, "-vf", f"fps={n / dur:.4f},scale=480:270,tile=4x2", "-frames:v", "1", sheet]
    subprocess.run(cmd, check=True)
    print(f"render {vid}\nsheet  {sheet}")


if __name__ == "__main__":
    main()
