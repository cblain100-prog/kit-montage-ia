#!/usr/bin/env python3
"""Creates a montage project from one or two phone videos.

  python3 tools/projet.py <slug> <front video> [<side video>] [--voix A|B] [--look exemple] [--copy] [--title "..."]

  one video   : one phone (camera A). Its sound is the voice, every cut reframes it (wide / tight / very tight).
  two videos  : the first is the FRONT camera (A, face to the lens, opens the video), the second the SIDE camera (B).
                The voice is taken from the camera with the clearest sound (the one holding the microphone), or --voix.
                The other camera is synchronised on it by correlating both soundtracks at several points (drift checked).

Writes projects/<slug>/ :
  assets/rush-A.<ext> [rush-B.<ext>]   links to the videos (--copy copies them)
  assets/voice.wav, assets/voice16.wav  the master voice, 48 kHz and 16 kHz mono
  assets/thumb-A.jpg [thumb-B.jpg]      one frame per camera, with the face found
  plan.json                             skeleton : cameras, offsets, sizes, faces, framings from the look, cut settings
Then : python3 tools/transcribe.py <slug>
"""
import argparse, json, os, re, shutil, subprocess, sys
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import montage as M

SR = 48000


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,color_transfer,sample_rate",
                        "-of", "json", path], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams", [])
    return {"duration": float(d.get("format", {}).get("duration", 0)),
            "audio": any(s.get("codec_type") == "audio" for s in streams),
            "transfer": next((s.get("color_transfer") for s in streams if s.get("codec_type") == "video"), None)}


def frame(path, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1", "-q:v", "3", out], check=True)
    from PIL import Image
    return Image.open(out).size


def facebox():
    """tools/bin/facebox (Apple Vision, compiled from tools/facebox.swift by scripts/install.sh)."""
    b = os.path.join(HERE, "tools", "bin", "facebox")
    if os.path.exists(b):
        return b
    os.makedirs(os.path.dirname(b), exist_ok=True)
    r = subprocess.run(["swiftc", "-O", "-o", b, os.path.join(HERE, "tools", "facebox.swift")], capture_output=True, text=True)
    return b if r.returncode == 0 else None


def face_centre(path, dur, d, cam):
    """Median face centre (x, y normalised, origin top-left) on 3 frames ; (0.5, 0.42) when no face is found."""
    fb = facebox()
    imgs = []
    for k, f in enumerate((0.25, 0.5, 0.75)):
        out = os.path.join(d, f"_face-{cam}-{k}.jpg")
        frame(path, dur * f, out)
        imgs.append(out)
    pts = []
    if fb:
        r = subprocess.run([fb] + imgs, capture_output=True, text=True).stdout
        for line in r.splitlines():
            j = json.loads(line)
            if "x" in j:
                pts.append((j["x"] + j["w"] / 2, j["y"] + j["h"] / 2))
    shutil.copy(imgs[1], os.path.join(d, f"thumb-{cam}.jpg"))
    for f in imgs:
        os.remove(f)
    if not pts:
        print(f"  ! camera {cam} : no face found ({'facebox missing' if not fb else 'Vision saw none'}), centre assumed")
        return [0.5, 0.42]
    return [round(float(np.median([p[0] for p in pts])), 3), round(float(np.median([p[1] for p in pts])), 3)]


def audio(path, sr):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).astype(np.float64)


def snr(x, sr):
    """Speech level minus room noise (dB), on 10 ms frames : the microphone camera has the higher one."""
    h = sr // 100
    n = len(x) // h
    db = 20 * np.log10(np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1)) + 1e-9)
    return float(np.percentile(db, 95) - np.percentile(db, 10))


def envelope(x, sr, rate=200):
    h = sr // rate
    n = len(x) // h
    e = np.sqrt(np.mean(x[:n * h].reshape(n, h) ** 2, axis=1))
    return (e - e.mean()) / (e.std() + 1e-9)


def lag(x, v, rate):
    """d such that x(t + d) matches v(t), in seconds (FFT cross-correlation)."""
    from scipy.signal import correlate, correlation_lags
    c = correlate(x, v, mode="full", method="fft")
    lags = correlation_lags(len(x), len(v), mode="full")
    k = int(np.argmax(c))
    return lags[k] / rate, float(c[k] / (np.linalg.norm(x) * np.linalg.norm(v) + 1e-9))


def sync(other, voice_x, sr=16000):
    """Offset of `other` on the voice : coarse on the loudness envelope of the whole files, then refined on the raw sound
    at 5 points (drift measured). Returns (offset, drift_ms, score)."""
    coarse, score = lag(envelope(other, sr), envelope(voice_x, sr), 200)
    fine = []
    dur = len(voice_x) / sr
    for f in (0.15, 0.32, 0.5, 0.68, 0.85):
        t = dur * f
        a, b = int(max(0, t - 4) * sr), int(min(dur, t + 4) * sr)
        v = voice_x[a:b]
        o0 = int((t - 4 + coarse - 0.25) * sr)
        if o0 < 0 or o0 + len(v) + int(0.5 * sr) > len(other):
            continue
        w = other[o0:o0 + len(v) + int(0.5 * sr)]
        d, sc = lag(w, v, sr)
        if sc > 0.2:
            fine.append(coarse - 0.25 + d - (a / sr - (t - 4)))
    if not fine:
        return round(coarse, 4), None, score
    off = float(np.median(fine))
    return round(off, 4), round((max(fine) - min(fine)) * 1000, 1), score


def tonemap_filter():
    """iPhone HDR (HLG / PQ) to SDR BT.709, when this ffmpeg has zscale ; else None."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    if " zscale " not in r:
        return None
    return "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("videos", nargs="+", help="front video, then the side video if there are two phones")
    ap.add_argument("--voix", choices=["A", "B"], help="camera that holds the microphone (default : measured)")
    ap.add_argument("--look", default="exemple")
    ap.add_argument("--copy", action="store_true", help="copy the videos into the project instead of linking them")
    ap.add_argument("--title", default="")
    ap.add_argument("--language", default="fr")
    A = ap.parse_args()
    if len(A.videos) > 2:
        raise SystemExit("one or two videos")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", A.slug):
        raise SystemExit("slug : lowercase letters, digits and dashes (e.g. yt-ma-video)")
    d = M.P(A.slug, "assets")
    os.makedirs(d, exist_ok=True)
    for sub in ("work", "renders", "inserts", "review"):
        os.makedirs(M.P(A.slug, sub), exist_ok=True)
    cams = ["A", "B"][:len(A.videos)]
    info, files = {}, {}
    for cam, src in zip(cams, A.videos):
        src = os.path.abspath(os.path.expanduser(src))
        if not os.path.exists(src):
            raise SystemExit(f"not found : {src}")
        dst = os.path.join(d, f"rush-{cam}{os.path.splitext(src)[1].lower()}")
        if os.path.lexists(dst):
            os.remove(dst)
        if A.copy:
            shutil.copy2(src, dst)
        else:
            os.symlink(src, dst)
        files[cam] = dst
        info[cam] = probe(dst)
        if not info[cam]["audio"]:
            print(f"  ! camera {cam} has no sound track")
        print(f"camera {cam} : {os.path.basename(src)}, {info[cam]['duration']:.1f} s, transfer {info[cam]['transfer']}")
    sizes, faces = {}, {}
    for cam in cams:
        frame(files[cam], info[cam]["duration"] / 2, os.path.join(d, f"_size-{cam}.jpg"))
        from PIL import Image
        sizes[cam] = list(Image.open(os.path.join(d, f"_size-{cam}.jpg")).size)
        os.remove(os.path.join(d, f"_size-{cam}.jpg"))
        faces[cam] = face_centre(files[cam], info[cam]["duration"], d, cam)
        print(f"camera {cam} : {sizes[cam][0]}x{sizes[cam][1]}, face at {faces[cam]}")
        if sizes[cam][1] > sizes[cam][0]:
            print(f"  ! camera {cam} is vertical : this kit edits 16:9 videos, film in landscape")
        if sizes[cam][0] < 3840:
            print(f"  ! camera {cam} is not 4K : tight framings will be softer (film in 4K next time)")
    # voice camera
    a16 = {cam: audio(files[cam], 16000) for cam in cams if info[cam]["audio"]}
    if not a16:
        raise SystemExit("no sound on any camera")
    if A.voix:
        vc = A.voix
    elif len(a16) == 1:
        vc = next(iter(a16))
    else:
        s = {cam: snr(a16[cam], 16000) for cam in a16}
        vc = max(s, key=s.get)
        print("sound clarity (dB) : " + ", ".join(f"{c} {v:.1f}" for c, v in s.items()) + f" -> voice from camera {vc}")
    offsets = {vc: 0.0}
    for cam in cams:
        if cam == vc:
            continue
        if cam not in a16:
            raise SystemExit(f"camera {cam} has no sound : it cannot be synchronised")
        off, drift, score = sync(a16[cam], a16[vc])
        offsets[cam] = off
        print(f"sync : camera {cam} = voice time {off:+.3f} s (drift {drift} ms over 5 points, match {score:.2f})")
        if drift is None or drift > 40:
            print("  ! the sync is not reliable : check the first seconds of both cameras by ear (tools/hear.py), or film a clap")
    # master voice
    full = audio(files[vc], SR)
    sf.write(os.path.join(d, "voice.wav"), full.astype(np.float32), SR)
    sf.write(os.path.join(d, "voice16.wav"), a16[vc].astype(np.float32), 16000)
    peak = float(np.mean(np.abs(full) > 0.985) * 100)
    if peak > 0.01:
        print(f"  ! the voice clips ({peak:.2f} % of samples at full scale) : microphone too close, see the skill")
    # plan skeleton from the look
    look_f = os.path.join(HERE, "looks", A.look, "look.json")
    look = json.load(open(look_f)) if os.path.exists(look_f) else {}
    fr = look.get("framing", {}).get("one_camera" if len(cams) == 1 else "two_cameras", {})
    plan_f = M.P(A.slug, "plan.json")
    plan = json.load(open(plan_f)) if os.path.exists(plan_f) else {}
    grade = {}
    tm = None
    for cam in cams:
        if info[cam]["transfer"] in ("arib-std-b67", "smpte2084"):
            tm = tm or tonemap_filter()
            if tm:
                grade[cam] = tm
            else:
                print(f"  ! camera {cam} is HDR and this ffmpeg has no zscale : colours may look grey (brew reinstall ffmpeg)")
    default_cycle = ["A", "At", "Att"] if len(cams) == 1 else ["At", "A", "Bt", "At", "A", "Btt"]
    plan.update({
        "title": A.title or plan.get("title", ""),
        "language": A.language,
        "look": A.look,
        "cameras": cams,
        "voice_cam": vc,
        "offsets": offsets,
        "sizes": sizes,
        "faces": faces,
        "framings": fr.get("cycle", default_cycle),
        "zoom": fr.get("zoom", {"At": 1.25, "Att": 1.5} if len(cams) == 1 else {"At": 1.15, "Bt": 1.3, "Btt": 1.5}),
        "first_angle": fr.get("first", default_cycle[0]),
    })
    if grade:
        plan["grade"] = grade
    if fr.get("crop_x_min"):
        plan["crop_x_min"] = fr["crop_x_min"]
    cut = look.get("cut", {})
    for k, v in {"cam_hold": {"A": 5.5, "B": 3.0}, "intro_cam_hold": 3.0, "tail_keep": 0.28, "edge_keep": 0.12, "max_pause": 0.45,
                 "pause_keep": 0.38, "min_shot": 1.4, "max_shot": 3.4, "shot_target": 2.6, "min_face": 1.5}.items():
        plan.setdefault(k, cut.get(k, v))
    for k, v in {"keep": [], "inserts": [], "sfx": [], "whisper_prompt": ""}.items():
        plan.setdefault(k, v)
    json.dump(plan, open(plan_f, "w"), ensure_ascii=False, indent=1)
    print(f"project ready : {M.P(A.slug)} ({len(cams)} camera{'s' if len(cams) > 1 else ''}, voice {vc})")
    print(f"next : {M.python()} tools/transcribe.py {A.slug}")


if __name__ == "__main__":
    main()
