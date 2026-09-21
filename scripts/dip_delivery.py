#!/usr/bin/env python3
"""Report deterministic DIP delivery identity without mutating the repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote


MODES = ("plan", "implement", "correct", "review", "publish-pr", "merge-sync", "release")
HANDOFFS = {
    "plan": ("prepare an external specification", "scope acceptance"),
    "implement": ("prepare an isolated uncommitted candidate", "independent review"),
    "correct": ("apply only approved findings", "independent review"),
    "review": ("return a read-only review decision", "review resolution"),
    "publish-pr": ("verify the approved candidate identity", "commit and push authorization"),
    "merge-sync": ("verify the exact PR and CI identity", "merge authorization"),
    "release": ("verify release identity and artifacts", "tagging and publication authorization"),
}


class IdentityError(RuntimeError):
    """Raised when repository identity cannot be established safely."""


@dataclass(frozen=True)
class DeliveryIdentity:
    repository: str
    worktree: str
    mode: str
    branch: str | None
    head: str
    parent: str | None
    tree: str
    main_ref: str
    origin_main: str
    merge_base: str
    behind: int
    ahead: int
    modified_paths: tuple[str, ...]
    staged_paths: tuple[str, ...]
    untracked_paths: tuple[str, ...]
    candidate_paths: tuple[str, ...]
    diff_check: str
    expected_paths: tuple[str, ...] | None
    paths_match: bool | None
    candidate_tree: str | None
    unmerged_paths: tuple[str, ...]
    insertions: int | None
    deletions: int | None
    next_permitted_action: str
    human_decision_required: str
    ready: bool
    failures: tuple[str, ...]


def _inside(path: Path, directory: Path) -> bool:
    # Existing ancestors also establish containment for absent suffixes and
    # case aliases. Resolve separately at call sites to check lexical aliases too.
    for ancestor in (path, *path.parents):
        try:
            if ancestor.samefile(directory):
                return True
        except FileNotFoundError:
            continue
    return False


@dataclass(frozen=True)
class _Preflight:
    root: Path
    git_dir: Path
    common: Path
    temporary: Path


def _read_git_marker(path: Path) -> str:
    # Only regular files; bound reads rather than following arbitrary marker
    # chains. Embedded newlines in a filesystem path remain meaningful.
    if not path.is_file():
        raise IdentityError("invalid Git directory marker")
    with path.open("rb") as source:
        raw = source.read(65537)
    if not raw or len(raw) > 65536 or b"\0" in raw:
        raise IdentityError("invalid Git directory marker")
    return raw.decode("utf-8").removesuffix("\n")


def _preflight(repo: Path) -> _Preflight:
    # No executable or tempfile API may precede this filesystem-only boundary:
    # even the macOS Git launcher can write TMPDIR/xcrun_db before Git starts.
    # This validates the local layout, not Git identity (which Git derives later).
    try:
        root = repo.resolve(strict=True)
        if not root.is_dir():
            raise IdentityError("repository path must be an existing worktree root directory")
        marker = root / ".git"
        if marker.is_dir():
            git_dir = marker.resolve(strict=True)
        else:
            value = _read_git_marker(marker)
            if not value.startswith("gitdir: ") or not value[len("gitdir: "):]:
                raise IdentityError("invalid Git directory marker")
            git_dir = (root / value[len("gitdir: "):]).resolve(strict=True)
        common = git_dir
        common_marker = git_dir / "commondir"
        if common_marker.exists() or common_marker.is_symlink():
            value = _read_git_marker(common_marker)
            if not value:
                raise IdentityError("invalid Git common-directory marker")
            common = (git_dir / value).resolve(strict=True)
        if not (git_dir.is_dir() and (git_dir / "HEAD").is_file()
                and (common / "objects").is_dir() and (common / "refs").is_dir()):
            raise IdentityError("invalid repository/worktree Git directory layout")
        head = _read_git_marker(git_dir / "HEAD")
        if not re.fullmatch(r"ref: refs/[^\x00-\x20\x7f]+|[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", head):
            raise IdentityError("invalid Git HEAD marker")
        candidates = [os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")]
        candidates.append(tempfile.tempdir)  # Read the cache; do not call gettempdir().
        configured = [Path(os.fsdecode(value)).resolve() for value in candidates if value is not None]
        protected = (root, git_dir, common)
        if any(_inside(path, directory) for path in configured for directory in protected):
            raise IdentityError("temporary storage must be outside the worktree and Git common directory")
        # Avoid tempfile's write probes and its final working-directory fallback.
        # Every allocation and Git launcher uses this verified external parent.
        for path in (*configured, Path("/tmp").resolve(), Path("/var/tmp").resolve()):
            if (path.is_dir() and not any(_inside(path, directory) for directory in protected)
                    and os.access(path, os.W_OK | os.X_OK)):
                return _Preflight(root, git_dir, common, path)
        raise IdentityError("no verified external temporary directory is available")
    except IdentityError:
        raise
    except (OSError, UnicodeError, RuntimeError) as error:
        raise IdentityError("invalid repository/worktree filesystem preflight") from error


def _git_environment() -> dict[str, str]:
    # Ambient Git overrides can redirect storage, enable tracing to files, or
    # inject configuration. The explicit repository and temporary stores win.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1",
        GIT_TRACE2="0", GIT_TRACE2_EVENT="0", GIT_TRACE2_PERF="0",
    )
    return environment


def _git(
    repo: Path, *arguments: str, env: dict[str, str] | None = None,
    input: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    preflight = _preflight(repo)
    environment = dict(_git_environment() if env is None else env)
    environment.update({name: str(preflight.temporary) for name in ("TMPDIR", "TEMP", "TMP")})
    return subprocess.run(
        (
            "git", "--no-pager", "--literal-pathspecs",
            "-c", "core.splitIndex=false", "-c", "core.fsmonitor=false",
            "-c", "core.untrackedCache=false", "-c", f"core.hooksPath={os.devnull}",
            "-c", "gc.auto=0", "-c", "maintenance.auto=false",
            "-c", "submodule.recurse=false", *arguments,
        ),
        cwd=repo, env=environment, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, input=input,
    )


def _run(
    repo: Path, *arguments: str, env: dict[str, str] | None = None,
    input: bytes | None = None,
) -> bytes:
    completed = _git(repo, *arguments, env=env, input=input)
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise IdentityError(f"git {' '.join(arguments)} failed: {detail}")
    return completed.stdout


def _text(repo: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    try:
        return _run(repo, *arguments, env=env).decode("utf-8").removesuffix("\n")
    except UnicodeDecodeError as error:
        raise IdentityError("Git reported non-UTF-8 identity data; refusing to continue") from error


def _require_safe_configuration(repo: Path, env: dict[str, str]) -> None:
    # Configuration, index enumeration and attribute lookup do not run filters.
    # Reject applicable conversions before diff/add; disabling them silently
    # would change blob identity. Unused global drivers (e.g. LFS) are harmless.
    configuration = _run(repo, "config", "--null", "--list", env=env)
    drivers = set()
    for entry in configuration.split(b"\0"):
        key, _, value = entry.partition(b"\n")
        if key == b"extensions.partialclone" or (
            re.fullmatch(rb"remote\..*\.promisor", key) and value.lower() not in (b"false", b"0")
        ):
            raise IdentityError("partial clone configuration prevents read-only inspection")
        match = re.fullmatch(rb"filter\.(.*)\.(clean|process)", key)
        if value and match:
            drivers.add(match[1])
    if not drivers:
        return
    paths = _paths(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z", env=env)
    attributes = _run(
        repo, "check-attr", "-z", "--stdin", "filter",
        input=b"".join(path.encode("utf-8") + b"\0" for path in paths),
        env=env,
    ).split(b"\0")
    for driver in attributes[2::3]:
        if driver in drivers:
            raise IdentityError("configured clean/process filters prevent read-only inspection")


def _paths(repo: Path, *arguments: str, env: dict[str, str] | None = None) -> tuple[str, ...]:
    raw = _run(repo, *arguments, env=env)
    paths = []
    for value in raw.split(b"\0"):
        if not value:
            continue
        try:
            paths.append(value.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise IdentityError("Git reported a non-UTF-8 path; refusing to continue") from error
    return tuple(sorted(paths))


@contextmanager
def _inspection_environment(repo: Path) -> Iterator[dict[str, str]]:
    configuration = _run(repo, "config", "--null", "--list")
    git_dir = Path(_text(repo, "rev-parse", "--absolute-git-dir"))
    common = Path(_text(repo, "rev-parse", "--git-common-dir"))
    common = (repo / common).resolve()
    object_source = (repo / _text(repo, "rev-parse", "--git-path", "objects")).resolve()
    alternates = object_source / "info/alternates"
    if alternates.exists() and alternates.read_bytes().strip():
        raise IdentityError("alternate object stores prevent read-only inspection")
    parent = _preflight(repo).temporary
    with tempfile.TemporaryDirectory(prefix="dip-inspection-", dir=parent) as directory:
        temporary = Path(directory)
        private_git = temporary / "git"
        private_git.mkdir()
        (private_git / "commondir").write_text(str(common) + "\n", encoding="utf-8")
        # Even reads can refresh shared-index timestamps. Git can also freshen
        # existing loose objects in an alternate store during add/write-tree.
        # Copy, never hardlink, both stores before any index/content inspection.
        for source in (git_dir / "HEAD", git_dir / "index", git_dir / "config.worktree",
                       *git_dir.glob("sharedindex.*")):
            if source.is_file():
                shutil.copyfile(source, private_git / source.name)
        objects = temporary / "objects"
        shutil.copytree(object_source, objects)
        environment = _git_environment()
        environment.update(
            GIT_DIR=str(private_git), GIT_COMMON_DIR=str(common),
            GIT_WORK_TREE=str(repo), GIT_INDEX_FILE=str(private_git / "index"),
            GIT_OBJECT_DIRECTORY=str(objects),
        )
        # A gitdir-conditional include must not silently disappear on relocation.
        if _run(repo, "config", "--null", "--list", env=environment) != configuration:
            raise IdentityError("Git configuration changes under isolated inspection")
        yield environment


def _candidate(
    repo: Path, paths: tuple[str, ...], head: str,
    env: dict[str, str],
) -> tuple[str | None, int | None, int | None, str]:
    temporary_parent = _preflight(repo).temporary
    with tempfile.TemporaryDirectory(prefix="dip-delivery-", dir=temporary_parent) as directory:
        environment = dict(env)
        environment["GIT_INDEX_FILE"] = str(Path(directory) / "index")
        _run(repo, "read-tree", head, env=environment)
        if paths:
            _run(repo, "add", "-A", "--", *paths, env=environment)
        check = _git(
            repo, "diff", "--no-ext-diff", "--no-textconv", "--cached", "--check", head,
            env=environment,
        )
        if check.returncode:
            return None, None, None, "fail"
        numstat = _run(
            repo, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
            "--cached", "--numstat", "-z", head, env=environment,
        )
        insertions = deletions = 0
        for field in (value for value in numstat.split(b"\0") if value):
            parts = field.split(b"\t", 2)
            if len(parts) != 3 or any(value != b"-" and not value.isdigit() for value in parts[:2]):
                raise IdentityError("Git reported invalid diff totals; refusing to continue")
            insertions += 0 if parts[0] == b"-" else int(parts[0])
            deletions += 0 if parts[1] == b"-" else int(parts[1])
        tree = _text(repo, "write-tree", env=environment)
        return tree, insertions, deletions, "pass"


def inspect_repository(
    repo: Path,
    mode: str,
    expected_paths: tuple[str, ...] | None = None,
    main_ref: str = "origin/main",
) -> DeliveryIdentity:
    if mode not in MODES:
        raise IdentityError("unknown delivery mode")
    requested = _preflight(repo).root
    root = Path(_text(requested, "rev-parse", "--show-toplevel")).resolve()
    if requested != root:
        raise IdentityError(f"repository path must be the worktree root: {root}")
    with _inspection_environment(root) as environment:
        return _inspect_repository(root, mode, expected_paths, main_ref, environment)


def _inspect_repository(
    root: Path, mode: str, expected_paths: tuple[str, ...] | None,
    main_ref: str, env: dict[str, str],
) -> DeliveryIdentity:
    _require_safe_configuration(root, env)
    head = _text(root, "rev-parse", "HEAD", env=env)
    tree = _text(root, "rev-parse", "HEAD^{tree}", env=env)
    branch_value = _text(root, "branch", "--show-current", env=env)
    branch = branch_value or None
    parent_process = _git(root, "rev-parse", "HEAD^", env=env)
    parent = parent_process.stdout.decode("utf-8").strip() if parent_process.returncode == 0 else None
    origin_main = _text(root, "rev-parse", main_ref, env=env)
    merge_base = _text(root, "merge-base", "HEAD", main_ref, env=env)
    behind_text, ahead_text = _text(
        root, "rev-list", "--left-right", "--count", f"{main_ref}...HEAD", env=env,
    ).split()
    diff_options = ("--no-ext-diff", "--no-textconv", "--no-renames", "--name-only", "-z")
    modified = _paths(root, "diff", *diff_options, env=env)
    staged = _paths(root, "diff", "--cached", *diff_options, env=env)
    untracked = _paths(root, "ls-files", "--others", "--exclude-standard", "-z", env=env)
    candidate_paths = tuple(sorted(set(modified) | set(staged) | set(untracked)))
    normalized_expected = None if expected_paths is None else tuple(sorted(expected_paths))
    paths_match = (
        None
        if normalized_expected is None
        else len(set(normalized_expected)) == len(normalized_expected)
        and candidate_paths == normalized_expected
    )
    failures = []
    if branch is None:
        failures.append("detached HEAD")
    if paths_match is False:
        failures.append("candidate paths differ from expected paths")
    unmerged = _paths(root, "ls-files", "-u", "-z", env=env)
    if unmerged:
        failures.append("index contains unmerged paths")
    visible = _paths(root, "diff", "--cached", "--ita-visible-in-index", *diff_options, env=env)
    invisible = _paths(root, "diff", "--cached", "--ita-invisible-in-index", *diff_options, env=env)
    if set(visible) != set(invisible):
        failures.append("index contains intent-to-add paths")
    candidate_tree = None
    insertions = deletions = None
    diff_check = "not-run"
    if not failures:
        candidate_tree, insertions, deletions, diff_check = _candidate(root, candidate_paths, head, env)
        if diff_check != "pass":
            failures.append("candidate diff fails whitespace validation")
    if failures:
        candidate_tree = insertions = deletions = None
    next_action, decision = HANDOFFS[mode]
    return DeliveryIdentity(
        str(root), str(root), mode, branch, head, parent, tree, main_ref,
        origin_main, merge_base, int(behind_text), int(ahead_text), modified,
        staged, untracked, candidate_paths, diff_check, normalized_expected,
        paths_match, candidate_tree, unmerged, insertions, deletions, next_action,
        decision,
        not failures, tuple(failures),
    )


def render_markdown(identity: DeliveryIdentity) -> str:
    def value(item: object) -> str:
        if isinstance(item, str):
            return f"`{quote(item, safe='/._-+')}`"
        if isinstance(item, tuple):
            return "[" + ", ".join(value(part) for part in item) + "]"
        return json.dumps(item)

    # Include every JSON field. Code spans are percent-encoded UTF-8 strings;
    # bare null/booleans/numbers and bracketed lists retain their JSON types.
    lines = ["# DIP delivery identity", "", "String values use UTF-8 percent encoding.", ""]
    for name, item in asdict(identity).items():
        lines.append(f"- {name.replace('_', ' ').capitalize()}: {value(item)}")
    return "\n".join(lines) + "\n"


def _safe_output_path(output: Path, repo: Path) -> Path:
    preflight = _preflight(repo)
    lexical = Path(os.path.abspath(output))
    resolved = output.resolve()

    if any(
        _inside(candidate, directory)
        for candidate in (lexical, resolved)
        for directory in (preflight.root, preflight.git_dir, preflight.common)
    ):
        raise IdentityError("--output must be outside the worktree and Git common directory")
    if resolved.is_file() and resolved.stat().st_nlink > 1:
        raise IdentityError("--output must not overwrite a multiply linked file")
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--expected-path", action="append", default=None)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args(argv)
    try:
        output_path = None if arguments.output is None else _safe_output_path(arguments.output, arguments.repo)
        identity = inspect_repository(
            arguments.repo, arguments.mode,
            None if arguments.expected_path is None else tuple(arguments.expected_path),
            arguments.main_ref,
        )
    except (IdentityError, OSError, UnicodeError) as error:
        print(f"DIP delivery identity failed: {error}", file=sys.stderr)
        return 2
    output = (
        json.dumps(asdict(identity), indent=2, sort_keys=True) + "\n"
        if arguments.format == "json" else render_markdown(identity)
    )
    try:
        if output_path is None:
            sys.stdout.write(output)
        else:
            output_path.write_text(output, encoding="utf-8")
    except (OSError, UnicodeError):
        print("DIP delivery identity failed: unable to write report", file=sys.stderr)
        return 2
    return 0 if identity.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())
