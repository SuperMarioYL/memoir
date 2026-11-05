"""Version-consistency guard (m6, extended in v0.3.0).

The version string lives on multiple hand-maintained surfaces; this test fails
CI when they drift apart instead of letting the drift ship.
"""

import json
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


def test_site_content_version_matches_package_version():
    """The published site carries the product version too (bare, no leading v)."""
    site = json.loads((ROOT / "web" / "site.json").read_text(encoding="utf-8"))
    assert site["meta"]["content_version"] == memoir.__version__


def test_version_is_the_current_release():
    assert memoir.__version__ == "0.3.0"
