"""Run all tests and save genuine test output and machine-readable status."""
from __future__ import annotations

from datetime import datetime, timezone
import io
from pathlib import Path
import sys
import unittest

from common import save


ROOT = Path(__file__).resolve().parent


def main() -> int:
    output = ROOT / "output"
    output.mkdir(exist_ok=True)
    captured = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(stream=captured, verbosity=2).run(suite)
    log = captured.getvalue()
    (output / "tests.log").write_text(log, encoding="utf-8")
    save(output / "tests-verification.json", {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
         "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
         "python": sys.version, "created_at": datetime.now(timezone.utc).isoformat()})
    print(log)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
