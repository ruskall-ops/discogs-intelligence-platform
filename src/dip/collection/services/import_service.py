from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dip.collection.importers import DiscogsCSVImporter
from dip.persistence.sqlite import Database


@dataclass(frozen=True)
class ImportSummary:
    """Summary returned after importing a Discogs collection."""

    imported_records: int
    total_rows: int
    valid_release_ids: int
    invalid_release_ids: int


class ImportService:
    """Coordinate collection imports between the importer and database."""

    def __init__(
        self,
        database: Database,
        importer: DiscogsCSVImporter | None = None,
    ) -> None:
        self.database = database
        self.importer = importer or DiscogsCSVImporter()

    def import_collection(self, path: Path) -> ImportSummary:
        result = self.importer.read(path)

        imported_records = self.database.import_releases(
            result.rows,
            result.release_id_column,
        )

        return ImportSummary(
            imported_records=imported_records,
            total_rows=result.total_rows,
            valid_release_ids=result.valid_release_ids,
            invalid_release_ids=result.invalid_release_ids,
        )
