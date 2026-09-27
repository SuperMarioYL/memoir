"""Version-consistency guard (m6).

The version string lives on multiple hand-maintained surfaces; this test fails
CI when they drift apart instead of letting the drift ship.
"""

import tomllib
from pathlib import Path

import memoir

ROOT = Path(__file__).resolve().parent.parent


def test_version_file_matches_package_version():
    version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version_file == memoir.__version__


def test_pyproject_version_matches_package_version():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == memoir.__version__


def test_version_is_the_current_release():
    assert memoir.__version__ == "0.2.0"
