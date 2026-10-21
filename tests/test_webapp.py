"""HTTP integration tests against a real server and the real B1/B2 engines."""
from __future__ import annotations

import http.client
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import encode, load, save
from webapp import APP_ID, Lab, make_server
import b1
import b2

TEMP = ROOT / "tmp" / "web-tests"
TEMP.mkdir(parents=True, exist_ok=True)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=TEMP)
        cls.data = Path(cls.temp.name) / "runs"
        cls.server = make_server(0, cls.data)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        deadline = time.monotonic() + 10
        while cls.server.lab.active and time.monotonic() < deadline:
            time.sleep(.05)
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()

    def http(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=15)
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        data = json.dumps(body).encode() if body is not None else None
        connection.request(method, path, data, request_headers)
        response = connection.getresponse()
        payload, status, response_headers = response.read(), response.status, dict(response.getheaders())
        connection.close()
        if response_headers.get("Content-Type", "").startswith("application/json"):
            payload = json.loads(payload)
        return status, payload, response_headers

    def run_demo(self, kind):
        status, job, _ = self.http("POST", "/api/runs", {"kind": kind})
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status, current, _ = self.http("GET", "/api/runs/" + job["id"])
            if current["status"] not in ("queued", "running"):
                self.assertEqual(current["status"], "done", current.get("error"))
                return current
            time.sleep(.03)
        self.fail("Web demo timed out")

    def test_static_health_and_no_secret_configuration(self):
        status, health, _ = self.http("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["app"], APP_ID)
        self.assertNotIn("api_key", health)
        for path in ("/", "/styles.css", "/app.js", "/favicon.svg"):
            with self.subTest(path=path):
                status, data, headers = self.http("GET", path)
                self.assertEqual(status, 200)
                self.assertTrue(data)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_all_demo_contexts_progress_downloads_and_restart(self):
        job = self.run_demo("all")
        self.assertTrue(job["result"]["passed"])
        self.assertGreaterEqual(len(job["events"]), 12)
        self.assertIn("b1", job["views"])
        self.assertIn("b2", job["views"])
        self.assertNotIn(b1.RAW_MARKER, encode(job))
        self.assertNotIn(b2.RAW_MARKER, encode(job))
        for part in ("b1", "b2"):
            context = job["views"][part]["request"]
            self.assertEqual(len(context["input"]), 2)
        route = "/api/runs/" + job["id"]
        status, artifact, _ = self.http("GET", route + "/artifact?name=b1-test-after")
        self.assertEqual(status, 200)
        self.assertIn(b"Ran 4 tests", artifact)
        status, artifact, _ = self.http("GET", route + "/artifact?name=verification&download=1")
        self.assertEqual(status, 200)
        self.assertTrue(artifact["passed"])
        status, archive, headers = self.http("GET", route + "/export")
        self.assertEqual(status, 200)
        self.assertIn("attachment", headers["Content-Disposition"])
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            self.assertIn("b1/checkpoint.json", zipped.namelist())
            self.assertIn("b2/logs/service-23.jsonl", zipped.namelist())
            self.assertIn("PROMPT_WEB_CHALLENGE_B.md", zipped.namelist())
        status, sample, _ = self.http("GET", route + "/raw-sample?file=service-00.jsonl&line=44")
        self.assertEqual(sample["lines"][0]["line"], 44)
        self.assertIn(b2.RAW_MARKER, sample["lines"][0]["content"])
        # Fetching human evidence must not mutate the stored model request.
        status, context, _ = self.http("GET", route + "/artifact?name=b2-request")
        self.assertNotIn(b2.RAW_MARKER, encode(context))
        reloaded = Lab(self.data)
        self.assertEqual(reloaded.get(job["id"])["status"], "done")
        self.assertTrue(reloaded.details(job["id"])["result"]["passed"])

    def test_b1_only_executes_cold_resume(self):
        job = self.run_demo("b1")
        self.assertIn("b1", job["result"])
        self.assertNotIn("b2", job["result"])
        self.assertEqual(job["result"]["b1"]["resume"]["test_returncode"], 0)

    def test_b2_only_executes_code_runtime(self):
        job = self.run_demo("b2")
        self.assertIn("b2", job["result"])
        self.assertNotIn("b1", job["result"])
        self.assertEqual(job["views"]["b2"]["findings"]["error_records"], 960)

    def test_invalid_requests_and_unknown_fields(self):
        for body in ({"kind": "shell"}, {"with_api": "false"}, {"code": "print(1)"}, [], {"kind": "b1", "with_api": True}):
            with self.subTest(body=body):
                status, _, _ = self.http("POST", "/api/runs", body)
                self.assertEqual(status, 400)

    def test_api_mode_requires_explicit_configuration(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "OPENAI_MODEL": ""}):
            status, data, _ = self.http("POST", "/api/runs", {"kind": "all", "with_api": True})
        self.assertEqual(status, 400)
        self.assertIn("OPENAI_API_KEY", data["error"])

    def test_cross_origin_and_foreign_host_rejected(self):
        status, _, _ = self.http("POST", "/api/runs", {"kind": "all"}, {"Origin": "https://external.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.http("GET", "/api/health", headers={"Host": "external.example"})
        self.assertEqual(status, 403)

    def test_concurrent_run_is_rejected(self):
        with self.server.lab.lock:
            self.server.lab.active = "occupied"
        try:
            status, _, _ = self.http("POST", "/api/runs", {"kind": "all"})
            self.assertEqual(status, 409)
        finally:
            with self.server.lab.lock:
                self.server.lab.active = None

    def test_private_files_and_traversal_are_not_served(self):
        for path in ("/webapp.py", "/../Challenge%20A/data/web-chat.sqlite3", "/api/runs/unknown", "/api/docs?name=../webapp.py"):
            with self.subTest(path=path):
                self.assertEqual(self.http("GET", path)[0], 404)

    def test_interrupted_job_is_recoverable_after_restart(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            base = Path(folder)
            job_id = "20261021T000000Z-1234abcd"
            save(base / job_id / "job.json", {"id": job_id, "status": "running", "created_at": "now",
                 "kind": "all", "with_api": False, "events": [], "error": None})
            lab = Lab(base)
            self.assertEqual(lab.get(job_id)["status"], "error")
            self.assertIn("Server", lab.get(job_id)["error"])
            self.assertIsNone(lab.active)

    def test_worker_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            lab = Lab(Path(folder))
            with patch("webapp.b1.demo", side_effect=RuntimeError("fixture failed")):
                job = lab.start("b1")
                deadline = time.monotonic() + 3
                while lab.active and time.monotonic() < deadline:
                    time.sleep(.02)
            self.assertEqual(lab.get(job["id"])["status"], "error")
            self.assertIsNone(lab.get(job["id"])["result"])
            self.assertEqual(lab.get(job["id"])["error"], "fixture failed")

    def test_atomic_save_retries_transient_windows_lock(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            path = Path(folder) / "state.json"
            save(path, {"old": True})
            real_replace = Path.replace
            attempts = []
            def transient(source, target):
                attempts.append(1)
                if len(attempts) < 3:
                    raise PermissionError("temporary Windows sharing lock")
                return real_replace(source, target)
            with patch.object(Path, "replace", transient), patch("common.time.sleep"):
                save(path, {"new": True})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(load(path), {"new": True})

    def test_persistent_save_failure_releases_run_gate(self):
        with tempfile.TemporaryDirectory(dir=TEMP) as folder:
            lab = Lab(Path(folder))
            job_id = "20261021T000000Z-1234abcd"
            lab.jobs[job_id] = {"id": job_id, "created_at": "now", "kind": "b1", "status": "queued",
                "with_api": False, "events": [], "error": None, "result": None}
            lab.active = job_id
            with patch("webapp.save", side_effect=PermissionError("persistent lock")):
                lab.execute(job_id)
            self.assertIsNone(lab.active)
            self.assertEqual(lab.get(job_id)["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
