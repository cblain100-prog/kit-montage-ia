"""The creator edits the cuts and the music from the studio page.
Every change is written to projects/<slug>/plan.json (the source of truth), so it survives every rebuild ; previews are computed
with the engine itself (same cut rules, same music rules) so what is heard is what the rebuild gives."""
import copy, json, os, subprocess, sys, threading, time
import numpy as np, soundfile as sf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import montage as M
import prompteur as PR

SR, FPS = 48000, 30


class Montage:
    def __init__(self, slug):
        self.slug = slug
        self.plan_path = PR.P(slug, "plan.json")
        self.cache = PR.P(slug, "review", "cache"); os.makedirs(self.cache, exist_ok=True)
        self.lock = threading.Lock()
        self.job = {"state": "idle"}
        self._voice = None

    # ------------------------------------------------------------------ helpers
    def plan(self):
        return json.load(open(self.plan_path))

    def save(self, plan):
        json.dump(plan, open(self.plan_path, "w"), indent=2, ensure_ascii=False)

    def log(self, entry):
        """Every change the creator makes in the studio is kept in projects/<slug>/review/studio-log.json, so that
        tools/learn.py turns it into his style (« ce que tu règles dans le studio, Claude ne le refait plus »)."""
        f = PR.P(self.slug, "review", "studio-log.json")
        data = json.load(open(f)) if os.path.exists(f) else []
        data.append(dict(entry, t=time.strftime("%Y-%m-%d %H:%M"), learned=False))
        json.dump(data, open(f, "w"), indent=1, ensure_ascii=False)

    def voice(self):
        if self._voice is None:
            x, sr = sf.read(PR.voice(self.slug), always_2d=True)
            self._voice = x.mean(1).astype(np.float32), sr
        return self._voice

    def edl_for(self, plan):
        """The engine's cut for a (modified) plan, without touching assets/edl.json."""
        saved = {}
        orig_load, orig_save = PR.load_plan, M.save
        PR.load_plan = lambda s: copy.deepcopy(plan)
        M.save = lambda data, path: saved.setdefault("edl", data)
        try:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                PR.cmd_cut(self.slug)
        finally:
            PR.load_plan, M.save = orig_load, orig_save
        return saved["edl"]["pieces"]

    def take_bounds(self, plan):
        ws = PR.words(self.slug)
        out = []
        for k in plan["keep"]:
            out.append((PR.anchor(self.slug, k[0], ws), PR.anchor_end(self.slug, k[1], ws)))
        return out

    # ------------------------------------------------------------------ cuts
    def joints(self):
        plan = self.plan(); ws = PR.words(self.slug); tb = self.take_bounds(plan)
        pieces = PR.edl(self.slug)
        res = []
        for i in range(len(tb) - 1):
            (s0, e0), (s1, e1) = tb[i], tb[i + 1]
            before = [w for w in ws if s0 - 0.05 <= w["start"] < e0][-7:]
            after = [w for w in ws if s1 - 0.05 <= w["start"] < e1][:7]
            opt = next((x for x in plan["keep"][i + 1][2:] if isinstance(x, dict)), {})
            res.append({"i": i, "out": round(PR.to_out(self.slug, e0 - 0.01, pieces), 2), "end": round(e0, 2), "start": round(s1, 2),
                        "before": " ".join(w["text"].strip() for w in before), "after": " ".join(w["text"].strip() for w in after),
                        "join": bool(opt.get("join"))})
        return res

    def takes(self):
        """Every take with its words (to remove words inside a take)."""
        plan = self.plan(); ws = PR.words(self.slug); tb = self.take_bounds(plan); pieces = PR.edl(self.slug)
        return [{"i": i, "out": round(PR.to_out(self.slug, s + 0.01, pieces), 2),
                 "words": [[w["text"].strip(), round(w["start"], 2), round(w["end"], 2)] for w in ws if s - 0.05 <= w["start"] < e]}
                for i, (s, e) in enumerate(tb)]

    def _modified(self, plan, i, d_end=0.0, d_start=0.0, join=None):
        plan = copy.deepcopy(plan); tb = self.take_bounds(plan)
        if d_end:
            plan["keep"][i][1] = f"src:{tb[i][1] + d_end:.2f}"
        if d_start:
            plan["keep"][i + 1][0] = f"src:{tb[i + 1][0] + d_start:.2f}"
        if join is not None:
            k = plan["keep"][i + 1]
            d = next((x for x in k[2:] if isinstance(x, dict)), None)
            if d is None:
                d = {}; k.append(d)
            d["join"] = bool(join)
            if not join:
                d.pop("join")
        if d_end:  # an end moved by hand is exact : no « finish the word » extension past it
            k = plan["keep"][i]
            d = next((x for x in k[2:] if isinstance(x, dict)), None)
            if d is None:
                k.append({"strict_end": True})
            else:
                d["strict_end"] = True
        return plan

    def preview_joint(self, i, d_end=0.0, d_start=0.0, join=None, ctx=2.5):
        """Audio of the joint as the engine will cut it : ctx seconds before and after."""
        plan = self._modified(self.plan(), i, d_end, d_start, join)
        pieces = self.edl_for(plan)
        tb = self.take_bounds(plan)
        s1 = tb[i + 1][0]
        k = min(range(len(pieces)), key=lambda j: abs(pieces[j]["src"][0] / FPS - s1) if not pieces[j].get("cold") else 1e9)
        t_join = pieces[k]["out"][0] / FPS
        v, sr = self.voice()
        out = []
        for p in pieces:
            a, b = p["out"][0] / FPS, p["out"][1] / FPS
            if b < t_join - ctx or a > t_join + ctx:
                continue
            sa, sb = p["src"][0] / FPS, p["src"][1] / FPS
            seg = v[int(sa * sr):int(sb * sr)].copy()
            f = min(len(seg) // 2, int(0.006 * sr))
            if f:
                seg[:f] *= np.linspace(0, 1, f); seg[-f:] *= np.linspace(1, 0, f)
            lo = max(0.0, (t_join - ctx) - a); hi = min(b - a, (t_join + ctx) - a)
            out.append(seg[int(lo * sr):int(hi * sr)])
        y = np.concatenate(out) if out else np.zeros(sr)
        path = os.path.join(self.cache, f"joint-{i}.wav")
        sf.write(path, y, sr)
        return path

    def set_joint(self, i, d_end=0.0, d_start=0.0, join=None):
        with self.lock:
            self.save(self._modified(self.plan(), i, d_end, d_start, join))
        return {"ok": True}

    def delete_words(self, i, w_start, w_end):
        """Remove the words of take i from w_start to w_end (rush times) : the take is split around them."""
        with self.lock:
            plan = self.plan(); k = plan["keep"][i]
            note = f"retiré dans le studio ({w_start:.2f}-{w_end:.2f})"
            left = [k[0], f"src:{w_start - 0.02:.2f}", note, {"strict_end": True}]
            right = [f"src:{w_end + 0.02:.2f}", k[1]] + [x for x in k[2:] if isinstance(x, dict) and not x.get("join")]
            plan["keep"][i:i + 1] = [left, right]
            self.save(plan)
        return {"ok": True}

    def delete_take(self, i):
        with self.lock:
            plan = self.plan(); k = plan["keep"][i]; del plan["keep"][i]; self.save(plan)
        self.log({"kind": "cut", "what": "take", "take": k[:2]})
        return {"ok": True}

    # ------------------------------------------------------------------ music
    def music(self):
        plan = self.plan(); m = plan["music"]
        times = M.load(PR.P(self.slug, "work", "insert-times.json"))
        segs, _, _ = PR.music_layout(self.slug, plan, 1e6, times)
        order = sorted(range(len(m["segments"])), key=lambda j: segs[[g["at"] for g in segs].index(m["segments"][j]["at"])]["t"] if m["segments"][j]["at"] in [g["at"] for g in segs] else 0)
        out = []
        for j in order:
            g = m["segments"][j]
            t = next((x["t"] for x in segs if x["at"] == g["at"] and x["file"] == g["file"]), 0)
            out.append({"j": j, "t": round(t, 2), "track": os.path.splitext(os.path.basename(g["file"]))[0].replace("-", " "), "under_db": g.get("under_db", 18)})
        return {"segments": out, "fade_out": m.get("fade_out", 1.5)}

    def set_music(self, levels):
        changes = []
        with self.lock:
            plan = self.plan()
            for j, v in levels.items():
                g = plan["music"]["segments"][int(j)]
                if abs(g.get("under_db", 18) - float(v)) > 0.05:
                    changes.append({"segment": int(j), "track": os.path.basename(g["file"]), "role": "intro" if int(j) == 0 else "body",
                                    "from": g.get("under_db", 18), "to": float(v)})
                g["under_db"] = float(v)
            self.save(plan)
        for c in changes:
            self.log(dict(c, kind="music"))
        return {"ok": True}

    def preview_music(self, levels):
        """The whole mix (voice + sounds + music with these levels, ducked under the voice like the edit) as m4a."""
        plan = self.plan()
        for j, v in levels.items():
            plan["music"]["segments"][int(j)]["under_db"] = float(v)
        times = M.load(PR.P(self.slug, "work", "insert-times.json"))
        plan["inserts"] = [x for x in plan["inserts"] if x["id"] in times]
        voice, _ = sf.read(PR.P(self.slug, "work", "base.wav"), always_2d=True)
        if voice.shape[1] == 1:
            voice = np.repeat(voice, 2, 1)
        dur = len(voice) / SR
        orig = PR.load_plan
        PR.load_plan = lambda s: plan
        try:
            import io, contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                bed, hooks, _ = PR.build_music_bed(self.slug, plan, dur)
        finally:
            PR.load_plan = orig
        b, _ = sf.read(bed, always_2d=True); h, _ = sf.read(hooks, always_2d=True)
        sys.path.insert(0, os.path.join(HERE, "premiere"))
        import build_timeline as BT
        duck = np.repeat(10 ** (BT.duck_curve(self.slug, plan) / 20), SR // 10)
        n = len(voice)
        def fit(x):
            return np.pad(x, ((0, max(0, n - len(x))), (0, 0)))[:n]
        sfx = np.zeros((n, 2))
        for f, t, db in PR.sfx_cues(self.slug, plan, times, dur):
            if not PR.sfx_file(f):
                continue
            x, r = sf.read(PR.sfx_file(f), always_2d=True)
            x = (x if x.shape[1] == 2 else np.repeat(x[:, :1], 2, 1)) * 10 ** (db / 20)
            i0 = int(t * SR); L = min(len(x), n - i0)
            if L > 0:
                sfx[i0:i0 + L] += x[:L]
        mix = voice + sfx + fit(b) * np.pad(duck, (0, max(0, n - len(duck))))[:n, None] + fit(h)
        wav = os.path.join(self.cache, "mix.wav"); sf.write(wav, np.clip(mix * 1.2, -1, 1), SR)
        out = os.path.join(self.cache, f"mix-{int(time.time())}.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "aac", "-b:a", "160k", out], check=True)
        return out

    # ------------------------------------------------------------------ rebuild
    def rebuild(self, name, on_done):
        if self.job.get("state") == "running":
            return {"ok": False, "error": "une reconstruction tourne déjà"}
        script = os.path.join(HERE, "review", "rebuild.sh")
        log = os.path.join(self.cache, "rebuild.log")
        self.job = {"state": "running", "started": time.time(), "name": name, "log": log}

        def run():
            r = subprocess.run(["bash", script, self.slug, name], stdout=open(log, "w"), stderr=subprocess.STDOUT, cwd=HERE)
            if r.returncode == 0:
                self.job.update(state="done", ended=time.time())
                on_done(name)
            else:
                self.job.update(state="error", ended=time.time())
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True}

    def status(self):
        j = dict(self.job)
        if j.get("log") and os.path.exists(j["log"]):
            lines = [l for l in open(j["log"], errors="ignore").read().splitlines() if l.startswith("STEP ")]
            j["step"] = lines[-1][5:] if lines else ""
        if j.get("started"):
            j["elapsed"] = int((j.get("ended") or time.time()) - j["started"])
        return j


# ------------------------------------------------------------------ Tella-like timeline (click, split, delete)
def _wave(self, per_s=50):
    x, sr = sf.read(PR.P(self.slug, "work", "base.wav"), always_2d=True)
    x = np.abs(x.mean(1)); hop = sr // per_s
    n = len(x) // hop
    pk = x[:n * hop].reshape(n, hop).max(1)
    pk = np.sqrt(pk / (pk.max() + 1e-9))  # perceptual, quiet syllables stay visible
    return {"per_s": per_s, "dur": len(x) / sr, "peaks": (pk * 255).astype(int).tolist()}


def _cuts(self):
    """Output times where two non-contiguous rush pieces meet (the existing cuts)."""
    ps = PR.edl(self.slug)
    return [round(b["out"][0] / FPS, 3) for a, b in zip(ps, ps[1:]) if abs(a["src"][1] - b["src"][0]) > 1]


def _delete_ranges(self, ranges):
    """Remove output ranges [a, b] from the edit : mapped to rush time through the current cut, subtracted from the takes."""
    pieces = PR.edl(self.slug)
    src, per_range = [], []
    for a, b in ranges:
        per_range.append([])
        for p in pieces:
            pa, pb = p["out"][0] / FPS, p["out"][1] / FPS
            lo, hi = max(a, pa), min(b, pb)
            if hi - lo > 0.02 and not p.get("cold"):
                t = p.get("tempo", 1.0)
                src.append((p["src"][0] / FPS + (lo - pa) * t, p["src"][0] / FPS + (hi - pa) * t))
                per_range[-1].append(src[-1])
    with self.lock:
        plan = self.plan(); tb = self.take_bounds(plan); keep = []
        for (s, e), k in zip(tb, plan["keep"]):
            parts = [(s, e, k)]
            for x, y in src:
                nxt = []
                for ps_, pe_, kk in parts:
                    if y <= ps_ or x >= pe_:
                        nxt.append((ps_, pe_, kk)); continue
                    opts = [o for o in kk[2:] if isinstance(o, dict)]
                    if x > ps_ + 0.05:  # what stays before the removed part ends exactly there
                        left = [kk[0], f"src:{x:.2f}", "coupé dans le studio (timeline)"] + [dict({kq: vq for o in opts for kq, vq in o.items()}, strict_end=True)]
                        nxt.append((ps_, x, left))
                    if y < pe_ - 0.05:
                        right = [f"src:{y:.2f}", kk[1], "coupé dans le studio (timeline)"] + [{kq: vq for o in opts for kq, vq in o.items() if kq != "join"}]
                        nxt.append((y, pe_, right))
                parts = nxt
            keep += [kk for _, _, kk in parts]
        plan["keep"] = keep
        plan.setdefault("_history", []).append({"t": time.strftime("%Y-%m-%d %H:%M"), "deleted_out": ranges})
        self.save(plan)
    ws = PR.words(self.slug)
    for (a, b), parts in zip(ranges, per_range):
        said = " ".join(w["text"].strip() for x, y in parts for w in ws if x - 0.02 <= w["start"] < y)
        self.log({"kind": "cut", "what": "range", "out": [round(a, 2), round(b, 2)], "rush": [[round(x, 2), round(y, 2)] for x, y in parts],
                  "removed_words": said, "silence_only": not said, "dur": round(sum(y - x for x, y in parts), 2)})
    return {"ok": True, "removed_src": [[round(x, 2), round(y, 2)] for x, y in src]}


Montage.wave, Montage.cuts, Montage.delete_ranges = _wave, _cuts, _delete_ranges
