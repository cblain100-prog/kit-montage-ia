#!/usr/bin/env python3
"""Word-by-word transcription of the master voice (Whisper medium, on the Apple GPU when mlx-whisper is installed).

  python3 tools/transcribe.py <slug> [--model medium]     -> assets/transcript.json, prints one line per segment

Takes about 1 minute per 1 to 2 minutes of rush on an Apple Silicon Mac (the model, about 1.5 GB, is downloaded the first
time). Launch it in the background for a long rush. plan.whisper_prompt (names, jargon) helps the spelling.
Never decide a cut on this text alone : Whisper merges false starts and retakes (see tools/redites.py, tools/hear.py)."""
import argparse, os, sys, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import montage as M
import fastwhisper
import prompteur as PR

ap = argparse.ArgumentParser()
ap.add_argument("slug")
ap.add_argument("--model", default="medium")
A = ap.parse_args()
plan = PR.load_plan(A.slug)
t0 = time.time()
r = fastwhisper.load_model(A.model).transcribe(PR.voice(A.slug, True), language=plan.get("language", "fr"), word_timestamps=True,
                                               condition_on_previous_text=False, initial_prompt=plan.get("whisper_prompt") or None)
words = [{"text": w["word"].strip(), "start": round(w["start"], 3), "end": round(w["end"], 3)} for s in r["segments"] for w in s.get("words", [])]
M.save({"model": f"whisper {A.model}", "words": words,
        "segments": [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()} for s in r["segments"]]},
       PR.P(A.slug, "assets", "transcript.json"))
for s in r["segments"]:
    print(f"[{s['start']:7.2f}-{s['end']:7.2f}] {s['text'].strip()}")
print(f"{len(words)} words in {time.time() - t0:.0f} s -> {PR.P(A.slug, 'assets', 'transcript.json')}")
