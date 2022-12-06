from dataclasses import dataclass
from gzip import GzipFile
from io import TextIOWrapper
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
        if self.path.suffix == ".gz":
            # noinspection PyTypeChecker
            with self.path.open("rb") as file, \
                    GzipFile(fileobj=file, mode="rb") as gzip_file, \
                    TextIOWrapper(gzip_file) as text_file:
                return sum(1 for _ in text_file)
        else:
            with self.path.open("rt") as file:
                return sum(1 for _ in file)

    def __iter__(self) -> Iterator[ArchivedUrl]:
        schema = ArchivedUrl.schema()
        if self.path.suffix == ".gz":
            # noinspection PyTypeChecker
            with self.path.open("rb") as file, \
                    GzipFile(fileobj=file, mode="rb") as gzip_file, \
                    TextIOWrapper(gzip_file) as text_file:
                for line in text_file:
                    yield schema.loads(line)
        else:
            with self.path.open("rt") as file:
                for line in file:
                    yield schema.loads(line)
