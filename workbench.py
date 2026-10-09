"""Local Lingshu workbench. All world results come from the upstream engine."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import queue
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
from dependencies import resolve
from metrics import refresh
from agent import AgentService, routes as agent_routes
from data_backup import create_backup
from version import VERSION
WORLD_SOURCE, BRAIN_SOURCE = resolve()
CONFIG["port"] = int(os.environ.get("LINGSHU_WORKBENCH_PORT", CONFIG["port"]))
DATA = Path(os.environ.get("LINGSHU_WORKBENCH_DATA", BASE / CONFIG["data_dir"])).resolve()
sys.path.insert(0, str(WORLD_SOURCE))
from lingshu.world.scene_simulator import SceneSimulator
from lingshu.world.world_model import UnifiedWorldModel
from lingshu.world.brain_store import MCPClient, BrainStore, BrainAgent, BrainError


def now():
    return datetime.now(timezone.utc).isoformat()


class TimedBrainClient(MCPClient):
    """Keep the upstream adapter, add a deadline and drain both stdio pipes."""

    def __init__(self, **kwargs):
        self._inbox = queue.Queue()
        self._errors = deque(maxlen=8)
        self._reader_started = False
        self._readers = []
        try:
            super().__init__(**kwargs)
        except Exception:
            if hasattr(self, "_p"):
                self._p.kill()
                self._p.wait(timeout=3)
            raise

    def _read(self):
        if not self._reader_started:
            self._reader_started = True

            def reader():
                for line in self._p.stdout:
                    self._inbox.put(line)
                self._inbox.put(None)

            def errors():
                for line in self._p.stderr:
                    self._errors.append(line.strip())

            self._readers = [threading.Thread(target=reader, daemon=True), threading.Thread(target=errors, daemon=True)]
            for thread in self._readers:
                thread.start()
        deadline = time.monotonic() + 20
        while True:
            try:
                line = self._inbox.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                self._p.kill()
                self._p.wait(timeout=3)
                raise BrainError("记忆工具超过 20 秒未响应，连接已关闭，可重新连接。")
            if line is None:
                raise BrainError("记忆进程已退出：" + " / ".join(self._errors)[-500:])
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and ("result" in message or "error" in message):
                return message

    def close(self):
        super().close()
        if self._p.poll() is None:
            try:
                self._p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._p.kill()
                self._p.wait(timeout=3)
        for thread in self._readers:
            thread.join(timeout=3)
        for pipe in (self._p.stdout, self._p.stderr):
            pipe.close()


class Memory:
    def __init__(self):
        self.agent = None
        self.lock = threading.RLock()
        self.error = None

    def connect(self):
        with self.lock:
            self.close()
            try:
                # Issue the upstream recorder role against our own token store.
                # The plaintext stays in process memory and child env only.
                token_path = str(DATA / "memory-aux" / "_tokens.json")
                token_env = {key: value for key, value in os.environ.items() if not key.startswith("MDCG_")}
                token_env.update({"PYTHONPATH": str(BRAIN_SOURCE), "MDCG_AUX_ROOT": str(DATA / "memory-aux"), "MDCG_TOKEN_FILE": token_path, "MDCG_DATA_ROOT": str(DATA / "brain-data"), "MDCG_STATE_ROOT": str(DATA / "brain-state")})
                issued = subprocess.run(
                    [sys.executable, "-X", "utf8", "-c", "import json; from md_cg.tokens import issue; print(json.dumps(issue('recorder', actor='lingshu-workbench', clearance='internal', ttl=86400, label='isolated workbench demo', layers_allow=['contextual'], ops_allow=['read','write','info','status','edges','recent'])))"],
                    env=token_env, capture_output=True, text=True, encoding="utf-8", timeout=10,
                )
                if issued.returncode:
                    raise BrainError("Demo 记录凭据签发失败：" + issued.stderr[-400:])
                token = json.loads(issued.stdout)["token"]
                client = TimedBrainClient(
                    python=sys.executable,
                    pythonpath=str(BRAIN_SOURCE),
                    root=str(DATA / "memory"),
                    extra_env={"MDCG_STG_STATE": "1", "MDCG_MCP_SURFACE": "full", "MDCG_ACTOR": "lingshu-workbench", "MDCG_SESSION": "workbench-demo", "MDCG_AUX_ROOT": str(DATA / "memory-aux"), "MDCG_TOKEN_FILE": token_path, "MDCG_TOKEN": token, "MDCG_DATA_ROOT": str(DATA / "brain-data"), "MDCG_STATE_ROOT": str(DATA / "brain-state")},
                )
                self.agent = BrainAgent(BrainStore(client))
                self.error = None
                return self.status()
            except Exception as exc:
                self.error = str(exc)
                return self.status()

    def status(self):
        return {
            "connected": bool(self.agent and self.agent.store.client._p.poll() is None),
            "server": self.agent.store.client.server_info if self.agent else {},
            "root": str(DATA / "memory"),
            "error": self.error,
        }

    def call(self, name, arguments):
        with self.lock:
            if not self.status()["connected"]:
                raise BrainError(self.error or "记忆未连接，请在连接页重新连接。")
            try:
                return self.agent.store.client.call(name, arguments)
            except Exception as exc:
                self.error = str(exc)
                raise

    def remember(self, content, tags=None):
        with self.lock:
            if not self.status()["connected"]:
                raise BrainError(self.error or "记忆未连接")
            ref = self.agent.engine.add_perception(
                content, importance=0.7, tags=["workbench", *(tags or [])]
            )
            return {"ok": True, "id": ref.id, "content": content}

    def close(self):
        if self.agent:
            self.agent.store.client.close()
            self.agent = None


SCENARIOS = {
    "pursuit": {"name": "追逐与游走", "description": "观察追逐者与随机游走目标，推断行为并验证下一步预测。", "icon": "orbit"},
    "perturbation": {"name": "外部扰动", "description": "运行中途移动目标，观察预测失效、异常记录与后续恢复。", "icon": "bolt"},
    "avoidance": {"name": "避让观察", "description": "让两个实体避开障碍，比较推断方向、实际轨迹与置信度。", "icon": "route"},
}


def create_world(scenario):
    scene = SceneSimulator(size=24)
    scene.create_scene(trees=0, water=False)
    if scenario == "avoidance":
        obstacle = scene.add_entity("障碍物", "wander", pos=(12, 1.5, 12), speed=0)
        scene.add_entity("探索者 A", "avoid", pos=(9, 1.5, 10), speed=0.35, goal=obstacle)
        scene.add_entity("探索者 B", "avoid", pos=(15, 1.5, 14), speed=0.28, goal=obstacle)
    else:
        target = scene.add_entity("游走目标", "wander", pos=(15, 1.5, 13), speed=0.35)
        scene.add_entity("追逐者", "seek", pos=(6, 1.5, 5), speed=0.48, goal=target)
        scene.add_entity("观察者", "wander", pos=(5, 1.5, 17), speed=0.18)
    model = UnifiedWorldModel(world=scene)
    model.perceive(tool="workbench_observer")
    return scene, model


class Store:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(DATA / "sessions.sqlite", check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.connection.commit()

    def load(self):
        result = {}
        for run_id, data in self.connection.execute("SELECT id, data FROM runs"):
            run = json.loads(data)
            refresh(run)
            if run["status"] in ("running", "cancelling", "saving"):
                run["status"] = "interrupted"
                run["finished_at"] = now()
                run["events"].append({"kind": "interrupted", "title": "服务重启，任务已中断", "at": now(), "data": {}})
                self.save(run)
            result[run_id] = run
        return result

    def save(self, run):
        self.connection.execute("INSERT OR REPLACE INTO runs VALUES (?, ?)", (run["id"], json.dumps(run, ensure_ascii=False)))
        self.connection.commit()


memory = Memory()
store = None
runs = {}
jobs = {}
agent_service = None


@asynccontextmanager
async def lifespan(app):
    global store, runs, agent_service
    store = Store()
    runs = store.load()
    def cancel_agent_experiments(ids):
        for run_id in ids:
            if run_id in jobs and run_id in runs and runs[run_id]['status'] in ('running', 'saving'):
                jobs[run_id]['stop'].set()
    agent_service = AgentService(DATA, CONFIG['port'], cancel_agent_experiments)
    await asyncio.to_thread(memory.connect)
    yield
    await agent_service.close()
    for job in jobs.values():
        job["stop"].set()
    await asyncio.gather(*(job["task"] for job in jobs.values()), return_exceptions=True)
    await asyncio.to_thread(memory.close)
    store.connection.close()


app = FastAPI(title="Lingshu Desktop Agent", version=VERSION, lifespan=lifespan)
app.state.backing_up = False
app.include_router(agent_routes(lambda: agent_service))


@app.middleware("http")
async def local_boundary(request: Request, call_next):
    # The UI binds to loopback. Reject cross-site writes and DNS-rebinding hosts.
    allowed_hosts = {"127.0.0.1", "localhost", "[::1]", "testserver"}
    hostname = request.headers.get("host", "").rsplit(":", 1)[0]
    if hostname not in allowed_hosts:
        return JSONResponse({"detail": "仅允许本机访问"}, status_code=403)
    origin = request.headers.get("origin")
    expected = {f"http://127.0.0.1:{CONFIG['port']}", f"http://localhost:{CONFIG['port']}"}
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in expected:
        return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({"detail": "拒绝跨站请求"}, status_code=403)
    if app.state.backing_up and request.method not in ('GET', 'HEAD', 'OPTIONS'):
        return JSONResponse({'detail':'正在生成备份，请稍后再操作。'}, status_code=409)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(BrainError)
async def memory_error(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=503)


def get_run(run_id):
    if run_id not in runs:
        raise HTTPException(404, "任务不存在")
    return runs[run_id]


def add_event(run, kind, title, data=None):
    run["events"].append({"kind": kind, "title": title, "at": now(), "data": data or {}})


def frame(scene, model, verification=None):
    return {
        "tick": scene.tick_count,
        "scene": scene.scene_state(),
        "graph": model.graph(),
        "verification": verification,
        "anomalies": model.anomalies(limit=30),
    }


class RunInput(BaseModel):
    scenario: str = "pursuit"
    note: str = Field(default="", max_length=1000)
    ticks: int = Field(default=18, ge=4, le=120)
    interval_ms: int = Field(default=300, ge=50, le=2000)
    save_memory: bool = True


async def execute(run, request, stop):
    try:
        if memory.status()["connected"]:
            try:
                recall = await asyncio.to_thread(memory.call, "mdcg_recall", {"query": SCENARIOS[request.scenario]["name"], "k": 5})
                add_event(run, "recall", "检索相关记忆", recall)
            except Exception as exc:
                add_event(run, "warning", "记忆检索失败，继续场景运行", {"error": str(exc)})
        else:
            add_event(run, "warning", "记忆未连接，继续场景运行", {"error": memory.error})
        scene, model = create_world(request.scenario)
        add_event(run, "scene", "创建场景 · 3 个实体", {"source": "lingshu.world.scene_simulator", "size": 24})
        run["frames"].append(frame(scene, model))
        for index in range(request.ticks):
            if stop.is_set():
                run["status"] = "cancelled"
                add_event(run, "cancelled", "任务已停止，已完成记录保留")
                break
            prediction = model.generate(horizon=1)
            if request.scenario == "perturbation" and index == request.ticks // 2:
                target = next(iter(scene.entities.values()))
                target.pos = (3.0, 1.5, 21.0)
                add_event(run, "perturbation", "注入外部扰动 · 移动游走目标", {"entity": target.id, "pos": target.pos})
            scene.step(n=1)
            observed = model.perceive(tool="workbench_observer")
            verified = model.verify()
            model.infer_patterns()
            run["frames"].append(frame(scene, model, verified))
            run["completed_ticks"] = scene.tick_count
            run["hits"] += verified["hits"]
            run["total"] += verified["total"]
            run["hit_rate"] = round(run["hits"] / run["total"], 4) if run["total"] else None
            run["anomaly_count"] = model.graph()["anomaly_count"]
            refresh(run)
            add_event(run, "tick", f"第 {scene.tick_count:02d} 步 · 预测 → 观测 → 验证", {"prediction": prediction, "observation": observed, "verification": verified})
            store.save(run)
            try:
                await asyncio.wait_for(stop.wait(), timeout=request.interval_ms / 1000)
            except asyncio.TimeoutError:
                pass
        if run["status"] in ("running", "cancelling"):
            if stop.is_set():
                run["status"] = "cancelled"
                add_event(run, "cancelled", "任务已停止，已完成记录保留")
            else:
                run["status"] = "saving"
                store.save(run)
                if request.save_memory:
                    try:
                        summary = (
                            f"工作台场景实验：{run['title']}。任务 {run['id']}；"
                            f"完成 {run['completed_ticks']} 步，"
                            f"预测验证 {run['hits']}/{run['total']}，"
                            f"命中率 {run['hit_rate']:.1%}，异常 {run['anomaly_count']} 次。"
                            f"实体：{', '.join(e.category for e in scene.entities.values())}。"
                            f"备注：{request.note or '无'}。"
                        )
                        result = await asyncio.to_thread(memory.remember, summary, ["experiment", request.scenario])
                        run["memory_id"] = result["id"]
                        add_event(run, "memory", "运行结果已写入记忆", result)
                    except Exception as exc:
                        add_event(run, "warning", "场景已完成，记忆写入失败", {"error": str(exc)})
                run["status"] = "completed"
                add_event(run, "completed", "运行完成 · 可回看全部轨迹", {"ticks": run["completed_ticks"], "hits": run["hits"], "total": run["total"]})
    except Exception as exc:
        run["status"] = "failed"
        add_event(run, "error", "运行失败", {"error": str(exc)})
    finally:
        run["finished_at"] = now()
        store.save(run)
        jobs.pop(run["id"], None)


@app.get("/api/health")
async def health():
    status = await agent_service.status()
    return {"ok": True, "version": VERSION, "world": "lingshu.world.UnifiedWorldModel", "memory": memory.status(),
            "llm": {"connected": status['ready'] and status['verified'], "configured": status['ready'], "description": status['description'], "runtime": status['transport']}}


@app.get("/api/scenarios")
async def scenarios():
    return [{"id": key, **value} for key, value in SCENARIOS.items()]


@app.post('/api/backup')
async def backup():
    if jobs or agent_service.jobs:
        raise HTTPException(409, '请先完成或停止正在运行的对话与实验，再生成备份。')
    app.state.backing_up = True
    try:
        chats, experiments = copy.deepcopy(list(agent_service.chats.values())), copy.deepcopy(list(runs.values()))
        def snapshot():
            with memory.lock:
                return create_backup(chats, experiments, DATA / 'memory')
        payload = await asyncio.to_thread(snapshot)
        return Response(payload, media_type='application/zip', headers={
            'Content-Disposition': 'attachment; filename="lingshu-data-backup.zip"', 'Cache-Control':'no-store'})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        app.state.backing_up = False


@app.get("/api/preview/{scenario}")
async def preview(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(422, "未知场景")
    scene, model = create_world(scenario)
    return frame(scene, model)


@app.post("/api/runs", status_code=201)
async def start_run(request: RunInput, http_request: Request):
    if request.scenario not in SCENARIOS:
        raise HTTPException(422, "未知场景")
    if len(jobs) >= 3:
        raise HTTPException(409, "最多同时运行 3 个任务")
    run_id = uuid.uuid4().hex[:12]
    owner_turn_id = http_request.headers.get('x-lingshu-turn-id')
    if owner_turn_id:
        agent_service.own_experiment(owner_turn_id, run_id)
    run = {
        "id": run_id, "title": SCENARIOS[request.scenario]["name"], "scenario": request.scenario,
        "note": request.note, "status": "running", "created_at": now(), "finished_at": None,
        "requested_ticks": request.ticks, "completed_ticks": 0, "hit_rate": None,
        "hits": 0, "total": 0, "anomaly_count": 0, "memory_id": None, "events": [], "frames": [],
        "owner_turn_id": owner_turn_id,
    }
    add_event(run, "start", "开始运行", request.model_dump())
    refresh(run)
    runs[run_id] = run
    store.save(run)
    stop = asyncio.Event()
    task = asyncio.create_task(execute(run, request, stop))
    jobs[run_id] = {"task": task, "stop": stop}
    return copy.deepcopy(run)


@app.get("/api/runs")
async def list_runs():
    return [{key: value for key, value in run.items() if key not in ("frames", "events")} for run in sorted(runs.values(), key=lambda r: r["created_at"], reverse=True)]


@app.get("/api/runs/{run_id}")
async def read_run(run_id: str):
    return get_run(run_id)


@app.post("/api/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = get_run(run_id)
    if run["status"] == "saving":
        raise HTTPException(409, "场景已运行完毕，正在保存记忆")
    if run_id in jobs:
        jobs[run_id]["stop"].set()
        run["status"] = "cancelling"
        # execute recognizes cancellation at its next boundary.
    return {"id": run_id, "status": run["status"]}


@app.get("/api/runs/{run_id}/export")
async def export_run(run_id: str):
    return JSONResponse(get_run(run_id), headers={"Content-Disposition": f'attachment; filename="lingshu-{run_id}.json"'})


class MemoryInput(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


@app.post("/api/memory")
async def remember(request: MemoryInput):
    if not request.content.strip():
        raise HTTPException(422, "记忆内容不能为空")
    return await asyncio.to_thread(memory.remember, request.content.strip(), ["note"])


@app.get("/api/memory")
async def recall(query: str = "工作台", limit: int = 20):
    if not 1 <= limit <= 50 or len(query) > 1000:
        raise HTTPException(422, "查询长度或数量超出范围")
    return await asyncio.to_thread(memory.call, "mdcg_recall", {"query": query or "工作台", "k": limit, "budget_tokens": 5000, "max_item_tokens": 500})


@app.post("/api/memory/reconnect")
async def reconnect():
    return await asyncio.to_thread(memory.connect)


@app.get("/api/integrations")
async def integrations():
    agent_status = await agent_service.status()
    def cordis(command, bridge):
        return (
            "- insert:\n    - id: lingshu-lab-mcp\n"
            "      name: '@deepseek-ai/dsh-mcp-client'\n      config:\n"
            "        serverName: lingshu_lab\n        transport: stdio\n"
            f"        command: {json.dumps(command, ensure_ascii=False)}\n"
            f"        args: [\"-X\", \"utf8\", {json.dumps(bridge, ensure_ascii=False)}]\n"
            f"        env:\n          LINGSHU_WORKBENCH_URL: \"http://127.0.0.1:{CONFIG['port']}\"\n"
            "        failOnStartupError: true\n"
        )
    return {
        "memory": memory.status(),
        "mcp": {"mcpServers": {"lingshu-workbench": {
            "command": sys.executable,
            "args": ["-X", "utf8", str(BASE / "mcp_bridge.py")],
            "env": {"LINGSHU_WORKBENCH_URL": f"http://127.0.0.1:{CONFIG['port']}"},
        }}},
        "tools": ["lingshu_list_scenarios", "lingshu_run_scene", "lingshu_get_run", "lingshu_cancel_run", "lingshu_recall", "lingshu_remember"],
        "dsh": {"status": "ready" if agent_status['ready'] else "unconfigured", "ready": agent_status['ready'], "verified": agent_status['verified'], "runtime_version": agent_status['version'],
                "cordis_patch": cordis(sys.executable, str(BASE / "mcp_bridge.py")),
                "public_patch": cordis("<本机 Python 可执行文件>", "<实验台目录>/mcp_bridge.py"),
                "note": "桌面首页已接入真实 Harness 会话。可对话、续聊、停止，查看实验调用和独立记忆召回。其他客户端可使用以下配置。"},
    }


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE / "static" / "index.html", headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=CONFIG["host"], port=CONFIG["port"], log_level="info")
