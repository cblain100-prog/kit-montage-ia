#!/usr/bin/env python3
"""Core helpers shared by the kit (paths, config, shell, JSON).

Everything is relative to the kit folder (the folder of this file). Personal settings live in `kit.config.json`
(optional, git-ignored), for example:

  {"output_dir": "~/Movies/montages", "premiere_projects": "projects"}

  output_dir         where finished videos are copied (default ~/Downloads)
  premiere_projects  "projects" (default: each version's .prproj sits in projects/<slug>/premiere/) or an absolute folder
  browser            app used to open the studio page (default: the system default browser)
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 30


def config():
    f = os.path.join(HERE, "kit.config.json")
    cfg = json.load(open(f)) if os.path.exists(f) else {}
    return {"output_dir": os.path.expanduser(cfg.get("output_dir", "~/Downloads")),
            "premiere_projects": cfg.get("premiere_projects", "projects"),
            "browser": cfg.get("browser")}


def personal_looks():
    """The creator's styles : every folder of looks/ except the empty model (_modele)."""
    d = os.path.join(HERE, "looks")
    return sorted(x for x in os.listdir(d) if not x.startswith("_") and os.path.exists(os.path.join(d, x, "look.json")))


def output_dir():
    d = config()["output_dir"]
    os.makedirs(d, exist_ok=True)
    return d


def P(slug, *parts):
    return os.path.join(HERE, "projects", slug, *parts)


def python():
    """The kit's own Python (.venv) when it exists, else the one running."""
    v = os.path.join(HERE, ".venv", "bin", "python")
    return v if os.path.exists(v) else sys.executable


def sh(cmd, **kw):
    print("$", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    subprocess.run(cmd, check=True, **kw)


def load(path):
    return json.load(open(path))


def save(obj, path):
    json.dump(obj, open(path, "w"), ensure_ascii=False, indent=1)


def open_url(url):
    """Opens a page in the configured browser (kit.config.json « browser »), else the default one."""
    b = config()["browser"]
    subprocess.Popen(["open", "-a", b, url] if b else ["open", url])
