"""Drive Premiere Pro from Python through the Premiere Pro MCP connector (vendor/premiere-mcp, installed by scripts/install-premiere.sh) over stdio.
Premiere must be open with a saved project and Window > Extensions > MCP Bridge (CEP) > Start Bridge.
  from ppclient import PP; pp = PP(); pp("get_project_info")"""
import json, os, subprocess

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendor", "premiere-mcp", "dist", "index.js")


class PP:
    def __init__(self):
        if not os.path.exists(SERVER):
            raise SystemExit("Premiere connector missing : run scripts/install-premiere.sh")
        env = dict(os.environ, PREMIERE_TEMP_DIR="/tmp/premiere-mcp-bridge", PREMIERE_MCP_TELEMETRY="0")
        self.p = subprocess.Popen(["node", SERVER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, text=True)
        self.i = 0
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "kit-montage-ia", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"); self.p.stdin.flush()

    def _rpc(self, method, params):
        self.i += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.i, "method": method, "params": params}) + "\n"); self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("Premiere MCP server closed")
            r = json.loads(line)
            if r.get("id") == self.i:
                if "error" in r:
                    raise RuntimeError(json.dumps(r["error"], ensure_ascii=False))
                return r["result"]

    def schema(self, name):
        return next(t for t in self._rpc("tools/list", {})["tools"] if t["name"] == name)["inputSchema"]

    def __call__(self, tool, **args):
        import time
        for k in range(12):  # Premiere busy (a long import, an export) : the bridge misses its heartbeat for a few seconds
            r = self._rpc("tools/call", {"name": tool, "arguments": args})
            txt = json.dumps(r, ensure_ascii=False)
            if r.get("isError") and ("Bridge is not running" in txt or "timed out" in txt) and k < 11:
                time.sleep(5); continue
            break
        out = r.get("structuredContent") or json.loads(r["content"][0]["text"]) if r.get("content") else r
        if r.get("isError"):
            raise RuntimeError(f"{tool}: {json.dumps(out, ensure_ascii=False)[:600]}")
        return out

    def close(self):
        self.p.terminate()
