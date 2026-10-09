"""Four zoom styles on the same face track, built as Premiere sequences, to choose a look inside Premiere itself.
  python3 premiere/zoom_variants.py <slug> [seconds=15]
Takes the first seconds of projects/<slug>/work/base-v.mp4 (after prompteur.py base), its cuts (assets/edl.json) and its
strong words (numbers, keywords, the look's accent_words), and adds four sequences zoom-A .. zoom-D to the open project :
  A hard punch-in on the strong word, held, back at the next cut
  B slow linear push through every shot (100 -> 108 %)
  C quick eased zoom on the strong word (100 -> 115 % in 0.27 s), held to the cut
  D every shot opens tight and pulls out (118 -> 100 % in 0.45 s)
The ffmpeg choice video (tools/choix.py zooms) shows the same four styles without Premiere."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prompteur as PR
from ppclient import PP
import ppbatch as PB

F = 1 / 30  # one frame


def ease(t0, dur, v0, v1, steps=6):
    """Cubic ease-out drawn with keys."""
    return [(t0 + dur * k / steps, v0 + (v1 - v0) * (1 - (1 - k / steps) ** 3)) for k in range(steps + 1)]


def keys(style, cuts, end, words):
    nxt = lambda t: min([c for c in cuts if c > t] + [end])
    k = []
    if style == "A":
        k.append((0.0, 100))
        for w in words:
            c = nxt(w)
            k += [(w - F, 100), (w, 118), (c - F, 118), (c, 100)]
    if style == "B":
        for a, b in zip(cuts, cuts[1:] + [end]):
            k += [(a, 100), (b - F, 108)]
    if style == "C":
        k.append((0.0, 100))
        for w in words:
            c = nxt(w)
            k += [(w - 0.05 - F, 100)] + ease(w - 0.05, 0.27, 100, 115) + [(c - F, 115), (c, 100)]
    if style == "D":
        for a, b in zip(cuts, cuts[1:] + [end]):
            k += ease(a, 0.45, 118, 100) + [(b - F, 100)]
    seen, out = set(), []
    for t, v in sorted(k):
        t = round(max(t, 0), 3)
        if t not in seen and t < end:
            seen.add(t); out.append((t, round(v, 2)))
    return out


def main(slug, secs=15.0):
    import re, subprocess
    W = PR.P(slug, "work")
    clip = os.path.join(W, f"zoom-choice-{int(secs)}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(W, "base-v.mp4"), "-t", str(secs), "-c", "copy", clip], check=True)
    cuts = sorted({p["out"][0] / 30 for p in PR.edl(slug) if p["out"][0] / 30 < secs} | {0.0})
    look = PR.load_look(PR.load_plan(slug)) or {}
    rx = re.compile(r"\d|^(" + look.get("zoom", {}).get("accent_words", "jamais|attention|important") + r")\b", re.I)
    pieces = PR.edl(slug)
    words = [PR.to_out(slug, w["start"], pieces) for w in PR.words(slug) if rx.search(w["text"].strip(" .,!?«»"))]
    words = [w for w in words if w < secs - 0.5][:6] or [secs / 3, 2 * secs / 3]
    pp = PP()
    item = pp("import_media", filePath=clip, binName="choix-zooms")
    item = item.get("data", item)
    iid = item.get("id") or item.get("projectItemId")
    seqs = {}
    for style in "ABCD":
        sid = pp("create_sequence_from_clips", projectItemIds=[iid], name=f"zoom-{style}")["data"]["sequenceId"]
        cid = pp("get_full_sequence_info", sequenceId=sid)["data"]["videoTracks"][0]["clips"][0]["nodeId"]
        PB.scale_keys(pp, sid, [(cid, keys(style, cuts, secs, words))])
        seqs[style] = sid
        print(style, sid)
    json.dump(seqs, open(os.path.join(W, "zoom-seqs.json"), "w"))
    pp.close()


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 15.0)
