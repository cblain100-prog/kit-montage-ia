#!/usr/bin/env python3
"""YouTube 16:9 talking-head montage, read at the teleprompter, filmed with ONE or TWO phones.

  one phone   : camera A only. Its sound is the voice, every cut reframes it (wide / tight / very tight).
  two phones  : camera A = front, camera B = side. The voice comes from the camera that holds the microphone
                (plan.voice_cam, "B" by default) ; plan.offsets {cam: s} = file time minus master time, measured by
                tools/projet.py (the older plan.sync_a is still read : A time = master time + sync_a).
  Times in plan.json are seconds on the voice camera (assets/voice.wav), called master or rush time below.
  Camera B over several files (plan.b_sources [[from, to, file, shift, face?]]) : a range no file holds is shown on A.

A cut changes the framing, so the retakes and breaths removed by `cut` never show as jump cuts. Inserts (cards,
recreated UI, sketches, real captures) are HyperFrames compositions placed by their spoken word, full screen (opaque
mp4) or over the face (transparent webm). Music runs under the whole video, ducked by the voice, then -14 LUFS.

  python3 prompteur.py words <slug> [from] [to]   transcript lines with master times, to write plan.keep and the inserts
  python3 prompteur.py cut <slug>                 plan.keep -> tightened pieces + framings -> assets/edl.json
  python3 prompteur.py base <slug>                face cam (framings) + voice -> work/base-v.mp4, work/base.wav
  python3 prompteur.py inserts <slug>             one HyperFrames composition per insert (inserts/<id>/), linted
  python3 prompteur.py render <slug>              render inserts (skipped when unchanged)
  python3 prompteur.py compose <slug> <name>      base + inserts + sfx + music -> renders/<name>.mp4 (ffmpeg path)
  python3 prompteur.py sheet <slug> <name>        contact sheet: every insert at mid-life + every framing
  python3 prompteur.py all <slug> <name>
  checks (run them, a viewer catches every one of these by eye):
  python3 prompteur.py takes <slug>               each kept take transcribed alone (leftover retakes)
  python3 prompteur.py gaps <slug> [0.5]          every hole inside a take heard alone (false starts)
  python3 prompteur.py outwords <slug>            edited voice transcribed -> word timings of the captions
  python3 prompteur.py verbatim <slug>            on-screen text = the speaker's exact words
  python3 prompteur.py joints <slug> <name>       no frame of face at the joints of full-screen inserts
"""
import hashlib, json, os, re, shutil, subprocess, sys

import numpy as np
import soundfile as sf

import montage as M
import music

W, H, FPS, SR = 1920, 1080, 30, 48000
# pinned: an unpinned `npx hyperframes` tried to fetch a just-announced 0.8.104 that npm could not serve (2026-10-01),
# the render died silently and the old file stayed in place
HF = os.environ.get("HYPERFRAMES", "hyperframes@0.8.103")
HERE = M.HERE


def P(slug, *p):
    return os.path.join(HERE, "projects", slug, *p)


def voice(slug, k16=False):
    """The master voice (48 kHz, or 16 kHz for Whisper). Older projects named it voice-B.wav."""
    f = P(slug, "assets", "voice16.wav" if k16 else "voice.wav")
    old = P(slug, "assets", "voice-B16.wav" if k16 else "voice-B.wav")
    return f if os.path.exists(f) or not os.path.exists(old) else old


def cam_offset(plan, cam):
    """File time of camera `cam` minus master time."""
    if "offsets" in plan:
        return plan["offsets"].get(cam, 0.0)
    return plan.get("sync_a", 0.0) if cam == "A" else 0.0


def cam_size(plan, cam):
    """Native picture size of a camera (measured by tools/projet.py ; older plans : A 1080p, B 4K)."""
    return tuple(plan.get("sizes", {}).get(cam) or ((1920, 1080) if cam == "A" else (3840, 2160)))


def load_plan(slug):
    return M.load(P(slug, "plan.json"))


def words(slug):
    return M.load(P(slug, "assets", "transcript.json"))["words"]


def anchor(slug, a, ws=None):
    """'mot@123.4' -> start of the transcript word nearest 123.4 whose text starts with 'mot' (B time); numbers pass."""
    if isinstance(a, (int, float)) or (isinstance(a, str) and a.startswith("cold:")):
        return a if isinstance(a, str) else float(a)
    if isinstance(a, str) and a.startswith("src:"):
        return float(a[4:])
    w, t = a.rsplit("@", 1)
    # Whisper splits elisions (« l » + « 'IA. ») : punctuation and apostrophes are ignored on both sides
    clean = lambda x: x.lower().strip(".,!?«»:;'’ ")
    t, w = float(t), clean(w)
    ws = ws or words(slug)
    cands = [x for x in ws if abs(x["start"] - t) < 2.5 and clean(x["text"]).startswith(w)]
    if not cands:
        raise SystemExit(f"anchor {a}: word not found near {t}")
    return min(cands, key=lambda x: abs(x["start"] - t))["start"]


def anchor_end(slug, a, ws=None):
    """Like anchor, but the END of the word (to close a kept range on a word)."""
    if isinstance(a, (int, float)):
        return float(a)
    if isinstance(a, str) and a.startswith("src:"):  # an exact rush time (a split inside a take, QA 2026-10-03)
        return float(a[4:])
    s = anchor(slug, a, ws)
    return next(x["end"] for x in (ws or words(slug)) if x["start"] == s)


# ------------------------------------------------------------------ words
def cmd_words(slug, a=0, b=1e9):
    a, b = float(a), float(b)
    line, t0, prev = [], None, None
    for w in words(slug):
        if not (a <= w["start"] <= b):
            continue
        if prev is not None and w["start"] - prev > 0.6 and line:
            print(f"[{t0:7.2f}] {' '.join(line)}"); line = []
        if not line:
            t0 = w["start"]
        line.append(f"{w['text']}" if len(line) % 6 else f"{w['text']}@{w['start']:.1f}")
        prev = w["end"]
    if line:
        print(f"[{t0:7.2f}] {' '.join(line)}")


# ------------------------------------------------------------------ cut
def energy(slug):
    """RMS level in dB every 10 ms on the master voice (cached)."""
    cache = P(slug, "work", "energy.npy")
    if os.path.exists(cache):
        return np.load(cache)
    y, sr = sf.read(voice(slug))
    if y.ndim > 1:
        y = y.mean(1)
    hop = sr // 100
    n = len(y) // hop
    rms = np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.save(cache, db)
    return db


def tighten(slug, plan, s, e):
    """Linear rhythm : inside a kept range every pause longer than plan.max_pause becomes exactly plan.pause_keep (both
    from the creator's look ; neutral defaults 0.8 / 0.6 s) ; shorter pauses are left as said. The take keeps
    plan.edge_keep (0.2 s) before its first sound and after its last one. Silence is measured with a low threshold
    (plan.quiet_db, 38 dB under the take's speaking level) so a soft onset or word ending is never eaten."""
    db = energy(slug)
    i0, i1 = int(round(s * 100)), int(round(e * 100))  # round, never truncate (295.40 -> frame 29539 started a take one frame into the next word)
    s, e = i0 / 100, i1 / 100
    seg = db[i0:i1]
    if len(seg) < 10:
        return [(s, e)]
    loud = seg >= max(np.percentile(seg, 95) - plan.get("quiet_db", 38), plan.get("speech_db", -42))
    idx = np.flatnonzero(loud)
    if not len(idx):
        return [(s, e)]
    edge, maxp, keep = plan.get("edge_keep", 0.2), plan.get("max_pause", 0.8), plan.get("pause_keep", 0.6)
    thr = max(np.percentile(seg, 95) - plan.get("quiet_db", 38), plan.get("speech_db", -42))  # room noise (-50 dB) is not speech (QA v3)
    # start : a hand-written start that falls inside the first word moves back to its attack (short first words were
    # clipped), then plan.edge_keep of silence before it, never over another sound
    te = plan.get("speech_db", -42)  # one absolute speech threshold for the edges, same as tools/qa_measure.py
    ie = np.flatnonzero(seg >= te)
    ie = ie if len(ie) else idx
    first = s + ie[0] / 100
    k = i0
    if plan.get("_strict_start") and db[k] >= te:  # strict_start : a cut placed between two words said without a gap (two words with no gap between them)
        first = s
    elif db[k] >= te:
        n = 0
        while n < 35 and k - n - 1 >= 0 and db[k - n - 1] >= te:
            n += 1
        first = s - n / 100
    k, n = int(round(first * 100)), 0
    while n < int(edge * 100) and k - n - 1 >= 0 and db[k - n - 1] < te:
        n += 1
    head = first - n / 100
    tail = min(e, s + (ie[-1] + 1) / 100 + edge)
    # end : the end of a sentence breathes (a word ending must never be eaten) :
    # plan.tail_keep (0.4 s) after the last sound, past the hand-written end if needed, never into the next sound (a
    # retake). A word still sounding across the hand-written end is finished first, but only if it was already
    # sounding before it (otherwise that sound is the attack of a retake)
    last = s + (ie[-1] + 1) / 100
    after = db[i1:i1 + 150] >= te
    if not plan.get("_strict_end") and len(after) > 3 and after[:3].any() and db[max(0, i1 - 5):i1].max() >= te:  # strict_end : never finish into the next word
        run = 0
        for kk, v in enumerate(after[:50]):
            run = 0 if v else run + 1
            if run >= 12:
                last = e + (kk - run + 1) / 100
                break
    li = int(round(last * 100))
    nxt = np.flatnonzero(db[li:li + 150] >= te)  # from the end of the word itself : a retake can start 30 ms later (QA v4)
    room = last + nxt[0] / 100 - 0.03 if len(nxt) else last + 1.5
    tail = max(tail, min(last + plan.get("tail_keep", 0.4), room))
    tighten.breath = tail - last  # silence actually kept after the last word (cmd_cut gives the missing part to the next take)
    pieces, cur = [], head
    for k0, k1 in zip(idx[:-1], idx[1:]):
        gap = (k1 - k0 - 1) / 100
        if gap > maxp:
            qs, qe = s + (k0 + 1) / 100, s + k1 / 100
            pieces.append((cur, qs + keep * 0.62))  # more air after the last word than before the next (v2 : cuts too soon after he speaks)
            cur = qe - keep * 0.38
    pieces.append((cur, tail))
    return [(a_, b_) for a_, b_ in pieces if b_ - a_ > 0.1]


def cmd_cut(slug):
    """plan.keep = [[start, end, note?, {"tempo": 0.94}?], ...] in B time (the good takes, in order). Each take is
    tightened (linear pauses, see tighten), every piece snapped to frames. Cameras (no zoom on the speaker's face, ever) :
    a new take always cuts to the next framing; a shortened pause cuts too when both shots last plan.min_shot (1.2 s),
    otherwise the framing stays (a tiny jump rather than a flash); a sentence longer than plan.max_shot cuts before a word
    after a comma. A cut reframes on the same camera until it has been shown plan.cam_hold s, then goes to the other one. A take with "tempo" < 1 is slowed down (audio time-stretched, video slowed: only under a full-screen insert)."""
    plan = load_plan(slug)
    pieces, missing, db = [], 0.0, energy(slug)
    opts = [next((x for x in k[2:] if isinstance(x, dict)), {}) for k in plan["keep"]]
    for n_k, k in enumerate(plan["keep"]):
        s, e = anchor(slug, k[0]), anchor_end(slug, k[1])
        opt = opts[n_k]
        # {"join": true} : this take continues the previous one's sentence (no gap may split one sentence) : 0.06 s kept
        # after the previous word, 0.03 s before this one, nothing borrowed
        nxt_join = n_k + 1 < len(opts) and opts[n_k + 1].get("join")
        tp = dict(plan, tail_keep=0.06, edge_keep=plan.get("edge_keep", 0.2)) if nxt_join else plan
        if opt.get("strict_end"):
            tp = dict(tp, _strict_end=True)
        if opt.get("strict_start"):
            tp = dict(tp, _strict_start=True)
        if opt.get("tail_keep") and not nxt_join:  # more breath after this take's last word (the next take has no silence to give, QA 2026-10-04)
            tp = dict(tp, tail_keep=opt["tail_keep"])
        if opt.get("join"):
            tp = dict(tp, edge_keep=0.03)
            missing = 0.0
        tk = tighten(slug, tp, s, e)
        if nxt_join and tk:  # tighten keeps at least edge_keep after the last sound : trim to the join tail
            tk[-1] = (tk[-1][0], min(tk[-1][1], e + 0.06) if e > tk[-1][0] else tk[-1][1])
        if missing > 0.02 and tk:  # the previous take ran straight into speech  :
            a0 = tk[0][0]           # its pause is taken from the silence before this take, never over a sound
            thr = max(np.percentile(db[int(s * 100):int(e * 100)], 95) - plan.get("quiet_db", 38), plan.get("speech_db", -42))
            k0 = int(a0 * 100)
            n = 0
            while n < int(missing * 100) and k0 - n - 1 >= 0 and db[k0 - n - 1] < thr:
                n += 1
            tk[0] = (a0 - max(0, n - 5) / 100, tk[0][1])  # 50 ms clear of the sound before (the tail of a dropped word)
        missing = 0.0 if nxt_join else max(0.0, plan.get("tail_keep", 0.4) - getattr(tighten, "breath", 0.4))
        for j, (a, b) in enumerate(tk):
            fa, fb = round(a * FPS), round(b * FPS)
            if fb - fa >= 3:
                pieces.append([fa, fb, j == 0, opt.get("tempo", 1.0), bool(opt.get("cold"))])
    # rhythm from the creator's look (plan.min_shot / max_shot / shot_target) ; neutral default : a long sentence is not split
    min_shot, max_shot = plan.get("min_shot", 1.0), plan.get("max_shot", 1e9)
    # framings : each new shot takes the next framing of plan.framings (the creator's choice) ; neutral default : the whole
    # picture of each camera. In the intro (rush time < plan.intro_until, optional) shots last plan.intro_shot.
    cycle = plan.get("framings") or (["A", "B"] if len(plan.get("cameras", ["A", "B"])) > 1 else ["A"])
    # the cycle advances by position, so a framing may come back in it (looking the name up again looped on its first place)
    pos = {"i": -1}
    # camera hold : with two cameras a cut may reframe on the SAME camera until that camera has been on screen
    # plan.cam_hold seconds ; only then the next cut goes to the other camera. Neutral default 0 : every cut may change camera.
    hold, intro_hold = plan.get("cam_hold", 0.0), plan.get("intro_cam_hold", plan.get("cam_hold", 0.0))
    cam = {"len": 0.0}  # seconds the current camera has been shown

    def toggle(a, intro=False):
        if not cycle:
            return {"A": "B", "B": "A"}[a[0]]
        if pos["i"] < 0 or cycle[pos["i"]] != a:  # first call, or an angle forced from outside (lock, first_angle)
            pos["i"] = cycle.index(a) if a in cycle else -1
        h = intro_hold if intro else hold
        h = h.get(a[0], 0.0) if isinstance(h, dict) else (h or 0.0)
        one_cam = len({f[0] for f in cycle}) == 1  # one phone : every cut reframes the same camera
        same = one_cam or (cam["len"] < h and len({f for f in cycle if f[0] == a[0]}) > 1)
        for _ in range(len(cycle)):  # next framing of the same camera, or of the other one once the hold is reached
            pos["i"] = (pos["i"] + 1) % len(cycle)
            if (cycle[pos["i"]][0] == a[0]) == same and cycle[pos["i"]] != a:
                break
        return cycle[pos["i"]]
    ws = words(slug)
    # plan.first_angle : the very first shot (default : the first framing of the cycle)
    edl, out, shot_len, ang = [], 0, 0.0, plan.get("first_angle") or cycle[0]
    for n, (fa, fb, first, tempo, cold) in enumerate(pieces):
        intro = fa / FPS < plan.get("intro_until", 0) or cold
        mx, tg = (plan.get("intro_shot", 1.7) + 0.5, plan.get("intro_shot", 1.7)) if intro and plan.get("intro_shot") else (max_shot, plan.get("shot_target", 2.6))
        mn = 1.0 if intro else min_shot
        dur = (fb - fa) / FPS / tempo
        if n and (first or (shot_len >= mn and dur >= mn)):
            ang, shot_len = toggle(ang, intro), 0.0
        lock = plan.get("lock_angle_from")  # [rush s, angle] : from there one camera, no change (e.g. the goodbye on one framing)
        locked = bool(lock) and fa / FPS >= lock[0] and not cold
        if locked:
            ang = lock[1]
        splits = [fa]
        if tempo == 1.0 and not locked:  # long sentence: a cut every ~2.6 s, just before a word that follows a comma (else any word)
            start = fa / FPS - shot_len
            while True:
                last = splits[-1] / FPS if len(splits) > 1 else start
                if fb / FPS - last <= mx:
                    break
                # never before the piece itself : the shot may have started in an earlier piece (2026-10-03 : shorter pauses
                # made a split land before fa, a piece of negative length)
                cands = [w for w in ws if max(last + mn, splits[-1] / FPS + 0.3) < w["start"] < fb / FPS - mn]
                if not cands:
                    break
                after_comma = {id(w2) for w1, w2 in zip(ws, ws[1:]) if w1["text"].rstrip().endswith((",", ";", ":"))}
                target = last + tg
                good = [w for w in cands if id(w) in after_comma and abs(w["start"] - target) < 1.0]
                c = min(good or cands, key=lambda w: abs(w["start"] - target))["start"]
                splits.append(round((c - 0.04) * FPS))
        splits.append(fb)
        for j in range(len(splits) - 1):
            if j and not locked:
                ang, shot_len = toggle(ang, intro), 0.0
            a, b = splits[j], splits[j + 1]
            n_out = round((b - a) / tempo)
            shown = ang
            if plan.get("b_sources") and not b_source(plan, a / FPS, b / FPS):
                # camera B has no picture here : the front camera only, wide / tight alternating so every cut still shows
                shown = "At" if edl and edl[-1]["angle"] == "A" else "A"
            p = {"src": [a, b], "out": [out, out + n_out], "angle": shown}
            if cold:
                p["cold"] = True
            if intro and j == 0 and first and plan.get("dezoom", 0):  # a sentence of the intro opens on a quick dezoom
                p["dezoom"] = plan["dezoom"]
            if tempo != 1.0:
                p["tempo"] = tempo
            cam["len"] = (cam["len"] if edl and edl[-1]["angle"][0] == shown[0] else 0.0) + n_out / FPS
            edl.append(p)
            out += n_out
            shot_len += n_out / FPS
    M.save({"fps": FPS, "pieces": edl}, P(slug, "assets", "edl.json"))
    shots = sum(1 for x, y in zip(edl, edl[1:]) if x["angle"] != y["angle"]) + 1
    cams = sum(1 for x, y in zip(edl, edl[1:]) if x["angle"][0] != y["angle"][0]) + 1
    print(f"{len(plan['keep'])} takes -> {len(edl)} pieces, {out / FPS:.1f}s out, {shots} shots (mean {out / FPS / shots:.2f}s), "
          f"{cams} camera runs (mean {out / FPS / cams:.2f}s)")


def edl(slug):
    return M.load(P(slug, "assets", "edl.json"))["pieces"]


def to_out(slug, t, pieces=None):
    """B source time -> output time (a time inside a removed part goes to the next kept piece)."""
    cold = isinstance(t, str) and t.startswith("cold:")
    f = float(t[5:] if cold else t) * FPS
    for p in pieces or edl(slug):
        if bool(p.get("cold")) != cold:  # the cold open replays a later moment : anchors go to the main edit unless "cold:"
            continue
        if f < p["src"][1]:
            return (p["out"][0] + max(0, f - p["src"][0]) / p.get("tempo", 1.0)) / FPS
    return (pieces or edl(slug))[-1]["out"][1] / FPS


# ------------------------------------------------------------------ base (face cam + voice)
def angle_filter(plan, ang):
    """Crop/scale for a framing : "A" / "B" = the whole picture, "At" / "Att" / "Bt" / "Btt" = tighter crops centred on
    the measured face (plan.faces), zoom factors in plan.zoom. Any source size is scaled to 1920x1080."""
    cam = ang[0]
    fx, fy = plan["faces"][cam]
    src_w, src_h = cam_size(plan, cam)
    if len(ang) == 1:
        return "scale=1920:1080:flags=lanczos"
    z = plan.get("zoom", {}).get(ang)
    if not z:
        raise SystemExit(f"framing {ang} has no zoom factor in plan.zoom : the creator's style (looks/<name>/look.json, framing) must give it ; run the style-de-montage skill")
    cw, chh = int(src_w / z) // 2 * 2, int(src_h / z) // 2 * 2
    # plan.crop_x_min {cam: px} keeps an edge object (a mirror, a lamp) out of the tight shot
    x = min(max(int(fx * src_w - cw / 2), plan.get("crop_x_min", {}).get(cam, 0)), src_w - cw)
    y = min(max(int(fy * src_h - chh * 0.42), 0), src_h - chh)
    return f"crop={cw}:{chh}:{x}:{y},scale=1920:1080:flags=lanczos"


def deflicker_mask(slug, cam, d):
    """Gray mask (white = deflickered) at the camera's native size: full left of d.x px, fading over d.feather px.
    The mask is looped as a still image by ffmpeg's maskedmerge (single frame input repeats)."""
    from PIL import Image
    size = cam_size(load_plan(slug), cam)
    f = P(slug, "work", f"mask-{cam}-{d['x']}-{d['feather']}.png")
    if not os.path.exists(f):
        x = np.arange(size[0])
        row = np.clip((d["x"] + d["feather"] - x) / d["feather"], 0, 1) * 255
        Image.fromarray(np.tile(row.astype(np.uint8), (size[1], 1))).save(f)
    return f


def b_source(plan, s, e):
    """plan.b_sources [[from, to, file, shift]] (master seconds ; file time = master + shift) -> the source that holds
    the whole range [s, e], or None (that range exists on camera A only)."""
    return next((x for x in plan["b_sources"] if x[0] <= s and e <= x[1]), None)


def cmd_base(slug):
    plan, pieces = load_plan(slug), edl(slug)
    if plan.get("until"):
        pieces = [p for p in pieces if p["out"][0] < plan["until"] * FPS]
    wd = P(slug, "work", "pieces")
    os.makedirs(wd, exist_ok=True)
    grade = plan.get("grade", {})
    lst, jobs = [], []
    for p in pieces:
        a, b = p["src"]
        n = p["out"][1] - p["out"][0]
        if n <= 0:  # « -frames:v -18 » made ffmpeg run for 30 h and write a 51 GB .part (found 2026-10-04)
            raise SystemExit(f"piece {a}-{b} has {n} frames : fix plan.keep (a take ends before it starts)")
        tempo = p.get("tempo", 1.0)
        cam = p["angle"][0]
        t = a / FPS + cam_offset(plan, cam)
        rush, pl = P(slug, "assets", f"rush-{cam}.mov"), plan
        if cam == "B" and plan.get("b_sources"):  # camera B split over several files (storage full mid-shoot, 2026-10-03)
            src = b_source(plan, a / FPS, b / FPS)
            rush, t = P(slug, "assets", src[2]), a / FPS + src[3]
            if len(src) > 4:  # the phone was set down again between the files : its own face position
                pl = dict(plan, faces={**plan["faces"], "B": src[4]})
        key = f"v2{cam}{p['angle']}{a}-{b}-{tempo}-{angle_filter(pl, p['angle'])}-{grade.get(cam, '')}" + (f"-dz{p['dezoom']}" if p.get("dezoom") else "")
        f = os.path.join(wd, hashlib.md5(key.encode()).hexdigest()[:12] + ".mp4")
        dfl = plan.get("deflicker", {}).get(cam)
        if dfl:
            key += json.dumps(dfl)
            f = os.path.join(wd, hashlib.md5(key.encode()).hexdigest()[:12] + ".mp4")
        if not os.path.exists(f):
            # one colour range for every piece: camera A records full range (yuvj420p), B limited; mixing them in the
            # concat changes the stream parameters mid-video (filtergraph re-init: inserts dropped, contrast jumps)
            dz = ""
            if p.get("dezoom"):  # optional quick dezoom at the start of an intro sentence (plan.dezoom)
                z0, nf = p["dezoom"], 12
                dz = (f",scale=3840:2160:flags=lanczos,zoompan=z='if(lt(on,{nf}),1+{z0 - 1:.3f}*pow(1-on/{nf},3),1)':d=1"
                      f":x='(iw-iw/zoom)/2':y='(ih-ih/zoom)*0.42':s=1920x1080:fps=30")
            vf = ((f"setpts=PTS/{tempo}," if tempo != 1.0 else "") + angle_filter(pl, p["angle"]) + ("," + grade[cam] if grade.get(cam) else "")
                  + ",fps=30" + dz + ",scale=out_range=tv,format=yuv420p")
            cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.4f}", "-i", rush]
            if dfl:  # light flicker (lamp vs 30 fps) in a zone: average plan frames there, feathered mask
                cmd += ["-loop", "1", "-i", deflicker_mask(slug, cam, dfl), "-filter_complex",
                        f"[0:v]format=yuv420p,split[o][t];[t]tmix=frames={dfl.get('frames', 3)}[tm];[1:v]format=gray,scale=iw:ih[mk];"
                        f"[o][tm][mk]maskedmerge,{vf}[v]", "-map", "[v]"]
            else:
                cmd += ["-vf", vf]
            jobs.append((cmd + ["-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-r", "30", "-video_track_timescale", "30000",
                                "-color_range", "tv", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-f", "mp4", f + ".part"], f))
        lst.append(f"file '{f}'")
    def run(job):
        M.sh(job[0])
        os.replace(job[1] + ".part", job[1])  # a run killed mid-piece left a moov-less file in the cache: the concat stopped at 117 s (v2)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(plan.get("jobs", 5)) as ex:
        list(ex.map(run, jobs))
    print(f"base: {len(jobs)} new pieces encoded")
    open(P(slug, "work", "pieces.txt"), "w").write("\n".join(lst) + "\n")
    M.sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", P(slug, "work", "pieces.txt"), "-c", "copy", P(slug, "work", "base-v.mp4")])
    got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", P(slug, "work", "base-v.mp4")], capture_output=True, text=True).stdout)
    want = pieces[-1]["out"][1] / FPS
    if abs(got - want) > 0.2:
        raise SystemExit(f"base-v.mp4 is {got:.1f}s, the edit is {want:.1f}s: a piece is broken")
    # voice: same frame-exact pieces from the master sound, 6 ms fades at every joint (no click)
    y, sr = sf.read(voice(slug))
    if y.ndim > 1:
        y = y.mean(1)
    fade = int(0.012 * sr)
    ramp = np.linspace(0, 1, fade)
    out = []
    for n, p in enumerate(pieces):
        a, b = p["src"]
        s, e = round(a / FPS * sr), round(b / FPS * sr)
        x = y[s:e].copy()
        if p.get("tempo", 1.0) != 1.0:  # time-stretch, pitch kept (ffmpeg atempo), to the exact output length
            tmp_in, tmp_out = P(slug, "work", "st-in.wav"), P(slug, "work", "st-out.wav")
            sf.write(tmp_in, x, sr)
            M.sh(["ffmpeg", "-v", "error", "-y", "-i", tmp_in, "-af", f"atempo={p['tempo']}", tmp_out])
            x, _ = sf.read(tmp_out)
            need = round((p["out"][1] - p["out"][0]) / FPS * sr)
            x = np.pad(x, (0, max(0, need - len(x))))[:need]
        if n == 0 or pieces[n - 1]["src"][1] != a:  # a real cut (not a mere angle change): fade in
            x[:fade] *= ramp
        if n == len(pieces) - 1 or pieces[n + 1]["src"][0] != b:
            x[-fade:] *= ramp[::-1]
            # a word that the rush cuts short (he ran straight into the next sentence) ends with a soft 70 ms fall
            # instead of a wall
            h = sr // 100
            lv = [20 * np.log10(np.sqrt(np.mean(x[i:i + h] ** 2)) + 1e-9) for i in range(0, len(x) - h, h)]
            k = max((i for i, v in enumerate(lv) if v > -40), default=None)
            if k is not None and lv[k] > -30:
                stop, w = (k + 1) * h, int(0.07 * sr)
                x[max(0, stop - w):stop] *= np.cos(np.linspace(0, np.pi / 2, stop - max(0, stop - w))) ** 2
        out.append(x)
    sf.write(P(slug, "work", "base.wav"), np.concatenate(out), sr)
    nfr = sum(p["out"][1] - p["out"][0] for p in pieces)
    print(f"base: {len(pieces)} pieces, {nfr / FPS:.2f}s")


# ------------------------------------------------------------------ inserts
def cmd_inserts(slug):
    import prompteur_blocks as B
    plan, pieces, ws = load_plan(slug), edl(slug), words(slug)
    T = lambda a: to_out(slug, anchor(slug, a, ws), pieces)
    for ins in plan["inserts"]:
        s = T(ins["at"]) + ins.get("lead", 0)
        e = T(ins["until"]) + ins.get("tail", 0) if "until" in ins else s + ins["dur"]
        ins["_s"], ins["_e"] = round(s * FPS) / FPS, round(e * FPS) / FPS
    # the face never shows less than plan.min_face (1.5 s) between two full-screen inserts: the first one holds instead
    full = sorted((i for i in plan["inserts"] if not overlay_kind(i)), key=lambda i: i["_s"])
    for x, y in zip(full, full[1:]):
        if 0 < y["_s"] - x["_e"] < plan.get("min_face", 1.5):
            print(f"  hold {x['id']} to {y['id']} (face gap {y['_s'] - x['_e']:.2f}s)")
            x["_e"] = y["_s"]
    # a full-screen insert starting just after a cut starts on the cut; one ending just before a cut runs to it
    # (otherwise a sliver of face shows: a flash)
    cuts = [p["out"][0] / FPS for p in pieces[1:]]
    fulls = [i for i in plan["inserts"] if not overlay_kind(i)]
    covered = lambda a, b: any(o["_s"] <= a and o["_e"] >= b for o in fulls)
    for i in fulls:
        before = [c for c in cuts if 0 < i["_s"] - c < 1.0 and not covered(c, i["_s"])]
        if before:
            i["_s"] = max(before)
        after = [c for c in cuts if 0 < c - i["_e"] < 1.0 and not covered(i["_e"], c)]
        if after:
            i["_e"] = min(after)
    ow = P(slug, "assets", "out_words.json")  # word timings of the edited voice (transcribed after base)
    owords = M.load(ow)["words"] if os.path.exists(ow) else []
    import prompteur_blocks as PB
    for ins in plan["inserts"]:
        ins["_words"] = [[PB._norm(w["text"]), round(w["start"] - ins["_s"], 3)] for w in owords
                         if ins["_s"] - 1.0 <= w["start"] <= ins["_e"] + 1.0 and PB._norm(w["text"])]
    # two full-screen inserts that touch: the first one runs 3 frames under the next (no single frame of face at the joint);
    # every other full-screen insert gets one more frame, so its last planned frame is really covered (v6 check)
    for x, y in zip(full, full[1:]):
        if abs(y["_s"] - x["_e"]) < 0.05:
            x["_e"] = y["_s"] + 3 / FPS
    for x in full:
        if not any(abs(y["_s"] - x["_e"] + 3 / FPS) < 0.01 for y in full):
            x["_e"] += 1 / FPS
    # a keyword never sits on a full-screen visual (it would be hidden or fight it) : dropped there
    # (nor under another overlay such as a pop-up : it would hide it)
    others = full + [o for o in plan["inserts"] if overlay_kind(o) and o.get("kind") not in ("keyword", "icon")]
    drop = [i["id"] for i in plan["inserts"] if i.get("kind") == "keyword" and not i.get("over")  # over : asked for there
            and any(o["_s"] < i["_e"] - 0.1 and o["_e"] > i["_s"] + 0.1 for o in others)]
    if drop:
        print("  keywords under a full visual, dropped :", ", ".join(drop))
        plan["inserts"] = [i for i in plan["inserts"] if i["id"] not in drop]
    gsap = os.path.join(HERE, "assets", "gsap.min.js")
    if not os.path.exists(gsap):
        raise SystemExit("assets/gsap.min.js is missing : run scripts/install.sh (it downloads GSAP from npm)")
    B.set_brand((load_look(plan) or {}).get("brand"))
    for ins in plan["inserts"]:
        d = P(slug, "inserts", ins["id"])
        os.makedirs(f"{d}/assets/fonts", exist_ok=True)
        shutil.copy(gsap, f"{d}/assets/")
        for f in B.fonts():
            shutil.copy(os.path.join(HERE, "assets", "fonts", f), f"{d}/assets/fonts/")
        for f in ins.get("files", []):
            shutil.copy(P(slug, f), f"{d}/assets/")
        shutil.copy(os.path.join(HERE, "assets", "hyperframes.json"), f"{d}/hyperframes.json")
        rel = lambda a: max(0.0, T(a) - ins["_s"])
        html, cues = B.build(ins, ins["_e"] - ins["_s"], rel, P(slug, "assets"))
        ins["_cues"] = [c for c in cues if 0 <= c[1] < ins["_e"] - ins["_s"] or c[1] < 0] + [list(c) for c in ins.get("sfx", [])]
        for f in ins.get("files", []):
            html += f"<!-- {hashlib.md5(open(P(slug, f), 'rb').read()).hexdigest()} -->"
        open(f"{d}/index.html", "w").write(html)
        lint = subprocess.run(["npx", "--yes", HF, "lint"], cwd=d, capture_output=True, text=True).stdout
        errs = [l for l in lint.splitlines() if "✗" in l]
        print(f"{ins['id']:16s} {ins['_s']:7.2f} -> {ins['_e']:7.2f} ({ins['_e'] - ins['_s']:.1f}s) {'OK' if not errs else chr(10).join(errs)}")
        if errs:
            raise SystemExit("lint errors")
    M.save({i["id"]: [i["_s"], i["_e"], i["_cues"]] for i in plan["inserts"]}, P(slug, "work", "insert-times.json"))
    for i in plan["inserts"]:
        i.pop("_words", None)
    face_report(slug, plan, pieces)


def face_report(slug, plan, pieces):
    """Visible face shots (outside full-screen inserts): any shorter than 1 s is a flash (review, v2 at 0:23)."""
    full = sorted((i["_s"], i["_e"]) for i in plan["inserts"] if not overlay_kind(i))
    total = pieces[-1]["out"][1] / FPS
    bad = []
    for p in pieces:
        a, b = p["out"][0] / FPS, p["out"][1] / FPS
        vis, t = [], a
        for s0, e0 in full:
            if e0 <= t or s0 >= b:
                continue
            if s0 > t:
                vis.append((t, s0))
            t = max(t, e0)
        if t < b:
            vis.append((t, b))
        bad += [(x, y, p["angle"]) for x, y in vis if y - x < 1.0 and not (y >= total - 0.05)]
    for x, y, ang in bad:
        print(f"  ! face flash {x:6.2f} -> {y:6.2f} ({y - x:.2f}s, angle {ang})")
    print(f"face shots under 1 s: {len(bad)}")


def overlay_kind(ins):
    import prompteur_blocks as B
    return ins["kind"] in B.OVERLAYS or bool(ins.get("overlay"))


def cmd_render(slug):
    plan = load_plan(slug)
    os.makedirs(P(slug, "work", "ins"), exist_ok=True)
    times = M.load(P(slug, "work", "insert-times.json"))
    todo = []
    for ins in (i for i in plan["inserts"] if i["id"] in times):  # keywords dropped by cmd_inserts are not rendered
        d = P(slug, "inserts", ins["id"])
        ext = "webm" if overlay_kind(ins) else "mp4"
        out = P(slug, "work", "ins", f"{ins['id']}.{ext}")
        h = hashlib.md5(open(f"{d}/index.html", "rb").read()).hexdigest()
        if os.path.exists(out) and os.path.exists(out + ".md5") and open(out + ".md5").read() == h:
            print(f"{ins['id']}: unchanged"); continue
        todo.append((ins["id"], d, ext, out, h))
    def one(job):
        iid, d, ext, out, h = job
        print(f"{iid}: rendering", flush=True)
        before = os.path.getmtime(out) if os.path.exists(out) else 0
        r = subprocess.run(["npx", "--yes", HF, "render", "--format", ext, "--output", out, "--quiet"], cwd=d,
                           stdout=open(out + ".log", "w"), stderr=subprocess.STDOUT)
        if r.returncode or not os.path.exists(out) or os.path.getmtime(out) <= before:
            return f"{iid}: render failed, see {out}.log"
        open(out + ".md5", "w").write(h)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(plan.get("render_jobs", 4)) as ex:  # 4 headless Chromes at once (2026-10-04 : one by one took 40 min)
        errs = [e for e in ex.map(one, todo) if e]
    if errs:
        raise SystemExit("\n".join(errs))


# ------------------------------------------------------------------ compose
def sfx_cues(slug, plan, times, dur):
    """Every sound effect of the edit as (file, out time, dB) : insert sounds, the look's rules, plan.sfx, levels, dedupe.
    Shared by compose (pre-mixed track) and premiere/build_timeline.py (one clip per sound)."""
    cues = []
    look = load_look(plan)
    # sounds built into the inserts (typing, pops of a list...) : only when the creator chose them (look.sound.insert_sounds)
    if not plan.get("no_sfx") and (look or {}).get("sound", {}).get("insert_sounds"):
        for ins in plan["inserts"]:
            for f, off, db in times[ins["id"]][2]:
                cues.append((f, times[ins["id"]][0] + off, db))
    look = load_look(plan)
    if look and not plan.get("no_sfx"):  # the look's sound rules (none when the creator chose none)
        rule = {c["on"]: c for c in look.get("sound", {}).get("cues", [])}
        covered = []
        for ins in plan["inserts"]:
            s0, e0 = times[ins["id"]][:2]
            if s0 >= dur:
                continue
            c = rule.get("keyword or icon pop") if overlay_kind(ins) else rule.get("visual entrance")
            if not overlay_kind(ins):
                covered.append((s0, e0))
            if c:
                cues.append((c["file"], max(0.0, s0 - c.get("lead", 0)), c["db"]))
        c = rule.get("every face cut")
        for p in edl(slug)[1:] if c else []:
            t = p["out"][0] / FPS
            if t < dur and not any(a - 0.05 <= t <= b + 0.05 for a, b in covered):
                cues.append((c["file"], t, c["db"]))
    for f, t, db in plan.get("sfx", []):  # extra sounds placed on a spoken word ("mot@123.4", "cold:420.6") or an output time
        cues.append((f, to_out(slug, anchor(slug, t)) if isinstance(t, str) else float(t), db))
    # one level scale for every sound effect (-10 to -27 dB made some sounds vanish under the voice) :
    # plan.sfx_levels {file: dB} wins, else nothing below plan.sfx_floor (-24 dB, except typing)
    lv, floor = plan.get("sfx_levels") or (look or {}).get("sound", {}).get("levels", {}), plan.get("sfx_floor")
    if lv or floor is not None:
        cues = [(f, t, lv.get(f, max(db, floor) if floor is not None and f != "typing.wav" else db)) for f, t, db in cues]
    # the same sound twice within 150 ms is one sound (seven pops 70 ms apart made a buzz)
    cues.sort(key=lambda c: c[1])
    kept = []
    for c in cues:
        if not any(k[0] == c[0] and abs(k[1] - c[1]) < 0.15 for k in kept[-12:]):
            kept.append(c)
    cues = [c for c in kept if sfx_file(c[0])]
    return cues


def load_look(plan):
    """plan.look = a folder of looks/ (the creator's style, chosen once with the « style-de-montage » skill on choice
    videos, then applied, never reinvented)."""
    return json.load(open(os.path.join(HERE, "looks", plan["look"], "look.json"))) if plan.get("look") else None


SFX_DIR = os.path.join(HERE, "assets", "sfx")
_missing = set()


def sfx_file(f):
    """Path of a sound effect in assets/sfx, or None (with one warning) when it is not there : a missing sound never
    stops a render (tools/make_sfx.py writes the default set, the user may replace any of them)."""
    path = os.path.join(SFX_DIR, f)
    if os.path.exists(path):
        return path
    if f not in _missing:
        _missing.add(f)
        print(f"  ! sound effect missing, skipped : assets/sfx/{f} (run tools/make_sfx.py)")
    return None


def cmd_compose(slug, name="v1"):
    plan = load_plan(slug)
    times = M.load(P(slug, "work", "insert-times.json"))
    plan["inserts"] = [i for i in plan["inserts"] if i["id"] in times]  # cmd_inserts drops keywords under full visuals
    base_v, base_a = P(slug, "work", "base-v.mp4"), P(slug, "work", "base.wav")
    # plan.base_video : the face track after Premiere applied the look's zooms (premiere/apply_look.py), same length
    base_v = P(slug, plan["base_video"]) if plan.get("base_video") else base_v
    dur = len(sf.read(base_a)[0]) / SR
    inputs, fc, last = ["-i", base_v, "-i", base_a], [], "0:v"
    k = 2
    for ins in plan["inserts"]:
        s, e = times[ins["id"]][:2]
        if s >= dur:
            continue
        f = P(slug, "work", "ins", f"{ins['id']}.{'webm' if overlay_kind(ins) else 'mp4'}")
        inputs += (["-c:v", "libvpx-vp9"] if f.endswith("webm") else []) + ["-i", f]
        # half a frame early: an insert placed on frame n must be drawn ON frame n (v5 : starting exactly at s, ffmpeg drew
        # it one frame late and one frame of the camera underneath showed at the cut)
        off = max(0.0, round(s * FPS) / FPS - 0.5 / FPS)
        # and the last frame cloned once: ffmpeg's overlay drops an input's last frame (it ends at that frame's pts)
        fc.append(f"[{k}:v]tpad=stop_mode=clone:stop=1,setpts=PTS-STARTPTS+{off:.4f}/TB[i{k}];[{last}][i{k}]overlay=0:0:eof_action=pass:format=auto[v{k}]")
        last, k = f"v{k}", k + 1
    # sound effects: plan.sfx = [[file, at(anchor or out time with "o:" prefix), dB], ...] + per-insert "sfx"
    mix = ["[voice]"]
    cues = sfx_cues(slug, plan, times, dur)
    # every sound effect pre-mixed into one track (a full video has hundreds: one ffmpeg input each was too heavy)
    if cues:
        sfx = np.zeros((int((dur + 2) * SR), 2))
        cache = {}
        for f, t, db in cues:
            if t >= dur:
                continue
            if f not in cache:
                x, r = sf.read(sfx_file(f), always_2d=True)
                if r != SR:
                    import scipy.signal as ss
                    x = ss.resample(x, int(len(x) * SR / r))
                cache[f] = x[:, :2] if x.shape[1] >= 2 else np.repeat(x, 2, axis=1)
            x = cache[f] * 10 ** (db / 20)
            i0 = int(max(t, 0) * SR)
            n = min(len(x), len(sfx) - i0)
            sfx[i0:i0 + n] += x[:n]
        sfx_path = P(slug, "work", "sfx-track.wav")
        sf.write(sfx_path, sfx, SR)
        inputs += ["-i", sfx_path]
        mix.append(f"[{k}:a]"); k += 1
    voice_gain = plan.get("voice_gain_db", 0)
    fc.insert(0, f"[1:a]volume={voice_gain}dB,asplit=2[voice][key]")
    m = plan.get("music")
    if m and m.get("segments"):
        bed, hooks, report = build_music_bed(slug, plan, dur)
        inputs += ["-i", bed, "-i", hooks]
        fc.append(f"[{k}:a]anull[bd];[bd][key]sidechaincompress=threshold=0.06:ratio={m.get('duck_ratio', 1.6)}:attack=60:"
                  f"release={m.get('duck_release', 700)}:makeup=1[bed]")
        mix += ["[bed]", f"[{k + 1}:a]"]; k += 2
        print(report)
    elif m:
        # Single-track music : the track starts on its drop
        # (m.offset), a cinematic hit lands on chosen words (m.hits, the sting's riser runs before them), the bed cuts out
        # just before a strong announcement (m.mutes) and comes up under full-screen inserts (m.boost_db).
        f = os.path.join(HERE, m["file"])
        trimmed = P(slug, "work", "music-src.wav")
        M.sh(["ffmpeg", "-v", "error", "-y", "-ss", str(m.get("offset", 0)), "-i", f, "-ac", "2", "-ar", "48000", trimmed])
        gain = M_lufs(base_a) - m.get("under_db", 12) - M_lufs(trimmed)
        inputs += ["-i", music.loop_track(trimmed, dur)]
        fo = m.get("fade_out", 3)
        T = lambda a: to_out(slug, anchor(slug, a)) if isinstance(a, str) else float(a)
        terms = []
        for a, b in m.get("mutes", []):
            terms.append(f"between(t,{T(a):.3f},{T(b):.3f})*(-1)")
        for a, b, d in m.get("dips", []):  # [from, to, dB] : the bed held lower, back up at « to »
            terms.append(f"between(t,{T(a):.3f},{T(b):.3f})*({10 ** (d / 20) - 1:.3f})")
        if m.get("boost_db"):
            g = 10 ** (m["boost_db"] / 20) - 1
            for ins in plan["inserts"]:
                if not overlay_kind(ins):
                    s0, e0 = times[ins["id"]][:2]
                    terms.append(f"between(t,{s0:.3f},{e0:.3f})*{g:.3f}")
        expr = "max(0,1+" + "+".join(terms) + ")" if terms else "1"
        fc.append(f"[{k}:a]atrim=0:{dur:.3f},afade=t=in:d={m.get('fade_in', 0.02)},afade=t=out:st={dur - fo:.2f}:d={fo},volume={gain:.1f}dB,"
                  f"volume='{expr}':eval=frame[bd];"
                  f"[bd][key]sidechaincompress=threshold=0.06:ratio={m.get('duck_ratio', 1.6)}:attack=60:release={m.get('duck_release', 700)}:makeup=1[bed]")
        mix.append("[bed]"); k += 1
        for j, h in enumerate(m.get("hits", [])):
            at = T(h["at"]) if isinstance(h, dict) else T(h)
            drop = min(h.get("riser", 0.8) if isinstance(h, dict) else 0.8, at)
            wav = P(slug, "work", f"hit{j}.wav")
            music.write_wav(wav, music.STINGS[m.get("sting", "c")](drop))
            st = at - drop
            inputs += ["-i", wav]
            ms = int(max(st, 0) * 1000)
            fc.append(f"[{k}:a]adelay={ms}|{ms},volume={m.get('hit_db', -8)}dB[h{j}]")
            mix.append(f"[h{j}]"); k += 1
        print(f"music {m['file']} from {m.get('offset', 0)}s: {gain:+.1f} dB ({m.get('under_db', 12)} LU under the voice), "
              f"{len(m.get('hits', []))} hits, {len(m.get('mutes', []))} mutes")
    else:
        fc.append("[key]anullsink")
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I={plan.get('lufs', -14)}:TP={plan.get('true_peak', -1.5)}:LRA=11,aresample=48000[a]")  # plan.lufs : -14 by default (YouTube), lower on a clipped recording
    fc.append(f"[{last}]format=yuv420p[v]")
    out = P(slug, "renders", f"{name}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    M.sh(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
          "-movflags", "+faststart", "-t", f"{dur:.3f}", out])
    print(f"rendered {out} ({dur:.2f}s)")


def music_layout(slug, plan, dur, times=None):
    """plan.music resolved to output times : (segments with "t", silences [(a, b)], hooks [(file, t, dB, "start"|"end")]).
    Times : a number (output s), "mot@123.4" / "src:123.4" (spoken word), "ins:<id>" (start of an insert, e.g. a chapter card).
    cuts [[a, b, sound]] : b < 0 means |b| s BEFORE a (« 1 s before the card ») ; stops [[a, b]] : b = "end" runs to the end."""
    m = plan["music"]
    times = times or M.load(P(slug, "work", "insert-times.json"))
    def T(a):
        if isinstance(a, str) and a.startswith("ins:"):
            return times[a[4:]][0]
        return to_out(slug, anchor(slug, a)) if isinstance(a, str) else float(a)
    def span(a, b):
        if b == "end":
            return T(a), dur
        if isinstance(b, (int, float)) and b < 0:
            return T(a) + b, T(a)
        return T(a), T(b)
    segs = sorted((g for g in ({**g, "t": T(g["at"])} for g in m["segments"]) if g["t"] < dur), key=lambda g: g["t"])
    sil, hooks = [], []
    o = m.get("open")
    if o:
        stop, back = T(o["stop"]), T(o["back"])
        sil.append((stop, back))
        hooks += [(o.get("riser", "hook-riser-1.wav"), stop, o.get("riser_db", -16), "end"), (o.get("impact", "hook-impact-1.wav"), back, o.get("impact_db", -12), "start")]
        if o.get("start_hit"):  # the video opens on a low hit, the music under it
            hooks.append((o.get("impact", "hook-impact-1.wav"), 0.0, o.get("impact_db", -12) - 3, "start"))
    for c in m.get("cuts", []):
        t0, t1 = span(c[0], c[1])
        if len(c) > 3 and c[3] == "fade":  # a chapter change fades out (music_fades), the sound still lands on the card
            t0, t1 = _fade_span(T, c)
            if c[2]:
                hooks.append((c[2], t1, -18, "start"))
            if len(c) > 4 and c[4] == "end":  # the outro : no music after the fade
                sil.append((t1, dur))
            continue
        sil.append((t0, t1))
        if len(c) > 2 and c[2]:
            hooks.append((c[2], t1 - (0.15 if "whoosh" in c[2] else 0), -18, "start"))
    c = m.get("close")
    if c:
        t = T(c["at"])
        nxt = min([g["t"] for g in segs if g["t"] > t] + [dur])
        sil.append((t, nxt))
        hooks.append((c.get("sound", "hook-reverse-1.wav"), t, c.get("db", -16), "end"))
    sil += [span(a, b) for a, b in m.get("stops", [])]
    return segs, sil, [h for h in hooks if h[1] < dur and h[0]]


def music_fades(slug, plan, dur, times=None):
    """plan.music.cuts marked "fade" ([anchor, -1.5, sound, "fade"]) -> [(t0, t1)] : the music fades out over t0..t1, the next
    track starts at t1 (a fade instead of a hard stop)."""
    times = times or M.load(P(slug, "work", "insert-times.json"))
    T = lambda a: times[a[4:]][0] if isinstance(a, str) and a.startswith("ins:") else (to_out(slug, anchor(slug, a)) if isinstance(a, str) else float(a))
    out = []
    for c in plan["music"].get("cuts", []):
        if len(c) > 3 and c[3] == "fade":
            t0, t1 = _fade_span(T, c)
            if t0 < dur:
                out.append((t0, min(t1, dur)))
    return out


def _fade_span(T, c):
    """[anchor, -1.5, ...] : the fade ends on the anchor (a chapter card) ; [anchor, 2.0, ...] : it starts on the anchor and
    lasts 2 s (the outro) ; [anchor, anchor2, ...] : from one to the other."""
    a = T(c[0])
    if isinstance(c[1], (int, float)):
        return (a + c[1], a) if c[1] < 0 else (a, a + c[1])
    return a, T(c[1])


def music_end_before(plan, f):
    """The look's palette may stop a track before a part the creator does not want : {"file": ..., "end_before": 138} (seconds of the file)."""
    look = load_look(plan) or {}
    return next((p.get("end_before") for p in look.get("music", {}).get("palette", []) if p["file"] == f), None)


def build_music_bed(slug, plan, dur):
    """Music bed from plan.music (written by tools/music_plan.py from the creator's look) :
      segments [{file, at, offset, under_db}] : a track enters at « at » (anchor or out time) from its « offset » and runs until
        the next segment or a stop ; under_db = LU under the voice (from the look) ;
      cuts [[from, to, sound?]] : a hard stop (10 ms, no fade) before a strong sentence, back at « to » with sound
        (whoosh / impact) ;
      open {riser, impact, stop, back} : the intro hook, riser ending on « stop » (music silent), impact on « back » ;
      close {at, sound} : the end of the intro, a sound ending on « at », the music cut dead there ;
      stops [[from, to]] : no music (demos, lists, calls to action).
    Returns (bed.wav ducked later under the voice, hooks.wav never ducked, report)."""
    m = plan["music"]
    T = lambda a: to_out(slug, anchor(slug, a)) if isinstance(a, str) else float(a)
    n = int((dur + 0.5) * SR)
    vl = M_lufs(P(slug, "work", "base.wav"))
    bed, hooks = np.zeros((n, 2)), np.zeros((n, 2))
    gate = np.ones(n)

    def load(f, offset=0.0, need=None):
        tmp = P(slug, "work", "music-seg.wav")
        eb = music_end_before(plan, f)  # a track is never played past a part the creator does not want
        M.sh(["ffmpeg", "-v", "error", "-y", "-ss", str(offset)] + (["-to", str(eb)] if eb else []) + ["-i", os.path.join(HERE, os.path.expanduser(f)), "-ac", "2", "-ar", str(SR), tmp])
        x, _ = sf.read(tmp, always_2d=True)
        if need and len(x) < need:  # loop with a 3 s crossfade
            x = sf.read(music.loop_track(tmp, need / SR + 1), always_2d=True)[0]
        return x, M_lufs(tmp)

    segs, sils, hks = music_layout(slug, plan, dur)
    rep = []
    for i, g in enumerate(segs):
        a = int(g["t"] * SR); b = int(segs[i + 1]["t"] * SR) if i + 1 < len(segs) else n
        x, lu = load(g["file"], g.get("offset", 0), b - a)
        gain = 10 ** ((vl - g.get("under_db", 18) - lu) / 20)
        L = min(b - a, len(x))
        y = x[:L] * gain
        y[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]
        bed[a:a + L] += y
        rep.append(f"{g['t']:.1f}s {os.path.basename(g['file'])} @{g.get('offset', 0)} -{g.get('under_db', 18)} LU")

    def sfx(f, t, db, end=False):
        if not sfx_file(f):
            return
        x, r = sf.read(sfx_file(f), always_2d=True)
        if r != SR:
            import scipy.signal as ss; x = ss.resample(x, int(len(x) * SR / r))
        x = (x if x.shape[1] == 2 else np.repeat(x[:, :1], 2, 1)) * 10 ** (db / 20)
        i0 = int(t * SR) - (len(x) if end else 0)
        j0 = max(0, -i0); i0 = max(0, i0)
        L = min(len(x) - j0, n - i0)
        if L > 0:
            hooks[i0:i0 + L] += x[j0:j0 + L]

    def silence(t0, t1):
        a, b = int(t0 * SR), int(t1 * SR)
        r = int(0.01 * SR)
        gate[a:b] = 0
        gate[max(a - r, 0):a] = np.minimum(gate[max(a - r, 0):a], np.linspace(1, 0, a - max(a - r, 0)))
        gate[b:b + r] = np.minimum(gate[b:b + r], np.linspace(0, 1, len(gate[b:b + r])))

    for f, t, db, kind in hks:
        sfx(f, t, db, end=(kind == "end"))
    for a0, b0 in sils:
        silence(a0, b0)
    for a0, b0 in music_fades(slug, plan, dur):
        a, b = int(a0 * SR), int(b0 * SR)
        gate[a:b] = np.minimum(gate[a:b], np.linspace(1, 0, b - a) ** 2)
    rep.append(f"{len(hks)} hooks, {len(sils)} silences")
    fo = int(m.get("fade_out", 1.5) * SR)
    gate[-fo:] *= np.linspace(1, 0, fo)
    bed *= gate[:, None]
    pb, ph = P(slug, "work", "music-bed.wav"), P(slug, "work", "music-hooks.wav")
    sf.write(pb, bed[:int(dur * SR)], SR); sf.write(ph, hooks[:int(dur * SR)], SR)
    return pb, ph, "music : " + " | ".join(rep)


def M_lufs(path):
    err = subprocess.run(["ffmpeg", "-i", path, "-af", "ebur128", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[0-9.]+) LUFS", err)[-1])


def cmd_sheet(slug, name="v1"):
    plan = load_plan(slug)
    times = M.load(P(slug, "work", "insert-times.json"))
    src = P(slug, "renders", f"{name}.mp4")
    sd = P(slug, "work", "sheet")
    shutil.rmtree(sd, ignore_errors=True); os.makedirs(sd)
    shots = [(i["id"], (times[i["id"]][0] + times[i["id"]][1]) / 2) for i in plan["inserts"]]
    seen = set()
    for p in edl(slug):
        if p["angle"] not in seen and (not plan.get("until") or p["out"][0] < plan["until"] * FPS):
            seen.add(p["angle"]); shots.append((p["angle"], (p["out"][0] + p["out"][1]) / 2 / FPS))
    for n, (lab, t) in enumerate(sorted(shots, key=lambda x: x[1])):
        M.sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-vf",
              f"scale=640:-1,drawtext=text='{lab} {t:.1f}':x=10:y=10:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6",
              os.path.join(sd, f"{n:03d}.jpg")])
    M.sh(["ffmpeg", "-v", "error", "-y", "-pattern_type", "glob", "-i", os.path.join(sd, "*.jpg"), "-vf", f"tile=4x{min(6, max(1, -(-len(shots) // 4)))}:padding=6",
          P(slug, "renders", f"{name}-sheet-%02d.jpg")])
    print("sheets:", sorted(f for f in os.listdir(P(slug, "renders")) if f.startswith(f"{name}-sheet")))


# ------------------------------------------------------------------ checks (validated workflow, 2026-10-01)
def lang(slug):
    return load_plan(slug).get("language", "fr")


def _whisper(model="medium"):
    import fastwhisper  # Apple GPU (mlx), openai-whisper fallback
    return fastwhisper.load_model(model)


def cmd_takes(slug):
    """Each kept take transcribed ALONE (medium): the full-rush transcript merges retakes (a phrase
    said twice read as once). Read every line for a doubled phrase; then `gaps`."""
    plan, (y, sr) = load_plan(slug), sf.read(voice(slug, True))
    m = _whisper()
    for k in plan["keep"]:
        a, b = anchor(slug, k[0]), anchor_end(slug, k[1])
        r = m.transcribe(y[int(a * sr):int(b * sr)].astype(np.float32), language=lang(slug), word_timestamps=True,
                         condition_on_previous_text=False, temperature=0)
        print(f"[{a:.2f}-{b:.2f}]", " ".join(f"{w['word'].strip()}@{a + w['start']:.2f}" for s in r["segments"] for w in s["words"]))


def cmd_gaps(slug, min_gap="0.5"):
    """Every hole longer than min_gap between two words of a kept take, heard alone in a 1-2 s window, with the
    sound level: a word cut short then silence = a false start to remove from plan.keep."""
    plan, (y, sr), ws = load_plan(slug), sf.read(voice(slug, True)), words(slug)
    m = _whisper()
    for k in plan["keep"]:
        a, b = anchor(slug, k[0]), anchor_end(slug, k[1])
        inside = [w for w in ws if a <= w["start"] <= b]
        for w1, w2 in zip(inside, inside[1:]):
            if w2["start"] - w1["end"] > float(min_gap) or w1["end"] - w1["start"] > 0.9:
                lo, hi = w1["start"] - 0.3, w2["end"] + 0.3
                seg = np.concatenate([np.zeros(int(.3 * sr)), y[int(lo * sr):int(hi * sr)], np.zeros(int(.3 * sr))]).astype(np.float32)
                print(f"{lo:7.2f}-{hi:7.2f}  {w1['text']} … {w2['text']}  ->", m.transcribe(seg, language=lang(slug), condition_on_previous_text=False, temperature=0)["text"])


def cmd_outwords(slug):
    """Transcribe the EDITED voice (work/base.wav) with word timings -> assets/out_words.json: every caption word
    blurs in on these timings; read the text once more for a leftover retake or a clipped word."""
    M.sh(["ffmpeg", "-v", "error", "-y", "-i", P(slug, "work", "base.wav"), "-ac", "1", "-ar", "16000", P(slug, "work", "base16.wav")])
    r = _whisper().transcribe(P(slug, "work", "base16.wav"), language=lang(slug), word_timestamps=True, condition_on_previous_text=False,
                              temperature=0, initial_prompt=load_plan(slug).get("whisper_prompt") or None)
    ws = [{"text": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3)} for s in r["segments"] for w in s["words"]]
    M.save({"words": ws}, P(slug, "assets", "out_words.json"))
    print(r["text"])


def cmd_verbatim(slug):
    """Every text shown on screen must be the speaker's exact words (except the name tag, a number said in letters shown
    in digits, and a line he dictated: mark it "free")."""
    import re
    plan = load_plan(slug)
    src = " ".join(w["text"] for w in M.load(P(slug, "assets", "out_words.json"))["words"])
    norm = lambda t: " ".join(x for x in re.sub(r"[.,!?:;«»\u00a0]", " ", t.lower().replace("’", "'")).replace("'", " ' ").split() if x != "'")
    S = norm(src)
    for i in plan["inserts"]:
        texts = [ln[1] for ln in i.get("punch", []) if not (len(ln) > 5 and ln[5] == "free")]
        texts += [it["t"] for it in i.get("items", [])] + [i[k]["t"] if isinstance(i.get(k), dict) else i[k] for k in ("title", "sub", "label") if i.get(k)]
        for t in texts:
            print(("OK  " if norm(t) in S else "XX  ") + i["id"].ljust(12) + t)


def cmd_joints(slug, name):
    """First and last frame of every full-screen insert compared with the face track underneath: any match is a
    frame of the speaker's face at a joint (v3, v5: one frame was enough for him to see it)."""
    t, plan = M.load(P(slug, "work", "insert-times.json")), load_plan(slug)

    def frame(path, n):
        # seek straight to frame n (decoding from the start for each frame took hours on a full video)
        k = min(n, 10)  # accurate seek 10 frames before, then the exact frame by index
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{(n - k) / FPS:.4f}", "-i", path, "-vf", f"select='eq(n\\,{k})',scale=96:54,format=gray",
                            "-frames:v", "1", "-f", "rawvideo", "-"], capture_output=True)
        return np.frombuffer(r.stdout, np.uint8).astype(float)
    bad = 0
    for i in plan["inserts"]:
        if overlay_kind(i):
            continue
        s, e = t[i["id"]][:2]
        for n in (round(s * FPS), round(e * FPS) - 1):
            a, b = frame(P(slug, "renders", f"{name}.mp4"), n), frame(P(slug, "work", "base-v.mp4"), n)
            if len(a) == len(b) == 96 * 54 and np.abs(a - b).mean() < 6:
                bad += 1
                print(f"  ! {i['id']} frame {n}: face cam shows")
    print(f"joints with a face frame: {bad}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    c, slug, rest = sys.argv[1], sys.argv[2], sys.argv[3:]
    if c == "all":
        for f in (cmd_cut, cmd_base, cmd_inserts, cmd_render):
            f(slug)
        cmd_compose(slug, *rest); cmd_sheet(slug, *rest)
    else:
        globals()[f"cmd_{c}"](slug, *rest)
