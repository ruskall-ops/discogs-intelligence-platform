from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from dip.app.collector_run import (
    CollectorRunExecutionError,
    CollectorRunProgress,
    CollectorRunResult,
    CollectorRunService,
    CollectorRunStatus,
    CollectorRunUnavailableError,
)
from dip.intelligence.modules.opportunity_scoring import calculate
from dip.persistence.sqlite import Database


CAPTURED_AT = datetime(2026, 7, 25, 9, 30, 45, tzinfo=timezone.utc)


class _Provider:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_release(self, release_id):
        self.calls.append(release_id)
        response = self.responses[release_id]
        if isinstance(response, Exception):
            raise response
        return response


class _Repository:
    def __init__(self, release_ids=(3, 1, 2)):
        self.ids = release_ids
        self.events = []
        self.run_id = 41
        self.fail_on = None

    def release_ids(self):
        self.events.append(("release_ids",))
        return self.ids

    def start_analysis_run(self, run_type, source, application_version):
        self.events.append(
            ("start", run_type, source, application_version)
        )
        return self.run_id

    def previous_snapshot(self, release_id, before):
        self.events.append(("previous", release_id, before))
        if self.fail_on == ("previous", release_id):
            raise OSError("storage unavailable")
        return {"wants": 1, "copies_for_sale": 2, "lowest_price": 3}

    def add_snapshot(self, run_id, release_id, captured_at, data):
        self.events.append(
            ("snapshot", run_id, release_id, captured_at, data)
        )
        if self.fail_on == ("snapshot", release_id):
            raise OSError("snapshot failed")
        return True

    def upsert_score(self, release_id, captured_at, score):
        self.events.append(("score", release_id, captured_at, score))
        if self.fail_on == ("score", release_id):
            raise OSError("score persistence failed")

    def complete_analysis_run(
        self, run_id, releases_attempted, releases_succeeded, releases_failed
    ):
        self.events.append(
            (
                "complete",
                run_id,
                releases_attempted,
                releases_succeeded,
                releases_failed,
            )
        )

    def fail_analysis_run(
        self,
        run_id,
        error_message,
        releases_attempted,
        releases_succeeded,
        releases_failed,
    ):
        self.events.append(
            (
                "fail",
                run_id,
                error_message,
                releases_attempted,
                releases_succeeded,
                releases_failed,
            )
        )


def _facts(wants=10):
    return {
        "wants": wants,
        "haves": 5,
        "copies_for_sale": 2,
        "lowest_price": 12.5,
        "currency": "GBP",
        "styles": "",
        "genres": "",
        "discogs_uri": "",
    }


class CollectorRunServiceTestCase(unittest.TestCase):
    def service(
        self,
        repository=None,
        responses=None,
        *,
        score_calculator=lambda current, previous: {"score": current["wants"]},
        callback=None,
    ):
        repository = repository or _Repository()
        provider = _Provider(
            responses
            or {release_id: _facts(release_id) for release_id in repository.ids}
        )
        factory_calls = []
        clock_calls = []
        waits = []

        def factory(token):
            factory_calls.append(token)
            return provider

        def clock():
            clock_calls.append(True)
            return CAPTURED_AT

        service = CollectorRunService(
            repository,
            factory,
            score_calculator,
            "0.4.0",
            1.08,
            clock=clock,
            wait=waits.append,
        )
        return service, repository, provider, factory_calls, clock_calls, waits

    def test_empty_collection_fails_before_provider_or_mutation(self):
        repository = _Repository(())
        service, _, _, factory_calls, clock_calls, _ = self.service(repository)

        with self.assertRaises(CollectorRunUnavailableError):
            service.run("temporary-token")

        self.assertEqual(repository.events, [("release_ids",)])
        self.assertEqual(factory_calls, [])
        self.assertEqual(clock_calls, [])

    def test_invalid_token_is_rejected_before_repository_or_provider_access(self):
        for token, error in ((None, TypeError), ("", ValueError)):
            with self.subTest(token=token):
                repository = _Repository((1,))
                service, _, _, factory_calls, _, _ = self.service(repository)

                with self.assertRaises(error):
                    service.run(token)  # type: ignore[arg-type]

                self.assertEqual(repository.events, [])
                self.assertEqual(factory_calls, [])

    def test_provider_factory_failure_is_chained_as_application_error(self):
        primary = RuntimeError("provider factory contained sensitive detail")
        events = []

        class Repository(_Repository):
            def release_ids(self):
                events.append("release_ids")
                return (1,)

        def factory(token):
            events.append("provider_factory")
            raise primary

        repository = Repository()
        service = CollectorRunService(
            repository,
            factory,
            lambda current, previous: {},
            "0.4.0",
            0,
            clock=lambda: CAPTURED_AT,
            wait=lambda seconds: None,
        )

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIs(caught.exception.__cause__, primary)
        self.assertIsNone(caught.exception.analysis_run_id)
        self.assertEqual(caught.exception.attempted_releases, 0)
        self.assertEqual(caught.exception.successful_releases, 0)
        self.assertEqual(caught.exception.failed_releases, 0)
        self.assertNotIn("temporary-token", str(caught.exception))
        self.assertNotIn(str(primary), str(caught.exception))
        self.assertEqual(events, ["release_ids", "provider_factory"])
        self.assertEqual(repository.events, [])

    def test_analysis_run_start_failure_is_chained_as_application_error(self):
        primary = OSError("analysis start contained storage detail")
        events = []
        provider = _Provider({1: _facts()})

        class Repository(_Repository):
            def release_ids(self):
                events.append("release_ids")
                return (1,)

            def start_analysis_run(
                self, run_type, source, application_version
            ):
                events.append("start_analysis_run")
                raise primary

            def fail_analysis_run(self, *args):
                events.append("fail_analysis_run")

        def factory(token):
            events.append("provider_factory")
            return provider

        service = CollectorRunService(
            Repository(),
            factory,
            lambda current, previous: {},
            "0.4.0",
            0,
            clock=lambda: CAPTURED_AT,
            wait=lambda seconds: None,
        )

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIs(caught.exception.__cause__, primary)
        self.assertIsNone(caught.exception.analysis_run_id)
        self.assertEqual(caught.exception.attempted_releases, 0)
        self.assertEqual(caught.exception.successful_releases, 0)
        self.assertEqual(caught.exception.failed_releases, 0)
        self.assertNotIn("temporary-token", str(caught.exception))
        self.assertNotIn(str(primary), str(caught.exception))
        self.assertEqual(
            events,
            ["release_ids", "provider_factory", "start_analysis_run"],
        )
        self.assertEqual(provider.calls, [])

    def test_invalid_analysis_run_identity_is_a_pre_run_execution_failure(self):
        events = []
        provider = _Provider({1: _facts()})

        class Repository(_Repository):
            def release_ids(self):
                events.append("release_ids")
                return (1,)

            def start_analysis_run(
                self, run_type, source, application_version
            ):
                events.append("start_analysis_run")
                return True

            def fail_analysis_run(self, *args):
                events.append("fail_analysis_run")

        def factory(token):
            events.append("provider_factory")
            return provider

        service = CollectorRunService(
            Repository(),
            factory,
            lambda current, previous: {},
            "0.4.0",
            0,
            clock=lambda: CAPTURED_AT,
            wait=lambda seconds: None,
        )

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIsNone(caught.exception.analysis_run_id)
        self.assertIsInstance(caught.exception.__cause__, TypeError)
        self.assertEqual(
            events,
            ["release_ids", "provider_factory", "start_analysis_run"],
        )
        self.assertEqual(provider.calls, [])

    def test_malformed_and_duplicate_ids_fail_before_mutation(self):
        for values, error in (
            ((1, True), TypeError),
            ((1, 0), ValueError),
            ((1, -2), ValueError),
            ((1, "2"), TypeError),
            ((1, 1), ValueError),
        ):
            with self.subTest(values=values):
                repository = _Repository(values)
                service, _, _, factory_calls, _, _ = self.service(repository)
                with self.assertRaises(error):
                    service.run("temporary-token")
                self.assertEqual(repository.events, [("release_ids",)])
                self.assertEqual(factory_calls, [])

    def test_provider_is_lazy_and_order_is_repository_supplied(self):
        service, repository, provider, factory_calls, clock_calls, waits = (
            self.service()
        )
        self.assertEqual(factory_calls, [])

        result = service.run("temporary-token")

        self.assertEqual(factory_calls, ["temporary-token"])
        self.assertEqual(provider.calls, [3, 1, 2])
        self.assertEqual(clock_calls, [True])
        self.assertEqual(waits, [1.08, 1.08])
        self.assertEqual(result.status, CollectorRunStatus.COMPLETED)
        self.assertEqual(
            repository.events[-1], ("complete", 41, 3, 3, 0)
        )

    def test_successful_operation_order_and_single_timestamp(self):
        repository = _Repository((7,))
        service, repository, provider, _, _, _ = self.service(repository)

        result = service.run("temporary-token")

        captured = CAPTURED_AT.isoformat(timespec="seconds")
        self.assertEqual(provider.calls, [7])
        self.assertEqual(
            [event[0] for event in repository.events],
            ["release_ids", "start", "previous", "snapshot", "score", "complete"],
        )
        self.assertEqual(repository.events[2], ("previous", 7, captured))
        self.assertEqual(repository.events[3][3], captured)
        self.assertEqual(repository.events[4][2], captured)
        self.assertEqual(result.captured_at, CAPTURED_AT)

    def test_none_and_provider_exception_are_recoverable(self):
        repository = _Repository((1, 2, 3))
        responses = {1: None, 2: RuntimeError("provider"), 3: _facts()}
        service, repository, provider, _, _, waits = self.service(
            repository, responses
        )

        result = service.run("secret-value")

        self.assertEqual(provider.calls, [1, 2, 3])
        self.assertEqual(result.status, CollectorRunStatus.PARTIAL)
        self.assertEqual(result.failed_release_ids, (1, 2))
        self.assertEqual(
            repository.events[-1], ("complete", 41, 3, 1, 2)
        )
        self.assertEqual(waits, [1.08, 1.08])
        self.assertNotIn("secret-value", repr(result))

    def test_all_provider_failures_mark_run_failed_safely(self):
        repository = _Repository((1, 2))
        service, repository, _, _, _, _ = self.service(
            repository, {1: None, 2: RuntimeError("contains token")}
        )

        result = service.run("highly-secret")

        self.assertEqual(result.status, CollectorRunStatus.FAILED)
        self.assertEqual(result.failed_release_ids, (1, 2))
        failure = repository.events[-1]
        self.assertEqual(failure[0], "fail")
        self.assertEqual(failure[3:], (2, 0, 2))
        self.assertNotIn("highly-secret", failure[2])
        self.assertNotIn("contains token", failure[2])

    def test_persistence_failure_is_fatal_and_preserves_cause_and_counts(self):
        repository = _Repository((1, 2))
        repository.fail_on = ("snapshot", 2)
        service, repository, _, _, _, _ = self.service(repository)

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertEqual(caught.exception.analysis_run_id, 41)
        self.assertEqual(caught.exception.attempted_releases, 2)
        self.assertEqual(caught.exception.successful_releases, 1)
        self.assertEqual(caught.exception.failed_releases, 0)
        failure = repository.events[-1]
        self.assertEqual(failure[0], "fail")
        self.assertEqual(failure[3:], (2, 1, 0))
        self.assertEqual(failure[2], "Collector Run failed unexpectedly.")

    def test_score_calculation_failure_is_fatal(self):
        repository = _Repository((1,))

        def broken_score(current, previous):
            raise ArithmeticError("defect")

        service, repository, _, _, _, _ = self.service(
            repository, score_calculator=broken_score
        )

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIsInstance(caught.exception.__cause__, ArithmeticError)
        self.assertEqual(repository.events[-1][0], "fail")

    def test_primary_fatal_cause_survives_cleanup_failure(self):
        primary = OSError("primary storage detail")
        cleanup = RuntimeError("secondary cleanup detail")
        cleanup_calls = []
        repository = _Repository((1,))

        def add_snapshot(run_id, release_id, captured_at, data):
            raise primary

        def fail_analysis_run(
            run_id,
            error_message,
            releases_attempted,
            releases_succeeded,
            releases_failed,
        ):
            cleanup_calls.append(
                (
                    run_id,
                    error_message,
                    releases_attempted,
                    releases_succeeded,
                    releases_failed,
                )
            )
            raise cleanup

        repository.add_snapshot = add_snapshot
        repository.fail_analysis_run = fail_analysis_run
        service, _, _, _, _, _ = self.service(repository)

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token")

        self.assertIs(caught.exception.__cause__, primary)
        self.assertEqual(caught.exception.analysis_run_id, 41)
        self.assertEqual(caught.exception.attempted_releases, 1)
        self.assertEqual(caught.exception.successful_releases, 0)
        self.assertEqual(caught.exception.failed_releases, 0)
        self.assertEqual(
            cleanup_calls,
            [(41, "Collector Run failed unexpectedly.", 1, 0, 0)],
        )
        exposed = f"{caught.exception!s} {cleanup_calls!r}"
        self.assertNotIn("temporary-token", exposed)
        self.assertNotIn(str(primary), exposed)
        self.assertNotIn(str(cleanup), exposed)

    def test_progress_sequence_is_initial_then_per_attempt(self):
        repository = _Repository((5, 6))
        progress = []
        service, _, _, _, _, _ = self.service(
            repository, {5: _facts(), 6: None}
        )

        service.run("temporary-token", progress.append)

        self.assertEqual(
            progress,
            [
                CollectorRunProgress(2, 0, 0, 0),
                CollectorRunProgress(2, 1, 1, 0, 5),
                CollectorRunProgress(2, 2, 1, 1, 6),
            ],
        )

    def test_progress_callback_failure_is_fatal(self):
        repository = _Repository((1,))
        service, repository, _, _, _, _ = self.service(repository)

        def callback(progress):
            raise LookupError("UI callback failed")

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token", callback)

        self.assertIsInstance(caught.exception.__cause__, LookupError)
        self.assertEqual(repository.events[-1][0], "fail")
        self.assertEqual(repository.events[-1][3:], (0, 0, 0))

    def test_progress_callback_failure_after_success_preserves_work_and_counts(self):
        callback_failure = LookupError("callback sensitive detail")
        repository = _Repository((1, 2))
        callbacks = []
        service, repository, provider, _, _, waits = self.service(repository)

        def callback(progress):
            callbacks.append(progress)
            if progress.attempted_releases == 1:
                raise callback_failure

        with self.assertRaises(CollectorRunExecutionError) as caught:
            service.run("temporary-token", callback)

        self.assertIs(caught.exception.__cause__, callback_failure)
        self.assertEqual(caught.exception.attempted_releases, 1)
        self.assertEqual(caught.exception.successful_releases, 1)
        self.assertEqual(caught.exception.failed_releases, 0)
        self.assertEqual(provider.calls, [1])
        self.assertEqual(waits, [])
        self.assertEqual(
            [event[0] for event in repository.events],
            ["release_ids", "start", "previous", "snapshot", "score", "fail"],
        )
        failure = repository.events[-1]
        self.assertEqual(failure[3:], (1, 1, 0))
        self.assertNotIn("temporary-token", failure[2])
        self.assertNotIn(str(callback_failure), failure[2])
        self.assertEqual(len(callbacks), 2)

    def test_invalid_clock_fails_before_analysis_run(self):
        repository = _Repository((1,))
        service = CollectorRunService(
            repository,
            lambda token: _Provider({1: _facts()}),
            lambda current, previous: {},
            "0.4.0",
            0,
            clock=lambda: datetime(2026, 1, 1),
            wait=lambda seconds: None,
        )

        with self.assertRaises(ValueError):
            service.run("temporary-token")

        self.assertEqual(
            [event[0] for event in repository.events], ["release_ids"]
        )


class CollectorRunModelTestCase(unittest.TestCase):
    def test_models_are_immutable(self):
        progress = CollectorRunProgress(1, 0, 0, 0)
        result = CollectorRunResult(
            1, CAPTURED_AT, CollectorRunStatus.COMPLETED, 1, 1, 1, 0
        )
        with self.assertRaises(FrozenInstanceError):
            progress.total_releases = 2  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.status = CollectorRunStatus.FAILED  # type: ignore[misc]

    def test_progress_rejects_invalid_counts_and_identities(self):
        invalid = (
            lambda: CollectorRunProgress(True, 0, 0, 0),
            lambda: CollectorRunProgress(-1, 0, 0, 0),
            lambda: CollectorRunProgress(1, 1, 0, 0),
            lambda: CollectorRunProgress(1, 2, 1, 1),
            lambda: CollectorRunProgress(1, 0, 0, 0, True),
            lambda: CollectorRunProgress(1, 0, 0, 0, 0),
            lambda: CollectorRunProgress(1, 0, 0, 0, 1),
            lambda: CollectorRunProgress(1, 1, 1, 0),
        )
        for factory in invalid:
            with self.subTest(factory=factory):
                with self.assertRaises((TypeError, ValueError)):
                    factory()

    def test_result_status_must_agree_with_counts(self):
        with self.assertRaises(ValueError):
            CollectorRunResult(
                1,
                CAPTURED_AT,
                CollectorRunStatus.COMPLETED,
                2,
                2,
                1,
                1,
                (2,),
            )
        with self.assertRaises(TypeError):
            CollectorRunResult(
                1,
                CAPTURED_AT,
                CollectorRunStatus.FAILED,
                1,
                1,
                0,
                1,
                [1],  # type: ignore[arg-type]
            )
        with self.assertRaises(ValueError):
            CollectorRunResult(
                1,
                CAPTURED_AT,
                CollectorRunStatus.COMPLETED,
                0,
                0,
                0,
                0,
            )


class CollectorRunSQLiteIntegrationTestCase(unittest.TestCase):
    @staticmethod
    def _seed(database, release_ids):
        database.conn.executemany(
            "INSERT INTO releases (release_id, artist, title) VALUES (?, ?, ?)",
            tuple(
                (release_id, f"Artist {release_id}", f"Release {release_id}")
                for release_id in release_ids
            ),
        )
        database.conn.executemany(
            "INSERT INTO collection_ownership (release_id, quantity) VALUES (?, 1)",
            tuple((release_id,) for release_id in release_ids),
        )

    def test_run_persists_legacy_run_snapshots_and_scores(self):
        temporary_directory = tempfile.TemporaryDirectory()
        database = Database(Path(temporary_directory.name) / "collector-run.db")
        try:
            database.conn.executemany(
                "INSERT INTO releases (release_id, artist, title) VALUES (?, ?, ?)",
                ((2, "Two", "Second"), (1, "One", "First")),
            )
            database.conn.executemany(
                "INSERT INTO collection_ownership (release_id, quantity) VALUES (?, 1)",
                ((2,), (1,)),
            )
            provider = _Provider({1: _facts(11), 2: _facts(22)})
            service = CollectorRunService(
                database,
                lambda token: provider,
                calculate,
                "0.4.0",
                0,
                clock=lambda: CAPTURED_AT,
                wait=lambda seconds: None,
            )

            result = service.run("temporary-token")

            run = database.conn.execute(
                "SELECT * FROM analysis_runs"
            ).fetchone()
            snapshots = database.conn.execute(
                """
                SELECT release_id, analysis_run_id, captured_at
                FROM market_snapshots
                ORDER BY id
                """
            ).fetchall()
            scores = database.conn.execute(
                "SELECT release_id FROM scores ORDER BY release_id"
            ).fetchall()
            self.assertEqual(provider.calls, [1, 2])
            self.assertEqual(result.status, CollectorRunStatus.COMPLETED)
            self.assertEqual(run["id"], result.analysis_run_id)
            self.assertEqual(
                (
                    run["status"],
                    run["releases_attempted"],
                    run["releases_succeeded"],
                    run["releases_failed"],
                ),
                ("completed", 2, 2, 0),
            )
            self.assertEqual(
                tuple(
                    (
                        row["release_id"],
                        row["analysis_run_id"],
                        row["captured_at"],
                    )
                    for row in snapshots
                ),
                (
                    (1, result.analysis_run_id, CAPTURED_AT.isoformat(timespec="seconds")),
                    (2, result.analysis_run_id, CAPTURED_AT.isoformat(timespec="seconds")),
                ),
            )
            self.assertEqual(
                tuple(row["release_id"] for row in scores), (1, 2)
            )
        finally:
            database.close()
            temporary_directory.cleanup()

    def test_partial_run_completes_with_only_successful_evidence(self):
        temporary_directory = tempfile.TemporaryDirectory()
        database = Database(Path(temporary_directory.name) / "partial-run.db")
        try:
            self._seed(database, (3, 1, 2))
            provider_detail = "provider partial sensitive detail"
            provider = _Provider(
                {
                    1: _facts(11),
                    2: RuntimeError(provider_detail),
                    3: None,
                }
            )
            service = CollectorRunService(
                database,
                lambda token: provider,
                calculate,
                "0.4.0",
                0,
                clock=lambda: CAPTURED_AT,
                wait=lambda seconds: None,
            )

            result = service.run("temporary-token")

            run = database.conn.execute(
                "SELECT * FROM analysis_runs"
            ).fetchone()
            snapshots = database.conn.execute(
                """
                SELECT release_id, analysis_run_id
                FROM market_snapshots
                ORDER BY id
                """
            ).fetchall()
            scores = database.conn.execute(
                "SELECT release_id FROM scores ORDER BY release_id"
            ).fetchall()
            self.assertEqual(provider.calls, [1, 2, 3])
            self.assertEqual(result.status, CollectorRunStatus.PARTIAL)
            self.assertEqual(result.failed_release_ids, (2, 3))
            self.assertEqual(
                (
                    run["status"],
                    run["releases_attempted"],
                    run["releases_succeeded"],
                    run["releases_failed"],
                ),
                ("completed", 3, 1, 2),
            )
            self.assertIsNone(run["error_message"])
            self.assertEqual(
                tuple(
                    (row["release_id"], row["analysis_run_id"])
                    for row in snapshots
                ),
                ((1, result.analysis_run_id),),
            )
            self.assertEqual(
                tuple(row["release_id"] for row in scores), (1,)
            )
            self.assertNotIn(provider_detail, repr(tuple(run)))
        finally:
            database.close()
            temporary_directory.cleanup()

    def test_zero_success_run_is_failed_without_release_evidence(self):
        temporary_directory = tempfile.TemporaryDirectory()
        database = Database(Path(temporary_directory.name) / "failed-run.db")
        try:
            self._seed(database, (2, 1))
            provider_detail = "provider failure sensitive detail"
            token = "temporary-token"
            provider = _Provider(
                {1: RuntimeError(provider_detail), 2: None}
            )
            service = CollectorRunService(
                database,
                lambda supplied_token: provider,
                calculate,
                "0.4.0",
                0,
                clock=lambda: CAPTURED_AT,
                wait=lambda seconds: None,
            )

            result = service.run(token)

            run = database.conn.execute(
                "SELECT * FROM analysis_runs"
            ).fetchone()
            snapshot_count = database.conn.execute(
                "SELECT COUNT(*) FROM market_snapshots"
            ).fetchone()[0]
            score_count = database.conn.execute(
                "SELECT COUNT(*) FROM scores"
            ).fetchone()[0]
            self.assertEqual(provider.calls, [1, 2])
            self.assertEqual(result.status, CollectorRunStatus.FAILED)
            self.assertEqual(result.failed_release_ids, (1, 2))
            self.assertEqual(
                (
                    run["status"],
                    run["releases_attempted"],
                    run["releases_succeeded"],
                    run["releases_failed"],
                ),
                ("failed", 2, 0, 2),
            )
            self.assertEqual(
                run["error_message"],
                "Collector Run completed with no successful release refreshes.",
            )
            self.assertEqual(snapshot_count, 0)
            self.assertEqual(score_count, 0)
            self.assertNotIn(provider_detail, run["error_message"])
            self.assertNotIn(token, run["error_message"])
        finally:
            database.close()
            temporary_directory.cleanup()


if __name__ == "__main__":
    unittest.main()
