from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import BytesIO
from pathlib import Path
from typing import Iterator

from warcio import ArchiveIterator
from warcio.recordloader import ArcWarcRecord

from archive_query_log.orm import Serp, WarcLocation
from archive_query_log.utils.warc import WarcStore


def iter_test_serps(path: Path) -> Iterator[Serp]:
    with path.open("rt", encoding="utf-8") as file:
        for line in file:
            yield Serp.model_validate_json(line)


@dataclass(frozen=True)
class TestWarcStore(WarcStore):
    serps_path: Path

    @cached_property
    def _path(self) -> Path:
        return self.serps_path.with_suffix(".warc.gz")

    @contextmanager
    def read(self, location: WarcLocation) -> Iterator[ArcWarcRecord]:
        if location.file != self._path.name:
            raise ValueError(f"Unexpected file: {location.file}")

        with self._path.open("rb") as file:
            file.seek(location.offset)
            buffer = file.read(location.length)

        with GzipFile(fileobj=BytesIO(buffer), mode="rb") as gzip_file:
            iterator = ArchiveIterator(gzip_file)
            yield next(iterator)
