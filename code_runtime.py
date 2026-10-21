"""Local Code Mode tools SDK and approved-code execution. NOT a security sandbox."""
from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import sys

from common import confined, encode, load, save, sha256


ROOT = Path(__file__).resolve().parent
APPROVED = ROOT / "programs" / "analyze_logs.py"
MAX_OUTPUT_BYTES = 12000


class LogTools:
    def __init__(self, root: Path, *, max_files=128, max_file_bytes=4_000_000,
                 max_total_bytes=64_000_000, max_records=200_000, max_line_bytes=8192):
        self.root = root.resolve()
        self.max_files, self.max_file_bytes = max_files, max_file_bytes
        self.max_total_bytes, self.max_records = max_total_bytes, max_records
        self.max_line_bytes = max_line_bytes
        self.trace = []
        self.records = 0
        self.bytes_read = 0

    def list_files(self, pattern: str) -> list[str]:
        if pattern != "*.jsonl":
            raise ValueError("Only root-level *.jsonl is allowed")
        paths = sorted(self.root.glob(pattern))
        if len(paths) > self.max_files:
            raise ValueError("File count exceeds limit")
        names = []
        for path in paths:
            resolved = confined(self.root, path.name)
            if not resolved.is_file() or resolved.stat().st_size > self.max_file_bytes:
                raise ValueError("Invalid/oversized log file")
            names.append(path.name)
        self.trace.append({"tool": "list_files", "matched_files": len(names)})
        return names

    def read_lines(self, filename: str):
        path = confined(self.root, filename)
        if path.suffix != ".jsonl" or not path.is_file() or path.stat().st_size > self.max_file_bytes:
            raise ValueError("Invalid/oversized log file")
        entry = {"tool": "read_lines", "file": filename, "lines": 0, "bytes": 0}
        self.trace.append(entry)
        with path.open("rb") as stream:
            while True:
                raw = stream.readline(self.max_line_bytes + 1)
                if not raw:
                    break
                if len(raw) > self.max_line_bytes:
                    raise ValueError("Log line exceeds limit")
                self.records += 1
                self.bytes_read += len(raw)
                if self.records > self.max_records or self.bytes_read > self.max_total_bytes:
                    raise ValueError("Runtime data budget exceeded")
                entry["lines"] += 1
                entry["bytes"] += len(raw)
                yield entry["lines"], raw.decode("utf-8", errors="replace")


def execute_approved(root: Path, program: Path, trace_path: Path) -> dict:
    code = program.read_text(encoding="utf-8")
    if code != APPROVED.read_text(encoding="utf-8"):
        raise ValueError("Only the reviewed analyze_logs.py program is executable")
    sdk = LogTools(root)
    namespace = {"tools": sdk, "__name__": "code_mode_program"}
    # Approved program must not print. Raw/intermediate stdout never reaches the agent.
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        exec(compile(code, str(program), "exec"), namespace)
    if captured.getvalue():
        raise ValueError("Code Mode program printed intermediate output")
    result = namespace.get("result")
    if not isinstance(result, dict) or len(encode(result).encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ValueError("Final result exceeds output budget or has invalid shape")
    save(trace_path, {"program_sha256": sha256(program), "tools": sdk.trace,
                      "records_read": sdk.records, "bytes_read": sdk.bytes_read,
                      "intermediate_stdout_bytes": 0, "security_sandbox": False})
    return result


def run_code(call: dict, root: Path, directory: Path) -> dict:
    if call.get("name") != "run_code" or call.get("arguments", {}).get("language") != "python":
        raise ValueError("Expected run_code Python call")
    code = call["arguments"]["code"]
    if code != APPROVED.read_text(encoding="utf-8"):
        raise ValueError("Unreviewed code rejected; a subprocess is not a sandbox")
    directory.mkdir(parents=True, exist_ok=True)
    program = directory / "executed-program.py"
    program.write_text(code, encoding="utf-8")
    worker = subprocess.run([sys.executable, "-B", "-X", "utf8", str(ROOT / "code_runtime.py"),
                             "--root", str(root), "--program", str(program),
                             "--trace", str(directory / "tool-trace.json")],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    if worker.returncode:
        # Do not return arbitrary error text containing tool data to context.
        (directory / "runtime-error.log").write_text(worker.stderr, encoding="utf-8")
        raise RuntimeError("Code Mode failed; diagnostic retained on disk")
    if len(worker.stdout.encode("utf-8")) > MAX_OUTPUT_BYTES or worker.stderr:
        raise ValueError("Unexpected runtime output")
    (directory / "runtime-stdout.json").write_text(worker.stdout, encoding="utf-8")
    return load(directory / "runtime-stdout.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--program", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    args = parser.parse_args()
    print(encode(execute_approved(args.root, args.program, args.trace)))
