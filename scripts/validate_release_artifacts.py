"""Build and validate DIP artifacts without importing the source checkout."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
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
    environment["DIP_VALIDATION_CHECKOUT"] = str(ROOT.resolve())
    check = """
import importlib.metadata
import importlib.resources
import os
from pathlib import Path
from unittest.mock import Mock, patch
import dip
from dip.collection.services import ImportService
from dip.composition import build_desktop_application_dependencies

assert dip.__version__ == "0.6.0"
assert importlib.metadata.version("discogs-intelligence-platform") == "0.6.0"
assert os.environ["DIP_VALIDATION_CHECKOUT"] not in str(
    Path(dip.__file__).resolve()
)
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
with patch(
    "dip.composition.DiscogsClient",
    side_effect=AssertionError("provider constructed during composition"),
) as provider:
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
    current = dependencies.project_management.active_project()
    assert current.name == "Current Collection"
    current_id = current.project_id
    assert len(dependencies.project_management.list_projects()) == 1
    assert dependencies.collector_run._provider_factory is provider
    provider.assert_not_called()
    csv_path = Path("installed-validation.csv")
    csv_path.write_text(
        "Catalog#,Artist,Title,Label,Format,Rating,Released,release_id,"
        "CollectionFolder,Date Added,Collection Media Condition,"
        "Collection Sleeve Condition,Collection Notes\\n"
        "CAT,Fixture Artist,Fixture Title,Fixture Label,Vinyl,5,2026,1101,"
        "Folder,2026-08-01,Mint,Mint,\\n"
        "CAT,Fixture Artist,Fixture Title,Fixture Label,Vinyl,5,2026,1101,"
        "Folder,2026-08-01,Mint,Mint,\\n"
        "CAT,Fixture Artist,Fixture Title,Fixture Label,Vinyl,5,2026,1202,"
        "Folder,2026-08-01,Mint,Mint,\\n",
        encoding="utf-8",
    )
    summary = ImportService(dependencies.database).import_collection(csv_path)
    assert summary.imported_records == 3
    assert dependencies.database.conn.execute(
        "SELECT COUNT(*) FROM releases"
    ).fetchone()[0] == 2
    assert dependencies.database.conn.execute(
        "SELECT COUNT(*) FROM collection_ownership"
    ).fetchone()[0] == 2
    assert dependencies.database.conn.execute(
        "SELECT COUNT(*) FROM decisions"
    ).fetchone()[0] == 2
    assert dependencies.database.conn.execute(
        "SELECT quantity FROM collection_ownership "
        "ORDER BY release_id LIMIT 1"
    ).fetchone()[0] == 2
finally:
    dependencies.database.close()

with patch(
    "dip.composition.DiscogsClient",
    side_effect=AssertionError("provider constructed during reopen"),
) as provider:
    reopened = build_desktop_application_dependencies()
try:
    assert reopened.project_management.active_project().project_id == current_id
    projects = reopened.project_management.list_projects()
    assert len(projects) == 1
    assert projects[0].project_id == current_id
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM releases"
    ).fetchone()[0] == 2
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM collection_ownership"
    ).fetchone()[0] == 2
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM decisions"
    ).fetchone()[0] == 2
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM analysis_runs"
    ).fetchone()[0] == 0
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM marketplace_snapshots"
    ).fetchone()[0] == 0
    assert reopened.database.conn.execute(
        "SELECT COUNT(*) FROM desktop_session"
    ).fetchone()[0] == 0
    provider.assert_not_called()
finally:
    reopened.database.close()

from dip.data_sources.discogs.client import DiscogsClient
assert DiscogsClient("validation-token").session.headers["User-Agent"] == (
    "RussellDiscogsIntelligencePlatform/0.6.0"
)

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
    _validate_compatibility_client(
        artifact,
        python,
        environment_root / "compatibility-client",
        environment,
    )


def _validate_compatibility_client(
    artifact: Path,
    python: Path,
    working_directory: Path,
    environment: dict[str, str],
) -> None:
    working_directory.mkdir()
    target = working_directory / "discogs_client.py"
    distributed = _sdist_compatibility_client(artifact)
    if distributed is None:
        shutil.copyfile(ROOT / "discogs_client.py", target)
    else:
        target.write_bytes(distributed)
    checkout = str(ROOT.resolve())
    check = f"""
from pathlib import Path
import dip
from discogs_client import DiscogsClient

assert dip.__version__ == "0.6.0"
assert {checkout!r} not in str(Path(dip.__file__).resolve())
assert DiscogsClient("validation-token").session.headers["User-Agent"] == (
    "RussellDiscogsIntelligencePlatform/0.6.0"
)
"""
    isolated = dict(environment)
    isolated.pop("PYTHONPATH", None)
    _run(str(python), "-c", check, cwd=working_directory, env=isolated)


def _sdist_compatibility_client(artifact: Path) -> bytes | None:
    if not artifact.name.endswith(".tar.gz"):
        return None
    with tarfile.open(artifact, "r:gz") as archive:
        members = tuple(
            member
            for member in archive.getmembers()
            if member.isfile() and Path(member.name).name == "discogs_client.py"
        )
        if not members:
            return None
        if len(members) != 1:
            raise RuntimeError(
                "Expected at most one compatibility client in the source distribution."
            )
        extracted = archive.extractfile(members[0])
        if extracted is None:
            raise RuntimeError("Could not read the distributed compatibility client.")
        return extracted.read()


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
