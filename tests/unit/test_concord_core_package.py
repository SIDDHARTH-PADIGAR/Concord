"""Packaging sanity checks for concord-core.

These tests exist to catch a specific, easy-to-make mistake: a package
that "looks" correctly configured (pyproject.toml exists, build passes)
but is actually broken when installed -- version mismatches between
pyproject.toml and __init__.py, missing py.typed markers, or an editable
install pointing at the wrong source tree.

Nobody notices this class of bug until a downstream service imports
concord_core and gets a stale or inconsistent version. Catching it here,
before any domain code exists, means every later milestone builds on a
package we've actually verified is installed correctly.
"""

from importlib import metadata
from pathlib import Path

import concord_core


def test_version_matches_installed_metadata() -> None:
    """__init__.py's __version__ must match what pip/hatchling installed.

    These two numbers come from different files (pyproject.toml and
    __init__.py) and nothing enforces they stay in sync except this
    test. It's a one-line check that prevents a real, common mistake:
    bumping one and forgetting the other.
    """
    installed_version = metadata.version("concord-core")
    assert concord_core.__version__ == installed_version


def test_package_is_typed() -> None:
    """concord_core must ship a py.typed marker (PEP 561).

    Every other service in this repo will import concord_core and run
    mypy --strict against that import. Without py.typed, mypy treats
    concord_core as untyped and silently stops checking it -- which
    defeats the entire point of strict mode downstream.
    """
    package_dir = Path(concord_core.__file__).parent
    assert (package_dir / "py.typed").exists()
