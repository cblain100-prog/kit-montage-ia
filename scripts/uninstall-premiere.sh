#!/bin/bash
# Removes what scripts/install-premiere.sh added. Each step says what it does ; nothing else is touched.
#   scripts/uninstall-premiere.sh [--keep-debug-mode]
#   --keep-debug-mode  leave Adobe's CEP debug mode on (other unsigned panels you use may need it)
set -uo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
KEEP=0; [ "${1:-}" = "--keep-debug-mode" ] && KEEP=1
if command -v claude >/dev/null && claude mcp get premiere-pro 2>/dev/null | grep -q "$KIT/vendor/premiere-mcp"; then
  claude mcp remove premiere-pro -s user && echo "Claude Code : premiere-pro removed"
fi
python3 - "$HOME/.claude/settings.json" <<'PY'
import json, os, sys
p = sys.argv[1]
deny = {"mcp__premiere-pro__execute_extendscript", "mcp__premiere-pro__delete_preview_files", "mcp__premiere-pro__invoke_tool"}
if os.path.exists(p):
    s = json.load(open(p))
    d = s.get("permissions", {}).get("deny", [])
    if any(x in deny for x in d):
        s["permissions"]["deny"] = [x for x in d if x not in deny]
        json.dump(s, open(p, "w"), indent=2, ensure_ascii=False)
        print("Claude Code denials for premiere-pro removed")
PY
rm -rf "$HOME/Library/Application Support/Adobe/CEP/extensions/MCPBridgeCEP" && echo "Premiere panel removed"
if [ "$KEEP" = 0 ]; then
  # PlayerDebugMode lets Premiere load ANY unsigned panel : turned back off
  for v in 10 11 12; do defaults delete "com.adobe.CSXS.$v" PlayerDebugMode 2>/dev/null; done
  echo "CEP debug mode off (com.adobe.CSXS.10/11/12 PlayerDebugMode removed)"
fi
rm -rf /tmp/premiere-mcp-bridge "$KIT/vendor/premiere-mcp" && echo "bridge folder and vendor/premiere-mcp removed"
echo "Left in place : ~/.premiere-mcp-bridge/config.json (telemetry and update checks off ; delete it if you want)."
