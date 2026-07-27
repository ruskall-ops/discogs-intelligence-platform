from pathlib import Path
import subprocess
import tempfile
import unittest


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

        validator = (
            Path(__file__).resolve().parents[1]
            / "scripts/validate_release_artifacts.py"
        ).read_text(encoding="utf-8")
        self.assertIn('environment.pop("PYTHONPATH", None)', validator)
        self.assertIn("TemporaryDirectory", validator)
        self.assertIn('"dip.app:main"', validator)
        self.assertIn("shutil.rmtree(path)", validator)

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
