"""Optional real Responses API calls; credentials never enter saved artifacts."""
from __future__ import annotations

import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from common import load, save


DOCS = ["https://developers.openai.com/api/docs/guides/text",
        "https://developers.openai.com/api/docs/guides/token-counting"]


def config() -> tuple[str, str]:
    key, model = os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_MODEL", "")
    if not key or not model:
        raise ValueError("Real API mode needs OPENAI_API_KEY and OPENAI_MODEL in the environment")
    return key, model


def call(payload: dict, key: str, model: str) -> dict:
    body = {**payload, "model": model, "store": False, "max_output_tokens": 8192}
    req = urllib.request.Request("https://api.openai.com/v1/responses",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        code = exc.code
        exc.close()
        raise RuntimeError(f"Responses API HTTP {code}; no response body or credentials logged") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Responses API connection/timeout failed") from None
    if result.get("status") != "completed":
        raise RuntimeError("Model response incomplete; not counted as a successful evaluation")
    text = "\n".join(part["text"] for item in result.get("output", []) if item.get("type") == "message"
                     for part in item.get("content", []) if part.get("type") == "output_text")
    usage = result.get("usage")
    if not text or not isinstance(usage, dict) or not isinstance(usage.get("input_tokens"), int):
        raise RuntimeError("Missing model output or real usage.input_tokens")
    return {"request": body, "text": text, "usage": usage, "response_id": result.get("id"), "model": result.get("model", model)}


def evaluate(run_directory: Path) -> dict:
    key, model = config()
    results = {}
    for part, relative in (("b1", "b1/cold-start/resume-request.json"), ("b2", "b2/managed-request.json")):
        payload = load(run_directory / relative)
        if part == "b1":
            payload["instructions"] += (
                '\nReturn ONLY JSON with keys open_error (string), failed_attempts (array of strategy IDs), '
                'next_operation (string), constraints (array of strings). Copy exact values from CHECKPOINT, '
                'including open_error from the first open issue error. No markdown.')
        else:
            payload["instructions"] += (
                '\nReturn ONLY JSON with keys files_scanned, malformed_lines, error_records (integers), '
                'top_errors (array of objects with code and count), and caveat (string). No markdown.')
        result = call(payload, key, model)
        # Store actual response and usage first, even if semantic verification fails.
        save(run_directory / "api" / f"{part}-response.json", result)
        try:
            answer = json.loads(result["text"])
            if part == "b1":
                state = load(run_directory / "b1/checkpoint.json")["state"]
                expected_attempts = [row["strategy"] for row in state["failed_attempts"]]
                passed = (sorted(answer["failed_attempts"]) == sorted(expected_attempts)
                          and answer["next_operation"] == state["next_action"]["operation"]
                          and answer["constraints"] == state["constraints"]
                          and answer["open_error"] == state["open_issues"][0]["error"])
            else:
                expected = load(run_directory / "b2/ground-truth.json")
                passed = (all(answer[k] == expected[k] for k in ("files_scanned", "malformed_lines", "error_records"))
                          and {x["code"]: x["count"] for x in answer["top_errors"]} == expected["counts"]
                          and bool(answer["caveat"]))
        except (ValueError, KeyError, TypeError, AttributeError):
            passed = False
        results[part] = {"semantic_checks_passed": passed, "usage": result["usage"], "model": result["model"]}
    summary = {"status": "executed", "results": results, "passed": all(x["semantic_checks_passed"] for x in results.values()),
               "scope": "Model reads managed context only; B1 fixture repair and B2 program dispatch are separately verified offline",
               "baseline_api_usage": None, "note": "Raw baseline not sent. No measured API before/after token comparison."}
    save(run_directory / "api/verification.json", summary)
    return summary
