#!/usr/bin/env python3
"""A/B/C choice videos : the SAME sentence of the creator, edited several ways, one after the other, each labelled with
its letter and what it is. The creator answers with a letter (« la B, mais parfois la C ») and the answer goes into their
style. The options are neutral and widely spread on purpose : they come from no one's style.

  python3 tools/choix.py <slug> cadrages   A one fixed framing | B wide and tight | C wide, tight and very tight
  python3 tools/choix.py <slug> rythme     A cut between sentences only, natural pauses | B a cut about every 4 s | C every 2 s, short pauses
  python3 tools/choix.py <slug> zooms      A no zoom | B light (slow push 4 %) | C strong (push 8 % + quick zoom on the strong word)
  python3 tools/choix.py <slug> sons       A no sound effect | B soft (a light click on cuts) | C marked (click, whoosh, pop, low hit)
  python3 tools/choix.py <slug> musique [--tracks a.mp3,b.mp3,c.mp3]   one track per mood (tools/musique.py get trio), under the voice
  python3 tools/choix.py <slug> mots       A no word on screen | B simple | C bold (accent colour)
Options : --words  strong words as anchors "MOT@rush time" (default : a number or the longest word of the sentence)
          --look   style whose brand colours and font are used (default plan.look)

The project needs a short excerpt already cut : tools/projet.py, tools/transcribe.py, plan.keep with ONE sentence (8 to
15 s), prompteur.py cut and base. Output : projects/<slug>/renders/choix-<kind>.mp4, copied to the output folder."""
import argparse, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "tools"))
import montage as M
import prompteur as PR
from look_ffmpeg import render_keys, frames

FPS = 30
FONT = os.path.join(HERE, "assets", "fonts", "Poppins-ExtraBold.ttf")


def ease(t0, dur, v0, v1, steps=6):
    return [(t0 + dur * k / steps, v0 + (v1 - v0) * (1 - (1 - k / steps) ** 3)) for k in range(steps + 1)]


def strong_words(slug, given):
    """Output times of the strong words : the given anchors, else numbers and the longest words of the excerpt."""
    pieces = PR.edl(slug)
    if given:
        return [(w.split("@")[0], PR.to_out(slug, PR.anchor(slug, w), pieces), w) for w in given]
    kept = lambda t: any(p["src"][0] <= t * FPS < p["src"][1] for p in pieces)
    ws = [w for w in PR.words(slug) if kept(w["start"])]
    clean = lambda x: x.strip(" .,!?«»:;'’")
    rank = sorted(ws, key=lambda w: (not re.search(r"\d", w["text"]), -len(clean(w["text"]))))
    cand = rank[:1] + [w for w in rank[1:] if abs(w["start"] - rank[0]["start"]) < 2.5][:1]  # one keyword : words said together
    return sorted([(clean(w["text"]), PR.to_out(slug, w["start"], pieces), f"{clean(w['text'])}@{w['start']:.2f}") for w in cand], key=lambda x: x[1])


def label(src, letter, dst, audio=None):
    """The variant with its letter top-left (and its own sound when given)."""
    vf = f"drawtext=fontfile='{FONT}':text='{letter}':x=60:y=40:fontsize=110:fontcolor=white:borderw=6:bordercolor=black@0.6"
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src] + (["-i", audio] if audio else []) + ["-vf", vf, "-map", "0:v"] + \
          (["-map", "1:a"] if audio else ["-map", "0:a?"]) + ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-r", "30",
                                                            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", dst]
    subprocess.run(cmd, check=True)


def card(letter, dst, sub=""):
    """0.9 s black card with the big letter (and what it is, in small)."""
    txt = f"drawtext=fontfile='{FONT}':text='{letter}':x=(w-tw)/2:y=(h-th)/2-40:fontsize=260:fontcolor=white"
    if sub:
        sub = sub.replace("'", "’").replace(":", " ")
        txt += f",drawtext=fontfile='{FONT}':text='{sub}':x=(w-tw)/2:y=h/2+150:fontsize=44:fontcolor=white@0.7"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x0a0a0a:s=1920x1080:r=30:d=0.9", "-f", "lavfi",
                    "-i", "anullsrc=r=48000:cl=stereo", "-vf", txt, "-t", "0.9", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", dst], check=True)


def concat(parts, dst):
    n = len(parts)
    inputs = sum((["-i", p] for p in parts), [])
    fc = "".join(f"[{i}:v][{i}:a]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                    "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dst], check=True)


def mix(slug, out, cues=(), music=None, under=14.0):
    """Voice + sound effects [(file, t, dB)] + optional music track (file, offset) under the voice, -14 LUFS."""
    W = PR.P(slug, "work")
    voice = os.path.join(W, "base.wav")
    dur = frames(os.path.join(W, "base-v.mp4")) / FPS
    inputs, fc, labels = ["-i", voice], ["[0:a]aformat=channel_layouts=stereo,asplit=2[v][key]"], ["[v]"]
    k = 1
    for f, t, db in cues:
        p = PR.sfx_file(f)
        if not p:
            continue
        inputs += ["-i", p]
        ms = int(max(t, 0) * 1000)
        fc.append(f"[{k}:a]aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={db}dB[s{k}]")
        labels.append(f"[s{k}]"); k += 1
    if music:
        f, off = music
        gain = PR.M_lufs(voice) - under - track_lufs(f, off, dur)
        inputs += ["-ss", str(off), "-i", os.path.join(HERE, f)]
        fc.append(f"[{k}:a]aformat=channel_layouts=stereo,atrim=0:{dur:.2f},afade=t=in:d=0.3,afade=t=out:st={max(dur - 1.5, 0):.2f}:d=1.5,"
                  f"volume={gain:.1f}dB[m0];[m0][key]sidechaincompress=threshold=0.06:ratio=1.6:attack=60:release=700[m]")
        labels.append("[m]"); k += 1
    else:
        fc.append("[key]anullsink")
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[a]", "-t", f"{dur:.3f}", out], check=True)
    return out


def track_lufs(f, off, dur):
    tmp = os.path.join("/tmp", "choix-track.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(off), "-i", os.path.join(HERE, f), "-t", f"{dur:.2f}", "-ac", "2", tmp], check=True)
    return PR.M_lufs(tmp)


def zoom_track(slug, style, words, d):
    """The face track with one zoom option drawn on it (same renderer as the style) : A none, B light, C strong."""
    W = PR.P(slug, "work")
    base = os.path.join(W, "base-v.mp4")
    n = frames(base)
    end = n / FPS
    cuts_f = sorted({p["out"][0] for p in PR.edl(slug) if p["out"][0] < n} | {0})
    cuts = [c / FPS for c in cuts_f]
    shots = list(zip(cuts, cuts[1:] + [end]))
    F = 1 / FPS
    push = {"A": 0, "B": 4, "C": 8}[style]
    keys = []
    for k, (a, b) in enumerate(shots):
        f0, f1 = (100 + push, 100) if k % 2 else (100, 100 + push)
        w = next((t for _, t, _ in words if a + 0.2 <= t < b - 0.4), None)
        if style == "C" and w is not None:
            v0 = f0 + (f1 - f0) * (w - 0.05 - a) / (b - a)
            keys += [(a, f0), (w - 0.05 - F, v0)] + ease(w - 0.05, 0.27, v0, v0 + 15) + [(b - F, v0 + 15)]
        else:
            keys += [(a, f0), (b - F, f1)]
    seen, out = set(), []
    for t, v in sorted(keys):
        t = round(max(t, 0), 3)
        if t not in seen and t < end:
            seen.add(t); out.append((t, round(v, 2)))
    dst = os.path.join(d, f"zoom-{style}.mp4")
    render_keys(base, out, cuts_f, n, os.path.join(d, f"ff-{style}"), dst)
    return dst


def recut(slug, overrides, d, tag):
    """Cuts the excerpt again with plan overrides (framings, rhythm) and returns (face video, voice wav) ; plan restored."""
    import contextlib, io
    pf = PR.P(slug, "plan.json")
    orig = open(pf).read()
    try:
        plan = json.loads(orig)
        plan.update(overrides)
        plan.pop("base_video", None)
        open(pf, "w").write(json.dumps(plan, ensure_ascii=False, indent=1))
        with contextlib.redirect_stdout(io.StringIO()):
            PR.cmd_cut(slug); PR.cmd_base(slug)
        v, a = os.path.join(d, f"face-{tag}.mp4"), os.path.join(d, f"voice-{tag}.wav")
        shutil.copy(PR.P(slug, "work", "base-v.mp4"), v)
        mix(slug, a)
        return v, a
    finally:
        open(pf, "w").write(orig)
        with contextlib.redirect_stdout(io.StringIO()):
            PR.cmd_cut(slug); PR.cmd_base(slug)


def keyword_overlays(slug, words, look_name, d):
    """Renders the two keyword styles (HyperFrames, transparent WebM) on the strong words ; returns {style: (webm, start)}."""
    import prompteur_blocks as B
    plan = PR.load_plan(slug)
    look = json.load(open(os.path.join(HERE, "looks", look_name or plan.get("look", "_modele"), "look.json")))
    B.set_brand(look.get("brand"))
    pieces = PR.edl(slug)
    s = max(0.0, min(t for _, t, _ in words) - 0.15)
    e = max(t for _, t, _ in words) + 1.8
    rel = lambda a: max(0.0, PR.to_out(slug, PR.anchor(slug, a), pieces) - s)
    out = {}
    for style in ("simple", "gras"):
        wd = os.path.join(d, f"kw-{style}")
        os.makedirs(os.path.join(wd, "assets", "fonts"), exist_ok=True)
        shutil.copy(os.path.join(HERE, "assets", "gsap.min.js"), os.path.join(wd, "assets"))
        shutil.copy(os.path.join(HERE, "assets", "hyperframes.json"), os.path.join(wd, "hyperframes.json"))
        for f in B.fonts():
            shutil.copy(os.path.join(HERE, "assets", "fonts", f), os.path.join(wd, "assets", "fonts"))
        if style == "gras":
            ws = [[txt.upper(), anc] + (["acc"] if i == len(words) - 1 else []) for i, (txt, _, anc) in enumerate(words)]
        else:
            ws = [[txt, anc] for txt, _, anc in words]
        ins = {"id": f"kw-{style}", "kind": "keyword", "style": style, "words": ws}
        html, _ = B.build(ins, e - s, rel, PR.P(slug, "assets"))
        open(os.path.join(wd, "index.html"), "w").write(html)
        webm = os.path.join(d, f"kw-{style}.webm")
        r = subprocess.run(["npx", "--yes", PR.HF, "render", "--format", "webm", "--output", webm, "--quiet"], cwd=wd, capture_output=True, text=True)
        if r.returncode or not os.path.exists(webm):
            raise SystemExit(f"HyperFrames render failed : {r.stdout[-400:]} {r.stderr[-400:]}")
        out[style] = (webm, s)
    return out


def overlay(video, webm, start, dst):
    off = max(0.0, round(start * FPS) / FPS - 0.5 / FPS)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-c:v", "libvpx-vp9", "-i", webm, "-filter_complex",
                    f"[1:v]setpts=PTS-STARTPTS+{off:.4f}/TB[k];[0:v][k]overlay=0:0:eof_action=pass:format=auto,format=yuv420p[v]",
                    "-map", "[v]", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-r", "30", dst], check=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug"); ap.add_argument("kind", choices=["cadrages", "rythme", "zooms", "sons", "musique", "mots"])
    ap.add_argument("--words", help='strong words, comma separated anchors "MOT@12.3"')
    ap.add_argument("--tracks", help="musique : 2 or 3 files of assets/music, comma separated")
    ap.add_argument("--look")
    A = ap.parse_args()
    slug = A.slug
    W = PR.P(slug, "work")
    if not os.path.exists(os.path.join(W, "base-v.mp4")):
        raise SystemExit("cut the excerpt first : prompteur.py cut and base")
    d = os.path.join(W, f"choix-{A.kind}"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    plan = PR.load_plan(slug)
    two = len(plan.get("cameras", ["A"])) > 1
    words = strong_words(slug, [w.strip() for w in A.words.split(",")] if A.words else None)
    print("strong words :", ", ".join(f"{w} ({t:.2f} s)" for w, t, _ in words))
    cut_times = [p["out"][0] / FPS for p in PR.edl(slug)[1:]]
    variants = []  # (letter, what, video, audio)
    if A.kind == "cadrages":
        opts = ([("A", "un seul cadrage", {"framings": ["A", "B"], "zoom": {}}),
                 ("B", "large et serré", {"framings": ["A", "At", "B", "Bt"], "zoom": {"At": 1.25, "Bt": 1.25}}),
                 ("C", "large, serré, très serré", {"framings": ["A", "At", "Att", "B", "Bt", "Btt"], "zoom": {"At": 1.2, "Att": 1.5, "Bt": 1.2, "Btt": 1.5}})]
                if two else
                [("A", "un seul cadrage", {"framings": ["A"], "zoom": {}}),
                 ("B", "large et serré", {"framings": ["A", "At"], "zoom": {"At": 1.3}}),
                 ("C", "large, serré, très serré", {"framings": ["A", "At", "Att"], "zoom": {"At": 1.25, "Att": 1.6}})])
        for L, what, o in opts:
            print(f"  {L} values for the style (framing) : cycle {o['framings']}, zoom {o['zoom']}, first {o['framings'][0]}")
            o = dict(o, first_angle=o["framings"][0], max_shot=3.0, shot_target=2.5, min_shot=1.4, cam_hold=0.0)
            variants.append((L, what) + recut(slug, o, d, L))
    elif A.kind == "rythme":
        fr = plan.get("framings") if len(plan.get("framings") or []) > 1 else (["A", "At", "B", "Bt"] if two else ["A", "At"])
        zm = plan.get("zoom") or {"At": 1.25, "Bt": 1.25}
        opts = [("A", "coupes entre les phrases, pauses naturelles", {"max_shot": 1e9, "max_pause": 0.8, "pause_keep": 0.6}),
                ("B", "une coupe toutes les 4 s environ", {"max_shot": 5.0, "shot_target": 4.0, "min_shot": 2.0, "max_pause": 0.6, "pause_keep": 0.45}),
                ("C", "une coupe toutes les 2 s, pauses courtes", {"max_shot": 2.6, "shot_target": 2.0, "min_shot": 1.2, "max_pause": 0.45, "pause_keep": 0.3})]
        for L, what, o in opts:
            print(f"  {L} values for the style (cut) : {o}")
            o = dict(o, framings=fr, zoom=zm, first_angle=fr[0], cam_hold=0.0)
            variants.append((L, what) + recut(slug, o, d, L))
    elif A.kind == "zooms":
        voice = mix(slug, os.path.join(d, "voice.wav"))
        for L, what in (("A", "aucun zoom"), ("B", "zoom léger"), ("C", "zoom marqué sur le mot fort")):
            variants.append((L, what, zoom_track(slug, L, words, d), voice))
    else:
        video = os.path.join(W, "base-v.mp4")
        if A.kind == "sons":
            marked = [("click-soft.wav", t, -25) for t in cut_times] + [("whoosh-short.wav", 0.0, -24)] + \
                     [("pop.wav", t - 0.02, -21) for _, t, _ in words] + [("impact-bass-1.wav", words[0][1], -21)]
            variants = [("A", "aucun bruitage", video, mix(slug, os.path.join(d, "a.wav"))),
                        ("B", "bruitages doux", video, mix(slug, os.path.join(d, "b.wav"), [("click-soft.wav", t, -30) for t in cut_times])),
                        ("C", "bruitages marqués", video, mix(slug, os.path.join(d, "c.wav"), marked))]
        elif A.kind == "musique":
            mdir = os.path.join(HERE, "assets", "music")
            if A.tracks:
                tracks = [f"assets/music/{os.path.basename(t)}" for t in A.tracks.split(",")]
            else:
                cr = json.load(open(os.path.join(mdir, "CREDITS.json"))) if os.path.exists(os.path.join(mdir, "CREDITS.json")) else {}
                by_mood = {}
                for f, e in sorted(cr.items()):
                    if os.path.exists(os.path.join(mdir, f)):
                        by_mood.setdefault(e.get("mood", f), f)
                tracks = [f"assets/music/{f}" for f in list(by_mood.values())[:3]]
                if len(tracks) < 2:
                    tracks = [f"assets/music/{f}" for f in sorted(os.listdir(mdir)) if f.endswith((".mp3", ".wav", ".m4a"))][:3]
            if len(tracks) < 2:
                raise SystemExit("put at least 2 tracks in assets/music first (tools/musique.py get trio)")
            import musique
            for L, f in zip("ABC", tracks[:3]):
                off = musique.good_from(os.path.join(HERE, f))[0]
                variants.append((L, os.path.splitext(os.path.basename(f))[0].replace("-", " "), video, mix(slug, os.path.join(d, f"{L}.wav"), music=(f, off), under=16.0)))
        elif A.kind == "mots":
            voice = mix(slug, os.path.join(d, "voice.wav"))
            kw = keyword_overlays(slug, words, A.look, d)
            variants = [("A", "pas de mot à l'écran", video, voice),
                        ("B", "mots simples", overlay(video, *kw["simple"], os.path.join(d, "b.mp4")), voice),
                        ("C", "mots en gras", overlay(video, *kw["gras"], os.path.join(d, "c.mp4")), voice)]
    parts = []
    for L, what, v, a in variants:
        c = os.path.join(d, f"card-{L}.mp4"); card(L, c, what)
        lv = os.path.join(d, f"lab-{L}.mp4"); label(v, L, lv, a)
        parts += [c, lv]
    out = PR.P(slug, "renders", f"choix-{A.kind}.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    concat(parts, out)
    final = os.path.join(M.output_dir(), f"{slug}-choix-{A.kind}.mp4")
    shutil.copy(out, final)
    print("choice video :", final)
    for L, what, _, _ in variants:
        print(f"  {L} : {what}")


if __name__ == "__main__":
    main()
