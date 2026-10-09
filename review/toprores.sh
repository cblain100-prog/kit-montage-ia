#!/bin/sh
f="$1"; b=$(basename "$f" .webm)
ffmpeg -v error -y -c:v libvpx-vp9 -i "$f" -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le "ins-pp/$b.mov"
