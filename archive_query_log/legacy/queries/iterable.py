from dataclasses import dataclass
from gzip import GzipFile
from pathlib import Path
from typing import Sized, Iterable, Iterator

from archive_query_log.legacy.model import ArchivedQueryUrl
from archive_query_log.legacy.util.text import count_lines, text_io_wrapper


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
        with (self.path.open("rb") as file,
              GzipFile(fileobj=file, mode="rb") as gzip_file):
            return count_lines(gzip_file)

    def __iter__(self) -> Iterator[ArchivedQueryUrl]:
        schema = ArchivedQueryUrl.schema()
        with (self.path.open("rb") as file,
              GzipFile(fileobj=file, mode="rb") as gzip_file,
              text_io_wrapper(gzip_file) as text_file):
            for line in text_file:
                query_url = schema.loads(line, many=True)
                if isinstance(query_url, list):
                    raise ValueError(
                        f"Expected one query URL per line: {line}")
                yield query_url
