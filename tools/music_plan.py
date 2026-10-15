#!/usr/bin/env python3
"""Writes plan.music from the creator's look (looks/<look>/look.json, music section). Only what the creator chose is used :
  - palette   : the tracks they picked (empty = no music, plan.music removed) ;
  - intro / body under_lu : how far under the voice the music sits (required as soon as there is a palette) ;
  - change_on_chapter : a new track on each chapter card (inserts marked "chapter": true), with a fade before the card ;
  - intro.open {riser, impact, start_hit} : an opening hook (needs --open-stop and --open-back) ;
  - intro.close (a sound file) : the end of the intro (needs --close) ;
  - outro {fade} : the music fades out on the conclusion (needs --outro), none under the call to action.
  python3 tools/music_plan.py <slug> [--open-stop "mot@37.30" --open-back "mot@39.90"] [--close "src:115.2"] [--cut "mot@72.38" ...] [--outro "mot@612.4"]
Anchors are rush words (« mot@123.4 ») or « src:123.4 », so later cut changes never move the music. Check by ear after."""
import argparse, itertools, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import prompteur as PR

ap = argparse.ArgumentParser()
ap.add_argument("slug"); ap.add_argument("--open-stop"); ap.add_argument("--open-back")
ap.add_argument("--close", help="end of the intro : the look's closing sound ends here")
ap.add_argument("--after-close", help="where the 2nd track enters (default : the first chapter card)")
ap.add_argument("--cut", action="append", default=[], help="a strong sentence : the music stops 0.35 s before it (needs intro.open.impact)")
ap.add_argument("--switch", help="one change of track (2nd track of the palette, 1.5 s fade before), e.g. where the steps start ; for a style without change_on_chapter")
ap.add_argument("--outro", help="the conclusion : the music fades out there, then no music under the call to action")
ap.add_argument("--look", help="default : plan.look")
A = ap.parse_args()

plan = PR.load_plan(A.slug)
look = json.load(open(os.path.join(HERE, "looks", A.look or plan.get("look", "_modele"), "look.json")))
mu = look.get("music") or {}
pal = [p for p in mu.get("palette", []) if os.path.exists(os.path.join(HERE, p["file"]))]
if not pal:
    plan.pop("music", None)
    json.dump(plan, open(PR.P(A.slug, "plan.json"), "w"), indent=2, ensure_ascii=False)
    raise SystemExit("no music in the style's palette (or the files are missing) : the video is made without music")
intro, body = mu.get("intro") or {}, mu.get("body") or {}
if intro.get("under_lu") is None and body.get("under_lu") is None:
    raise SystemExit("the style has tracks but no level (music.intro.under_lu / music.body.under_lu) : finish the style with the create-style skill")
lu_intro = intro.get("under_lu", body.get("under_lu"))
lu_body = body.get("under_lu", lu_intro)
times = json.load(open(PR.P(A.slug, "work", "insert-times.json")))
t_close = PR.to_out(A.slug, PR.anchor(A.slug, A.close)) if A.close else 0.0
cards = [i["id"] for i in plan["inserts"] if i.get("chapter") and i["id"] in times and times[i["id"]][0] > t_close] if mu.get("change_on_chapter") else []
offs = {p["file"]: itertools.cycle(p.get("good_from") or [0]) for p in pal}
order = itertools.cycle(range(len(pal)))
segs, last = [], None


def pick():
    global last
    for _ in range(len(pal)):
        k = next(order)
        if k != last or len(pal) == 1:
            last = k
            p = pal[k]
            return p["file"], next(offs[p["file"]])


f, o = pick()
# with an opening mark (a snap of the fingers...), nothing plays before it : the raw part stays raw (Colin 2026-10-13)
segs.append({"file": f, "at": A.open_back or 0, "offset": o, "under_db": lu_intro})
if A.after_close and mu.get("change_on_chapter"):
    f, o = pick(); segs.append({"file": f, "at": A.after_close, "offset": o, "under_db": lu_body})
elif A.close and lu_body != lu_intro:  # same track, its own level after the intro
    segs.append({"file": f, "at": A.close, "offset": o, "under_db": lu_body})
for c in cards:
    f, o = pick(); segs.append({"file": f, "at": f"ins:{c}", "offset": o, "under_db": lu_body})
if A.switch:  # Colin 2026-10-14 : a calmer track from « je t'explique ça en quatre étapes », lower, to the end
    f, o = pick(); segs.append({"file": f, "at": A.switch, "offset": o, "under_db": lu_body})
op = intro.get("open") or {}
outro = mu.get("outro") or {}
plan["music"] = {
    "segments": segs,
    "cuts": ([[c, -0.35, op.get("impact")] for c in A.cut] if op else [])
            + [[f"ins:{c}", -1.5, None, "fade"] for c in cards]
            + ([[A.switch, -1.5, None, "fade"]] if A.switch else [])
            + ([[A.outro, outro.get("fade", 2.0), None, "fade", "end"]] if A.outro and outro else []),
    "stops": [], "duck_ratio": 1.6, "duck_release": 700, "fade_out": 2.5}
if op and A.open_stop and A.open_back:
    plan["music"]["open"] = {"stop": A.open_stop, "back": A.open_back, "riser": op.get("riser"), "impact": op.get("impact"), "start_hit": op.get("start_hit", False)}
if intro.get("close") and A.close:
    plan["music"]["close"] = {"at": A.close, "sound": intro["close"]}
json.dump(plan, open(PR.P(A.slug, "plan.json"), "w"), indent=2, ensure_ascii=False)
print(f"music : {len(segs)} segment(s), {len(cards)} chapter change(s), opening hook {'yes' if 'open' in plan['music'] else 'no'}, "
      f"intro end {'yes' if 'close' in plan['music'] else 'no'}, outro {'yes' if A.outro and outro else 'no'}")
credits = sorted({p["credit"] for p in pal if p.get("credit") and any(g["file"] == p["file"] for g in segs)})
if credits:
    print("credits for the description :\n  " + "\n  ".join(credits))
