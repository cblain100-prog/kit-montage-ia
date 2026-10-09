#!/usr/bin/env python3
"""Print the loudness of the master voice every 40 ms between two rush times, to find the silences around a retake.

  python3 tools/energy.py <slug> <s0> <s1>        ('#' bar = louder; words show as blocks, gaps as dots)
"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import montage as M
import prompteur as PR
slug, s0, s1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
out = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(s0), "-t", str(s1 - s0), "-i", PR.voice(slug), "-vn", "-ac", "1", "-ar", "16000",
                      "-af", "aresample=16000,asetnsamples=640,astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-", "-f", "null", "-"],
                     capture_output=True, text=True).stdout
vals = [float(l.split("=")[1]) if "inf" not in l else -99 for l in out.splitlines() if "RMS_level" in l]
for i, v in enumerate(vals):
    print(f"{s0 + i * 0.04:7.2f} {v:6.1f} " + ("#" * max(0, int((v + 60) / 2)) if v > -60 else "."))
