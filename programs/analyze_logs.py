"""Approved Code Mode program: tools SDK injected by the local runtime.

No prints, file opens or raw records returned. The runtime emits `result` once.
"""
from collections import Counter
from datetime import datetime, timezone
import json
import re

groups = {}
malformed = Counter()
total = 0
errors = 0
files = tools.list_files("*.jsonl")
for filename in files:
    for line_number, line in tools.read_lines(filename):
        total += 1
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            malformed["json"] += 1
            continue
        if not isinstance(record, dict) or not all(isinstance(record.get(k), str) for k in ("timestamp", "level", "service", "code")):
            malformed["schema"] += 1
            continue
        # Only normalized dimensions can enter context; message/payload stay opaque.
        if (record["level"] not in ("DEBUG", "INFO", "WARN", "ERROR", "FATAL")
                or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", record["code"])
                or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", record["service"])):
            malformed["schema"] += 1
            continue
        try:
            moment = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError("Timezone required")
            stamp = moment.astimezone(timezone.utc).isoformat()
        except ValueError:
            malformed["timestamp"] += 1
            continue
        if record["level"] not in ("ERROR", "FATAL"):
            continue
        errors += 1
        code = record["code"]
        if code not in groups:
            if len(groups) >= 256:
                raise ValueError("Error cardinality exceeds limit")
            groups[code] = {"code": code, "count": 0, "services": Counter(),
                            "first_seen": stamp, "last_seen": stamp, "evidence": []}
        group = groups[code]
        if record["service"] not in group["services"] and len(group["services"]) >= 64:
            raise ValueError("Service cardinality exceeds limit")
        group["count"] += 1
        group["services"][record["service"]] += 1
        group["first_seen"] = min(group["first_seen"], stamp)
        group["last_seen"] = max(group["last_seen"], stamp)
        if len(group["evidence"]) < 2:
            group["evidence"].append({"file": filename, "line": line_number})

top = sorted(groups.values(), key=lambda item: (-item["count"], item["code"]))[:3]
for group in top:
    group["services"] = dict(sorted(group["services"].items()))
result = {"files_scanned": len(files), "lines_scanned": total, "malformed_lines": sum(malformed.values()),
          "malformed_by_reason": dict(malformed), "error_records": errors, "top_errors": top,
          "scope": "all *.jsonl; levels ERROR or FATAL; top 3 by count desc, code asc",
          "limitation": "Frequency and correlation do not prove root cause"}
