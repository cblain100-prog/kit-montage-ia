#!/usr/bin/env python3
"""Checks the install, one line per piece (OK / MANQUE / ATTENTION) with the fix. Exit code 1 when a required piece is missing.
  .venv/bin/python tools/check.py"""
import glob, importlib, json, os, platform, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "premiere"))
bad = 0


def line(ok, what, fix="", required=True):
    global bad
    tag = "OK       " if ok else ("MANQUE   " if required else "ATTENTION")
    if not ok and required:
        bad += 1
    print(f"{tag} {what}" + (f"  ->  {fix}" if not ok and fix else ""))


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception:
        return None


line(platform.system() == "Darwin", "macOS", "ce kit tourne sur Mac uniquement")
line(sys.version_info >= (3, 11), f"Python {sys.version.split()[0]}", "scripts/install.sh crée .venv avec Python 3.11+")
for m in ("numpy", "scipy", "soundfile", "PIL"):
    try:
        importlib.import_module(m); line(True, f"module {m}")
    except ImportError:
        line(False, f"module {m}", ".venv/bin/python -m pip install -r requirements.txt")
w = None
for m in ("mlx_whisper", "whisper"):
    try:
        importlib.import_module(m); w = m; break
    except ImportError:
        pass
line(bool(w), f"Whisper ({w or 'absent'})", ".venv/bin/python -m pip install -r requirements.txt")
for b, fix in (("ffmpeg", "brew install ffmpeg"), ("ffprobe", "brew install ffmpeg"), ("node", "brew install node"), ("npx", "brew install node"), ("git", "xcode-select --install")):
    line(bool(shutil.which(b)), b, fix)
r = run(["ffmpeg", "-hide_banner", "-filters"])
line(bool(r and " zscale " in r.stdout), "ffmpeg avec zscale (vidéos HDR d'iPhone)", "brew reinstall ffmpeg", required=False)
gs = os.path.join(HERE, "assets", "gsap.min.js")
line(os.path.exists(gs) and os.path.getsize(gs) > 10000, "GSAP (assets/gsap.min.js)", "scripts/install.sh")
fonts = ["InterTight-var.ttf", "inter-var.woff2", "Poppins-ExtraBold.ttf", "Anton-Regular.ttf", "jetbrainsmono-400.woff2"]
line(all(os.path.exists(os.path.join(HERE, "assets", "fonts", f)) for f in fonts), "polices (assets/fonts)", "git checkout assets/fonts")
sfx = glob.glob(os.path.join(HERE, "assets", "sfx", "*.wav"))
line(len(sfx) >= 18, f"bruitages ({len(sfx)} dans assets/sfx)", ".venv/bin/python tools/make_sfx.py")
mus = [f for f in glob.glob(os.path.join(HERE, "assets", "music", "*")) if f.endswith((".mp3", ".wav", ".m4a"))]
line(len(mus) >= 2, f"musiques ({len(mus)} dans assets/music)", ".venv/bin/python tools/musique.py get trio", required=False)
line(os.path.exists(os.path.join(HERE, "tools", "bin", "facebox")), "détecteur de visage (tools/bin/facebox)", "xcode-select --install puis scripts/install.sh", required=False)
r = run(["npx", "--yes", "hyperframes@0.8.103", "--version"])
line(bool(r and r.returncode == 0), "HyperFrames 0.8.103", "npx --yes hyperframes@0.8.103 --version (connexion internet)")
kd = os.path.expanduser("~/.config/kit-montage-ia/kit_dir")
line(os.path.exists(kd) and open(kd).read().strip() == HERE, "emplacement du kit enregistré", "scripts/install.sh --no-premiere", required=False)
for s in ("create-style", "montage"):
    p = os.path.expanduser(f"~/.claude/skills/{s}/SKILL.md")
    line(os.path.exists(p), f"skill {s}", "scripts/install.sh --no-premiere", required=False)
for a in sorted(glob.glob(os.path.join(HERE, "agents", "*.md"))):
    line(os.path.exists(os.path.expanduser(f"~/.claude/agents/{os.path.basename(a)}")), f"agent {os.path.basename(a)[:-3]}", "scripts/install.sh --no-premiere", required=False)
mine = __import__("montage").personal_looks()
line(bool(mine), "style perso : " + (", ".join(mine) if mine else "aucun"), "skill create-style (obligatoire avant le premier montage)", required=False)
# Premiere
import paths
app = paths.app()
line(bool(app), f"Premiere Pro ({os.path.basename(app) if app else 'absent'})", "installe Premiere Pro et Media Encoder avec Creative Cloud", required=False)
line(bool(glob.glob("/Applications/Adobe Media Encoder *")), "Media Encoder", "installe Media Encoder avec Creative Cloud", required=False)
vend = os.path.join(HERE, "vendor", "premiere-mcp")
r = run(["git", "-C", vend, "rev-parse", "HEAD"]) if os.path.isdir(vend) else None
line(os.path.exists(os.path.join(vend, "dist", "index.js")) and bool(r and r.stdout.startswith("f5e95e30")),
     "connecteur Premiere 1.2.8 (vendor/premiere-mcp)", "scripts/install-premiere.sh", required=False)
bd = "/tmp/premiere-mcp-bridge"
line(os.path.isdir(bd) and os.stat(bd).st_uid == os.getuid() and (os.stat(bd).st_mode & 0o077) == 0, "dossier du pont privé (/tmp/premiere-mcp-bridge en 700)", "scripts/install-premiere.sh", required=False)
try:
    cfg = json.load(open(os.path.expanduser("~/.premiere-mcp-bridge/config.json")))
except Exception:
    cfg = {}
line(cfg.get("telemetry") is False and cfg.get("updateCheck") is False, "télémétrie et vérification de mise à jour du connecteur coupées", "scripts/install-premiere.sh", required=False)
try:
    deny = json.load(open(os.path.expanduser("~/.claude/settings.json"))).get("permissions", {}).get("deny", [])
except Exception:
    deny = []
need = ["mcp__premiere-pro__execute_extendscript", "mcp__premiere-pro__delete_preview_files", "mcp__premiere-pro__invoke_tool"]
line(all(d in deny for d in need), "outils risqués du connecteur interdits à Claude (settings.json)", "scripts/install-premiere.sh", required=False)
line(os.path.isdir(os.path.expanduser("~/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP")), "panneau MCP Bridge dans Premiere", "scripts/install-premiere.sh", required=False)
r = run(["claude", "mcp", "get", "premiere-pro"]) if shutil.which("claude") else None
line(bool(r and r.returncode == 0), "connecteur déclaré dans Claude Code (premiere-pro)", "scripts/install-premiere.sh", required=False)
age = paths.heartbeat_age()
line(age is not None and age < 60, "pont Premiere en marche" + (f" (dernier signe il y a {int(age)} s)" if age is not None else ""),
     "Premiere ouvert avec le panneau Fenêtre > Extensions > MCP Bridge (CEP) ouvert, il démarre seul ; sinon « Start Bridge » (sans pont : ffmpeg + fichier XML pour Premiere)", required=False)
print("\n" + ("Tout ce qui est requis est là." if not bad else f"{bad} élément(s) requis manquant(s)."))
sys.exit(1 if bad else 0)
