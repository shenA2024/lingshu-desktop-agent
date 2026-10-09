"""MCP stdio interface to the running local workbench. No model credential required."""
from __future__ import annotations
import json
import os
import sys
from urllib.parse import urlencode, urlsplit, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from version import VERSION

URL = os.environ.get("LINGSHU_WORKBENCH_URL", "http://127.0.0.1:8787").rstrip("/")
parsed = urlsplit(URL)
if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1") or parsed.username or parsed.password:
    raise ValueError("Workbench URL must use local loopback HTTP")


def tool(name, description, properties=None, required=None):
    return {"name": name, "description": description, "inputSchema": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}


TOOLS = [
    tool("lingshu_list_scenarios", "List real Lingshu world-model simulation scenarios."),
    tool("lingshu_run_scene", "Start a preset deterministic experiment in Lingshu World Model Lab (observations include entity IDs). Note is recorded only, not interpreted as a free task. Returns a task id; query lingshu_get_run for verified results and per-mode coverage statistics.", {"scenario": {"type": "string", "enum": ["pursuit", "perturbation", "avoidance"]}, "ticks": {"type": "integer", "minimum": 4, "maximum": 120}, "note": {"type": "string", "maxLength": 1000}}, ["scenario"]),
    tool("lingshu_get_run", "Read a task's real status, latest world graph and recent execution events.", {"id": {"type": "string"}}, ["id"]),
    tool("lingshu_cancel_run", "Stop a running task and retain completed observations.", {"id": {"type": "string"}}, ["id"]),
    tool("lingshu_recall", "Recall from the isolated demo memory via the canonical dsh-memory engine.", {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"]),
    tool("lingshu_remember", "Write a note into the isolated demo memory via Lingshu's real brain adapter.", {"content": {"type": "string"}}, ["content"]),
]


def http(path, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if os.environ.get('LINGSHU_AGENT_TURN_ID'):
        headers['X-Lingshu-Turn-Id'] = os.environ['LINGSHU_AGENT_TURN_ID']
    req = Request(URL + path, data=data, headers=headers)
    try:
        with urlopen(req, timeout=35) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            body = json.loads(exc.read())
            detail = body.get("detail", body)
        except (ValueError, UnicodeError):
            detail = exc.reason
        raise ToolHTTPError(exc.code, detail) from exc


class ToolHTTPError(RuntimeError):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(json.dumps({"status": status, "detail": detail}, ensure_ascii=False))


def invoke(name, args):
    spec = next((t for t in TOOLS if t["name"] == name), None)
    if not spec:
        raise ValueError("Unknown tool: " + name)
    if not isinstance(args, dict):
        raise ValueError("Tool arguments must be an object")
    if set(args) - set(spec["inputSchema"]["properties"]) or set(spec["inputSchema"]["required"]) - set(args):
        raise ValueError("Invalid tool arguments")
    for key, value in args.items():
        field = spec["inputSchema"]["properties"][key]
        if field["type"] == "string" and not isinstance(value, str):
            raise ValueError(key + " must be a string")
        if field["type"] == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ValueError(key + " must be an integer")
        if "enum" in field and value not in field["enum"]:
            raise ValueError(key + " is not an allowed value")
        if "minimum" in field and not field["minimum"] <= value <= field["maximum"]:
            raise ValueError(key + " is out of range")
    if name == "lingshu_list_scenarios":
        return http("/api/scenarios")
    if name == "lingshu_run_scene":
        return http("/api/runs", {**args, "interval_ms": 150, "save_memory": True})
    if name == "lingshu_get_run":
        run = http("/api/runs/" + quote(str(args["id"]), safe=""))
        frames = run.pop("frames")
        run["latest_frame"] = frames[-1] if frames else None
        run["events"] = run["events"][-5:]
        return run
    if name == "lingshu_cancel_run":
        return http("/api/runs/" + quote(str(args["id"]), safe="") + "/cancel", {})
    if name == "lingshu_recall":
        return http("/api/memory?" + urlencode(args))
    if name == "lingshu_remember":
        return http("/api/memory", args)


def respond(message):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    request_id = message.get("id")
    method = message.get("method")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "lingshu-world-model-lab", "version": VERSION}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            try:
                value = invoke(params["name"], params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}]}
            except Exception as exc:
                result = {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}
    except Exception as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}}


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        try:
            reply = respond(json.loads(line))
        except Exception:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if reply:
            print(json.dumps(reply, ensure_ascii=False), flush=True)
