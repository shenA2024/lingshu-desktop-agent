"""Integration checks against pinned official engines, in a disposable data root."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from unittest.mock import AsyncMock
from urllib.error import HTTPError
from io import BytesIO
from contextlib import closing
import sqlite3
import zipfile
from data_backup import restore_backup

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
TEST_DATA = tempfile.TemporaryDirectory(prefix="lingshu-workbench-tests-")
os.environ["LINGSHU_WORKBENCH_DATA"] = TEST_DATA.name
from fastapi.testclient import TestClient
import workbench
import mcp_bridge


class WorkbenchIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(workbench.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        TEST_DATA.cleanup()

    def run_scene(self, scenario, ticks=8, save=False):
        response = self.client.post("/api/runs", json={"scenario": scenario, "ticks": ticks, "interval_ms": 50, "save_memory": save})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def finish(self, run_id):
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            run = self.client.get("/api/runs/" + run_id).json()
            if run["status"] not in ("running", "saving", "cancelling"):
                return run
            time.sleep(0.06)
        self.fail("Task did not finish")

    def test_world_predictions_use_actual_observations(self):
        run = self.finish(self.run_scene("pursuit"))
        self.assertEqual(run["status"], "completed")
        self.assertEqual(len(run["frames"]), 9)
        totals, hits = 0, 0
        for frame in run["frames"][1:]:
            verification = frame["verification"]
            for detail in verification["details"]:
                self.assertEqual(detail["actual"], frame["scene"]["entities"][detail["entity"]]["pos"])
                self.assertAlmostEqual(detail["distance"], math.dist(detail["predicted"], detail["actual"]), places=3)
                self.assertEqual(detail["hit"], math.dist(detail["predicted"], detail["actual"]) < detail["bound"])
            totals += verification["total"]
            hits += verification["hits"]
        self.assertEqual(run["total"], totals)
        self.assertEqual(run["hits"], hits)
        self.assertEqual(totals, 24)
        statistics = run["statistics"]
        self.assertEqual(statistics["verified"], totals)
        self.assertEqual(statistics["hits"], hits)
        self.assertEqual(sum(g["verified"] for g in statistics["groups"]), totals)
        for group in statistics["groups"]:
            details = [d for f in run["frames"][1:] for d in f["verification"]["details"] if d["mode"] == group["mode"]]
            self.assertAlmostEqual(group["mean_distance"], sum(d["distance"] for d in details) / len(details), places=3)
            self.assertAlmostEqual(group["mean_bound"], sum(d["bound"] for d in details) / len(details), places=3)

    def test_perturbation_is_reported_as_prediction_failure(self):
        run = self.finish(self.run_scene("perturbation"))
        changed = run["frames"][5]
        self.assertGreaterEqual(changed["graph"]["anomaly_count"], 1)
        self.assertLess(changed["verification"]["hits"], changed["verification"]["total"])
        self.assertTrue(any(e["kind"] == "perturbation" for e in run["events"]))

    def test_avoidance_moves_away_from_obstacle(self):
        run = self.finish(self.run_scene("avoidance"))
        initial, final = run["frames"][0]["scene"]["entities"], run["frames"][-1]["scene"]["entities"]
        obstacle = next(e for e in initial.values() if e["category"] == "障碍物")["pos"]
        for eid, entity in initial.items():
            if entity["category"] != "障碍物":
                self.assertGreater(math.dist(final[eid]["pos"], obstacle), math.dist(entity["pos"], obstacle))

    def test_backup_restores_real_memory_notes_and_history_without_secrets(self):
        chat = self.client.post('/api/agent/chats').json()
        self.client.patch('/api/agent/chats/'+chat['id'], json={'title':'Backup R602'})
        self.client.post('/api/memory', json={'content':'R602 备份恢复测试笔记'})
        response = self.client.post('/api/backup')
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else '')
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            names = archive.namelist()
            self.assertTrue(any(name.startswith('memory/') for name in names))
            self.assertFalse(any('key.dpapi' in name or '_tokens' in name or 'harness-home' in name for name in names))
        restored = Path(TEST_DATA.name)/'backup-restored'
        restore_backup(BytesIO(response.content), restored)
        with closing(sqlite3.connect(restored/'agent/chats.sqlite')) as db:
            record = json.loads(db.execute('SELECT data FROM chats WHERE id=?',(chat['id'],)).fetchone()[0])
        self.assertTrue(record['read_only'])
        recovered_memory = workbench.Memory()
        with patch.object(workbench,'DATA',restored):
            try:
                self.assertTrue(recovered_memory.connect()['connected'])
                result = recovered_memory.call('mdcg_recall',{'query':'R602','k':10})
                self.assertTrue(any('R602' in item['content'] for item in result['pack']),result)
            finally:
                recovered_memory.close()

    def test_backup_requires_idle_and_body_search_and_delete_work(self):
        run_id = self.run_scene('pursuit',ticks=120)
        self.assertEqual(self.client.post('/api/backup').status_code,409)
        self.client.post('/api/runs/'+run_id+'/cancel'); self.finish(run_id)
        service = workbench.agent_service
        fixture = Path(TEST_DATA.name)/'search-fixture.py'
        fixture.write_text('import sys,json; sys.stdin.buffer.read(); print(json.dumps({"type":"final","text":"unique-body-Q650"}))','utf-8')
        with patch.object(service,'status',AsyncMock(return_value={'ready':True})), \
             patch.object(service,'command',lambda args:[sys.executable,str(fixture)]):
            chat = self.client.post('/api/agent/chats').json()
            self.client.post(f"/api/agent/chats/{chat['id']}/messages",json={'content':'hello','request_id':'search-test-0001'})
            self.client.patch('/api/agent/chats/'+chat['id'],json={'title':'name without query'})
            for _ in range(100):
                if self.client.get('/api/agent/chats/'+chat['id']).json()['turns'][-1]['status']=='completed':
                    break
                time.sleep(.03)
            found = self.client.get('/api/agent/chats',params={'query':'Q650'}).json()
            self.assertEqual([item['id'] for item in found],[chat['id']])
            self.assertEqual(self.client.delete('/api/agent/chats/'+chat['id']).status_code,200)
            self.assertEqual(self.client.get('/api/agent/chats/'+chat['id']).status_code,404)

    def test_cancel_retains_partial_history_without_memory_write(self):
        run_id = self.run_scene("pursuit", ticks=120, save=True)
        time.sleep(0.17)
        response = self.client.post("/api/runs/" + run_id + "/cancel")
        self.assertEqual(response.status_code, 200)
        run = self.finish(run_id)
        self.assertEqual(run["status"], "cancelled")
        self.assertGreater(run["completed_ticks"], 0)
        self.assertLess(run["completed_ticks"], 120)
        self.assertIsNone(run["memory_id"])
        self.assertEqual(len(run["frames"]), run["completed_ticks"] + 1)
        exported = self.client.get("/api/runs/" + run_id + "/export")
        self.assertEqual(exported.json(), run)
        self.assertIn(run_id, exported.headers["content-disposition"])

    def test_memory_roundtrip_and_connection_recovery(self):
        health = self.client.get("/api/health").json()
        self.assertTrue(health["memory"]["connected"], health["memory"])
        self.assertFalse(health["llm"]["connected"])
        text = "工作台回归笔记：星际避让测例 Q791 的真实结果需要保留并召回。"
        result = self.client.post("/api/memory", json={"content": text})
        self.assertEqual(result.status_code, 200, result.text)
        node_id = result.json()["id"]
        memory = self.client.get("/api/memory", params={"query": "Q791"}).json()
        self.assertTrue(any(item["id"] == node_id and text in item["content"] for item in memory["pack"]))
        workbench.memory.agent.store.client._p.kill()
        workbench.memory.agent.store.client._p.wait(timeout=3)
        self.assertEqual(self.client.get("/api/memory").status_code, 503)
        recovered = self.client.post("/api/memory/reconnect").json()
        self.assertTrue(recovered["connected"], recovered)
        after = self.client.get("/api/memory", params={"query": "Q791"}).json()
        self.assertTrue(any(item["id"] == node_id for item in after["pack"]))
        run = self.finish(self.run_scene("avoidance", save=True))
        self.assertIsNotNone(run["memory_id"])

    def test_store_recovers_active_run_as_interrupted(self):
        sample = self.finish(self.run_scene("pursuit"))
        sample = json.loads(json.dumps(sample))
        sample["id"] = "restart-fixture"
        sample["status"] = "running"
        workbench.store.save(sample)
        restored = workbench.store.load()
        self.assertEqual(restored["restart-fixture"]["status"], "interrupted")
        self.assertEqual(restored["restart-fixture"]["frames"], sample["frames"])
        self.assertEqual(restored["restart-fixture"]["events"][-1]["kind"], "interrupted")

    def test_invalid_parameters_and_cross_site_writes(self):
        for payload in ({"scenario": "unknown"}, {"ticks": 0}, {"ticks": 10000}, {"note": "x" * 1001}):
            self.assertEqual(self.client.post("/api/runs", json=payload).status_code, 422)
        self.assertEqual(self.client.post("/api/memory", json={"content": " "}).status_code, 422)
        self.assertEqual(self.client.post("/api/runs", json={}, headers={"Origin": "https://unrelated.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/health", headers={"Host": "unrelated.example:8787"}).status_code, 403)
        self.assertEqual(self.client.get("/api/runs/does-not-exist").status_code, 404)

    def test_mcp_contract_and_bad_requests_do_not_crash(self):
        reply = mcp_bridge.respond({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(reply["result"]["serverInfo"]["name"], "lingshu-world-model-lab")
        tools = mcp_bridge.respond({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertEqual(len(tools["result"]["tools"]), 6)
        self.assertEqual(mcp_bridge.respond([])["error"]["code"], -32600)
        bad = mcp_bridge.respond({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "lingshu_run_scene", "arguments": {"scenario": "pursuit", "ticks": True}}})
        self.assertTrue(bad["result"]["isError"])
        self.assertEqual(mcp_bridge.respond({"jsonrpc": "2.0", "id": 4, "method": "ping"})["result"], {})

    def test_unobserved_prediction_remains_pending(self):
        from metrics import summarize
        scene, model = workbench.create_world("pursuit")
        prediction = model.generate()
        scene.step(); model.perceive()
        missing = next(iter(prediction["predictions"]))
        model._obs_snapshot.pop(missing)
        verification = model.verify()
        detail = next(d for d in verification["details"] if d["entity"] == missing)
        self.assertEqual(detail["status"], "pending")
        self.assertIsNone(detail["actual"])
        self.assertIsNone(detail["hit"])
        self.assertEqual(verification["total"], 2)
        stats = summarize([verification])
        self.assertEqual((stats["verified"], stats["pending"]), (2, 1))

    def test_mcp_http_error_preserves_detail_and_protocol(self):
        for status, detail in [(404, "任务不存在"), (422, [{"loc": ["body", "ticks"], "msg": "too small"}])]:
            error = HTTPError("http://127.0.0.1:8787/api/runs/missing", status, "error", {}, BytesIO(json.dumps({"detail": detail}).encode()))
            with patch.object(mcp_bridge, "urlopen", side_effect=error):
                reply = mcp_bridge.respond({"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "lingshu_get_run", "arguments": {"id": "missing"}}})
            self.assertEqual(reply["id"], 8)
            self.assertTrue(reply["result"]["isError"])
            self.assertEqual(json.loads(reply["result"]["content"][0]["text"]), {"status": status, "detail": detail})

    def test_stop_before_tool_result_cancels_owned_run_and_rejects_late_creation(self):
        service = workbench.agent_service
        fixture = Path(TEST_DATA.name) / 'owner-fixture.py'
        fixture.write_text('import sys,time; sys.stdin.buffer.read(); time.sleep(90)', 'utf-8')
        with patch.object(service, 'status', AsyncMock(return_value={'ready':True})), \
             patch.object(service, 'command', lambda args: [sys.executable, '-X', 'utf8', str(fixture)]):
            chat = self.client.post('/api/agent/chats').json()
            turn = self.client.post(f"/api/agent/chats/{chat['id']}/messages", json={
                'content':'run owner fixture','request_id':'owner-test-0001'}).json()
            headers = {'X-Lingshu-Turn-Id':turn['id']}
            manual = self.run_scene('pursuit', ticks=120)
            response = self.client.post('/api/runs', headers=headers,
                json={'scenario':'perturbation','ticks':120,'interval_ms':150,'save_memory':False})
            self.assertEqual(response.status_code, 201, response.text)
            owned = response.json()['id']
            recorded = self.client.get(f"/api/agent/chats/{chat['id']}").json()['turns'][-1]
            self.assertIn(owned, recorded['run_ids'])
            self.assertEqual(recorded['events'], [], 'No tool_result was delivered')
            self.client.post(f"/api/agent/chats/{chat['id']}/stop")
            late = self.client.post('/api/runs', headers=headers, json={'scenario':'pursuit'})
            self.assertEqual(late.status_code, 409, late.text)
            self.assertEqual(self.finish(owned)['status'], 'cancelled')
            self.assertEqual(self.client.get('/api/runs/'+manual).json()['status'], 'running')
            self.client.post('/api/runs/'+manual+'/cancel')
            self.finish(manual)

    def test_mcp_transmits_turn_ownership_without_exposing_it_to_model_schema(self):
        with patch.dict(os.environ, {'LINGSHU_AGENT_TURN_ID':'turn-fixture'}), \
             patch.object(mcp_bridge, 'urlopen') as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{}'
            mcp_bridge.http('/api/runs', {'scenario':'pursuit'})
            request = opened.call_args.args[0]
            self.assertEqual(request.get_header('X-lingshu-turn-id'), 'turn-fixture')
        spec = next(t for t in mcp_bridge.TOOLS if t['name']=='lingshu_run_scene')
        self.assertNotIn('owner_turn_id', spec['inputSchema']['properties'])


if __name__ == "__main__":
    unittest.main(verbosity=2)
