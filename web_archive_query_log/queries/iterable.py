from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sized, Iterable, Iterator, IO

from web_archive_query_log.model import ArchivedSerpUrl


@dataclass(frozen=True)
class ArchivedSerpUrls(Sized, Iterable[ArchivedSerpUrl]):
    """
    Read archived SERP URLs (with queries) from a JSONL file.
    """

    path: Path
    """
    Path where the SERP URLs are stored in JSONL format.
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

    def __iter__(self) -> Iterator[ArchivedSerpUrl]:
        schema = ArchivedSerpUrl.schema()
        with self.path.open("rt") as file:
            if self.path.suffix == ".gz":
                with GzipFile(fileobj=file, mode="rb") as gzip_file:
                    gzip_file: IO[bytes]
                    with TextIOWrapper(gzip_file) as text_file:
                        for line in text_file:
                            yield schema.loads(line)
            else:
                for line in file:
                    yield schema.loads(line)
