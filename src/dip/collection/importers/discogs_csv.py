from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RELEASE_ID_COLUMNS = (
    "release_id",
    "Release ID",
    "release id",
)


class CollectionImportError(Exception):
    """Raised when a collection export cannot be imported."""


@dataclass(frozen=True)
class CollectionImportResult:
    """Validated data read from a Discogs collection export."""

    rows: list[dict[str, Any]]
    release_id_column: str
    total_rows: int
    valid_release_ids: int
    invalid_release_ids: int


class DiscogsCSVImporter:
    """Read and validate an exported Discogs collection CSV file."""

    def read(self, path: Path) -> CollectionImportResult:
        csv_path = Path(path).expanduser().resolve()

        if not csv_path.exists():
            raise CollectionImportError(
                f"The selected file does not exist:\n{csv_path}"
            )

        if not csv_path.is_file():
            raise CollectionImportError(
                f"The selected path is not a file:\n{csv_path}"
            )

        try:
            with csv_path.open(
                "r",
                encoding="utf-8-sig",
                newline="",
            ) as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                rows = list(reader)
        except UnicodeDecodeError as exc:
            raise CollectionImportError(
                "The CSV could not be read as UTF-8."
            ) from exc
        except (OSError, csv.Error) as exc:
            raise CollectionImportError(
                f"Unable to read the Discogs CSV:\n{exc}"
            ) from exc

        release_id_column = self._find_release_id_column(fieldnames)

        valid_release_ids = 0
        invalid_release_ids = 0

        for row in rows:
            raw_release_id = str(
                row.get(release_id_column, "")
            ).strip()

            try:
                int(raw_release_id)
            except (TypeError, ValueError):
                invalid_release_ids += 1
            else:
                valid_release_ids += 1

        return CollectionImportResult(
            rows=rows,
            release_id_column=release_id_column,
            total_rows=len(rows),
            valid_release_ids=valid_release_ids,
            invalid_release_ids=invalid_release_ids,
        )

    @staticmethod
    def _find_release_id_column(fieldnames: list[str]) -> str:
        for candidate in RELEASE_ID_COLUMNS:
            if candidate in fieldnames:
                return candidate

        raise CollectionImportError(
            "No Discogs release ID column was found.\n\n"
            "Expected one of:\n"
            + "\n".join(f"• {name}" for name in RELEASE_ID_COLUMNS)
        )
