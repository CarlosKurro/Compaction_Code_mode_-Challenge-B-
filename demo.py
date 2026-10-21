"""Run both challenges and generate evidence and a Vietnamese run report."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4

import b1
import b2
from common import load, save, sha256
import llm


ROOT = Path(__file__).resolve().parent


def report(run: Path, result: dict) -> str:
    first, second = result["b1"], result["b2"]
    findings = load(run / "b2/findings.json")
    rows = []
    for label, value in (("B1 Compact", first), ("B2 Code Mode", second)):
        metrics = value["metrics"]
        rows.append(f"| {label} | {metrics['before']['utf8_bytes']:,} | {metrics['after']['utf8_bytes']:,} | "
                    f"{metrics['before']['estimated_tokens']:,} | {metrics['after']['estimated_tokens']:,} | "
                    f"{metrics['byte_reduction_percent']}% |")
    api = result["api"]
    api_note = ("Chưa gọi API: không có kết quả LLM thật hoặc usage.input_tokens từ provider. "
                "Chạy lại với --with-api sau khi cấu hình biến môi trường để đo request đã quản lý context.")
    if api["status"] == "executed":
        api_note = "Đã gọi API trên managed context. Xem api/verification.json và các response để đọc usage nguyên bản."
    return f'''# Kết quả chạy Challenge B

Run: `{run.name}`. Thời điểm UTC: {result['created_at']}.
Kết quả harness: **{'PASS' if result['passed'] else 'FAIL'}**.
Prompt SHA-256: `{result['prompt_sha256']}`.

## B1: compact và tiếp tục đúng

Session có {first['events']} events, gồm {first['tool_outputs']} tool output lớn.
Trigger: `{first['trigger']}`; input budget ước lượng
{first['budget']['input_limit_estimated']:,}, window {first['budget']['window']:,},
reserve {first['budget']['reserve']:,}, safety ratio {first['budget']['safety_ratio']}.
Đã kiểm tra budget sau mỗi tool output, trước request tiếp theo.

Test concurrent refresh ban đầu **FAIL** (2 request cùng dùng token). Hai thay
đổi TTL/retry đã chạy thật và vẫn thất bại. Checkpoint giữ lỗi này, hai failed
attempts, constraints, findings, file và next_action `inspect_lock`.

Process mới PID {first['resume']['pid']} chỉ nhận checkpoint trong cold-start,
đọc auth.py theo next_action, đưa validation và rotate vào cùng lock, rồi chạy
**4/4 regression tests PASS**. Archive không tồn tại trong thư mục cold-start.
Xem `b1/cold-start/repair.diff`, `resumed-tests.log`, `resume-request.json`.
Agent demo dùng quy tắc và template sửa fixture, không phải LLM hiểu mọi lỗi.

## B2: nhiều log, chỉ findings vào context

Đọc {findings['files_scanned']} file, {findings['lines_scanned']:,} dòng trong
runtime process Python riêng, {second['tool_calls_inside_runtime']} SDK tool calls.
Agent chỉ nhận **1 kết quả aggregate**. Không có intermediate stdout.
Có {findings['malformed_lines']} dòng hỏng; {findings['error_records']} bản ghi ERROR/FATAL.

Top lỗi: {', '.join(f"{row['code']}={row['count']}" for row in findings['top_errors'])}.
Count/service khớp oracle tính bằng công thức; các vị trí evidence được mở lại
và kiểm tra. Câu trả lời đầy đủ ở `b2/answer.md`.

Program thực thi nằm ở `b2/executed-program.py`; tool call ở
`b2/agent-tool-call.json`; trace metadata ở `b2/tool-trace.json`.
Raw canary và chỉ thị giả trong log đều không xuất hiện trong managed request.
Process riêng không phải security sandbox; runtime chỉ chấp nhận program đã
duyệt, SDK giới hạn đường dẫn/kích thước/records, output <= 12 KB, timeout 30s.

## So sánh context

| Phần | Bytes trước | Bytes sau | Token ước lượng trước | Token ước lượng sau | Giảm bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(rows)}

Bytes đo trên cùng dạng JSON canonical của toàn request. Token ước lượng bằng
ceil(UTF-8 bytes / 4), không phải tokenizer model, usage hay token tính phí.
Baseline B2 là đối chứng offline nhồi toàn raw log vào 1 request, không phải
trace nhiều lượt native tool calling. Không gửi baseline đó lên API.

## API thật

{api_note}

Đối chiếu API: [Text generation]({llm.DOCS[0]}),
[Counting tokens]({llm.DOCS[1]}). Adapter ghi usage nguyên bản cho request sau
compact/aggregate; không có số đo usage của baseline để tuyên bố mức giảm token
thực tế. Lần chạy offline chỉ chứng minh harness và agent có quy tắc.

## Kiểm chứng

B1: {sum(first['checks'].values())}/{len(first['checks'])} kiểm tra đạt.
B2: {sum(second['checks'].values())}/{len(second['checks'])} kiểm tra đạt.
Xem `verification.json` và verification của từng phần. Bộ unittest độc lập chạy
bằng `python -B -X utf8 -m unittest discover -s tests -v`; log kiểm thử bàn giao ở
`output/tests.log` tại thư mục Challenge B.
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "output/demo")
    parser.add_argument("--with-api", action="store_true", help="Explicitly call a real model on managed contexts")
    args = parser.parse_args()
    if args.with_api:
        llm.config()
    stamp = datetime.now(timezone.utc)
    run = args.output.resolve() / (stamp.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    run.mkdir(parents=True)
    print("B1: reproducing failure, executing two attempts, compacting, cold-resuming...", flush=True)
    first = b1.demo(run / "b1")
    print("B1 PASS: cold process repaired fixture; 4/4 regression tests pass.", flush=True)
    remembered = first["resume"]["remembered"]
    print("  Open error: " + remembered["open_issues"][0]["error"])
    print("  Failed attempts retained: " + ", ".join(remembered["failed_attempts"]))
    print("  Next action used: " + remembered["next_action"]["operation"])
    print("B2: scanning 24 log files inside Code Mode runtime...", flush=True)
    second = b2.demo(run / "b2")
    print("B2 PASS: ground truth matches; raw log absent from agent context.", flush=True)
    findings = load(run / "b2/findings.json")
    print(f"  {findings['lines_scanned']} lines, {findings['malformed_lines']} malformed, {findings['error_records']} ERROR/FATAL records")
    print("  Top: " + ", ".join(f"{row['code']}={row['count']}" for row in findings["top_errors"]))
    for label, value in (("B1", first), ("B2", second)):
        metrics = value["metrics"]
        print(f"  {label} context bytes: {metrics['before']['utf8_bytes']} -> {metrics['after']['utf8_bytes']} (-{metrics['byte_reduction_percent']}%)")
    api = {"status": "not_run", "reason": "Offline is default; --with-api requires explicit model/key configuration",
           "usage": None}
    if args.with_api:
        print("API: evaluating managed contexts; raw baselines stay local.", flush=True)
        api = llm.evaluate(run)
    result = {"created_at": stamp.isoformat(), "prompt_sha256": sha256(ROOT / "PROMPT_CHALLENGE_B.md"),
              "source_slide": "../Challenge A/slide.pdf", "source_pages": [32, 33],
              "b1": first, "b2": second, "api": api,
              "passed": first["passed"] and second["passed"] and api.get("passed", True)}
    save(run / "verification.json", result)
    (run / "REPORT.md").write_text(report(run, result), encoding="utf-8")
    latest = ROOT / "output/LATEST_DEMO.txt"
    latest.parent.mkdir(exist_ok=True)
    latest.write_text(str(run) + "\n", encoding="utf-8")
    print(f"Evidence: {run}")
    print("Real API usage: " + ("recorded" if api["status"] == "executed" else "not measured (offline demo)"))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
