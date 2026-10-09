#!/usr/bin/env python3
"""Writes plan.music from the project's look (looks/<look>/look.json, music section) :
  - intro : first palette track, 14 LU under the voice, opening hook (low hit on frame 1, riser -> silence under the shock
    sentence -> impact), hard cut + impact before strong sentences you list, closing reverse cymbal at the end of the intro ;
  - body : a NEW track on every chapter card (diamonds inserts), never the same twice in a row, each from a different
    « good_from » offset, 18 LU under the voice, 1 s hard cut before the card and an impact on it ;
  - music to the very end, 2.5 s fade out, no stop under the call to action.
  python3 tools/music_plan.py <slug> [--open-stop "trop@37.30" --open-back "C'est@39.90"] [--close "src:115.2"] [--cut "Moi@72.38" ...] [--outro "Alors@612.4"]
  (without --open-* : no opening hook ; without --close : the intro track runs until the first chapter card)
Anchors are rush words (« mot@123.4 ») or « src:123.4 », so later cut changes never move the music. Check by ear after."""
import argparse, itertools, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import prompteur as PR

ap = argparse.ArgumentParser()
ap.add_argument("slug"); ap.add_argument("--open-stop"); ap.add_argument("--open-back")
ap.add_argument("--close", help="end of the intro : the reverse cymbal swells up to here, then voice alone")
ap.add_argument("--after-close", help="where the 2nd track enters (default : the first chapter card)")
ap.add_argument("--cut", action="append", default=[], help="a strong sentence : 0.35 s of silence before it, impact on it")
ap.add_argument("--outro", help="the conclusion (« Alors voilà, j'espère que cette vidéo vous a plu ») : the music fades out over 2 s there, then no music under the call to action")
ap.add_argument("--look", help="default : plan.look")
A = ap.parse_args()

plan = PR.load_plan(A.slug)
look = json.load(open(os.path.join(HERE, "looks", A.look or plan.get("look", "exemple"), "look.json")))
mu = look["music"]
pal = [p for p in mu.get("palette", []) if os.path.exists(os.path.join(HERE, p["file"]))]
if not pal:
    plan.pop("music", None)
    json.dump(plan, open(PR.P(A.slug, "plan.json"), "w"), indent=2, ensure_ascii=False)
    raise SystemExit("no music in the look's palette (or the files are missing) : run tools/musique.py, the video is made without music")
times = json.load(open(PR.P(A.slug, "work", "insert-times.json")))
t_close = PR.to_out(A.slug, PR.anchor(A.slug, A.close)) if A.close else 0.0
# chapter cards after the intro only (the intro's « 7 techniques » card is diamonds too)
# a chapter card is a diamonds insert, or any insert flagged "chapter": true (scene-made cards, v1 2026-10-04)
cards = [i["id"] for i in plan["inserts"] if (i.get("kind") == "diamonds" or i.get("chapter")) and i["id"] in times and times[i["id"]][0] > t_close]
offs = {p["file"]: itertools.cycle(p["good_from"]) for p in pal}
order = itertools.cycle(range(len(pal)))
segs, last = [], None


def pick():
    global last
    for _ in range(len(pal)):
        k = next(order)
        if k != last:
            last = k
            p = pal[k]
            return p["file"], next(offs[p["file"]])


f, o = pick()
segs.append({"file": f, "at": 0, "offset": o, "under_db": mu["intro"].get("under_lu", 14)})
if A.after_close:
    f, o = pick(); segs.append({"file": f, "at": A.after_close, "offset": o, "under_db": mu["body"].get("under_lu", 18)})
for c in cards:
    f, o = pick(); segs.append({"file": f, "at": f"ins:{c}", "offset": o, "under_db": mu["body"].get("under_lu", 18)})
op = mu["intro"]["open"]
plan["music"] = {
    "segments": segs,
    "cuts": [[c, -0.35, op["impact"]] for c in A.cut] + [[f"ins:{c}", -1.5, "hook-impact-2.wav", "fade"] for c in cards]
            + ([[A.outro, mu.get("outro", {}).get("fade", 2.0), None, "fade", "end"]] if A.outro else []),
    "stops": [], "duck_ratio": 1.6, "duck_release": 700, "fade_out": 2.5}
if A.open_stop and A.open_back:
    plan["music"]["open"] = {"stop": A.open_stop, "back": A.open_back, "riser": op["riser"], "impact": op["impact"], "start_hit": op.get("start_hit", True)}
if A.close:
    plan["music"]["close"] = {"at": A.close, "sound": mu["intro"]["close"]}
json.dump(plan, open(PR.P(A.slug, "plan.json"), "w"), indent=2, ensure_ascii=False)
print(f"music : {len(segs)} tracks ({len(cards)} chapter cards), open hook {'yes' if A.open_stop else 'no'}, {len(A.cut)} cuts in the intro, close at {A.close}")
credits = sorted({p["credit"] for p in pal if p.get("credit") and any(g["file"] == p["file"] for g in segs)})
if credits:
    print("credits for the description :\n  " + "\n  ".join(credits))
