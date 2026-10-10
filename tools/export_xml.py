#!/usr/bin/env python3
"""Plan B when Premiere's bridge is down : the whole edit as a Final Cut Pro 7 XML file (« xmeml ») that Premiere imports
(Fichier > Importer, then double-click the new sequence) to give an EDITABLE Premiere project, without the connector.

  python3 tools/export_xml.py <slug> <name> [--no-check]   -> projects/<slug>/renders/<name>.xml (+ copy in the output folder)

Same tracks as premiere/build_timeline.py :
  V1 face pieces (framings already cropped) with the style's zooms as Basic Motion > Scale keyframes
  V2 full-screen inserts, V3+ overlays (ProRes 4444 with alpha, made by build_timeline.prepare)
  A1 voice, A2 music (one clip per kept span, ducking under the voice as Level keyframes), A3+ one clip per sound effect
The file is then read back with OpenTimelineIO (Apache-2.0, fcp_xml adapter) : same number of clips per track and same
duration, or the script stops. Each face piece is its own file starting at 0, so keyframe times are the same in the clip
and in its source (the FCP 7 XML convention is ambiguous there). Known limit : Premiere may drop motion keyframes on
some XML imports (reported on Adobe's forum) ; if the zooms are missing after import, the ffmpeg render still has them."""
import argparse, json, os, shutil, subprocess, sys
import xml.etree.ElementTree as ET
from urllib.parse import quote
import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "premiere"))
import montage as M
import prompteur as PR

FPS, SR = 30, 48000
_ids = {}


def dur_of(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True, text=True).stdout)


def sub(parent, tag, text=None, **attrib):
    e = ET.SubElement(parent, tag, attrib)
    if text is not None:
        e.text = str(text)
    return e


def rate(parent):
    r = sub(parent, "rate")
    sub(r, "timebase", FPS); sub(r, "ntsc", "FALSE")
    return r


def file_el(parent, path, kind):
    """<file> once with its full description, then by reference (FCP 7 XML rule)."""
    path = os.path.abspath(path)
    if path in _ids:
        return sub(parent, "file", id=_ids[path])
    fid = f"file-{len(_ids) + 1}"
    _ids[path] = fid
    f = sub(parent, "file", id=fid)
    sub(f, "name", os.path.basename(path))
    sub(f, "pathurl", "file://" + quote(path))
    rate(f)
    sub(f, "duration", round(dur_of(path) * FPS))
    media = sub(f, "media")
    if kind == "video":
        sc = sub(sub(media, "video"), "samplecharacteristics")
        sub(sc, "width", 1920); sub(sc, "height", 1080)
    else:
        sc = sub(sub(media, "audio"), "samplecharacteristics")
        sub(sc, "depth", 16); sub(sc, "samplerate", SR)
    return f


def clipitem(track, path, kind, start, length, src_in=0, name=None):
    n = len(track.findall("clipitem")) + 1
    c = sub(track, "clipitem", id=f"{kind}-{id(track) % 10000}-{n}")
    sub(c, "name", name or os.path.basename(path))
    sub(c, "duration", round(dur_of(path) * FPS))
    rate(c)
    sub(c, "start", start); sub(c, "end", start + length)
    sub(c, "in", src_in); sub(c, "out", src_in + length)
    file_el(c, path, kind)
    if kind == "audio":
        st = sub(c, "sourcetrack")
        sub(st, "mediatype", "audio"); sub(st, "trackindex", 1)
    return c


def scale_filter(c, keys):
    """Basic Motion > Scale keyframes [(frame in the clip, percent)]."""
    e = sub(sub(c, "filter"), "effect")
    sub(e, "name", "Basic Motion"); sub(e, "effectid", "basic"); sub(e, "effectcategory", "motion")
    sub(e, "effecttype", "motion"); sub(e, "mediatype", "video")
    p = sub(e, "parameter", authoringApp="PremierePro")
    sub(p, "parameterid", "scale"); sub(p, "name", "Scale"); sub(p, "valuemin", 0); sub(p, "valuemax", 1000)
    sub(p, "value", keys[0][1] if keys else 100)
    for fr, v in keys:
        k = sub(p, "keyframe"); sub(k, "when", fr); sub(k, "value", round(v, 2))


def level_filter(c, db, keys=None):
    """Audio Levels : linear gain (1.0 = 0 dB), optional keyframes [(frame in the clip, dB)]."""
    e = sub(sub(c, "filter"), "effect")
    sub(e, "name", "Audio Levels"); sub(e, "effectid", "audiolevels"); sub(e, "effectcategory", "audiolevels")
    sub(e, "effecttype", "audiolevels"); sub(e, "mediatype", "audio")
    p = sub(e, "parameter", authoringApp="PremierePro")
    sub(p, "parameterid", "level"); sub(p, "name", "Level"); sub(p, "valuemin", 0); sub(p, "valuemax", 3.98109)
    sub(p, "value", round(min(10 ** (db / 20), 3.98109), 5))
    for fr, d in keys or []:
        k = sub(p, "keyframe"); sub(k, "when", fr); sub(k, "value", round(min(10 ** (d / 20), 3.98109), 5))


def lanes(items):
    ends, out = [], []
    for it in items:
        k = next((i for i, e in enumerate(ends) if e <= it[0]), None)
        if k is None:
            ends.append(0); k = len(ends) - 1
        ends[k] = it[1]; out.append(k)
    return out


def build(slug, name):
    import build_timeline as BT
    import apply_look as AL
    W = PR.P(slug, "work")
    plan = PR.load_plan(slug)
    times = json.load(open(f"{W}/insert-times.json"))
    plan["inserts"] = [i for i in plan["inserts"] if i["id"] in times]
    pieces = PR.edl(slug)
    files = [l.split("'")[1] for l in open(f"{W}/pieces.txt") if l.strip()]
    dur = len(__import__("soundfile").read(f"{W}/base.wav")[0]) / SR
    n_total = round(dur * FPS)
    BT.prepare(W)
    root = ET.Element("xmeml", version="4")
    seq = sub(root, "sequence", id="sequence-1")
    sub(seq, "name", name); sub(seq, "duration", n_total); rate(seq)
    media = sub(seq, "media")
    video, audio = sub(media, "video"), sub(media, "audio")
    fmt = sub(sub(video, "format"), "samplecharacteristics")
    rate(fmt); sub(fmt, "width", 1920); sub(fmt, "height", 1080); sub(fmt, "pixelaspectratio", "square")
    expected = {}
    # V1 face pieces + zooms
    keys, _ = AL.plan_keys(slug, dur)
    kt, kv = np.array([k[0] for k in keys] or [0.0]), np.array([k[1] for k in keys] or [100.0])
    v1 = sub(video, "track")
    for p, f in zip(pieces, files):
        a, b = p["out"]
        if a >= n_total:
            continue
        b = min(b, n_total)
        c = clipitem(v1, f, "video", a, b - a, name=f"plan {p['angle']}")
        s, e = a / FPS, b / FPS
        pts = sorted({s, e - 1 / FPS} | {t for t in kt if s <= t < e})
        ks = sorted({round((t - s) * FPS): float(np.interp(t, kt, kv)) for t in pts}.items())  # one key per frame
        if any(abs(v - 100) > 0.01 for _, v in ks):
            scale_filter(c, ks)
    expected["video"] = [len(v1)]
    # V2 full-screen inserts, V3+ overlays
    full, over = [], []
    for ins in plan["inserts"]:
        s, e = times[ins["id"]][:2]
        if s >= dur:
            continue
        a = round(s * FPS)
        if PR.overlay_kind(ins):
            f = f"{W}/ins-pp/{ins['id']}.mov"; over.append((a, a + round(dur_of(f) * FPS), f, ins["id"]))
        else:
            f = f"{W}/ins/{ins['id']}.mp4"; full.append((a, a + round(dur_of(f) * FPS), f, ins["id"]))
    v2 = sub(video, "track")
    for a, b, f, i in full:
        clipitem(v2, f, "video", a, min(b, n_total) - a, name=i)
    over.sort()
    ol = lanes(over)
    otracks = [sub(video, "track") for _ in range(max(ol) + 1 if ol else 0)]
    for (a, b, f, i), k in zip(over, ol):
        clipitem(otracks[k], f, "video", a, min(b, n_total) - a, name=i)
    # A1 voice
    a1 = sub(audio, "track")
    level_filter(clipitem(a1, f"{W}/base.wav", "audio", 0, n_total, name="voix"), 0)
    # A2 music (ducked) + hooks, A3+ sound effects
    mclips, hooks = BT.music_plan(slug, plan, dur) if (plan.get("music") or {}).get("segments") else ([], [])
    a2 = sub(audio, "track")
    if mclips:
        duck = BT.duck_curve(slug, plan)
        for f, si, so, st, g in mclips:
            a = round(st * FPS); n = round((so - si) * FPS)
            ks = [(round(x * FPS), g + duck[min(int((st + x) * 10), len(duck) - 1)]) for x in np.arange(0, so - si, 0.5)]
            level_filter(clipitem(a2, f, "audio", a, n, src_in=round(si * FPS), name="musique"), g, ks)
    cues = sorted((c for c in PR.sfx_cues(slug, plan, times, dur) if c[1] < dur), key=lambda c: c[1])
    snd = sorted([(round(t * FPS), round(t * FPS) + max(1, round(dur_of(PR.sfx_file(f)) * FPS)), f, db) for f, t, db in cues + [h for h in hooks if PR.sfx_file(h[0])]])
    sl = lanes(snd)
    stracks = [sub(audio, "track") for _ in range(max(sl) + 1 if sl else 0)]
    for (a, b, f, db), k in zip(snd, sl):
        level_filter(clipitem(stracks[k], PR.sfx_file(f), "audio", a, min(b, n_total) - a, name=f), db)
    out = PR.P(slug, "renders", f"{name}.xml")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ET.indent(root)
    with open(out, "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        fh.write(ET.tostring(root, encoding="utf-8"))
    counts = {"video": [len(t.findall("clipitem")) for t in video.findall("track")],
              "audio": [len(t.findall("clipitem")) for t in audio.findall("track")]}
    return out, counts, n_total


def check(path, counts, n_total):
    """Reads the file back with OpenTimelineIO (fcp_xml adapter) and compares clips per track and duration."""
    import opentimelineio as otio
    tl = otio.adapters.read_from_file(path, adapter_name="fcp_xml")
    tl = tl if isinstance(tl, otio.schema.Timeline) else next(iter(tl))
    got = {"video": [len(list(t.find_clips())) for t in tl.video_tracks()],
           "audio": [len(list(t.find_clips())) for t in tl.audio_tracks()]}
    d = round(tl.duration().to_frames())
    if got != counts or abs(d - n_total) > 1:
        raise SystemExit(f"XML check failed : written {counts}, {n_total} frames ; read back {got}, {d} frames")
    return got, d


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("slug"); ap.add_argument("name"); ap.add_argument("--no-check", action="store_true")
    A = ap.parse_args()
    out, counts, n = build(A.slug, A.name)
    if not A.no_check:
        got, d = check(out, counts, n)
        print(f"checked with OpenTimelineIO : video {got['video']}, audio {got['audio']} clips per track, {d / FPS:.2f} s")
    dst = os.path.join(M.output_dir(), os.path.basename(out))
    shutil.copy(out, dst)
    print(f"timeline XML : {dst}\n  Premiere : Fichier > Importer, choisis ce fichier, puis double-clique la séquence « {A.name} ».")


if __name__ == "__main__":
    main()
