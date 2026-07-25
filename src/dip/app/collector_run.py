"""Application orchestration for the legacy Discogs Marketplace refresh stage."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


class CollectorRunStatus(str, Enum):
    """Terminal outcome of a Collector Run refresh stage."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value < 0:
        raise ValueError(f"{name} must be zero or greater.")
    return value


def _release_id(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{name} must be positive.")
    return value


@dataclass(frozen=True)
class CollectorRunProgress:
    """Immutable progress emitted before and after provider attempts."""

    total_releases: int
    attempted_releases: int
    successful_releases: int
    failed_releases: int
    current_release_id: int | None = None

    def __post_init__(self) -> None:
        total = _count(self.total_releases, "total_releases")
        attempted = _count(self.attempted_releases, "attempted_releases")
        successful = _count(self.successful_releases, "successful_releases")
        failed = _count(self.failed_releases, "failed_releases")
        if attempted != successful + failed:
            raise ValueError(
                "attempted_releases must equal successful_releases plus "
                "failed_releases."
            )
        if attempted > total:
            raise ValueError("attempted_releases cannot exceed total_releases.")
        if attempted == 0 and self.current_release_id is not None:
            raise ValueError(
                "current_release_id must be None before the first attempt."
            )
        if attempted > 0 and self.current_release_id is None:
            raise ValueError(
                "current_release_id is required after an attempted release."
            )
        if self.current_release_id is not None:
            _release_id(self.current_release_id, "current_release_id")


@dataclass(frozen=True)
class CollectorRunResult:
    """Immutable terminal result of the legacy refresh stage."""

    analysis_run_id: int
    captured_at: datetime
    status: CollectorRunStatus
    total_releases: int
    attempted_releases: int
    successful_releases: int
    failed_releases: int
    failed_release_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        _release_id(self.analysis_run_id, "analysis_run_id")
        if not isinstance(self.captured_at, datetime):
            raise TypeError("captured_at must be a datetime.")
        if self.captured_at.tzinfo is None or self.captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware.")
        if not isinstance(self.status, CollectorRunStatus):
            raise TypeError("status must be a CollectorRunStatus.")

        total = _count(self.total_releases, "total_releases")
        attempted = _count(self.attempted_releases, "attempted_releases")
        successful = _count(self.successful_releases, "successful_releases")
        failed = _count(self.failed_releases, "failed_releases")
        if total == 0:
            raise ValueError("A terminal result must contain releases.")
        if attempted != successful + failed:
            raise ValueError(
                "attempted_releases must equal successful_releases plus "
                "failed_releases."
            )
        if attempted != total:
            raise ValueError("A terminal result must account for every release.")
        failed_ids = self.failed_release_ids
        if not isinstance(failed_ids, tuple):
            raise TypeError("failed_release_ids must be a tuple.")
        for index, release_id in enumerate(failed_ids):
            _release_id(release_id, f"failed_release_ids[{index}]")
        if len(failed_ids) != self.failed_releases:
            raise ValueError(
                "failed_release_ids must contain one identity per failed release."
            )
        if len(set(failed_ids)) != len(failed_ids):
            raise ValueError("failed_release_ids must not contain duplicates.")

        expected = (
            CollectorRunStatus.COMPLETED
            if self.failed_releases == 0
            else CollectorRunStatus.FAILED
            if self.successful_releases == 0
            else CollectorRunStatus.PARTIAL
        )
        if self.status is not expected:
            raise ValueError("status does not agree with the terminal counts.")


class CollectorRunUnavailableError(RuntimeError):
    """Raised when no stored collection is available to refresh."""


class CollectorRunExecutionError(RuntimeError):
    """Raised when execution encounters an unexpected fatal failure."""

    def __init__(
        self,
        analysis_run_id: int | None,
        attempted_releases: int,
        successful_releases: int,
        failed_releases: int,
    ) -> None:
        super().__init__(
            "Collector Run failed unexpectedly "
            f"after {attempted_releases} attempted release(s)."
        )
        self.analysis_run_id = (
            None
            if analysis_run_id is None
            else _release_id(analysis_run_id, "analysis_run_id")
        )
        self.attempted_releases = _count(
            attempted_releases, "attempted_releases"
        )
        self.successful_releases = _count(
            successful_releases, "successful_releases"
        )
        self.failed_releases = _count(failed_releases, "failed_releases")


class CollectorRunRepository(Protocol):
    """Narrow legacy persistence operations required by a Collector Run."""

    def release_ids(self) -> Sequence[int]: ...

    def start_analysis_run(
        self,
        run_type: str,
        source: str,
        application_version: str | None,
    ) -> int: ...

    def previous_snapshot(
        self, release_id: int, before: str
    ) -> object | None: ...

    def add_snapshot(
        self,
        analysis_run_id: int,
        release_id: int,
        captured_at: str,
        data: Mapping[str, Any],
    ) -> bool: ...

    def upsert_score(
        self,
        release_id: int,
        calculated_at: str,
        score: Mapping[str, Any],
    ) -> None: ...

    def complete_analysis_run(
        self,
        run_id: int,
        releases_attempted: int,
        releases_succeeded: int,
        releases_failed: int,
    ) -> None: ...

    def fail_analysis_run(
        self,
        run_id: int,
        error_message: str,
        releases_attempted: int,
        releases_succeeded: int,
        releases_failed: int,
    ) -> None: ...


class DiscogsReleaseProvider(Protocol):
    def get_release(self, release_id: int) -> Mapping[str, Any] | None: ...


ProgressCallback = Callable[[CollectorRunProgress], None]
ProviderFactory = Callable[[str], DiscogsReleaseProvider]
ScoreCalculator = Callable[
    [Mapping[str, Any], object | None], Mapping[str, Any]
]


def utc_now() -> datetime:
    """Return the production Collector Run clock value."""

    return datetime.now(timezone.utc)


class CollectorRunService:
    """Synchronously orchestrate the existing legacy Marketplace refresh."""

    _FATAL_MESSAGE = "Collector Run failed unexpectedly."
    _NO_SUCCESS_MESSAGE = (
        "Collector Run completed with no successful release refreshes."
    )

    def __init__(
        self,
        repository: CollectorRunRepository,
        provider_factory: ProviderFactory,
        score_calculator: ScoreCalculator,
        application_version: str,
        request_delay_seconds: float,
        *,
        clock: Callable[[], datetime] = utc_now,
        wait: Callable[[float], None],
    ) -> None:
        if not callable(provider_factory):
            raise TypeError("provider_factory must be callable.")
        if not callable(score_calculator):
            raise TypeError("score_calculator must be callable.")
        if not isinstance(application_version, str) or not application_version:
            raise ValueError("application_version must be non-empty.")
        if isinstance(request_delay_seconds, bool) or not isinstance(
            request_delay_seconds, (int, float)
        ):
            raise TypeError("request_delay_seconds must be numeric.")
        if request_delay_seconds < 0:
            raise ValueError("request_delay_seconds must be zero or greater.")
        if not callable(clock) or not callable(wait):
            raise TypeError("clock and wait must be callable.")
        self._repository = repository
        self._provider_factory = provider_factory
        self._score_calculator = score_calculator
        self._application_version = application_version
        self._request_delay_seconds = float(request_delay_seconds)
        self._clock = clock
        self._wait = wait

    def run(
        self,
        token: str,
        progress_callback: ProgressCallback | None = None,
    ) -> CollectorRunResult:
        if not isinstance(token, str):
            raise TypeError("token must be a string.")
        if not token.strip():
            raise ValueError("token must be non-empty.")
        if progress_callback is not None and not callable(progress_callback):
            raise TypeError("progress_callback must be callable.")

        release_ids = self._validated_release_ids(
            self._repository.release_ids()
        )
        if not release_ids:
            raise CollectorRunUnavailableError(
                "No stored collection is available for a Collector Run."
            )

        try:
            provider = self._provider_factory(token)
        except Exception as exc:
            raise CollectorRunExecutionError(None, 0, 0, 0) from exc
        captured_at = self._clock()
        if not isinstance(captured_at, datetime):
            raise TypeError("Collector Run clock must return a datetime.")
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("Collector Run clock must be timezone-aware.")
        captured_value = captured_at.isoformat(timespec="seconds")
        try:
            run_id = self._repository.start_analysis_run(
                run_type="market_refresh",
                source="discogs",
                application_version=self._application_version,
            )
            _release_id(run_id, "analysis_run_id")
        except Exception as exc:
            raise CollectorRunExecutionError(None, 0, 0, 0) from exc

        attempted = succeeded = failed = 0
        failed_ids: list[int] = []
        try:
            self._emit(
                progress_callback,
                CollectorRunProgress(len(release_ids), 0, 0, 0),
            )
            for position, release_id in enumerate(release_ids):
                attempted += 1
                try:
                    data = provider.get_release(release_id)
                except Exception:
                    data = None

                if data is None:
                    failed += 1
                    failed_ids.append(release_id)
                else:
                    previous = self._repository.previous_snapshot(
                        release_id, captured_value
                    )
                    self._repository.add_snapshot(
                        run_id, release_id, captured_value, data
                    )
                    score = self._score_calculator(data, previous)
                    self._repository.upsert_score(
                        release_id, captured_value, score
                    )
                    succeeded += 1

                self._emit(
                    progress_callback,
                    CollectorRunProgress(
                        len(release_ids),
                        attempted,
                        succeeded,
                        failed,
                        release_id,
                    ),
                )
                if position < len(release_ids) - 1:
                    self._wait(self._request_delay_seconds)

            status = (
                CollectorRunStatus.COMPLETED
                if failed == 0
                else CollectorRunStatus.FAILED
                if succeeded == 0
                else CollectorRunStatus.PARTIAL
            )
            if status is CollectorRunStatus.FAILED:
                self._repository.fail_analysis_run(
                    run_id,
                    self._NO_SUCCESS_MESSAGE,
                    attempted,
                    succeeded,
                    failed,
                )
            else:
                self._repository.complete_analysis_run(
                    run_id, attempted, succeeded, failed
                )
            return CollectorRunResult(
                run_id,
                captured_at,
                status,
                len(release_ids),
                attempted,
                succeeded,
                failed,
                tuple(failed_ids),
            )
        except Exception as exc:
            try:
                self._repository.fail_analysis_run(
                    run_id,
                    self._FATAL_MESSAGE,
                    attempted,
                    succeeded,
                    failed,
                )
            except Exception:
                pass
            raise CollectorRunExecutionError(
                run_id, attempted, succeeded, failed
            ) from exc

    @staticmethod
    def _validated_release_ids(values: Sequence[int]) -> tuple[int, ...]:
        if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
            raise TypeError("release_ids must be a sequence.")
        validated: list[int] = []
        seen: set[int] = set()
        for index, value in enumerate(values):
            release_id = _release_id(value, f"release_ids[{index}]")
            if release_id in seen:
                raise ValueError("release_ids must not contain duplicates.")
            seen.add(release_id)
            validated.append(release_id)
        return tuple(validated)

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        progress: CollectorRunProgress,
    ) -> None:
        if callback is not None:
            callback(progress)
