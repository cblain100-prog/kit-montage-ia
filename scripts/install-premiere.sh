#!/bin/bash
# Installs the Premiere Pro connector (MCP server « Adobe_Premiere_Pro_MCP » by hetpatel-11, MIT licence) into vendor/premiere-mcp,
# at the exact commit the kit was tested with, plus one small local fix (Media Encoder found when macOS installs it as a folder).
#   scripts/install-premiere.sh [--skip-cep] [--skip-register] [--force-register]
#   --skip-cep        do not copy the Premiere panel (CEP extension) into ~/Library/Application Support/Adobe/CEP/extensions
#   --skip-register   do not register the server in Claude Code (claude mcp add)
# Then, once, inside Premiere Pro (the skill tells the user) :
#   1. Premiere Pro > Réglages (Preferences) > Plug-ins : cocher « Activer le mode développeur » (Enable developer mode), relancer Premiere
#   2. Fenêtre (Window) > Extensions > MCP Bridge (CEP) : Temp Directory = /tmp/premiere-mcp-bridge, Save Configuration, Start Bridge
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP.git"
COMMIT="12684e37297a702265985dffa7d33629d28074f4"   # release 1.2.3 (2026-08-27)
DEST="$KIT/vendor/premiere-mcp"
TEMP_DIR="/tmp/premiere-mcp-bridge"
CEP=1; REGISTER=1; FORCE=0
for a in "$@"; do
  case "$a" in
    --skip-cep) CEP=0 ;;
    --skip-register) REGISTER=0 ;;
    --force-register) FORCE=1 ;;
    *) echo "unknown option $a"; exit 1 ;;
  esac
done
command -v node >/dev/null || { echo "node manque (brew install node)"; exit 1; }
[ "$(node -p "process.versions.node.split('.')[0]")" -ge 20 ] || { echo "Node 20 ou plus requis"; exit 1; }

if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$KIT/vendor"
  git clone --quiet "$REPO" "$DEST"
fi
cd "$DEST"
if [ "$(git rev-parse HEAD)" != "$COMMIT" ]; then
  git fetch --quiet origin
  git checkout --quiet "$COMMIT"
fi
if git apply --check "$KIT/scripts/premiere-mcp-ame-folder.patch" 2>/dev/null; then
  git apply "$KIT/scripts/premiere-mcp-ame-folder.patch"
fi
if [ ! -f dist/index.js ] || [ src/bridge/index.ts -nt dist/index.js ]; then
  npm install --silent --no-audit --no-fund
  npm run --silent build
fi
[ -f dist/index.js ] || { echo "build failed : dist/index.js missing"; exit 1; }
echo "connector built : $DEST/dist/index.js"
mkdir -p "$TEMP_DIR"

if [ "$CEP" = 1 ]; then
  # Premiere loads unsigned panels only in CEP debug mode
  for v in 10 11 12; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done
  EXT="$HOME/Library/Application Support/Adobe/CEP/extensions"
  mkdir -p "$EXT"
  rm -rf "$EXT/MCPBridgeCEP"
  cp -R "$DEST/cep-plugin" "$EXT/MCPBridgeCEP"
  echo "Premiere panel installed : $EXT/MCPBridgeCEP"
fi

if [ "$REGISTER" = 1 ] && command -v claude >/dev/null; then
  if claude mcp get premiere-pro >/dev/null 2>&1 && [ "$FORCE" = 0 ]; then
    echo "Claude Code already has a « premiere-pro » server : kept (--force-register to replace it)"
  else
    claude mcp remove premiere-pro -s user >/dev/null 2>&1 || true
    claude mcp add premiere-pro -s user -e PREMIERE_TEMP_DIR="$TEMP_DIR" -e PREMIERE_MCP_TELEMETRY=0 -- node "$DEST/dist/index.js"
    echo "registered in Claude Code (user scope) : premiere-pro"
  fi
fi
cat <<'EOF'

Dans Premiere Pro, une seule fois :
  1. Premiere Pro > Réglages > Plug-ins : coche « Activer le mode développeur », puis quitte et relance Premiere.
  2. Fenêtre > Extensions > MCP Bridge (CEP) : Temp Directory = /tmp/premiere-mcp-bridge, Save Configuration, puis Start Bridge.
     (décoche « Share anonymous usage data » si tu préfères)
A chaque montage : Premiere ouvert, le panneau MCP Bridge sur « Start Bridge ».
EOF
