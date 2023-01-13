from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from typing import MutableMapping, Iterator, TypeVar, Generic, Mapping, \
    Type, IO
from uuid import UUID

from dataclasses_json import DataClassJsonMixin
from diskcache import Cache
from fastwarc import ArchiveIterator, GZipStream, FileStream, WarcRecord, \
    WarcRecordType
from fastwarc.stream_io import PythonIOStreamAdapter
from marshmallow import Schema
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.model import ArchivedUrl, ArchivedQueryUrl, \
    ArchivedParsedSerp, ArchivedSearchResultSnippet, ArchivedRawSerp


@dataclass(frozen=True)
class _Location:
    relative_path: Path
    offset: int


@dataclass(frozen=True)
class _ArchivedSnippetLocation(_Location):
    index: int


@dataclass(frozen=True)
class _LocationIndex(MutableMapping[UUID, _Location]):
    data_directory: Path
    index_name: str

    @cached_property
    def _index_path(self) -> Path:
        index_path = self.data_directory / "index" / self.index_name
        index_path.mkdir(parents=True, exist_ok=True)
        return index_path

    @cached_property
    def _index(self) -> Cache:
        return Cache(str(self._index_path))

    def __setitem__(self, key: UUID, value: _Location):
        self._index[key] = value

    def __delitem__(self, key: UUID) -> None:
        del self._index[key]

    def __getitem__(self, key: UUID) -> _Location:
        return self._index[key]

    def __contains__(self, key: UUID) -> bool:
        return key in self._index

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[UUID]:
        return iter(self._index)


_RecordType = TypeVar("_RecordType", bound=DataClassJsonMixin)


class _Index(Generic[_RecordType], Mapping[UUID, _RecordType], ABC):
    @property
    @abstractmethod
    def data_directory(self) -> Path:
        pass

    @property
    @abstractmethod
    def _index_name(self) -> str:
        pass

    @cached_property
    def _index(self) -> _LocationIndex:
        return _LocationIndex(self.data_directory, self._index_name)

    @abstractmethod
    def index(self) -> None:
        pass

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[UUID]:
        return iter(self._index)


class _JsonLineIndex(_Index[_RecordType]):
    @property
    @abstractmethod
    def _record_type(self) -> Type[_RecordType]:
        pass

    @cached_property
    def _schema(self) -> Schema:
        return self._record_type.schema()

    def _index_paths(self) -> Iterator[Path]:
        return self.data_directory.glob(f"{self._index_name}/*/*/*.jsonl.gz")

    def index(self) -> None:
        num_paths = sum(1 for _ in self._index_paths())
        paths = self._index_paths()
        paths = tqdm(
            paths,
            total=num_paths,
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        for path in paths:
            offset = 0
            with path.open("rb") as file:
                with GzipFile(fileobj=file, mode="r") as gzip_file:
                    gzip_file: IO[str]
                    for line in gzip_file:
                        record = self._schema.loads(line)
                        record_id = record.id
                        record_location = _Location(
                            path.relative_to(self.data_directory),
                            offset,
                        )
                        self._index[record_id] = record_location
                        offset = gzip_file.tell()

    def __getitem__(self, key: UUID) -> _RecordType:
        location = self._index[key]
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                return self._schema.loads(line)


@dataclass(frozen=True)
class ArchivedUrlIndex(_JsonLineIndex[ArchivedUrl]):
    _record_type = ArchivedUrl
    _index_name = "archived-urls"
    data_directory: Path = DATA_DIRECTORY_PATH


@dataclass(frozen=True)
class ArchivedQueryUrlIndex(_JsonLineIndex[ArchivedQueryUrl]):
    _record_type = ArchivedQueryUrl
    _index_name = "archived-query-urls"
    data_directory: Path = DATA_DIRECTORY_PATH


@dataclass(frozen=True)
class ArchivedRawSerpIndex(_Index[ArchivedRawSerp]):
    _index_name = "archived-raw-serps"
    _schema = ArchivedQueryUrl.schema()

    data_directory: Path = DATA_DIRECTORY_PATH

    def _index_paths(self) -> Iterator[Path]:
        return self.data_directory.glob("archived-raw-serps/*/*/*/*.warc.gz")

    def index(self) -> None:
        num_paths = sum(1 for _ in self._index_paths())
        paths = self._index_paths()
        paths = tqdm(
            paths,
            total=num_paths,
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        for path in paths:
            stream = GZipStream(FileStream(str(path), "rb"))
            for record in ArchiveIterator(
                    stream,
                    record_types=WarcRecordType.response
                                          ):
                record: WarcRecord
                offset = record.stream_pos
                record_url: ArchivedQueryUrl = self._schema.loads(
                    record.headers["Archived-URL"]
                )
                record_id = record_url.id
                record_location = _Location(
                    path.relative_to(self.data_directory),
                    offset,
                )
                self._index[record_id] = record_location

    def _read_serp_content(self, record: WarcRecord) -> ArchivedRawSerp:
        archived_serp_url: ArchivedQueryUrl = self._schema.loads(
            record.headers["Archived-URL"]
        )
        content_type = record.http_charset
        if content_type is None:
            content_type = "utf8"
        return ArchivedRawSerp(
            url=archived_serp_url.url,
            timestamp=archived_serp_url.timestamp,
            query=archived_serp_url.query,
            page=archived_serp_url.page,
            offset=archived_serp_url.offset,
            content=record.reader.read(),
            encoding=content_type,
        )

    def __getitem__(self, key: UUID) -> ArchivedRawSerp:
        # noinspection PyTypeChecker
        location: _ArchivedSnippetLocation = self._index[key]
        path = self.data_directory / location.relative_path
        with path.open("rb") as file:
            file.seek(location.offset)
            stream = GZipStream(PythonIOStreamAdapter(file))
            record: WarcRecord = next(ArchiveIterator(stream))
            return self._read_serp_content(record)


@dataclass(frozen=True)
class ArchivedParsedSerpIndex(_JsonLineIndex[ArchivedParsedSerp]):
    _record_type = ArchivedParsedSerp
    _index_name = "archived-parsed-serps"
    data_directory: Path = DATA_DIRECTORY_PATH


@dataclass(frozen=True)
class ArchivedSearchResultSnippetIndex(_Index[ArchivedSearchResultSnippet]):
    _schema = ArchivedParsedSerp.schema()
    _index_name = "archived-search-result-snippets"

    data_directory: Path = DATA_DIRECTORY_PATH

    def _index_paths(self) -> Iterator[Path]:
        return self.data_directory.glob("archived-parsed-serps/*/*/*.jsonl.gz")

    def index(self) -> None:
        num_paths = sum(1 for _ in self._index_paths())
        paths = self._index_paths()
        paths = tqdm(
            paths,
            total=num_paths,
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        for path in paths:
            offset = 0
            with path.open("rb") as file:
                with GzipFile(fileobj=file, mode="r") as gzip_file:
                    gzip_file: IO[str]
                    for line in gzip_file:
                        record = self._schema.loads(line)
                        snippets = enumerate(record.results)
                        for snippet_index, snippet in snippets:
                            snippet_id = snippet.id
                            snippet_location = _ArchivedSnippetLocation(
                                path.relative_to(self.data_directory),
                                offset,
                                snippet_index,
                            )
                            self._index[snippet_id] = snippet_location
                        offset = gzip_file.tell()

    def __getitem__(self, key: UUID) -> ArchivedSearchResultSnippet:
        # noinspection PyTypeChecker
        location: _ArchivedSnippetLocation = self._index[key]
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                record: ArchivedParsedSerp = self._schema.loads(line)
                return record.results[location.index]


if __name__ == '__main__':
    index = ArchivedRawSerpIndex()
    index.index()
    uuid = UUID("6942d399-da90-565a-add4-b35022a6fa86")
    print(f"{uuid} -> {index[uuid]}\n -> {index[uuid].id}")
