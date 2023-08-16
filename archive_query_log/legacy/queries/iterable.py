from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import Sized, Iterable, Iterator, IO

from archive_query_log.legacy.model import ArchivedQueryUrl
from archive_query_log.legacy.util.text import count_lines


@dataclass(frozen=True)
class ArchivedQueryUrls(Sized, Iterable[ArchivedQueryUrl]):
    """
    Read archived query URLs from a JSONL file.
    """

    path: Path
    """
    Path where the query URLs are stored in JSONL format.
    """

    def __post_init__(self):
        self._check_urls_path()

    def _check_urls_path(self):
        if not self.path.exists() or not self.path.is_file():
            raise ValueError(
                f"URLs path must be a file: {self.path}"
            )

    def __len__(self) -> int:
        with self.path.open("rb") as file:
            with GzipFile(fileobj=file, mode="rb") as gzip_file:
                gzip_file: IO[bytes]
                return count_lines(gzip_file)

    def __iter__(self) -> Iterator[ArchivedQueryUrl]:
        schema = ArchivedQueryUrl.schema()
        with self.path.open("rb") as file:
            with GzipFile(fileobj=file, mode="rb") as gzip_file:
                gzip_file: IO[bytes]
                with TextIOWrapper(gzip_file) as text_file:
                    for line in text_file:
                        yield schema.loads(line)
