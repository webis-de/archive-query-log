from dataclasses import dataclass
from pathlib import Path
from typing import Sized, Iterable, Iterator

from web_archive_query_log.model import ArchivedUrl


@dataclass(frozen=True)
class ArchivedUrls(Sized, Iterable[ArchivedUrl]):
    """
    Read archived URLs from a JSONL file.
    """

    path: Path
    """
    Path where the URLs are stored in JSONL format.
    """

    def __post_init__(self):
        self._check_urls_path()

    def _check_urls_path(self):
        if not self.path.exists() or not self.path.is_file():
            raise ValueError(
                f"URLs path must be a file: {self.path}"
            )

    def __len__(self) -> int:
        with self.path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedUrl]:
        schema = ArchivedUrl.schema()
        with self.path.open("rt") as file:
            for line in file:
                yield schema.loads(line)
