from dataclasses import dataclass
from pathlib import Path
from typing import Sized, Iterable, Iterator

from web_archive_query_log.model import ArchivedSerpUrl


@dataclass(frozen=True)
class ArchivedSerpUrls(Sized, Iterable[ArchivedSerpUrl]):
    """
    Read archived SERP URLs (with queries) from a JSONL file.
    """

    urls_path: Path
    """
    Path where the SERP URLs are stored in JSONL format.
    """

    def __post_init__(self):
        self._check_urls_path()

    def _check_urls_path(self):
        if not self.urls_path.exists() or not self.urls_path.is_file():
            raise ValueError(
                f"URLs path must be a file: {self.urls_path}"
            )

    def __len__(self) -> int:
        with self.urls_path.open("rt") as file:
            return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedSerpUrl]:
        schema = ArchivedSerpUrl.schema()
        with self.urls_path.open("rt") as file:
            for line in file:
                yield schema.loads(line)
