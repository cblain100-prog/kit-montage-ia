#!/bin/bash
# Full rebuild from the studio (the creator's cuts and music changes) : engine -> Premiere -> export -> <output_dir>/<name>.mp4
#   review/rebuild.sh <slug> <name>
set -e
SLUG="$1"; NAME="$2"
E="$(cd "$(dirname "$0")/.." && pwd)"; W="$E/projects/$SLUG/work"
PY="$E/.venv/bin/python"; [ -x "$PY" ] || PY=python3
cd "$E"
OUT=$("$PY" -c "import montage as M; print(M.output_dir())")
# what he set himself in the studio (music levels) becomes his style before anything else (tools/learn.py)
"$PY" tools/learn.py "$SLUG" --auto || true
echo "STEP 1/6 coupes"; "$PY" prompteur.py cut "$SLUG"
echo "STEP 2/6 plans caméra"; "$PY" prompteur.py base "$SLUG" > /dev/null
ffmpeg -v error -y -i "$W/base.wav" -ac 1 -ar 16000 "$W/base16.wav"
echo "STEP 3/6 visuels recalés"
if [ -f "projects/$SLUG/build_inserts.py" ]; then (cd "projects/$SLUG" && "$PY" build_inserts.py); fi
"$PY" prompteur.py outwords "$SLUG" > /dev/null && "$PY" prompteur.py inserts "$SLUG"
echo "STEP 4/6 rendus des animations"; "$PY" prompteur.py render "$SLUG"
# Premiere : mp4 re-encoded with short GOPs, transparent WebM -> ProRes 4444 (Premiere refuses WebM with alpha)
mkdir -p "$W/ins" && cd "$W"
ls ins/*.mp4 2>/dev/null | xargs -P 6 -n 1 "$E/review/reenc.sh" || true
rm -rf ins-pp && mkdir ins-pp && (ls ins/*.webm 2>/dev/null | xargs -P 6 -n 1 "$E/review/toprores.sh" || true)
cd "$E"
# Premiere's MCP Bridge must have written its heartbeat in the last 60 s ; when it is down (Premiere closed, « Start Bridge »
# not clicked), the look's zooms are drawn by ffmpeg and the engine composes the same edit (inserts, sounds, music, -14 LUFS)
HB=$("$PY" -c "import json,time;print(int(time.time()*1000-json.load(open('/tmp/premiere-mcp-bridge/bridge-heartbeat.json'))['t']))" 2>/dev/null || echo 999999)
# Premiere holds ONE project at a time : another build_timeline.py running means Premiere is busy, take the same fallback
BUSY=$(pgrep -f "premiere/build_timeline.py" | grep -v $$ | head -1 || true)
if [ "$HB" -lt 60000 ] && [ -z "$BUSY" ]; then
  echo "STEP 5/6 montage Premiere et export"; "$PY" -u premiere/build_timeline.py "$SLUG" --name "$NAME" --export
else
  echo "STEP 5/6 montage (Premiere indisponible : look ffmpeg + moteur, et fichier XML à importer dans Premiere)"; rm -rf "$W/look-ff"; "$PY" tools/look_ffmpeg.py "$SLUG" && "$PY" prompteur.py compose "$SLUG" "$NAME"
  "$PY" tools/export_xml.py "$SLUG" "$NAME" || echo "export XML impossible (le rendu ffmpeg est fait)"
fi
echo "STEP 6/6 livraison"; cp "projects/$SLUG/renders/$NAME.mp4" "$OUT/$NAME.mp4"
echo "STEP fini $OUT/$NAME.mp4"
