"""Where Premiere Pro and its export presets are on this Mac (any yearly version : 2025, 2026, ...)."""
import glob, os

BRIDGE = "/tmp/premiere-mcp-bridge"


def app():
    """Path of the newest « Adobe Premiere Pro <year>.app », or None."""
    found = sorted(glob.glob("/Applications/Adobe Premiere Pro */Adobe Premiere Pro *.app"))
    return found[-1] if found else None


def preset(name):
    """An export preset shipped with Premiere, found by its file name, e.g. "YouTube 1080p HD.epr"."""
    a = app()
    if not a:
        raise SystemExit("Adobe Premiere Pro is not installed in /Applications")
    hits = sorted(glob.glob(os.path.join(a, "Contents", "**", name), recursive=True))
    if not hits:
        raise SystemExit(f"Premiere preset not found : {name}")
    # the encoder presets (export) before the ingest ones
    return next((h for h in hits if "EncoderPresets" in h or "systempresets" in h), hits[0])


def youtube_preset():
    return preset("YouTube 1080p HD.epr")


def prores_preset():
    return preset("Match Source - Apple ProRes 422.epr")


def media_encoder_log():
    """Adobe Media Encoder's log : « Fichier codé avec succès » / « File successfully encoded » after each export."""
    hits = sorted(glob.glob(os.path.expanduser("~/Documents/Adobe/Adobe Media Encoder/*/AMEEncodingLog.txt")))
    return hits[-1] if hits else None


def heartbeat_age():
    """Seconds since the MCP Bridge panel last wrote its heartbeat (None when it never did)."""
    import json, time
    try:
        return time.time() - json.load(open(os.path.join(BRIDGE, "bridge-heartbeat.json")))["t"] / 1000
    except Exception:
        return None
