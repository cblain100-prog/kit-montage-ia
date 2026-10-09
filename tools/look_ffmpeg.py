#!/usr/bin/env python3
"""the creator's look zooms (looks/<look>/look.json) applied to the face track with ffmpeg, when Premiere's MCP Bridge is down
(v1, 2026-10-04 : the bridge stopped at 16:42 while review was away, nobody to click Start Bridge).
Same keys as premiere/apply_look.py (plan_keys : B push 100 -> 108 % over each shot, C eased +12 % on a strong word,
held to the cut), drawn shot by shot : a frame-wise scale about the frame centre, then a centre crop back to 1920x1080.
  python3 tools/look_ffmpeg.py <slug>      -> work/base-v-look.mp4 (same frames as base-v.mp4), sets plan.base_video
Then prompteur.py compose uses it. The Premiere path stays the default when the bridge answers."""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "premiere"))
import prompteur as PR
from apply_look import plan_keys

FPS = 30


def expr(keys, a):
    """Piecewise-linear scale factor (1.00 = 100 %) of frame n of a shot starting at out time a, from [(t, percent)]."""
    pts = [(round((t - a) * FPS), v / 100) for t, v in keys]
    pts = sorted(dict(pts).items())
    if len(pts) == 1:
        return f"{pts[0][1]:.5f}"
    e = f"{pts[-1][1]:.5f}"
    for (f0, v0), (f1, v1) in reversed(list(zip(pts, pts[1:]))):
        seg = f"({v0:.5f}+({v1 - v0:.5f})*(n-{f0})/{max(f1 - f0, 1)})"
        e = f"if(lt(n,{f1}),{seg},{e})"
    return f"if(lt(n,{pts[0][0]}),{pts[0][1]:.5f},{e})"


def frames(path):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
                               "-of", "csv=p=0", path], capture_output=True, text=True).stdout or 0)


def render_keys(base, keys, cuts, n_frames, d, dst):
    """Draws scale keys [(t, percent)] on the face track `base`, shot by shot (cuts = first frame of each shot), into dst."""
    shots = list(zip(cuts, cuts[1:] + [n_frames]))
    os.makedirs(d, exist_ok=True)

    def job(k):
        fa, fb = shots[k]
        a, b = fa / FPS, fb / FPS
        ks = [kv for kv in keys if a - 1e-3 <= kv[0] < b]
        if not ks:  # a shot without keys keeps the value reached just before
            prev = [kv for kv in keys if kv[0] < a]
            ks = [(a, prev[-1][1] if prev else 100.0)]
        z = expr(ks, a)
        out = os.path.join(d, f"{k:04d}.mp4")
        if os.path.exists(out) and frames(out) == fb - fa:  # a rerun only redoes the shots that are missing or short
            return out
        vf = (f"scale=w='2*trunc(960*({z}))':h='2*trunc(540*({z}))':eval=frame:flags=lanczos,"
              f"crop=1920:1080:(iw-1920)/2:(ih-1080)/2,setsar=1,format=yuv420p,"
              f"tpad=stop_mode=clone:stop=3")  # the last shot : the seek can leave it one frame short of base-v
        # seek half a frame early : "-ss 8.8667" is past frame 266 (8.86666 s), the shot started one frame late and its
        # last frame showed the next shot (a 1-frame flash at every other cut)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, fa - 0.5) / FPS:.4f}", "-i", base, "-frames:v", str(fb - fa), "-vf", vf, "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", "30", "-video_track_timescale", "30000",
                        "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", out], check=True)
        return out

    with ThreadPoolExecutor(6) as ex:
        outs = list(ex.map(job, range(len(shots))))
    lst = os.path.join(d, "list.txt")
    open(lst, "w").write("".join(f"file '{o}'\n" for o in outs))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", dst], check=True)
    got = frames(dst)
    if got != n_frames:
        raise SystemExit(f"look track has {got} frames, base has {n_frames}")
    return got


def main(slug):
    W = PR.P(slug, "work")
    base = os.path.join(W, "base-v.mp4")
    n_frames = frames(base)
    until = n_frames / FPS
    keys, acc = plan_keys(slug, until)
    cuts = sorted({p["out"][0] for p in PR.edl(slug) if p["out"][0] < n_frames} | {0})
    print(f"{len(keys)} keys, {len(cuts)} shots, accents C at {[round(x, 2) for x in acc]}")
    dst = os.path.join(W, "base-v-look.mp4")
    got = render_keys(base, keys, cuts, n_frames, os.path.join(W, "look-ff"), dst)
    plan_path = PR.P(slug, "plan.json")
    plan = json.load(open(plan_path))
    plan["base_video"] = "work/base-v-look.mp4"
    json.dump(plan, open(plan_path, "w"), ensure_ascii=False, indent=1)
    print(f"look track : {dst} ({got} frames), plan.base_video set")


if __name__ == "__main__":
    main(sys.argv[1])
