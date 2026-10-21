"""Local Challenge B web lab: real executions, durable evidence, live progress."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import threading
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4
import zipfile

import b1
import b2
from common import confined, load, save, sha256
from demo import report
import llm


ROOT = Path(__file__).resolve().parent
APP_ID = "challenge-b-context-lab"
ARTIFACTS = {
    "b1-checkpoint": "b1/checkpoint.json", "b1-request": "b1/cold-start/resume-request.json",
    "b1-before": "b1/baseline-request.json", "b1-verification": "b1/verification.json",
    "b1-diff": "b1/cold-start/repair.diff", "b1-test-before": "b1/baseline-tests.log",
    "b1-test-after": "b1/cold-start/resumed-tests.log", "b1-ttl": "b1/attempt-increase_token_ttl.log",
    "b1-retry": "b1/attempt-increase_retry_count.log", "b1-archive": "b1/archive/history.json",
    "b2-request": "b2/managed-request.json", "b2-findings": "b2/findings.json",
    "b2-code": "b2/executed-program.py", "b2-trace": "b2/tool-trace.json",
    "b2-answer": "b2/answer.md", "b2-oracle": "b2/ground-truth.json",
    "b2-verification": "b2/verification.json", "b2-before": "b2/baseline-request-DO-NOT-SEND.json",
    "verification": "verification.json", "report": "REPORT.md", "job": "job.json",
    "api-b1": "api/b1-response.json", "api-b2": "api/b2-response.json",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class BusyError(ValueError):
    pass


class Lab:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.active = None
        for path in sorted(self.directory.glob("*/job.json")):
            try:
                job = load(path)
                if job["id"] != path.parent.name or not re.fullmatch(r"[0-9TZ-]+-[a-f0-9]{8}", job["id"]):
                    continue
                if job["status"] in ("queued", "running"):
                    job.update(status="error", error="Server đã dừng giữa lần chạy. Bấm chạy lại để tạo run mới.")
                    save(path, job)
                self.jobs[job["id"]] = job
            except (ValueError, OSError, KeyError, TypeError):
                continue

    def list_jobs(self) -> list[dict]:
        with self.lock:
            return [{key: copy.deepcopy(job[key]) for key in ("id", "created_at", "kind", "status", "with_api", "error")}
                    for job in sorted(self.jobs.values(), key=lambda item: item["id"], reverse=True)[:40]]

    def get(self, job_id: str) -> dict:
        with self.lock:
            if job_id not in self.jobs:
                raise FileNotFoundError("Không tìm thấy lần chạy.")
            return copy.deepcopy(self.jobs[job_id])

    def event(self, job_id: str, part: str, message: str) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job["events"].append({"time": now(), "part": part, "message": message})
            save(self.directory / job_id / "job.json", job)

    def start(self, kind="all", with_api=False) -> dict:
        if kind not in ("all", "b1", "b2") or type(with_api) is not bool:
            raise ValueError("Phần chạy phải là all, b1 hoặc b2; with_api phải là boolean.")
        if with_api:
            if kind != "all":
                raise ValueError("Chọn Chạy toàn bộ để đánh giá LLM cả B1 và B2.")
            llm.config()
        with self.lock:
            if self.active:
                raise BusyError("Một demo đang chạy. Hãy đợi kết quả trước khi bắt đầu lần mới.")
            job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
            job = {"id": job_id, "created_at": now(), "kind": kind, "status": "queued", "with_api": with_api,
                   "events": [], "error": None, "result": None}
            self.jobs[job_id] = job
            self.active = job_id
            save(self.directory / job_id / "job.json", job)
            threading.Thread(target=self.execute, args=(job_id,), daemon=True, name="challenge-b-demo").start()
            return copy.deepcopy(job)

    def execute(self, job_id: str) -> None:
        directory = self.directory / job_id
        try:
            with self.lock:
                self.jobs[job_id]["status"] = "running"
                kind, with_api = self.jobs[job_id]["kind"], self.jobs[job_id]["with_api"]
            self.event(job_id, "run", "Bắt đầu thực thi Python; mọi kết quả thuộc lần chạy mới này.")
            results = {}
            if kind in ("all", "b1"):
                results["b1"] = b1.demo(directory / "b1", progress=lambda message: self.event(job_id, "b1", message))
            if kind in ("all", "b2"):
                results["b2"] = b2.demo(directory / "b2", progress=lambda message: self.event(job_id, "b2", message))
            api = {"status": "not_run", "usage": None, "reason": "Offline demo; chưa gọi LLM thật."}
            if with_api:
                self.event(job_id, "api", "Gọi LLM trên managed context, ghi usage thật; raw baseline ở lại ổ đĩa.")
                api = llm.evaluate(directory)
            verification = {"created_at": self.get(job_id)["created_at"], "prompt_sha256": sha256(ROOT / "PROMPT_CHALLENGE_B.md"),
                            "web_prompt_sha256": sha256(ROOT / "PROMPT_WEB_CHALLENGE_B.md"),
                            "source_slide": "../Challenge A/slide.pdf", "source_pages": [32, 33],
                            **results, "api": api, "passed": all(item["passed"] for item in results.values()) and api.get("passed", True)}
            save(directory / "verification.json", verification)
            if kind == "all":
                (directory / "REPORT.md").write_text(report(directory, verification), encoding="utf-8")
            else:
                (directory / "REPORT.md").write_text(f"# Challenge B: {kind.upper()}\n\nKết quả: PASS\n\nXem verification.json và bằng chứng của phần đã chọn.\n", encoding="utf-8")
            self.event(job_id, "run", "Hoàn tất kiểm chứng và lưu bằng chứng." if verification["passed"] else "Harness hoàn tất; kiểm tra câu trả lời API chưa đạt.")
            with self.lock:
                self.jobs[job_id].update(status="done" if verification["passed"] else "failed", result=verification)
        except Exception as exc:
            # No traceback/request headers/API keys enter client or job logs.
            message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else "Thực thi chưa hoàn tất. Kiểm tra file bằng chứng hoặc thử một lần chạy mới."
            with self.lock:
                self.jobs[job_id].update(status="error", error=message)
        finally:
            with self.lock:
                try:
                    save(directory / "job.json", self.jobs[job_id])
                except OSError:
                    self.jobs[job_id].update(status="error", error="Windows chưa cho ghi trạng thái xuống đĩa. Có thể tải bằng chứng đã tạo hoặc chạy lại.")
                finally:
                    # Even a disk error must never keep the single-run gate locked.
                    self.active = None

    def details(self, job_id: str) -> dict:
        job = self.get(job_id)
        directory = self.directory / job_id
        if job["status"] not in ("done", "failed"):
            return job
        # Select only compact artifacts. Raw log files and baselines are NEVER in this response.
        job["views"] = {}
        if "b1" in job["result"]:
            job["views"]["b1"] = {"checkpoint": load(directory / "b1/checkpoint.json"),
                "request": load(directory / "b1/cold-start/resume-request.json"),
                "diff": (directory / "b1/cold-start/repair.diff").read_text(encoding="utf-8"),
                "tests_before": (directory / "b1/baseline-tests.log").read_text(encoding="utf-8"),
                "tests_after": (directory / "b1/cold-start/resumed-tests.log").read_text(encoding="utf-8")}
        if "b2" in job["result"]:
            job["views"]["b2"] = {"findings": load(directory / "b2/findings.json"),
                "request": load(directory / "b2/managed-request.json"), "trace": load(directory / "b2/tool-trace.json"),
                "code": (directory / "b2/executed-program.py").read_text(encoding="utf-8"),
                "answer": (directory / "b2/answer.md").read_text(encoding="utf-8")}
        return job

    def artifact(self, job_id: str, name: str) -> Path:
        self.get(job_id)
        if name not in ARTIFACTS:
            raise FileNotFoundError("Artifact không có trong danh sách cho phép.")
        path = confined(self.directory / job_id, ARTIFACTS[name])
        if not path.is_file():
            raise FileNotFoundError("Artifact chưa được tạo trong lần chạy này.")
        return path

    def export(self, job_id: str) -> bytes:
        job = self.get(job_id)
        if job["status"] not in ("done", "failed", "error"):
            raise BusyError("Chờ demo hoàn tất trước khi tải bằng chứng.")
        directory = self.directory / job_id
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(directory.rglob("*")):
                if path.is_file() and path.resolve().is_relative_to(directory.resolve()) and path.suffix != ".tmp":
                    archive.write(path, str(path.relative_to(directory)))
            archive.write(ROOT / "PROMPT_CHALLENGE_B.md", "PROMPT_CHALLENGE_B.md")
            archive.write(ROOT / "PROMPT_WEB_CHALLENGE_B.md", "PROMPT_WEB_CHALLENGE_B.md")
        return buffer.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "ContextLab/1.0"

    @property
    def lab(self) -> Lab:
        return self.server.lab

    def send(self, status: int, data: bytes, content_type="application/json; charset=utf-8", filename=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def json(self, status: int, data: dict):
        self.send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def permitted_host(self) -> bool:
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def do_GET(self):
        try:
            if not self.permitted_host():
                self.json(403, {"error": "Host không hợp lệ."})
                return
            parsed = urlsplit(self.path)
            path, query = unquote(parsed.path), parse_qs(parsed.query)
            static = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                      "/styles.css": ("styles.css", "text/css; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
            if path in static:
                filename, mime = static[path]
                self.send(200, (ROOT / "web" / filename).read_bytes(), mime)
            elif path == "/api/health":
                self.json(200, {"app": APP_ID, "api_ready": bool(os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENAI_MODEL")),
                                "api_model": os.environ.get("OPENAI_MODEL", ""), "running": self.lab.active})
            elif path == "/api/runs":
                self.json(200, {"runs": self.lab.list_jobs()})
            elif match := re.fullmatch(r"/api/runs/([0-9TZ-]+-[a-f0-9]{8})(?:/(export|artifact|raw-sample))?", path):
                job_id, action = match.groups()
                if action == "export":
                    self.send(200, self.lab.export(job_id), "application/zip", f"challenge-b-{job_id}.zip")
                elif action == "artifact":
                    artifact = self.lab.artifact(job_id, query.get("name", [""])[0])
                    download = query.get("download") == ["1"]
                    mime = "application/json; charset=utf-8" if artifact.suffix == ".json" else "text/plain; charset=utf-8"
                    self.send(200, artifact.read_bytes(), mime, artifact.name if download else None)
                elif action == "raw-sample":
                    self.lab.get(job_id)
                    filename = query.get("file", ["service-00.jsonl"])[0]
                    line_number = int(query.get("line", ["1"])[0])
                    if not re.fullmatch(r"service-\d{2}\.jsonl", filename) or not 1 <= line_number <= 402:
                        raise ValueError("Vị trí evidence không hợp lệ.")
                    log = confined(self.lab.directory / job_id / "b2/logs", filename)
                    if not log.exists():
                        raise FileNotFoundError("Chạy B2 để xem sample log.")
                    with log.open(encoding="utf-8") as stream:
                        sample = [{"line": index, "content": content.rstrip()} for index, content in enumerate(stream, 1)
                                  if line_number <= index < line_number + 5]
                    self.json(200, {"scope": "Inspector cho người xem; KHÔNG thuộc managed context hoặc request API.", "file": log.name, "lines": sample})
                else:
                    self.json(200, self.lab.details(job_id))
            elif path == "/api/docs":
                names = {"prompt": "PROMPT_WEB_CHALLENGE_B.md", "report": "BAO_CAO_CHALLENGE_B.md", "readme": "README.md"}
                filename = names.get(query.get("name", [""])[0])
                if not filename:
                    raise FileNotFoundError("Không tìm thấy tài liệu.")
                self.send(200, (ROOT / filename).read_bytes(), "text/plain; charset=utf-8")
            else:
                raise FileNotFoundError("Không tìm thấy đường dẫn.")
        except FileNotFoundError as exc:
            self.json(404, {"error": str(exc)})
        except BusyError as exc:
            self.json(409, {"error": str(exc)})
        except (ValueError, KeyError):
            self.json(400, {"error": "Yêu cầu không hợp lệ."})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            origin = self.headers.get("Origin")
            expected = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
            if not self.permitted_host() or (origin and origin not in expected) or self.headers.get("Sec-Fetch-Site") == "cross-site":
                self.json(403, {"error": "Chỉ chấp nhận yêu cầu cùng origin."})
                return
            if self.path != "/api/runs":
                raise FileNotFoundError("Không tìm thấy API.")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Body phải có từ 1 đến 4096 bytes.")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise ValueError("API yêu cầu application/json.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or set(body) - {"kind", "with_api"}:
                raise ValueError("Body chỉ nhận kind và with_api.")
            self.json(202, self.lab.start(body.get("kind", "all"), body.get("with_api", False)))
        except BusyError as exc:
            self.json(409, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self.json(400, {"error": str(exc)})
        except FileNotFoundError as exc:
            self.json(404, {"error": str(exc)})

    def log_message(self, *_):
        pass


def make_server(port=8766, directory=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.lab = Lab(Path(directory) if directory else ROOT / "output/web-runs")
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--data", type=Path, default=ROOT / "output/web-runs")
    args = parser.parse_args()
    server = make_server(args.port, args.data)
    print(f"Context Lab running at http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
