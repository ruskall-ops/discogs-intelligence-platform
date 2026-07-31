"""Build and validate DIP artifacts without importing the source checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED_RELATIVE = (
    Path("build"),
    Path("dist"),
    Path("src/discogs_intelligence_platform.egg-info"),
)
GENERATED = tuple(ROOT / path for path in GENERATED_RELATIVE)


def main() -> None:
    _require_artifact_clean()
    try:
        with tempfile.TemporaryDirectory(
            prefix="dip-release-validation-"
        ) as directory:
            temporary = Path(directory)
            artifacts = temporary / "artifacts"
            artifacts.mkdir()
            _run(
                sys.executable,
                "-m",
                "build",
                "--outdir",
                str(artifacts),
                cwd=ROOT,
            )
            wheel = _one(artifacts.glob("*.whl"))
            sdist = _one(artifacts.glob("*.tar.gz"))
            _validate_artifact(wheel, temporary / "wheel")
            _validate_artifact(sdist, temporary / "sdist")
    finally:
        for path in GENERATED:
            if path.exists():
                shutil.rmtree(path)


def _require_artifact_clean(root: Path = ROOT) -> None:
    generated = tuple(root / path for path in GENERATED_RELATIVE)
    existing = tuple(path for path in generated if path.exists())
    if not existing:
        return
    names = ", ".join(
        path.relative_to(root).as_posix()
        for path in existing
    )
    raise RuntimeError(
        "Release validation requires an artifact-clean working tree. "
        f"Remove generated artifact paths: {names}"
    )


def _validate_artifact(artifact: Path, environment_root: Path) -> None:
    _run(
        sys.executable,
        "-m",
        "venv",
        str(environment_root),
        cwd=environment_root.parent,
    )
    python = environment_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _run(
        str(python),
        "-m",
        "pip",
        "install",
        str(artifact),
        cwd=environment_root,
    )
    database = environment_root / "installed-validation.sqlite3"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["DIP_DATABASE_FILENAME"] = str(database)
    check = """
import importlib.metadata
import importlib.resources
from unittest.mock import Mock, patch
import dip
from dip.composition import build_desktop_application_dependencies

assert dip.__version__ == "0.4.0"
entry_points = {
    value.name: value.value
    for value in importlib.metadata.distribution(
        "discogs-intelligence-platform"
    ).entry_points
}
assert entry_points["dip"] == "dip.app:main"
assert importlib.resources.files("dip.persistence.sqlite").joinpath(
    "schema.sql"
).is_file()
dependencies = build_desktop_application_dependencies()
try:
    versions = tuple(
        row[0]
        for row in dependencies.database.conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    )
    assert versions == tuple(range(1, 8))
    assert dependencies.database.conn.execute(
        "SELECT COUNT(*) FROM desktop_session"
    ).fetchone()[0] == 0
    assert dependencies.project_management.active_project().name == (
        "Current Collection"
    )
    assert isinstance(dependencies.collector_run._provider_factory, type)
finally:
    dependencies.database.close()

fake = Mock()
with patch("dip.experience.desktop.app.App", return_value=fake):
    import dip.app
    dip.app.main()
fake.mainloop.assert_called_once_with()
"""
    _run(
        str(python),
        "-c",
        check,
        cwd=environment_root,
        env=environment,
    )


def _one(values) -> Path:
    matches = tuple(values)
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one built artifact.")
    return matches[0]


def _run(*command: str, cwd: Path, env=None) -> None:
    subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
    )


if __name__ == "__main__":
    main()
