from contextlib import contextmanager
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import BytesIO
from pathlib import Path
from typing import Iterator, Any


from approvaltests import verify, DiffReporter
from approvaltests.integrations.pytest.py_test_namer import PyTestNamer
from pytest import FixtureRequest
from yaml import safe_dump
from warcio import ArchiveIterator
from warcio.recordloader import ArcWarcRecord

from archive_query_log.orm import Serp, WarcLocation
from archive_query_log.utils.warc import WarcStore

from tests import TESTS_DATA_PATH


def iter_test_serps(path: Path) -> Iterator[Serp]:
    with path.open("rt", encoding="utf-8") as file:
        for line in file:
            yield Serp.model_validate_json(line)


@dataclass(frozen=True)
class MockWarcStore(WarcStore):
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


class _Namer(PyTestNamer):
    _base_path: Path

    def __init__(self, request: FixtureRequest, base_path: Path) -> None:
        super().__init__(request)
        self._base_path = base_path

    def get_directory(self) -> str:
        return str(self._base_path)


def verify_yaml(
    request: FixtureRequest,
    data: Any,
) -> None:
    verify(
        data=safe_dump(data, allow_unicode=True, sort_keys=False),
        reporter=DiffReporter(),
        namer=_Namer(request, TESTS_DATA_PATH),
    )
