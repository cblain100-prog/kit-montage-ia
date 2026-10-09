#!/bin/bash
# Installs the montage kit on a Mac. Safe to run again (it only adds what is missing).
#   scripts/install.sh [--no-premiere] [--no-skills] [--skills-dir DIR]
# Steps : Homebrew tools (ffmpeg, node, python) -> .venv with requirements.txt -> GSAP (from npm) -> default sound effects
#         -> face detector (Apple Vision) -> HyperFrames (npx, pinned) -> the two skills in ~/.claude/skills -> Premiere connector
#         -> tools/check.py
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$KIT"
PREMIERE=1; SKILLS=1; SKILLS_DIR="$HOME/.claude/skills"
while [ $# -gt 0 ]; do
  case "$1" in
    --no-premiere) PREMIERE=0 ;;
    --no-skills) SKILLS=0 ;;
    --skills-dir) SKILLS_DIR="$2"; shift ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
  shift
done
GSAP_VERSION=3.14.2
HF_VERSION=0.8.103

say() { printf "\n== %s\n" "$1"; }
[ "$(uname -s)" = "Darwin" ] || { echo "Ce kit tourne sur Mac (macOS) uniquement."; exit 1; }

say "1/8 outils de base (Homebrew : ffmpeg, node, python)"
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x "$b" ] && eval "$($b shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew manque. Ouvre l'app Terminal, colle cette ligne, tape ton mot de passe de Mac, puis relance l'installation :"
  echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 2
fi
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v node >/dev/null 2>&1 || brew install node
NODE_MAJOR=$(node -p "process.versions.node.split('.')[0]")
[ "$NODE_MAJOR" -ge 20 ] || brew upgrade node || brew install node
command -v git >/dev/null 2>&1 || xcode-select --install || true
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v $c >/dev/null 2>&1 && $c -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then PY=$(command -v $c); break; fi
done
if [ -z "$PY" ]; then brew install python@3.12; PY="$(brew --prefix python@3.12)/bin/python3.12"; fi
echo "python : $PY ($($PY --version))"

say "2/8 environnement Python (.venv)"
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt

say "3/8 GSAP $GSAP_VERSION (animations, téléchargé depuis npm, pas redistribué dans le dépôt)"
if [ ! -s assets/gsap.min.js ] || ! head -c 200 assets/gsap.min.js | grep -q "GSAP $GSAP_VERSION"; then
  curl -fsSL "https://cdn.jsdelivr.net/npm/gsap@$GSAP_VERSION/dist/gsap.min.js" -o assets/gsap.min.js
fi

say "4/8 bruitages par défaut (générés, originaux)"
.venv/bin/python tools/make_sfx.py

say "5/8 détecteur de visage (Apple Vision)"
mkdir -p tools/bin
if ! swiftc -O -o tools/bin/facebox tools/facebox.swift 2>/dev/null; then
  echo "swiftc manque : lance « xcode-select --install », accepte, puis relance. Sans lui, le cadrage serré vise le centre de l'image."
fi

say "6/8 HyperFrames $HF_VERSION (rendu des animations)"
npx --yes "hyperframes@$HF_VERSION" --version >/dev/null 2>&1 || npx --yes "hyperframes@$HF_VERSION" --help >/dev/null 2>&1 || echo "HyperFrames sera téléchargé au premier rendu"

say "7/8 les deux skills"
if [ "$SKILLS" = 1 ]; then
  mkdir -p "$HOME/.config/kit-montage-ia"
  echo "$KIT" > "$HOME/.config/kit-montage-ia/kit_dir"
  mkdir -p "$SKILLS_DIR"
  for s in style-de-montage montage-youtube; do
    if [ -e "$SKILLS_DIR/$s" ] && [ ! -L "$SKILLS_DIR/$s" ]; then
      echo "$SKILLS_DIR/$s existe déjà (pas un lien) : laissé tel quel"
    else
      ln -sfn "$KIT/skills/$s" "$SKILLS_DIR/$s"; echo "skill $s -> $SKILLS_DIR/$s"
    fi
  done
fi

say "8/8 connecteur Premiere Pro"
if [ "$PREMIERE" = 1 ]; then
  if ls -d /Applications/Adobe\ Premiere\ Pro\ * >/dev/null 2>&1; then
    bash scripts/install-premiere.sh
  else
    echo "Premiere Pro n'est pas installé : le montage passera par ffmpeg. Installe Premiere Pro et Media Encoder (Creative Cloud), puis lance scripts/install-premiere.sh"
  fi
fi

say "vérification"
.venv/bin/python tools/check.py || true
