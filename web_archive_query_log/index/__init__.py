from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import TextIOWrapper
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import MutableMapping, Iterator, TypeVar, Generic, Mapping, \
    Type, IO, MutableSet
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
    ArchivedParsedSerp, ArchivedSearchResultSnippet, ArchivedRawSerp, \
    ArchivedRawSearchResult
from web_archive_query_log.util.text import count_lines


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
    focused: bool
    service: str | None
    index_name: str

    @cached_property
    def _index_path(self) -> Path:
        index_path = self.data_directory / "index"
        if self.focused:
            index_path /= "focused"
        if self.service is not None:
            index_path /= self.service
        index_path /= self.index_name
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


@dataclass(frozen=True)
class _PathIndex(MutableSet[Path]):
    data_directory: Path
    focused: bool
    service: str | None
    index_name: str

    @cached_property
    def _index_path(self) -> Path:
        index_path = self.data_directory / "index"
        if self.focused:
            index_path /= "focused"
        if self.service is not None:
            index_path /= self.service
        index_path /= f"{self.index_name}-paths"
        index_path.mkdir(parents=True, exist_ok=True)
        return index_path

    @cached_property
    def _index(self) -> Cache:
        return Cache(str(self._index_path))

    def add(self, value: Path) -> None:
        self._index[value] = True

    def discard(self, value: Path) -> None:
        del self._index[value]

    def __contains__(self, value: Path) -> bool:
        return value in self._index

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
    def focused(self) -> bool:
        pass

    @property
    @abstractmethod
    def service(self) -> str | None:
        pass

    @property
    @abstractmethod
    def _index_name(self) -> str:
        pass

    @cached_property
    def _index(self) -> _LocationIndex:
        return _LocationIndex(
            data_directory=self.data_directory,
            focused=self.focused,
            service=self.service,
            index_name=self._index_name,
        )

    @cached_property
    def _path_index(self) -> _PathIndex:
        return _PathIndex(
            data_directory=self.data_directory,
            focused=self.focused,
            service=self.service,
            index_name=self._index_name,
        )

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

    def _indexable_paths(self) -> Iterator[Path]:
        focused = "focused/" if self.focused else ""
        service = f"{self.service}" if self.service is not None else "*"
        paths = self.data_directory.glob(
            f"{focused}{self._index_name}/{service}/*/*.jsonl.gz"
        )
        paths = (
            path
            for path in paths
            if path not in self._path_index
        )
        return paths

    def _index_path(self, path: Path) -> None:
        if path in self._path_index:
            return
        offset = 0
        with path.open("rb") as file:
            with GzipFile(fileobj=file, mode="rb") as gzip_file:
                gzip_file: IO[bytes]
                num_lines = count_lines(gzip_file)
        with path.open("rb") as file:
            with GzipFile(fileobj=file, mode="r") as gzip_file:
                gzip_file: IO[str]
                lines = gzip_file
                if num_lines > 10_000:
                    lines = tqdm(
                        lines,
                        total=num_lines,
                        desc=f"Indexing {self._index_name}",
                        unit="line",
                    )
                for line in lines:
                    record = self._schema.loads(line)
                    record_id = record.id
                    record_location = _Location(
                        path.relative_to(self.data_directory),
                        offset,
                    )
                    self._index[record_id] = record_location
                    offset = gzip_file.tell()
        self._path_index.add(path)

    def index(self) -> None:
        paths = list(self._indexable_paths())
        if len(paths) == 0:
            return
        progress = tqdm(
            total=len(paths),
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        pool = ThreadPool()

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

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
class _WarcIndex(_Index[_RecordType]):

    @abstractmethod
    def _read_id(self, record: WarcRecord) -> UUID:
        pass

    @abstractmethod
    def _read_record(self, record: WarcRecord) -> _RecordType:
        pass

    def _indexable_paths(self) -> Iterator[Path]:
        focused = "focused/" if self.focused else ""
        service = f"{self.service}" if self.service is not None else "*"
        paths = self.data_directory.glob(
            f"{focused}{self._index_name}/{service}/*/*/*.warc.gz"
        )
        paths = (
            path
            for path in paths
            if path not in self._path_index
        )
        return paths

    def _index_path(self, path: Path) -> None:
        if path in self._path_index:
            return
        stream = GZipStream(FileStream(str(path), "rb"))
        num_records = sum(1 for _ in ArchiveIterator(
            stream,
            record_types=WarcRecordType.response,
            parse_http=False,
        ))
        stream = GZipStream(FileStream(str(path), "rb"))
        records = ArchiveIterator(
            stream,
            record_types=WarcRecordType.response
        )
        if num_records > 10_000:
            records = tqdm(
                records,
                total=num_records,
                desc=f"Indexing {self._index_name}",
                unit="record",
            )
        for record in records:
            record: WarcRecord
            offset = record.stream_pos
            record_id = self._read_id(record)
            record_location = _Location(
                path.relative_to(self.data_directory),
                offset,
            )
            self._index[record_id] = record_location
        self._path_index.add(path)

    def index(self) -> None:
        paths = list(self._indexable_paths())
        if len(paths) == 0:
            return
        progress = tqdm(
            total=len(paths),
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        pool = ThreadPool()

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

    def __getitem__(self, key: UUID) -> _RecordType:
        # noinspection PyTypeChecker
        location: _ArchivedSnippetLocation = self._index[key]
        path = self.data_directory / location.relative_path
        with path.open("rb") as file:
            file.seek(location.offset)
            stream = GZipStream(PythonIOStreamAdapter(file))
            record: WarcRecord = next(ArchiveIterator(stream))
            return self._read_record(record)


@dataclass(frozen=True)
class ArchivedUrlIndex(_JsonLineIndex[ArchivedUrl]):
    _record_type = ArchivedUrl
    _index_name = "archived-urls"

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedQueryUrlIndex(_JsonLineIndex[ArchivedQueryUrl]):
    _record_type = ArchivedQueryUrl
    _index_name = "archived-query-urls"

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedRawSerpIndex(_WarcIndex[ArchivedRawSerp]):
    _index_name = "archived-raw-serps"
    _schema = ArchivedQueryUrl.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None

    def _read_id(self, record: WarcRecord) -> UUID:
        return self._schema.loads(record.headers["Archived-URL"]).id

    def _read_record(self, record: WarcRecord) -> ArchivedRawSerp:
        archived_url: ArchivedQueryUrl = self._schema.loads(
            record.headers["Archived-URL"]
        )
        content_type = record.http_charset
        if content_type is None:
            content_type = "utf8"
        return ArchivedRawSerp(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            query=archived_url.query,
            page=archived_url.page,
            offset=archived_url.offset,
            content=record.reader.read(),
            encoding=content_type,
        )


@dataclass(frozen=True)
class ArchivedParsedSerpIndex(_JsonLineIndex[ArchivedParsedSerp]):
    _record_type = ArchivedParsedSerp
    _index_name = "archived-parsed-serps"

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedSearchResultSnippetIndex(_Index[ArchivedSearchResultSnippet]):
    _schema = ArchivedParsedSerp.schema()
    _index_name = "archived-search-result-snippets"

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None

    def _indexable_paths(self) -> Iterator[Path]:
        focused = "focused/" if self.focused else ""
        service = f"{self.service}" if self.service is not None else "*"
        paths = self.data_directory.glob(
            f"{focused}archived-parsed-serps/{service}/*/*.jsonl.gz"
        )
        paths = (
            path
            for path in paths
            if path not in self._path_index
        )
        return paths

    def _index_path(self, path: Path) -> None:
        if path in self._path_index:
            return
        offset = 0
        with path.open("rb") as file:
            with GzipFile(fileobj=file, mode="rb") as gzip_file:
                gzip_file: IO[bytes]
                num_lines = count_lines(gzip_file)
        with path.open("rb") as file:
            with GzipFile(fileobj=file, mode="r") as gzip_file:
                gzip_file: IO[str]
                lines = gzip_file
                if num_lines > 10_000:
                    lines = tqdm(
                        lines,
                        total=num_lines,
                        desc=f"Indexing {self._index_name}",
                        unit="line",
                    )
                for line in lines:
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
        self._path_index.add(path)

    def index(self) -> None:
        paths = list(self._indexable_paths())
        if len(paths) == 0:
            return
        progress = tqdm(
            total=len(paths),
            desc=f"Indexing {self._index_name}",
            unit="file",
        )
        pool = ThreadPool()

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

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


@dataclass(frozen=True)
class ArchivedRawSearchResultIndex(_WarcIndex[ArchivedRawSearchResult]):
    _index_name = "archived-raw-search-results"
    _schema = ArchivedSearchResultSnippet.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None

    def _read_id(self, record: WarcRecord) -> UUID:
        return self._schema.loads(record.headers["Archived-URL"]).id

    def _read_record(self, record: WarcRecord) -> ArchivedRawSearchResult:
        archived_url: ArchivedSearchResultSnippet = self._schema.loads(
            record.headers["Archived-URL"]
        )
        content_type = record.http_charset
        if content_type is None:
            content_type = "utf8"
        return ArchivedRawSearchResult(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            rank=archived_url.rank,
            title=archived_url.title,
            snippet=archived_url.snippet,
            content=record.reader.read(),
            encoding=content_type,
        )


if __name__ == '__main__':
    index = ArchivedRawSearchResultIndex()
