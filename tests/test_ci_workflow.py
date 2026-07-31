from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts.validate_release_artifacts import (
    _require_artifact_clean,
    _sdist_compatibility_client,
    _validate_compatibility_client,
)


class CIWorkflowTestCase(unittest.TestCase):
    def test_ci_contract_is_repository_owned_and_non_publishing(self) -> None:
        workflow = (
            Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
        ).read_text(encoding="utf-8")
        for expected in (
            "pull_request:",
            "push:",
            "branches: [main]",
            "actions/checkout@v4",
            "actions/setup-python@v5",
            'python-version: "3.11"',
            "python -m unittest discover -s tests -q",
            "python -m compileall -q src tests app.py discogs_client.py",
            "python scripts/validate_release_artifacts.py",
            "git merge-base HEAD",
            "git diff --check",
            "${{ github.event.before }}..${{ github.sha }}",
            "git diff-tree --root --check -r HEAD",
        ):
            self.assertIn(expected, workflow)
        for forbidden in ("secrets.", "upload-artifact", "publish", "twine"):
            self.assertNotIn(forbidden, workflow)
        self.assertEqual(workflow.count("runs-on:"), 2)
        self.assertEqual(
            workflow.count("python scripts/validate_release_artifacts.py"),
            2,
        )
        self.assertEqual(
            workflow.count(
                "python -m unittest discover -s tests -q"
            ),
            2,
        )
        self.assertEqual(
            workflow.count(
                "python -m compileall -q src tests app.py "
                "discogs_client.py"
            ),
            2,
        )
        self.assertEqual(
            workflow.count("Validate changed-content whitespace"),
            2,
        )
        linux_start = workflow.index("  linux:")
        macos_start = workflow.index("  macos:")
        for job_text in (
            workflow[linux_start:macos_start],
            workflow[macos_start:],
        ):
            ordered_commands = (
                "python scripts/validate_release_artifacts.py",
                "python -m pip install -e .[dev]",
                "python -m unittest discover -s tests -q",
                (
                    "python -m compileall -q src tests app.py "
                    "discogs_client.py"
                ),
            )
            positions = tuple(
                job_text.index(command)
                for command in ordered_commands
            )
            self.assertEqual(positions, tuple(sorted(positions)))
            self.assertIn("git merge-base HEAD", job_text)
            self.assertIn("git diff --check", job_text)

        validator = (
            Path(__file__).resolve().parents[1]
            / "scripts/validate_release_artifacts.py"
        ).read_text(encoding="utf-8")
        self.assertIn('environment.pop("PYTHONPATH", None)', validator)
        self.assertIn('isolated.pop("PYTHONPATH", None)', validator)
        self.assertIn('cwd=working_directory', validator)
        self.assertIn('Path(dip.__file__).resolve()', validator)
        self.assertIn("TemporaryDirectory", validator)
        self.assertIn('"dip.app:main"', validator)
        self.assertIn("shutil.rmtree(path)", validator)

    def test_sdist_compatibility_client_is_selected_exactly_or_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "discogs_client.py"
            source.write_text("distributed = True\n", encoding="utf-8")
            archive = root / "artifact.tar.gz"
            with tarfile.open(archive, "w:gz") as value:
                value.add(source, arcname="package/discogs_client.py")
            self.assertEqual(
                _sdist_compatibility_client(archive),
                b"distributed = True\n",
            )

            with tarfile.open(archive, "w:gz") as value:
                value.add(source, arcname="one/discogs_client.py")
                value.add(source, arcname="two/discogs_client.py")
            with self.assertRaisesRegex(RuntimeError, "at most one"):
                _sdist_compatibility_client(archive)

    def test_compatibility_client_validation_clears_checkout_import_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.whl"
            artifact.touch()
            working = root / "compatibility"
            with patch("scripts.validate_release_artifacts._run") as run:
                _validate_compatibility_client(
                    artifact,
                    Path("isolated-python"),
                    working,
                    {"PYTHONPATH": "checkout", "PRESERVED": "yes"},
                )
            self.assertEqual(run.call_args.kwargs["cwd"], working)
            self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])
            self.assertEqual(run.call_args.kwargs["env"]["PRESERVED"], "yes")
            self.assertTrue((working / "discogs_client.py").is_file())

    def test_linux_editable_install_artifact_is_named_and_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _require_artifact_clean(root)

            egg_info = (
                root / "src/discogs_intelligence_platform.egg-info"
            )
            egg_info.mkdir(parents=True)
            with self.assertRaisesRegex(
                RuntimeError,
                (
                    r"Remove generated artifact paths: "
                    r"src/discogs_intelligence_platform\.egg-info"
                ),
            ):
                _require_artifact_clean(root)
            self.assertTrue(egg_info.is_dir())

            (root / "build").mkdir()
            (root / "dist").mkdir()
            with self.assertRaisesRegex(
                RuntimeError,
                (
                    r"Remove generated artifact paths: build, dist, "
                    r"src/discogs_intelligence_platform\.egg-info"
                ),
            ):
                _require_artifact_clean(root)

    def test_whitespace_commands_execute_for_root_push_and_ranges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "ci@example.invalid")
            self._git(root, "config", "user.name", "CI")
            (root / "clean.txt").write_text("clean\n", encoding="utf-8")
            self._git(root, "add", "clean.txt")
            self._git(root, "commit", "-qm", "root")
            self.assertEqual(
                self._run(
                    root,
                    "git diff-tree --root --check -r HEAD",
                ).returncode,
                0,
            )
            root_commit = self._git(root, "rev-parse", "HEAD").stdout.strip()

            (root / "bad.txt").write_text("trailing   \n", encoding="utf-8")
            self._git(root, "add", "bad.txt")
            self._git(root, "commit", "-qm", "bad")
            bad_commit = self._git(root, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(
                self._run(
                    root,
                    f"git diff --check {root_commit}..{bad_commit}",
                ).returncode,
                0,
            )
            self.assertNotEqual(
                self._run(
                    root,
                    f"base=\"$(git merge-base HEAD {root_commit})\"; "
                    'git diff --check "${base}..HEAD"',
                ).returncode,
                0,
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._git(root, "init", "-q")
            self._git(root, "config", "user.email", "ci@example.invalid")
            self._git(root, "config", "user.name", "CI")
            (root / "bad.txt").write_text("trailing   \n", encoding="utf-8")
            self._git(root, "add", "bad.txt")
            self._git(root, "commit", "-qm", "root bad")
            self.assertNotEqual(
                self._run(
                    root,
                    "git diff-tree --root --check -r HEAD",
                ).returncode,
                0,
            )

    @staticmethod
    def _run(root: Path, command: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", "-c", command],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )

    @staticmethod
    def _git(
        root: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *arguments],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
