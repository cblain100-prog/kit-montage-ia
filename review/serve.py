"""The studio : a local review page for a montage version.
  python3 review/serve.py <video.mp4> --slug <slug> [--port 4700] [--no-open]
Opens http://localhost:4700 in the browser : the video, a « commenter » key (C) that stamps the current time, quick tags,
a Tella-like timeline (S to split, Delete, Cmd+Z), the music levels, and a « Reconstruire » button. Every comment is saved
at once to projects/<slug>/review/<video name>.json, which Claude reads and applies in one batch ; cuts and music levels
go straight into plan.json. Launch it with nohup so it outlives the Claude Code session :
  nohup .venv/bin/python review/serve.py ~/Downloads/<slug>-v1.mp4 --slug <slug> > projects/<slug>/review/serve.log 2>&1 &"""
import argparse, json, os, re, subprocess, sys, time, urllib.parse
from montage_api import Montage
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import montage as M
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--slug", required=True); ap.add_argument("--port", type=int, default=4700); ap.add_argument("--no-open", action="store_true")
A = ap.parse_args()
VIDEO = os.path.abspath(os.path.expanduser(A.video))
OUT_DIR = os.path.join(os.path.dirname(HERE), "projects", A.slug, "review")
os.makedirs(OUT_DIR, exist_ok=True)
OUT = os.path.join(OUT_DIR, os.path.splitext(os.path.basename(VIDEO))[0] + ".json")
MT = Montage(A.slug)


def switch_video(name):
    """After a rebuild from the page : serve the new version, with its own comment file."""
    global VIDEO, OUT
    VIDEO = os.path.join(M.output_dir(), f"{name}.mp4")
    OUT = os.path.join(OUT_DIR, name + ".json")


def next_name():
    m = re.search(r"-v(\d+)", os.path.basename(VIDEO))
    return re.sub(r"-v\d+", f"-v{int(m.group(1)) + 1}", os.path.splitext(os.path.basename(VIDEO))[0]) if m else "video-v2"


class H(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def _file(self, path, ctype):
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m.group(1): start = int(m.group(1))
            if m.group(2): end = int(m.group(2))
        end = min(end, start + 8 * 1024 * 1024 - 1, size - 1)
        self.send_response(206 if rng else 200)
        self.send_header("Content-Type", ctype); self.send_header("Accept-Ranges", "bytes"); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(end - start + 1))
        if rng: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start); left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk: break
                try: self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError): return
                left -= len(chunk)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path == "/api/joints": return self._send(200, json.dumps(MT.joints(), ensure_ascii=False))
            if u.path == "/api/takes": return self._send(200, json.dumps(MT.takes(), ensure_ascii=False))
            if u.path == "/api/music": return self._send(200, json.dumps(MT.music(), ensure_ascii=False))
            if u.path == "/api/status": return self._send(200, json.dumps(MT.status(), ensure_ascii=False))
            if u.path == "/api/wave": return self._send(200, json.dumps(MT.wave()))
            if u.path == "/api/cuts": return self._send(200, json.dumps(MT.cuts()))
            if u.path == "/api/joint.wav":
                j = q.get("join"); j = None if j in (None, "") else j == "1"
                return self._file(MT.preview_joint(int(q["i"]), float(q.get("de", 0)), float(q.get("ds", 0)), j), "audio/wav")
            if u.path.startswith("/cache/"):
                return self._file(os.path.join(MT.cache, os.path.basename(u.path)), "audio/mp4")
        except Exception as e:
            return self._send(500, json.dumps({"error": str(e)}))
        if self.path in ("/", "/index.html"):
            return self._send(200, open(os.path.join(HERE, "index.html"), encoding="utf-8").read(), "text/html; charset=utf-8")
        if self.path == "/comments":
            data = json.load(open(OUT)) if os.path.exists(OUT) else {"video": VIDEO, "comments": [], "done": False}
            data["title"] = os.path.basename(VIDEO); data["video_mtime"] = os.path.getmtime(VIDEO)
            return self._send(200, json.dumps(data, ensure_ascii=False))
        if self.path.startswith("/video"):
            return self._file(VIDEO, "video/mp4")
        self._send(404, "{}")

    def do_POST(self):
        if self.path.startswith("/api/"):
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            try:
                if self.path == "/api/joint": r = MT.set_joint(int(d["i"]), float(d.get("de", 0)), float(d.get("ds", 0)), d.get("join"))
                elif self.path == "/api/words": r = MT.delete_words(int(d["i"]), float(d["ws"]), float(d["we"]))
                elif self.path == "/api/take/delete": r = MT.delete_take(int(d["i"]))
                elif self.path == "/api/delete_ranges": r = MT.delete_ranges(d["ranges"])
                elif self.path == "/api/music": r = MT.set_music(d["levels"])
                elif self.path == "/api/music/preview": r = {"url": "/cache/" + os.path.basename(MT.preview_music(d["levels"]))}
                elif self.path == "/api/rebuild": r = MT.rebuild(next_name(), switch_video)
                else: r = {"error": "unknown"}
                return self._send(200, json.dumps(r, ensure_ascii=False))
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}, ensure_ascii=False))
        if self.path == "/comments":
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            data["video"] = VIDEO; data["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            json.dump(data, open(OUT, "w"), ensure_ascii=False, indent=1)
            return self._send(200, json.dumps({"ok": True, "file": OUT}))
        self._send(404, "{}")


for _ in range(10):  # several videos are reviewed at once (2026-10-04 : 4700 and 4701 taken) : the next free port
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", A.port), H)
        break
    except OSError:
        A.port += 1
url = f"http://localhost:{A.port}"
print("review", url, "->", OUT, flush=True)
if not A.no_open:
    M.open_url(url)
srv.serve_forever()
