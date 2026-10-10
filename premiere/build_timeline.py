"""Build the whole edit as a Premiere Pro timeline, through the Premiere MCP connector (Premiere does the montage).
  python3 premiere/build_timeline.py <slug> --name <slug>-vN [--export] [--until S] [--project path.prproj]
Premiere must be open with Window > Extensions > MCP Bridge (CEP) open (the bridge starts with the panel). A NEW Premiere project is created for
every version (projects/<slug>/premiere/<name>.prproj by default) : one project that piles up imports ends up not answering.
The Python engine only prepares the material (prompteur.py cut/base/inserts : framed face pieces, HyperFrames inserts, chosen sounds).
Premiere holds the edit :
  V1 face pieces (framings already cropped) + the look's zooms as Scale keyframes (Motion > Scale, any UI language)
  V2 full-screen inserts, V3+ overlays (keywords, icons ; WebM is refused by Premiere -> ProRes 4444 with alpha in work/ins-pp)
  A1 voice, A2+ one clip per sound effect (lanes so nothing overlaps), music track (one clip per kept span : hard cuts are clip ends),
  music ducked under the voice with Level keyframes (same curve as compose's sidechain), hooks (riser / impacts / reverse) as clips.
Export : Premiere (Media Encoder, YouTube 1080p preset), then loudness to -14 LUFS with ffmpeg (video copied)."""
import argparse, json, os, subprocess, sys, time
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "premiere"))
import prompteur as PR
import apply_look as AL
from ppclient import PP
import ppbatch as PB
import paths
import montage as M

FPS, SR = 30, 48000
SFX = os.path.join(HERE, "assets", "sfx")


def prepare(W):
    """Premiere-ready inserts : mp4 re-encoded with short GOPs (review/reenc.sh), transparent WebM -> ProRes 4444 with
    alpha in work/ins-pp (Premiere refuses WebM with alpha). Skipped when already done (review/rebuild.sh does it)."""
    import glob
    os.makedirs(f"{W}/ins-pp", exist_ok=True)
    for f in glob.glob(f"{W}/ins/*.mp4"):
        subprocess.run([os.path.join(HERE, "review", "reenc.sh"), f], check=True)
    for f in glob.glob(f"{W}/ins/*.webm"):
        mov = f"{W}/ins-pp/{os.path.splitext(os.path.basename(f))[0]}.mov"
        if not os.path.exists(mov) or os.path.getmtime(mov) < os.path.getmtime(f):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-c:v", "libvpx-vp9", "-i", f, "-c:v", "prores_ks", "-profile:v", "4444",
                            "-pix_fmt", "yuva444p10le", mov], check=True)


def project_path(slug, name):
    loc = M.config()["premiere_projects"]
    d = PR.P(slug, "premiere") if loc == "projects" else os.path.expanduser(loc)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{name}.prproj")


def check_export(out, dur):
    """Media Encoder can fail silently (a short file, black frames) : the export must last the edit, and the encoder log
    must say the file was encoded."""
    got = dur_of(out) if os.path.exists(out) else 0
    if got < dur - 0.5:
        raise SystemExit(f"Premiere export is {got:.1f} s, the edit is {dur:.1f} s : Media Encoder failed. Check {paths.media_encoder_log()} "
                         "then rebuild (or take the ffmpeg path : tools/look_ffmpeg.py + prompteur.py compose)")
    log = paths.media_encoder_log()
    if log:
        tail = open(log, errors="ignore").read()[-4000:]
        if os.path.basename(out) in tail and not any(k in tail for k in ("codé avec succès", "successfully encoded", "succès")):
            print(f"  ! check the Media Encoder log : {log}")


def dur_of(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)


def lanes(items):
    """items [(start, end, ...)] -> lane index per item, greedy, no overlap on a lane."""
    ends, out = [], []
    for it in items:
        k = next((i for i, e in enumerate(ends) if e <= it[0] - 0.001), None)
        if k is None:
            ends.append(0); k = len(ends) - 1
        ends[k] = it[1]; out.append(k)
    return out


def music_plan(slug, plan, dur):
    """Same rules as prompteur.build_music_bed, as clips : [(file, src_in, src_out, start, gain_db)] and hooks [(file, start, dB)]."""
    m = plan["music"]
    vl = PR.M_lufs(PR.P(slug, "work", "base.wav"))
    segs, sil, hooks = PR.music_layout(slug, plan, dur)
    clips = []
    fades = PR.music_fades(slug, plan, dur)
    md = PR.P(slug, "work", "music"); os.makedirs(md, exist_ok=True)
    import music as MU
    for i, g in enumerate(segs):
        a, b = g["t"], segs[i + 1]["t"] if i + 1 < len(segs) else dur
        off = g.get("offset", 0)
        # one file per segment, exactly as long as its chapter : a shorter track loops with a 3 s crossfade (v1,
        # 2026-10-05 : the clips pointed past the end of 86 s and 77 s tracks, no music from 3:25 to 4:52 and after 6:04 ;
        # the music never stops by accident), and a chapter change fades out inside it
        raw = os.path.join(md, f"raw-{i}.wav")
        eb = PR.music_end_before(plan, g["file"])  # never past the part of the track the creator does not want (palette end_before)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(off)] + (["-to", str(eb)] if eb else []) + ["-i", os.path.join(HERE, os.path.expanduser(g["file"])), "-ac", "2", "-ar", str(SR), raw], check=True)
        x, _ = sf.read(MU.loop_track(raw, b - a + 1), always_2d=True)
        x = x[:int(round((b - a) * SR))]
        tmp = PR.P(slug, "work", "music-seg.wav"); sf.write(tmp, x, SR)
        gain = vl - g.get("under_db", 18) - PR.M_lufs(tmp)
        for t0, t1 in fades:
            if a < t1 <= b + 0.05:
                i0, i1 = int((max(t0, a) - a) * SR), min(int((t1 - a) * SR), len(x))
                x[i0:i1] *= (np.linspace(1, 0, i1 - i0) ** 2)[:, None]
                x[i1:] = 0
        src = os.path.join(md, f"seg-{i}.wav"); sf.write(src, x, SR)
        off = 0.0
        spans = [(a, b)]
        for s0, s1 in sorted(sil):
            nxt = []
            for x, y in spans:
                if s1 <= x or s0 >= y:
                    nxt.append((x, y))
                else:
                    if s0 > x: nxt.append((x, s0))
                    if s1 < y: nxt.append((s1, y))
            spans = nxt
        for x, y in spans:
            if y - x > 0.1:
                clips.append((src, off + (x - a), off + (y - a), x, gain))
    out = []
    for f, t, db, anchor in hooks:
        if not PR.sfx_file(f):
            continue
        d = dur_of(PR.sfx_file(f))
        out.append((f, max(0.0, t - d) if anchor == "end" else t, db))
    return clips, out


def duck_curve(slug, plan):
    """Gain reduction (dB, <= 0) of the music under the voice, every 0.1 s : compose's sidechaincompress (threshold 0.06, ratio 1.6,
    attack 60 ms, release 700 ms) on the voice level."""
    m = plan["music"]
    v, _ = sf.read(PR.P(slug, "work", "base.wav"), always_2d=True); v = v.mean(1)
    hop = SR // 100
    lvl = np.sqrt(np.convolve(v ** 2, np.ones(hop) / hop, "same")[::hop] + 1e-12)
    thr, ratio = 0.06, m.get("duck_ratio", 1.6)
    over = np.maximum(20 * np.log10(lvl / thr), 0) * (1 - 1 / ratio)
    g, out, a, r = 0.0, [], np.exp(-1 / (0.06 * 100)), np.exp(-1 / (m.get("duck_release", 700) / 1000 * 100))
    for x in over:
        g = a * g + (1 - a) * x if x > g else r * g + (1 - r) * x
        out.append(-g)
    return np.array(out)[::10]  # every 0.1 s


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("--until", type=float, default=1e9)
    ap.add_argument("--name"); ap.add_argument("--export", action="store_true"); ap.add_argument("--key-time", default="clip")
    ap.add_argument("--zooms-on", help="existing sequence id : only add the zooms (and export)")
    ap.add_argument("--project", help="path of the NEW Premiere project (.prproj) ; default projects/<slug>/premiere/<name>.prproj. One light project per version (a shared project grew to 700+ duplicate items and Premiere stopped answering)")
    ap.add_argument("--same-project", action="store_true", help="build in the project already open in Premiere")
    A = ap.parse_args(); slug = A.slug
    A.name = A.name or f"montage-{slug}"
    age = paths.heartbeat_age()
    if age is None or age > 60:
        raise SystemExit("Premiere's MCP Bridge is not running (open Premiere and Window > Extensions > MCP Bridge (CEP) ; « Start Bridge » if it shows Stopped). "
                         "Fallback without Premiere : tools/look_ffmpeg.py <slug>, prompteur.py compose <slug> <name>, tools/export_xml.py <slug> <name>")
    plan, W = PR.load_plan(slug), PR.P(slug, "work")
    times = json.load(open(f"{W}/insert-times.json"))
    plan["inserts"] = [i for i in plan["inserts"] if i["id"] in times]
    pieces = PR.edl(slug); files = [l.split("'")[1] for l in open(f"{W}/pieces.txt") if l.strip()]
    assert len(pieces) == len(files)
    dur = min(len(sf.read(f"{W}/base.wav")[0]) / SR, A.until)
    prepare(W)
    pp = PP()
    if not A.same_project:
        A.project = A.project or project_path(slug, A.name)
        loc, nm = os.path.split(os.path.expanduser(A.project))
        r = pp("create_project", name=nm, location=loc)
        print("project", r.get("projectPath"), r.get("success"))
    if A.zooms_on:
        sid, name = A.zooms_on, A.name or f"montage-{slug}"
        face = [(p["out"][0] / FPS, p["out"][1] / FPS, f) for p, f in zip(pieces, files) if p["out"][0] / FPS < dur]
        info = pp("get_full_sequence_info", sequenceId=sid)["data"]
        return finish(pp, A, slug, plan, W, dur, sid, name, face, info, time.time())
    cache = {}
    stage = os.path.join(W, "pp-stage"); os.makedirs(stage, exist_ok=True)
    def staged(path):
        """Premiere caches a file's duration by its PATH, across projects : t1_opus.mp4 re-rendered longer kept its old 109
        frames and Media Encoder failed at that frame (v10, 2026-10-04 ; v9 got 22 s of black from a stale base.wav).
        Every file goes to Premiere under a name made of its content hash, hard-linked (no copy)."""
        import hashlib
        h = hashlib.md5()
        with open(path, "rb") as fh:
            h.update(fh.read(1 << 20)); fh.seek(0, 2); h.update(str(fh.tell()).encode())
        base, ext = os.path.splitext(os.path.basename(path))
        dst = os.path.join(stage, f"{base}-{h.hexdigest()[:10]}{ext}")
        if not os.path.exists(dst):
            os.link(path, dst)
        return dst
    def prefill(paths, bin_):  # one ExtendScript call per 60 files instead of one MCP call per file (2026-10-04)
        todo = sorted({p for p in paths if p not in cache})
        if todo:
            st = {staged(p): p for p in todo}
            for sp, nid in PB.import_files(pp, list(st), bin_).items():
                cache[st[sp]] = nid
    def imp(path, bin_):
        if path in cache: return cache[path]
        r = pp("import_media", filePath=staged(path), binName=bin_); d = r.get("data", r)
        cache[path] = d.get("id") or d.get("projectItemId")
        return cache[path]
    t0 = time.time()
    # ---- V1 face pieces
    face = [(p["out"][0] / FPS, p["out"][1] / FPS, f) for p, f in zip(pieces, files) if p["out"][0] / FPS < dur]
    prefill([f for _, _, f in face], "faces")
    ids = [imp(f, "faces") for _, _, f in face]
    name = A.name or f"montage-{slug}"
    sid = pp("create_sequence_from_clips", projectItemIds=[ids[0]], name=name)["data"]["sequenceId"]
    print(f"sequence {sid}, {len(face)} face pieces imported ({time.time() - t0:.0f}s)")
    # ---- inserts
    full, over = [], []
    for ins in plan["inserts"]:
        s, e = times[ins["id"]][:2]
        if s >= dur: continue
        st = max(0.0, round(s * FPS) / FPS)
        if PR.overlay_kind(ins):
            f = f"{W}/ins-pp/{ins['id']}.mov"; over.append((st, st + dur_of(f), f))
        else:
            f = f"{W}/ins/{ins['id']}.mp4"; full.append((st, st + dur_of(f), f))
    over.sort(); ol = lanes(over)
    # ---- audio
    cues = sorted((c for c in PR.sfx_cues(slug, plan, times, dur) if c[1] < dur), key=lambda c: c[1])
    mclips, hooks = music_plan(slug, plan, dur) if plan.get("music", {}).get("segments") else ([], [])
    snd = sorted([(t, t + dur_of(PR.sfx_file(f)), f, db) for f, t, db in cues] + [(t, t + dur_of(PR.sfx_file(f)), f, db) for f, t, db in hooks])
    sl = lanes(snd)
    nv, na = 2 + (max(ol) + 1 if ol else 0), 2 + (max(sl) + 1 if sl else 0)
    info = pp("get_full_sequence_info", sequenceId=sid)["data"]
    have_v, have_a = len(info["videoTracks"]), len(info["audioTracks"])
    if nv > have_v or na > have_a:
        pp("add_tracks", sequenceId=sid, videoTracks=max(0, nv - have_v), audioTracks=max(0, na - have_a))
    prefill([f for _, _, f in full], "inserts"); prefill([f for _, _, f in over], "overlays")
    prefill([os.path.join(SFX, f) for _, _, f, _ in snd], "sfx"); prefill([f for f, *_ in mclips], "music"); prefill([f"{W}/base.wav"], "audio")
    MUS = 1  # A2 music, A3+ sounds
    batch = [{"projectItemId": ids[i], "trackIndex": 0, "time": s, "linkAudio": False} for i, (s, e, f) in enumerate(face) if i > 0]
    batch += [{"projectItemId": imp(f, "inserts"), "trackIndex": 1, "time": s, "linkAudio": False} for s, e, f in full]
    batch += [{"projectItemId": imp(f, "overlays"), "trackIndex": 2 + k, "time": s, "linkAudio": False} for (s, e, f), k in zip(over, ol)]
    r = pp("add_to_timeline_batch", sequenceId=sid, clips=batch)
    print("video", r.get("status"), f"({time.time() - t0:.0f}s)")
    voice = imp(f"{W}/base.wav", "audio")
    abatch = [{"projectItemId": voice, "trackIndex": 0, "time": 0}]
    abatch += [{"projectItemId": imp(f, "music"), "trackIndex": MUS, "time": st, "sourceInPoint": a, "sourceOutPoint": b} for f, a, b, st, g in mclips]
    abatch += [{"projectItemId": imp(os.path.join(SFX, f), "sfx"), "trackIndex": 2 + k, "time": s} for (s, e, f, db), k in zip(snd, sl)]
    r = pp("add_to_timeline_batch", sequenceId=sid, clips=abatch)
    print("audio", r.get("status"), f"({time.time() - t0:.0f}s)")
    info = pp("get_full_sequence_info", sequenceId=sid)["data"]
    at = info["audioTracks"]
    near = lambda clips, t: min(clips, key=lambda c: abs(c.get("start", 0) - t))
    # ---- levels : sounds, music (base gain + ducking keys)
    PB.volumes(pp, sid, [(near(at[2 + k]["clips"], s)["nodeId"], db) for (s, e, f, db), k in zip(snd, sl)])
    duck = duck_curve(slug, plan)
    for f, a, b, st, g in mclips:
        c = near(at[MUS]["clips"], st)
        keys, last = [], None
        for t in np.arange(st, st + (b - a), 0.1):
            lv = round(g + duck[min(int(t * 10), len(duck) - 1)], 1)
            if last is None or abs(lv - last) >= 0.75:
                keys.append({"time": round(a + (t - st), 3), "level": lv}); last = lv
        fo = plan["music"].get("fade_out", 0)
        if fo and st + (b - a) >= dur - 0.2:  # the last track fades out over the end
            keys = [k for k in keys if k["time"] < b - fo] + [{"time": round(b - fo, 3), "level": last}, {"time": round(b - 0.01, 3), "level": -60}]
        else:
            keys.append({"time": round(b - 0.01, 3), "level": last})
        for j in range(0, len(keys), 200):
            pp("add_audio_keyframes", clipId=c["nodeId"], keyframes=keys[j:j + 200])
    print(f"levels done ({time.time() - t0:.0f}s)")
    return finish(pp, A, slug, plan, W, dur, sid, name, face, info, t0)


def finish(pp, A, slug, plan, W, dur, sid, name, face, info, t0):
    near = lambda clips, t: min(clips, key=lambda c: abs(c.get("start", 0) - t))
    # ---- zooms : the look's curve, keys on every face piece (boundaries interpolated so a shot over two pieces stays continuous)
    keys, acc = AL.plan_keys(slug, dur)
    kt, kv = np.array([k[0] for k in keys]), np.array([k[1] for k in keys])
    vt = info["videoTracks"][0]["clips"]
    jobs = []
    for s, e, f in face:
        c = near(vt, s)
        pts = sorted({round(s, 3), round(e - 1 / FPS, 3)} | {t for t in kt if s <= t < e})
        jobs.append((c["nodeId"], [(round(t - s if A.key_time == "clip" else t, 3), round(float(np.interp(t, kt, kv)), 2)) for t in pts]))
    PB.scale_keys(pp, sid, jobs)
    print(f"zooms done, accents {[round(x, 1) for x in acc]} ({time.time() - t0:.0f}s)")
    pp("save_project")
    json.dump({"sequenceId": sid, "name": name}, open(f"{W}/premiere-seq.json", "w"))
    if A.export:
        out = PR.P(slug, "renders", f"{name}-premiere.mp4")
        if os.path.exists(out): os.remove(out)
        pp("export_sequence", sequenceId=sid, outputPath=out, presetPath=paths.youtube_preset(), allowOverwrite=True)
        size, still = -1, 0
        for _ in range(3600):
            cur = os.path.getsize(out) if os.path.exists(out) else -1
            still = still + 1 if cur == size and cur > 0 else 0; size = cur
            if still >= 10: break
            time.sleep(2)
        check_export(out, dur)
        fin = PR.P(slug, "renders", f"{name}.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", out, "-t", f"{dur:.3f}", "-c:v", "copy", "-af", f"loudnorm=I={plan.get('lufs', -14)}:TP={plan.get('true_peak', -1.5)}:LRA=11", "-ar", "48000",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", fin], check=True)
        print("exported", fin, dur_of(fin))
    pp.close()


if __name__ == "__main__":
    main()
