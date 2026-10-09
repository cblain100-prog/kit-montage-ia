#!/usr/bin/env python3
"""A/B/C choice videos : the SAME sentence of the creator, edited several ways, one after the other, each labelled with
its letter. The creator answers with a letter (« la B, mais parfois la C ») and the answer goes into the look.

  python3 tools/choix.py <slug> zooms     A cuts only | B slow push / pull per shot | C B + eased punch-in on the strong word | D B + quick dezoom
  python3 tools/choix.py <slug> sons      A no sound effect | B soft (a light click on cuts) | C punchy (click, whoosh, pop, impact)
  python3 tools/choix.py <slug> musique [--tracks a.mp3,b.mp3,c.mp3]   one track per letter, 14 LU under the voice, ducked
  python3 tools/choix.py <slug> mots [--words "QUARANTAINE@23.6,UNE@23.5"]   A no keyword | B « chrome » (title font) | C kinetic Poppins
Options : --words  strong words as anchors "MOT@rush time" (default : numbers and long words of the sentence)
          --look   look whose brand colours are used (default plan.look)

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
    """The face track with one zoom style drawn on it (same renderer as the look)."""
    W = PR.P(slug, "work")
    base = os.path.join(W, "base-v.mp4")
    n = frames(base)
    end = n / FPS
    cuts_f = sorted({p["out"][0] for p in PR.edl(slug) if p["out"][0] < n} | {0})
    cuts = [c / FPS for c in cuts_f]
    shots = list(zip(cuts, cuts[1:] + [end]))
    F = 1 / FPS
    keys = []
    for k, (a, b) in enumerate(shots):
        f0, f1 = (108, 100) if k % 2 else (100, 108)
        w = next((t for _, t, _ in words if a + 0.2 <= t < b - 0.4), None)
        if style == "A":
            keys += [(a, 100), (b - F, 100)]
        elif style == "B" or w is None:
            keys += [(a, f0), (b - F, f1)]
        elif style == "C":
            v0 = f0 + (f1 - f0) * (w - 0.05 - a) / (b - a)
            keys += [(a, f0), (w - 0.05 - F, v0)] + ease(w - 0.05, 0.27, v0, v0 + 12) + [(b - F, v0 + 12)]
        elif style == "D":
            keys += ease(a, 0.45, 118, 100) + [(b - F, 103)]
    seen, out = set(), []
    for t, v in sorted(keys):
        t = round(max(t, 0), 3)
        if t not in seen and t < end:
            seen.add(t); out.append((t, round(v, 2)))
    dst = os.path.join(d, f"zoom-{style}.mp4")
    render_keys(base, out, cuts_f, n, os.path.join(d, f"ff-{style}"), dst)
    return dst


def keyword_overlays(slug, words, look_name, d):
    """Renders the two keyword styles (HyperFrames, transparent WebM) on the strong words ; returns {style: (webm, start)}."""
    import prompteur_blocks as B
    plan = PR.load_plan(slug)
    look = json.load(open(os.path.join(HERE, "looks", look_name or plan.get("look", "exemple"), "look.json")))
    B.set_brand(look.get("brand"))
    pieces = PR.edl(slug)
    s = max(0.0, min(t for _, t, _ in words) - 0.15)
    e = max(t for _, t, _ in words) + 1.8
    rel = lambda a: max(0.0, PR.to_out(slug, PR.anchor(slug, a), pieces) - s)
    out = {}
    for style in ("chrome", "kinetic"):
        wd = os.path.join(d, f"kw-{style}")
        os.makedirs(os.path.join(wd, "assets", "fonts"), exist_ok=True)
        shutil.copy(os.path.join(HERE, "assets", "gsap.min.js"), os.path.join(wd, "assets"))
        shutil.copy(os.path.join(HERE, "assets", "hyperframes.json"), os.path.join(wd, "hyperframes.json"))
        for f in B.fonts():
            shutil.copy(os.path.join(HERE, "assets", "fonts", f), os.path.join(wd, "assets", "fonts"))
        ws = [[txt.upper(), anc] + (["acc"] if i == len(words) - 1 and style == "chrome" else []) for i, (txt, _, anc) in enumerate(words)]
        if style == "kinetic":
            ws[-1] = ws[-1][:2] + [B.OR]
        ins = {"id": f"kw-{style}", "kind": "keyword", "style": "chrome" if style == "chrome" else "kinetic", "words": ws}
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
    ap.add_argument("slug"); ap.add_argument("kind", choices=["zooms", "sons", "musique", "mots"])
    ap.add_argument("--words", help='strong words, comma separated anchors "MOT@12.3"')
    ap.add_argument("--tracks", help="musique : 2 or 3 files of assets/music, comma separated")
    ap.add_argument("--look")
    A = ap.parse_args()
    slug = A.slug
    W = PR.P(slug, "work")
    if not os.path.exists(os.path.join(W, "base-v.mp4")):
        raise SystemExit("cut the excerpt first : prompteur.py cut and base")
    d = os.path.join(W, f"choix-{A.kind}"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    words = strong_words(slug, [w.strip() for w in A.words.split(",")] if A.words else None)
    print("strong words :", ", ".join(f"{w} ({t:.2f} s)" for w, t, _ in words))
    cut_times = [p["out"][0] / FPS for p in PR.edl(slug)[1:]]
    variants = []  # (letter, what, video, audio)
    if A.kind == "zooms":
        voice = mix(slug, os.path.join(d, "voice.wav"))
        for L, what in (("A", "coupes seules"), ("B", "poussée lente"), ("C", "zoom amorti sur le mot fort"), ("D", "dézoom rapide")):
            variants.append((L, what, zoom_track(slug, L, words, d), voice))
    else:
        video = zoom_track(slug, "B", words, d)
        if A.kind == "sons":
            punchy = [("click-soft.wav", t, -24) for t in cut_times] + [("whoosh-short.wav", 0.0, -22)] + \
                     [("pop.wav", t - 0.02, -20) for _, t, _ in words] + [("impact-bass-1.wav", words[0][1], -20)]
            variants = [("A", "aucun bruitage", video, mix(slug, os.path.join(d, "a.wav"))),
                        ("B", "doux", video, mix(slug, os.path.join(d, "b.wav"), [("click-soft.wav", t, -30) for t in cut_times])),
                        ("C", "punchy", video, mix(slug, os.path.join(d, "c.wav"), punchy))]
        elif A.kind == "musique":
            plan = PR.load_plan(slug)
            look = json.load(open(os.path.join(HERE, "looks", A.look or plan.get("look", "exemple"), "look.json")))
            if A.tracks:
                tracks = [(f"assets/music/{os.path.basename(t)}", 0) for t in A.tracks.split(",")]
            else:
                tracks = [(p["file"], p.get("good_from", [0])[0]) for p in look.get("music", {}).get("palette", [])]
                if len(tracks) < 2:
                    tracks = [(f"assets/music/{f}", 0) for f in sorted(os.listdir(os.path.join(HERE, "assets", "music"))) if f.endswith((".mp3", ".wav", ".m4a"))]
            if len(tracks) < 2:
                raise SystemExit("put at least 2 tracks in assets/music first (tools/musique.py get sombre)")
            for L, (f, off) in zip("ABC", tracks[:3]):
                variants.append((L, os.path.splitext(os.path.basename(f))[0].replace("-", " "), video, mix(slug, os.path.join(d, f"{L}.wav"), music=(f, off))))
        elif A.kind == "mots":
            voice = mix(slug, os.path.join(d, "voice.wav"), [("whoosh-short.wav", words[0][1] - 0.1, -26)])
            kw = keyword_overlays(slug, words, A.look, d)
            variants = [("A", "pas de mot à l'écran", video, voice),
                        ("B", "mots chromés", overlay(video, *kw["chrome"], os.path.join(d, "b.mp4")), voice),
                        ("C", "mots cinétiques", overlay(video, *kw["kinetic"], os.path.join(d, "c.mp4")), voice)]
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
