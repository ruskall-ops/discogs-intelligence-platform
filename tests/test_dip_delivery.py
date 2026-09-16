from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, replace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote, unquote

from scripts import dip_delivery as delivery
from scripts.dip_delivery import IdentityError, _paths


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/dip_delivery.py"


class DipDeliveryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "delivery@example.invalid")
        self.git("config", "user.name", "Delivery Test")
        self.write("base.txt", "base\n")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "base")
        self.git("remote", "add", "origin", str(self.repo))
        self.git("update-ref", "refs/remotes/origin/main", self.git("rev-parse", "HEAD").stdout.strip())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, name: str, value: str) -> None:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ("git", *arguments), cwd=self.repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
        )

    def invoke(
        self,
        mode: str,
        *arguments: str,
        secret: str = "do-not-print",
        cwd: Path | None = None,
        extra_environment: dict[str, str] | None = None,
    ):
        environment = dict(os.environ)
        environment["DIP_TEST_SECRET"] = secret
        environment.update(extra_environment or {})
        before = self.repository_snapshot()
        completed = subprocess.run(
            (sys.executable, str(SCRIPT), "--repo", str(self.repo), "--mode", mode,
             "--format", "json", *arguments),
            cwd=cwd or self.repo, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=30,
        )
        self.assertEqual(self.repository_snapshot(), before)
        payload = json.loads(completed.stdout) if completed.stdout else None
        self.assertNotIn(secret, completed.stdout + completed.stderr)
        return completed, payload

    def index_hash(self) -> str:
        return hashlib.sha256((self.repo / ".git/index").read_bytes()).hexdigest()

    def repository_snapshot(self, root: Path | None = None) -> dict:
        root = self.repo if root is None else root
        result = {}
        for path in (root, *root.rglob("*")):
            stat = path.lstat()
            content = (
                os.readlink(path) if path.is_symlink() else
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            )
            result[str(path.relative_to(root))] = (stat.st_mode, stat.st_mtime_ns, content)
        return result

    def assert_invalid(self, completed, data, reason: str) -> None:
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(data["ready"])
        self.assertIn(reason, data["failures"])
        for field in ("candidate_tree", "insertions", "deletions"):
            self.assertIsNone(data[field])

    def assert_markdown_matches_json(self, markdown: str, payload: dict) -> None:
        rows = [line for line in markdown.splitlines() if line.startswith("- ")]
        self.assertEqual(len(rows), len(payload))
        decoded = {}
        for line in rows:
            label, value = line[2:].split(": ", 1)
            key = label.lower().replace(" ", "_")
            json_value = re.sub(
                r"`([^`]*)`", lambda match: json.dumps(unquote(match[1])), value,
            )
            decoded[key] = json.loads(json_value)
        self.assertEqual(decoded, json.loads(json.dumps(payload)))
        self.assertFalse(re.search(r"[\x00-\x08\x0b-\x1f\x7f]", markdown))

    def test_clean_main_and_all_modes_report_concise_handoffs(self) -> None:
        for mode in ("plan", "implement", "correct", "review", "publish-pr", "merge-sync", "release"):
            with self.subTest(mode=mode):
                completed, data = self.invoke(mode)
                self.assertEqual(completed.returncode, 0)
                self.assertTrue(data["ready"])
                self.assertEqual(data["branch"], "main")
                self.assertEqual(data["ahead"], data["behind"])
                self.assertTrue(data["human_decision_required"])
        completed, data = self.invoke("publish-pr", cwd=ROOT)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(data["next_permitted_action"], "verify the approved candidate identity")
        self.assertEqual(data["human_decision_required"], "commit and push authorization")

    def test_uncommitted_staged_and_unstaged_paths_are_distinct(self) -> None:
        self.write("base.txt", "unstaged\n")
        self.write("staged.txt", "staged\n")
        self.git("add", "staged.txt")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(data["modified_paths"], ["base.txt"])
        self.assertEqual(data["staged_paths"], ["staged.txt"])
        self.assertEqual(data["candidate_paths"], ["base.txt", "staged.txt"])

    def test_exact_paths_unexpected_path_and_safe_filenames(self) -> None:
        names = ("file with spaces.txt", "safe-+_name.txt")
        for name in names:
            self.write(name, name + "\n")
        arguments = tuple(value for name in names for value in ("--expected-path", name))
        completed, data = self.invoke("implement", *arguments)
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["paths_match"])
        self.write("unexpected.txt", "extra\n")
        completed, data = self.invoke("implement", *arguments)
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(data["paths_match"])
        self.assertIn("unexpected.txt", data["candidate_paths"])

        completed, data = self.invoke(
            "implement", "--expected-path", names[0], "--expected-path", names[0],
            "--expected-path", names[1], "--expected-path", "unexpected.txt",
        )
        self.assertEqual(completed.returncode, 2)
        self.assertFalse(data["paths_match"])

    def test_staged_rename_reproduces_deletion_and_addition(self) -> None:
        before_index = self.index_hash()
        self.git("mv", "base.txt", "renamed file.txt")
        staged_index = self.index_hash()
        self.assertNotEqual(staged_index, before_index)
        completed, data = self.invoke(
            "review", "--expected-path", "base.txt",
            "--expected-path", "renamed file.txt",
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(data["staged_paths"], ["base.txt", "renamed file.txt"])
        self.assertTrue(data["paths_match"])
        self.assertEqual(self.index_hash(), staged_index)

    def test_detached_head_fails_closed(self) -> None:
        self.git("checkout", "--detach", "-q")
        completed, data = self.invoke("publish-pr")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data["branch"])
        self.assertIn("detached HEAD", data["failures"])

    def test_branch_behind_main_is_reported(self) -> None:
        base = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-qb", "candidate")
        self.git("checkout", "-q", "main")
        self.write("later.txt", "later\n")
        self.git("add", "later.txt")
        self.git("commit", "-qm", "later")
        self.git("update-ref", "refs/remotes/origin/main", self.git("rev-parse", "HEAD").stdout.strip())
        self.git("checkout", "-q", "candidate")
        self.assertEqual(self.git("rev-parse", "HEAD").stdout.strip(), base)
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual((data["behind"], data["ahead"]), (1, 0))

    def test_candidate_tree_uses_temporary_index_and_failure_does_not_mutate(self) -> None:
        self.write("base.txt", "changed\n")
        self.write("new.txt", "new\n")
        before_index = self.index_hash()
        before_status = self.git("status", "--porcelain=v1").stdout
        completed, data = self.invoke(
            "implement", "--expected-path", "base.txt", "--expected-path", "wrong.txt"
        )
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(self.index_hash(), before_index)
        self.assertEqual(self.git("status", "--porcelain=v1").stdout, before_status)
        self.assertIsNone(data["candidate_tree"])
        self.assertIsNone(data["insertions"])
        self.assertIsNone(data["deletions"])
        self.assertEqual(data["diff_check"], "not-run")
        self.assertFalse(data["paths_match"])

    def test_output_is_external_and_repository_state_is_unchanged(self) -> None:
        before_index = self.index_hash()
        before_status = self.git("status", "--porcelain=v1").stdout
        output = self.repo.parent / "delivery-report.json"
        completed, data = self.invoke("review", "--output", output)
        self.assertEqual(completed.returncode, 0)
        self.assertIsNone(data)
        self.assertTrue(output.exists())
        self.assertEqual(self.index_hash(), before_index)
        self.assertEqual(self.git("status", "--porcelain=v1").stdout, before_status)
        self.assertTrue(json.loads(output.read_text())["ready"])

    def test_output_inside_worktree_or_common_directory_is_rejected(self) -> None:
        for output in (self.repo / "report.json", self.repo / ".git" / "report.json"):
            with self.subTest(output=output):
                completed, data = self.invoke("review", "--output", output)
                self.assertEqual(completed.returncode, 2)
                self.assertIsNone(data)
                self.assertIn("outside the worktree", completed.stderr)
                self.assertFalse(output.exists())

    def test_markdown_encodes_hostile_paths(self) -> None:
        name = "host`ile\nname.txt"
        self.write(name, "hostile\n")
        completed = subprocess.run(
            (sys.executable, str(SCRIPT), "--repo", str(self.repo), "--mode", "review",
             "--format", "markdown"),
            cwd=self.repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("host%60ile%0Aname.txt", completed.stdout)
        self.assertNotIn(name, completed.stdout)

    def test_non_utf8_git_path_fails_closed(self) -> None:
        with patch("scripts.dip_delivery._run", return_value=b"bad-\xff.txt\0"):
            with self.assertRaisesRegex(IdentityError, "non-UTF-8 path"):
                _paths(self.repo, "ls-files", "-z")

    def test_unmerged_index_suppresses_candidate_identity_and_totals(self) -> None:
        blob = subprocess.run(
            ("git", "hash-object", "-w", "--stdin"), cwd=self.repo,
            input="conflict\n", text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        subprocess.run(
            ("git", "update-index", "--index-info"), cwd=self.repo,
            input=f"100644 {blob} 1\tconflict.txt\n", text=True, check=True,
        )
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data["candidate_tree"])
        self.assertIsNone(data["insertions"])
        self.assertIsNone(data["deletions"])
        self.assertEqual(data["diff_check"], "not-run")
        self.assertIn("index contains unmerged paths", data["failures"])
        with patch.object(delivery, "_candidate", side_effect=AssertionError("derived conflict")):
            self.assertFalse(delivery.inspect_repository(self.repo, "review").ready)

    def test_output_containment_handles_existing_missing_and_symlink_targets(self) -> None:
        self.write("child/keep", "fixture\n")
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            (external / "repo-link").symlink_to(self.repo, target_is_directory=True)
            (external / "git-link").symlink_to(self.repo / ".git", target_is_directory=True)
            (external / "file-link").symlink_to(self.repo / "base.txt")
            (self.repo / "outside-link").symlink_to(external, target_is_directory=True)
            targets = (
                self.repo / "base.txt", self.repo / "missing" / "report.json",
                self.repo / "child" / ".." / "new.json", self.repo / ".git/index",
                self.repo / ".git/HEAD", self.repo / ".git/refs/heads/main",
                self.repo / ".git/objects/new/report", external / "repo-link/new",
                external / "git-link/new", external / "file-link",
                self.repo / "outside-link/new",
            )
            for target in targets:
                with self.subTest(target=target):
                    completed, data = self.invoke("review", "--output", target)
                    self.assertEqual(completed.returncode, 2)
                    self.assertIsNone(data)
                    self.assertIn("outside the worktree", completed.stderr)
            for target in (external / "new.json", external / "new.json"):
                completed, data = self.invoke("review", "--output", target)
                self.assertEqual(completed.returncode, 0)
                self.assertIsNone(data)
                self.assertTrue(json.loads(target.read_text())["ready"])

    def test_case_alias_output_cannot_change_worktree_or_git_metadata(self) -> None:
        alias = self.repo.with_name(self.repo.name.upper())
        if alias == self.repo or not alias.exists():
            self.skipTest("A case-insensitive filesystem is required for the macOS regression.")
        self.assertTrue(alias.samefile(self.repo))
        for name in ("base.txt", "missing/new.json", ".git/index", ".git/HEAD",
                     ".git/refs/heads/main", ".git/objects/new"):
            with self.subTest(name=name):
                completed, data = self.invoke("review", "--output", alias / name)
                self.assertEqual(completed.returncode, 2)
                self.assertIsNone(data)
                self.assertIn("outside the worktree", completed.stderr)

    def test_linked_worktree_common_directory_is_protected(self) -> None:
        original = self.repo
        with tempfile.TemporaryDirectory() as directory:
            linked = Path(directory) / "linked"
            self.git("worktree", "add", "-q", "-b", "linked", str(linked))
            common_before = self.repository_snapshot(original / ".git")
            self.repo = linked
            try:
                for target in (original / ".git/index", original / ".git/new/report"):
                    completed, data = self.invoke("review", "--output", target)
                    self.assertEqual(completed.returncode, 2)
                    self.assertIsNone(data)
                completed, data = self.invoke("review")
                self.assertEqual(completed.returncode, 0)
                self.assertTrue(data["ready"])
                self.assertEqual(self.repository_snapshot(original / ".git"), common_before)
            finally:
                self.repo = original

    def test_external_hardlink_cannot_overwrite_a_repository_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report"
            os.link(self.repo / "base.txt", output)
            completed, data = self.invoke("review", "--output", output)
            self.assertEqual(completed.returncode, 2)
            self.assertIsNone(data)
            self.assertIn("multiply linked", completed.stderr)

    def test_split_index_configuration_and_existing_shared_index_are_read_only(self) -> None:
        self.git("config", "core.splitIndex", "true")
        self.write("base.txt", "changed\n")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(tuple((self.repo / ".git").glob("sharedindex.*")), ())
        self.git("update-index", "--split-index")
        self.assertTrue(tuple((self.repo / ".git").glob("sharedindex.*")))
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["ready"])

    def test_clean_and_process_filters_are_rejected_before_any_scan(self) -> None:
        self.write(".gitattributes", "base.txt filter=hostile\n")
        self.write("base.txt", "changed\n")
        code = "from pathlib import Path; Path('.git/filter-ran').touch()"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(code)}"
        for kind in ("clean", "process"):
            with self.subTest(kind=kind):
                self.git("config", f"filter.hostile.{kind}", command)
                completed, data = self.invoke("review")
                self.assertEqual(completed.returncode, 2)
                self.assertIsNone(data)
                self.assertIn("configured clean/process filters", completed.stderr)
                self.assertFalse((self.repo / ".git/filter-ran").exists())
                self.git("config", "--unset", f"filter.hostile.{kind}")

    def test_hooks_fsmonitor_and_external_diff_cannot_run(self) -> None:
        script = self.repo / ".git/side-effect"
        script.write_text(f"#!{sys.executable}\nfrom pathlib import Path\nPath('.git/integration-ran').touch()\n")
        script.chmod(0o755)
        self.git("config", "core.fsmonitor", str(script))
        self.git("config", "diff.external", str(script))
        for name in ("post-index-change", "pre-auto-gc"):
            (self.repo / ".git/hooks" / name).symlink_to(script)
        self.write("base.txt", "changed\n")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["ready"])
        self.assertFalse((self.repo / ".git/integration-ran").exists())

    def test_unused_filter_is_allowed_but_info_attributes_activate_rejection(self) -> None:
        self.git("config", "filter.unused.clean", "must-not-execute-unused-filter")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["ready"])
        (self.repo / ".git/info/attributes").write_text("base.txt filter=unused\n")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("configured clean/process filters", completed.stderr)

    def test_borrowed_object_stores_and_partial_clones_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            alternate = self.repo / ".git/objects/info/alternates"
            alternate.write_text(directory + "\n")
            completed, data = self.invoke("review")
            self.assertEqual(completed.returncode, 2)
            self.assertIsNone(data)
            self.assertIn("alternate object stores", completed.stderr)
            alternate.write_text("")
        self.git("config", "remote.origin.promisor", "true")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("partial clone configuration", completed.stderr)

    def test_conditional_configuration_cannot_silently_change_identity(self) -> None:
        included = self.repo / ".git/conditional-config"
        self.git("config", "--file", str(included), "core.autocrlf", "true")
        self.git("config", f"includeIf.gitdir:{self.repo}/.git.path", str(included))
        self.assertEqual(self.git("config", "--get", "core.autocrlf").stdout.strip(), "true")
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("configuration changes under isolated inspection", completed.stderr)

    def test_ambient_git_overrides_cannot_redirect_storage_or_write_traces(self) -> None:
        completed, data = self.invoke("review", extra_environment={
            "GIT_INDEX_FILE": str(self.repo / "other-index"),
            "GIT_TRACE": str(self.repo / "trace"),
            "GIT_TRACE2_EVENT": str(self.repo / "events"),
        })
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["ready"])

    def test_global_trace_configuration_cannot_write_during_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            configuration = Path(directory) / "git/config"
            configuration.parent.mkdir()
            for kind in ("normal", "event", "perf"):
                self.git(
                    "config", "--file", str(configuration), f"trace2.{kind}Target",
                    str(self.repo / ".git" / f"trace-{kind}"),
                )
            completed, data = self.invoke(
                "review", extra_environment={"XDG_CONFIG_HOME": directory},
            )
            self.assertEqual(completed.returncode, 0)
            self.assertTrue(data["ready"])
            self.assertEqual(tuple((self.repo / ".git").glob("trace-*")), ())

    def test_repository_local_temporary_directory_is_rejected_before_creation(self) -> None:
        temporary = self.repo / "temporary"
        temporary.mkdir()
        completed, data = self.invoke("review", extra_environment={"TMPDIR": str(temporary)})
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("outside the worktree", completed.stderr)

    def assert_preflight_rejected(self, repo: Path, environment: dict[str, str]) -> None:
        before = self.repository_snapshot()
        for output in ((), ("--output", str(self.repo.parent / "preflight-report.json"))):
            with (
                patch.dict(os.environ, environment),
                patch.object(delivery.subprocess, "run", side_effect=AssertionError("launched executable")) as command,
                patch.object(delivery.tempfile, "gettempdir", side_effect=AssertionError("probed temporary storage")),
                patch.object(delivery.tempfile, "TemporaryDirectory", side_effect=AssertionError("allocated temporary storage")),
                patch.object(delivery.tempfile, "mkdtemp", side_effect=AssertionError("allocated temporary storage")),
                redirect_stdout(io.StringIO()) as stdout,
                redirect_stderr(io.StringIO()) as stderr,
            ):
                result = delivery.main(("--repo", str(repo), "--mode", "review", "--format", "json", *output))
            self.assertEqual(result, 2)
            command.assert_not_called()
            self.assertEqual(stdout.getvalue(), "")
            self.assertTrue(stderr.getvalue().startswith("DIP delivery identity failed: "))
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(self.repository_snapshot(), before)

    def test_preflight_rejects_nested_missing_and_file_roots_without_executables(self) -> None:
        self.write("nested/child/keep", "fixture\n")
        for name in ("TMPDIR", "TMP", "TEMP"):
            for repo in (self.repo / "nested/child", self.repo / "absent", self.repo / "base.txt"):
                with self.subTest(variable=name, repo=repo):
                    self.assert_preflight_rejected(repo, {name: str(self.repo / ".git")})
        original = self.repo
        self.repo = original / "nested/child"
        try:
            before = self.repository_snapshot(original)
            completed, data = self.invoke("review", extra_environment={"TMPDIR": str(original / ".git")})
            self.assertEqual(completed.returncode, 2)
            self.assertIsNone(data)
            self.assertEqual(self.repository_snapshot(original), before)
            self.assertFalse((original / ".git/xcrun_db").exists())
        finally:
            self.repo = original

    def test_preflight_rejects_every_unsafe_temp_setting_and_symlink_before_git(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            (external / "git-link").symlink_to(self.repo / ".git", target_is_directory=True)
            (external / "repo-link").symlink_to(self.repo, target_is_directory=True)
            targets = (self.repo, self.repo / ".git", self.repo / ".git/missing/child",
                       external / "git-link", external / "repo-link/missing")
            for variable in ("TMPDIR", "TMP", "TEMP"):
                for target in targets:
                    with self.subTest(variable=variable, target=target):
                        environment = {name: directory for name in ("TMPDIR", "TMP", "TEMP")}
                        environment[variable] = str(target)
                        self.assert_preflight_rejected(self.repo, environment)
            with patch.object(delivery.tempfile, "tempdir", str(self.repo / ".git")):
                self.assert_preflight_rejected(self.repo, {"TMPDIR": directory})

    def test_preflight_rejects_case_alias_temp_locations_before_git(self) -> None:
        alias = self.repo.with_name(self.repo.name.upper())
        if alias == self.repo or not alias.exists():
            self.skipTest("A case-insensitive filesystem is required for the macOS regression.")
        self.assertTrue(alias.samefile(self.repo))
        for variable in ("TMPDIR", "TMP", "TEMP"):
            for target in (alias, alias / ".GIT", alias / ".GIT/missing"):
                with self.subTest(variable=variable, target=target):
                    self.assert_preflight_rejected(self.repo, {variable: str(target)})

    def test_preflight_resolves_linked_worktree_and_shared_common_directory(self) -> None:
        original = self.repo
        with tempfile.TemporaryDirectory() as directory:
            linked = Path(directory).resolve() / "linked"
            self.git("worktree", "add", "-q", "-b", "preflight", str(linked))
            git_dir = Path((linked / ".git").read_text().strip().removeprefix("gitdir: "))
            # Exercise relative .git and commondir pointers, both resolved by Python.
            (linked / ".git").write_text("gitdir: " + os.path.relpath(git_dir, linked) + "\n")
            (linked / "nested").mkdir()
            alias = Path(directory) / "common-link"
            alias.symlink_to(original / ".git", target_is_directory=True)
            common_before = self.repository_snapshot(original)
            self.repo = linked
            try:
                for variable in ("TMPDIR", "TMP", "TEMP"):
                    for target in (git_dir, original / ".git", alias):
                        with self.subTest(variable=variable, target=target):
                            self.assert_preflight_rejected(linked, {variable: str(target)})
                            self.assert_preflight_rejected(linked / "nested", {variable: str(target)})
                with patch.dict(os.environ, {name: directory for name in ("TMPDIR", "TMP", "TEMP")}):
                    preflight = delivery._preflight(linked)
                    self.assertTrue(preflight.git_dir.samefile(git_dir))
                    self.assertTrue(preflight.common.samefile(original / ".git"))
                    completed, data = self.invoke("review")
                self.assertEqual(completed.returncode, 0)
                self.assertTrue(data["ready"])
                self.assertEqual(self.repository_snapshot(original), common_before)
            finally:
                self.repo = original

    def test_preflight_rejects_invalid_and_oversized_git_markers_before_git(self) -> None:
        self.write("invalid/keep", "fixture\n")
        root = self.repo / "invalid"
        marker = root / ".git"
        for value in (b"", b"gitdir: \n", b"wrong: path\n", b"gitdir: missing\n",
                      b"gitdir: bad\0path\n", b"gitdir: \xff\n", b"x" * 65537):
            marker.write_bytes(value)
            with self.subTest(value=value[:30]):
                self.assert_preflight_rejected(root, {})
        marker.unlink()
        marker.mkdir()
        self.assert_preflight_rejected(root, {})
        (marker / "HEAD").write_text("ref: refs/heads/main\n")
        (marker / "objects").mkdir()
        (marker / "refs").mkdir()
        for value in ("", "not a Git HEAD\n"):
            (marker / "HEAD").write_text(value)
            self.assert_preflight_rejected(root, {})
        (marker / "HEAD").write_text("ref: refs/heads/main\n")
        for value in (b"", b"missing\n", b"x" * 65537):
            (marker / "commondir").write_bytes(value)
            self.assert_preflight_rejected(root, {})

    def test_preflight_external_storage_is_used_for_git_and_temporary_allocations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory).resolve()
            before = self.repository_snapshot()
            run = delivery.subprocess.run
            allocate = delivery.tempfile.TemporaryDirectory
            commands = []
            parents = []

            def checked_run(*args, **kwargs):
                commands.append(args)
                for name in ("TMPDIR", "TMP", "TEMP"):
                    self.assertEqual(Path(kwargs["env"][name]), external)
                return run(*args, **kwargs)

            def checked_allocate(*args, **kwargs):
                parents.append(Path(kwargs["dir"]))
                self.assertEqual(parents[-1], external)
                return allocate(*args, **kwargs)

            with (
                patch.dict(os.environ, {name: directory for name in ("TMPDIR", "TMP", "TEMP")}),
                patch.object(delivery.tempfile, "gettempdir", side_effect=AssertionError("unverified probe")),
                patch.object(delivery.subprocess, "run", side_effect=checked_run),
                patch.object(delivery.tempfile, "TemporaryDirectory", side_effect=checked_allocate),
            ):
                identity = delivery.inspect_repository(self.repo, "review")
                self.assertTrue(identity.ready)
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(delivery.main(("--repo", str(self.repo), "--mode", "review",
                                                    "--format", "json", "--output", str(external / "report.json"))), 0)
            self.assertTrue(json.loads((external / "report.json").read_text())["ready"])
            self.assertTrue(commands)
            self.assertGreaterEqual(len(parents), 2)
            self.assertEqual(self.repository_snapshot(), before)

    def test_intent_to_add_is_rejected_before_derivation_even_for_empty_files(self) -> None:
        for content in ("", "new\n"):
            with self.subTest(content=content):
                self.write("intent", content)
                self.git("add", "-N", "intent")
                completed, data = self.invoke("review")
                self.assert_invalid(completed, data, "index contains intent-to-add paths")
                self.assertEqual(data["diff_check"], "not-run")
                with patch.object(delivery, "_candidate", side_effect=AssertionError("derived intent")):
                    self.assertFalse(delivery.inspect_repository(self.repo, "review").ready)

    def test_whitespace_failure_suppresses_tree_and_totals(self) -> None:
        self.write("base.txt", "trailing whitespace \n")
        completed, data = self.invoke("review")
        self.assert_invalid(completed, data, "candidate diff fails whitespace validation")
        self.assertEqual(data["diff_check"], "fail")

    def test_other_failed_prerequisites_never_publish_identity(self) -> None:
        self.write("unexpected", "extra\n")
        completed, data = self.invoke("review", "--expected-path", "other")
        self.assert_invalid(completed, data, "candidate paths differ from expected paths")
        self.git("checkout", "--detach", "-q")
        completed, data = self.invoke("review")
        self.assert_invalid(completed, data, "detached HEAD")
        completed, data = self.invoke("review", "--main-ref", "missing")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertNotIn("Traceback", completed.stderr)

    def test_markdown_round_trips_every_dynamic_field(self) -> None:
        identity = delivery.inspect_repository(self.repo, "review")
        hostile = "host`ile\n- Ready: `yes`\t\x01\u202e\u2603%20"
        changes = {}
        for name, item in asdict(identity).items():
            if isinstance(item, str):
                changes[name] = hostile
            elif isinstance(item, tuple):
                changes[name] = (hostile, "null", "")
        identity = replace(identity, **changes)
        markdown = delivery.render_markdown(identity)
        self.assert_markdown_matches_json(markdown, asdict(identity))
        self.assertNotIn(hostile, markdown)
        self.assertIn(quote(hostile, safe='/._-+'), markdown)
        self.assertEqual(markdown, delivery.render_markdown(identity))

    def test_hostile_worktree_path_is_safe_in_ready_and_invalid_reports(self) -> None:
        original = self.repo
        hostile = original / "root`\n- Ready: `yes`\t\x01\u2603"
        self.git("clone", "-q", "--no-hardlinks", str(original), str(hostile))
        self.repo = hostile
        try:
            for detached in (False, True):
                if detached:
                    self.git("checkout", "--detach", "-q")
                completed, payload = self.invoke("review")
                self.assertEqual(completed.returncode, 2 if detached else 0)
                before = self.repository_snapshot()
                report = subprocess.run(
                    (sys.executable, str(SCRIPT), "--repo", str(hostile), "--mode", "review"),
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(report.returncode, completed.returncode)
                self.assertEqual(self.repository_snapshot(), before)
                self.assert_markdown_matches_json(report.stdout, payload)
                self.assertNotIn("\n- Ready: `yes`\n", report.stdout)
        finally:
            self.repo = original

    def test_hostile_rename_totals_count_addition_and_deletion(self) -> None:
        name = "one\ttwo\tthree\n`\x01\u2603.txt"
        self.git("mv", "base.txt", name)
        completed, data = self.invoke("review", "--expected-path", "base.txt", "--expected-path", name)
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(data["ready"])
        self.assertEqual((data["insertions"], data["deletions"]), (1, 1))
        self.assertEqual(data["candidate_paths"], ["base.txt", name])
        identity = delivery.inspect_repository(self.repo, "review", ("base.txt", name))
        self.assert_markdown_matches_json(delivery.render_markdown(identity), data)

    def test_filename_pathspec_syntax_is_treated_literally(self) -> None:
        name = ":(exclude)*"
        self.write(name, "literal\n")
        completed, data = self.invoke("review", "--expected-path", name)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(data["candidate_paths"], [name])
        self.assertEqual((data["insertions"], data["deletions"]), (1, 0))

    def test_non_utf8_index_path_has_stable_cli_failure(self) -> None:
        blob = self.git("rev-parse", "HEAD:base.txt").stdout.strip().encode()
        subprocess.run(
            ("git", "update-index", "--index-info"), cwd=self.repo,
            input=b"100644 " + blob + b"\tbad-\xff.txt\n", check=True,
        )
        completed, data = self.invoke("review")
        self.assertEqual(completed.returncode, 2)
        self.assertIsNone(data)
        self.assertIn("non-UTF-8 path", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)


class DeliveryGovernanceTestCase(unittest.TestCase):
    def test_root_preserves_repository_wide_architecture_and_persistence_rules(self) -> None:
        text = " ".join((ROOT / "AGENTS.md").read_text().split())
        obligations = (
            "docs/IntelligenceHistory.md", "docs/PersistenceArchitecture.md",
            "docs/MarketplaceArchitecture.md", "append-only", "no partial execution persistence",
            "must not recalculate intelligence", "registry of module comparers",
            "reconstruct validated domain models rather than raw rows", "Singular absence",
            "empty immutable collection", "registries/allow-lists", "duplicate JSON keys",
            "reconstructed naive values must remain naive", "stable secondary keys",
            "Migrations are atomic", "savepoints inside outer transactions",
            "roll back schema, data and version", "genuine previous-version schemas",
            "schema/migration parity", "reject booleans where integers are required",
            "preserve useful exception causes", "serialization failure before mutation",
            "Implement only the requested slice", "Update architecture documentation",
        )
        for obligation in obligations:
            with self.subTest(obligation=obligation):
                self.assertIn(obligation, text)

    def test_completion_gates_are_explicit_and_sections_are_unique(self) -> None:
        raw = (ROOT / "AGENTS.md").read_text()
        headings = re.findall(r"^## (.+)$", raw, flags=re.MULTILINE)
        self.assertEqual(len(headings), len(set(value.lower() for value in headings)))
        text = " ".join(raw.split())
        for obligation in (
            "always run the full test suite", "compilation or type checks",
            "`git diff --check`", "exact scope", "including new files",
            "graphical tests as skips, never passes", "isolated artifact builds",
            "installed artifact validation outside the checkout", "Never weaken coverage",
            "uncommitted and unstaged", "independent read-only review",
            "final committed-diff review", "Human approval is required",
        ):
            with self.subTest(obligation=obligation):
                self.assertIn(obligation, text)

    def test_skill_routes_all_seven_modes_and_retains_separate_authorization(self) -> None:
        skill = ROOT / ".agents/skills/dip-delivery/SKILL.md"
        text = skill.read_text()
        self.assertTrue(text.startswith("---\nname: dip-delivery\n"))
        self.assertIn("references/modes.md", text)
        self.assertIn("Authorization for one phase never authorizes the next", text)
        modes = (skill.parent / "references/modes.md").read_text()
        self.assertEqual(tuple(re.findall(r"^## (.+)$", modes, re.MULTILINE)), delivery.MODES)
        self.assertIn("Approval grants no mutation", modes)


if __name__ == "__main__":
    unittest.main()
