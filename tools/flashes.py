#!/usr/bin/env python3
"""Find 1- or 2-frame flashes in a render: frames that differ strongly from both the frame before and the frame
after (a shot showing between two inserts, a missing frame at a cut).

  python3 tools/flashes.py <video> [threshold=18]"""
import subprocess, sys
import numpy as np
v = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 18
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", v, "-vf", "scale=64:36", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, 36, 64, 3).astype(np.float32)
d = lambda i, j: float(np.abs(f[i] - f[j]).mean())
out = []
for i in range(1, len(f) - 1):
    if d(i, i - 1) > thr and d(i, i + 1) > thr:  # a frame unlike both neighbours: a shot of 1 frame
        out.append((i, "1 frame"))
for i in range(1, len(f) - 2):
    if d(i, i - 1) > thr and d(i + 1, i + 2) > thr and d(i, i + 1) < thr / 2:  # a shot of 2 frames
        out.append((i, "2 frames"))
print(f"{len(f)} frames, {len(out)} flash(es)")
for i, k in out:
    print(f"  {i / 30:7.3f} s ({int(i / 30) // 60}:{i / 30 % 60:05.2f}) {k}")
