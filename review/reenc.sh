#!/bin/sh
f="$1"
[ "$f.pp" -nt "$f" ] && exit 0
ffmpeg -v error -y -i "$f" -c:v libx264 -preset fast -crf 14 -bf 0 -g 15 -pix_fmt yuv420p -r 30 -an -movflags +faststart "$f.re.mp4" && mv "$f.re.mp4" "$f" && touch "$f.pp"
