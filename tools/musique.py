#!/usr/bin/env python3
"""Music for the kit : no track is shipped in the repo (licences), this tool fetches free ones and registers them.

  python3 tools/musique.py list                         catalogue + what is already in assets/music
  python3 tools/musique.py get sombre|electro|leger|<id> ...   download Kevin MacLeod tracks (CC BY 4.0) into assets/music
  python3 tools/musique.py add <file.mp3> --credit "..."       copy one of your own tracks (Mixkit, Pixabay, bought...)
  python3 tools/musique.py palette <look> <file> [<file> ...]  put these tracks in looks/<look>/look.json (music.palette)

Every track keeps its credit line in assets/music/CREDITS.json ; the montage skill prints the credits to paste in the
YouTube description. Kevin MacLeod's music is free on condition of that credit (CC BY 4.0). Mixkit and Pixabay tracks
need no credit, but read their licence page (a few Pixabay tracks are claimed by Content ID : test before publishing)."""
import json, os, re, subprocess, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HERE, "assets", "music")
CREDITS = os.path.join(DIR, "CREDITS.json")
KM = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/{}.mp3"
CC = '"{t}" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/'

# mood is a first guess : listen before choosing (the style skill builds a choice video for that)
CATALOGUE = {
    "sombre": ["Stormfront", "Lightless Dawn", "Hypnothis", "Long Note Four", "Darkest Child", "Dark Fog", "Deliberate Thought", "Investigations"],
    "electro": ["Voxel Revolution", "Cyborg Ninja", "Bit Shift", "Digital Lemonade", "Electrodoodle", "Chill Wave"],
    "leger": ["Cool Vibes", "Funk Game Loop", "Pamgaea", "Dreamer", "Inspired", "Local Forecast - Elevator"],
}


def slug(t):
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def credits():
    return json.load(open(CREDITS)) if os.path.exists(CREDITS) else {}


def save_credits(c):
    os.makedirs(DIR, exist_ok=True)
    json.dump(c, open(CREDITS, "w"), ensure_ascii=False, indent=1)


def duration(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                capture_output=True, text=True).stdout or 0)


def good_from(f):
    """Start offsets worth using : where the track reaches its body (within 3 dB of its median level), and later on."""
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-ac", "1", "-ar", "8000", "-f", "f32le", "-"], capture_output=True)
    x = np.frombuffer(r.stdout, np.float32)
    if not len(x):
        return [0]
    h = 8000
    n = len(x) // h
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)
    med = np.median(db)
    first = next((i for i, v in enumerate(db) if v > med - 3), 0)
    out = [int(first)]
    if n > 90:
        out.append(int(first + (n - first) * 0.4))
    return out


def cmd_list():
    have = credits()
    for mood, ts in CATALOGUE.items():
        print(f"{mood} :")
        for t in ts:
            print(f"  {'[ok] ' if slug(t) + '.mp3' in have else '     '}{slug(t):28s} {t}")
    mine = [f for f in have if not any(slug(t) + ".mp3" == f for ts in CATALOGUE.values() for t in ts)]
    if mine:
        print("ajoutés à la main :", ", ".join(mine))


def cmd_get(names):
    want = []
    for n in names:
        if n in CATALOGUE:
            want += CATALOGUE[n]
        else:
            t = next((t for ts in CATALOGUE.values() for t in ts if slug(t) == slug(n)), None)
            if not t:
                raise SystemExit(f"unknown track : {n} (see `list`)")
            want.append(t)
    c = credits()
    os.makedirs(DIR, exist_ok=True)
    for t in want:
        f = os.path.join(DIR, slug(t) + ".mp3")
        if not os.path.exists(f):
            req = urllib.request.Request(KM.format(urllib.parse.quote(t)), headers={"User-Agent": "kit-montage-ia"})
            with urllib.request.urlopen(req, timeout=60) as r, open(f + ".part", "wb") as o:
                o.write(r.read())
            os.replace(f + ".part", f)
        c[os.path.basename(f)] = {"name": f"{t}, Kevin MacLeod", "credit": CC.format(t=t), "licence": "CC BY 4.0",
                                  "source": "https://incompetech.com", "duration": round(duration(f), 1)}
        print(f"ok  {os.path.basename(f)}  ({c[os.path.basename(f)]['duration']} s)")
    save_credits(c)


def cmd_add(path, credit=None, name=None):
    import shutil
    os.makedirs(DIR, exist_ok=True)
    dst = os.path.join(DIR, slug(os.path.splitext(os.path.basename(path))[0]) + os.path.splitext(path)[1].lower())
    shutil.copy2(os.path.expanduser(path), dst)
    c = credits()
    c[os.path.basename(dst)] = {"name": name or os.path.splitext(os.path.basename(path))[0], "credit": credit, "licence": "to check" if not credit else "credit",
                                "duration": round(duration(dst), 1)}
    save_credits(c)
    print("ok", dst)


def cmd_palette(look, files):
    lf = os.path.join(HERE, "looks", look, "look.json")
    L = json.load(open(lf))
    c = credits()
    pal = []
    for f in files:
        b = os.path.basename(f)
        p = os.path.join(DIR, b)
        if not os.path.exists(p):
            raise SystemExit(f"not in assets/music : {b}")
        e = c.get(b, {})
        pal.append({"file": f"assets/music/{b}", "name": e.get("name", b), "good_from": good_from(p), "credit": e.get("credit")})
    L.setdefault("music", {})["palette"] = pal
    json.dump(L, open(lf, "w"), ensure_ascii=False, indent=2)
    for p in pal:
        print(f"palette : {p['name']}  from {p['good_from']} s")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "list":
        cmd_list()
    elif a[0] == "get":
        cmd_get(a[1:])
    elif a[0] == "add":
        opt = dict(zip(a[2::2], a[3::2]))
        cmd_add(a[1], opt.get("--credit"), opt.get("--name"))
    elif a[0] == "palette":
        cmd_palette(a[1], a[2:])
    else:
        print(__doc__)
