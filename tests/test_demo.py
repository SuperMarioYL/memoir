"""Guard for the documented demo command (v0.3.0).

README.md, README.zh-CN.md, web/site.json and docs/demo-results.json all publish
the command ``examples/presentation-demo.py`` and its recorded output. v0.2.0
shipped that command crashing (``TypeError: 'IngestResult' object is not
iterable``) because state hardening changed ``ingest_folder``'s return type and
the example was never updated, so this test runs the documented command and
holds it to the recorded transcript.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDED = ROOT / "docs" / "demo-results.json"


def test_presentation_demo_runs_and_matches_recorded_output():
    proc = subprocess.run(
        [sys.executable, "examples/presentation-demo.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    live = json.loads(proc.stdout)
    recorded = json.loads(
        json.loads(RECORDED.read_text(encoding="utf-8"))["steps"][0]["output"]
    )
    assert live == recorded
