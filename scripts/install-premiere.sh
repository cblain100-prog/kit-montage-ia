#!/bin/bash
# Installs the Premiere Pro connector (MCP server « Adobe_Premiere_Pro_MCP » by hetpatel-11, MIT licence) into vendor/premiere-mcp,
# at the exact commit the kit was audited and tested with (release 1.2.8), never from npm, never « @latest ».
#   scripts/install-premiere.sh [--skip-cep] [--skip-register] [--force-register]
#   --skip-cep        do not copy the Premiere panel (CEP extension) into ~/Library/Application Support/Adobe/CEP/extensions
#   --skip-register   do not register the server in Claude Code, do not touch ~/.claude/settings.json
# Hardening (security audit of 1.2.8, verdict WARNING, no malware) :
#   - the bridge folder /tmp/premiere-mcp-bridge is private (700) : the panel runs every command file dropped there ;
#   - telemetry and update checks off : env PREMIERE_MCP_TELEMETRY=0, DO_NOT_TRACK=1, PREMIERE_MCP_UPDATE_CHECK=0, and
#     ~/.premiere-mcp-bridge/config.json {"telemetry": false, "updateCheck": false} (read by the panel too) ;
#   - PREMIERE_MCP_TOOLSET=full : every tool listed by name, so Claude Code can refuse them one by one ;
#   - Claude Code permissions « deny » on execute_extendscript (runs any script with access to your files),
#     delete_preview_files (deletes any folder's files) and invoke_tool (would bypass the two denials).
# The kit's own Python client (premiere/ppclient.py, premiere/ppbatch.py) still sends its own, kit-written ExtendScript : the
# denials only stop the model from calling those tools directly.
# The panel is installed by this script (copy of cep-plugin), not by upstream scripts/install-macos.sh, which also edits
# Claude Desktop's configuration. Undo everything : scripts/uninstall-premiere.sh.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP.git"
COMMIT="f5e95e30787f85ec90b181e5b4a0ac38f68546ad"   # release 1.2.8 (audited 2026-10-10)
DEST="$KIT/vendor/premiere-mcp"
TEMP_DIR="${KIT_BRIDGE_DIR:-/tmp/premiere-mcp-bridge}"   # override only for tests
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

# 1. private bridge folder, before anything else
if [ -e "$TEMP_DIR" ]; then
  if [ "$(stat -f %u "$TEMP_DIR")" != "$(id -u)" ] || [ ! -d "$TEMP_DIR" ] || [ -L "$TEMP_DIR" ]; then
    echo "STOP : $TEMP_DIR existe mais n'appartient pas à ton compte (ou n'est pas un vrai dossier)."
    echo "Quelqu'un d'autre pourrait y déposer des commandes pour Premiere. Supprime-le (sudo rm -rf $TEMP_DIR) puis relance."
    exit 1
  fi
  chmod 700 "$TEMP_DIR"
else
  mkdir -m 700 -p "$TEMP_DIR"
fi

# 2. telemetry and update checks off for the server and the panel (merged into an existing file)
mkdir -p "$HOME/.premiere-mcp-bridge"
python3 - "$HOME/.premiere-mcp-bridge/config.json" "$TEMP_DIR" <<'PY'
import json, os, sys
p, tmp = sys.argv[1], sys.argv[2]
try:
    c = json.load(open(p)) if os.path.exists(p) else {}
    if not isinstance(c, dict):
        c = {}
except Exception:
    c = {}
c.update({"telemetry": False, "updateCheck": False})
c.setdefault("tempDirectory", tmp)
json.dump(c, open(p, "w"), indent=2)
print("config :", p, c)
PY

# 3. the connector at the audited commit
if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$KIT/vendor"
  git clone --quiet "$REPO" "$DEST"
fi
cd "$DEST"
if [ "$(git rev-parse HEAD)" != "$COMMIT" ]; then
  git checkout --quiet -- . 2>/dev/null || true
  git fetch --quiet origin
  git checkout --quiet "$COMMIT"
fi
# Media Encoder installed as a folder « Adobe Media Encoder 2026 » on macOS is not found (upstream issue #103, still open)
if git apply --check "$KIT/scripts/premiere-mcp-ame-folder.patch" 2>/dev/null; then
  git apply "$KIT/scripts/premiere-mcp-ame-folder.patch"
fi
if [ ! -f dist/index.js ] || [ src/bridge/index.ts -nt dist/index.js ] || ! grep -q '"version": "1.2.8"' package.json; then
  npm install --silent --no-audit --no-fund
  npm run --silent build
fi
[ -f dist/index.js ] || { echo "build failed : dist/index.js missing"; exit 1; }
echo "connector built (1.2.8) : $DEST/dist/index.js"

# 4. the Premiere panel (kit copy, Claude Desktop untouched)
if [ "$CEP" = 1 ]; then
  # Premiere loads unsigned panels only in CEP debug mode (undo : scripts/uninstall-premiere.sh)
  for v in 10 11 12; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done
  EXT="$HOME/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP"
  mkdir -p "$EXT"
  cp -R "$DEST/cep-plugin/." "$EXT/"   # copied over, so a panel open in Premiere is not deleted under itself
  echo "Premiere panel installed : $EXT"
fi

# 5. Claude Code : the server, then the denials
if [ "$REGISTER" = 1 ] && command -v claude >/dev/null; then
  if claude mcp get premiere-pro >/dev/null 2>&1 && [ "$FORCE" = 0 ]; then
    echo "Claude Code already has a « premiere-pro » server : kept (--force-register to replace it with the hardened one)"
  else
    claude mcp remove premiere-pro -s user >/dev/null 2>&1 || true
    claude mcp add premiere-pro -s user -e PREMIERE_TEMP_DIR="$TEMP_DIR" -e PREMIERE_MCP_TELEMETRY=0 -e DO_NOT_TRACK=1 \
      -e PREMIERE_MCP_UPDATE_CHECK=0 -e PREMIERE_MCP_TOOLSET=full -- node "$DEST/dist/index.js"
    echo "registered in Claude Code (user scope) : premiere-pro"
  fi
  python3 - "$HOME/.claude/settings.json" <<'PY'
import json, os, shutil, sys, time
p = sys.argv[1]
deny = ["mcp__premiere-pro__execute_extendscript", "mcp__premiere-pro__delete_preview_files", "mcp__premiere-pro__invoke_tool"]
os.makedirs(os.path.dirname(p), exist_ok=True)
s = {}
if os.path.exists(p):
    s = json.load(open(p))
    if not isinstance(s, dict):
        sys.exit(f"{p} is not a JSON object : left untouched, add the denials by hand : {deny}")
perm = s.setdefault("permissions", {})
cur = perm.setdefault("deny", [])
add = [d for d in deny if d not in cur]
if add:
    if os.path.exists(p):
        b = f"{p}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(p, b)
        print("backup :", b)
    cur += add
    json.dump(s, open(p, "w"), indent=2, ensure_ascii=False)
    print("Claude Code denials added :", ", ".join(add))
else:
    print("Claude Code denials already there")
PY
fi
cat <<'EOF'

Dans Premiere Pro, une seule fois :
  1. Premiere > Préférences > Plug-ins (le menu Premiere, en haut à gauche ; en anglais Preferences > Plugins) : coche « Activer le mode de développement » (« Enable developer mode »), puis quitte et relance Premiere.
  2. Fenêtre > Extensions > MCP Bridge (CEP) : le panneau démarre le pont tout seul à son ouverture.
     Vérifie que Temp Directory = /tmp/premiere-mcp-bridge. Le panneau doit afficher « Connected » et « Premiere Pro: Ready » ; s'il reste sur « Disconnected », clique « Start Bridge ».
A chaque montage : Premiere ouvert avec le panneau MCP Bridge ouvert (il peut rester dans un coin de l'écran).
EOF
