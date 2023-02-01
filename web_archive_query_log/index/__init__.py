from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import TextIOWrapper
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
from pathlib import Path
from typing import MutableMapping, Iterator, TypeVar, Generic, Mapping, \
    Type, IO, MutableSet, NamedTuple
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


class Location(NamedTuple):
    relative_path: Path
    offset: int


class ArchivedSnippetLocation(NamedTuple):
    relative_path: Path
    offset: int
    index: int


_LocationType = TypeVar("_LocationType", bound=NamedTuple)


@dataclass(frozen=True)
class _LocationIndex(
    MutableMapping[UUID, _LocationType],
    Generic[_LocationType],
):
    data_directory: Path
    focused: bool
    service: str | None
    index_name: str
    location_type: Type[_LocationType]

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

    def __setitem__(self, key: UUID, value: _LocationType):
        self._index[str(key)] = tuple(value)

    def __delitem__(self, key: UUID) -> None:
        del self._index[str(key)]

    def __getitem__(self, key: UUID) -> _LocationType:
        return self.location_type(*self._index[str(key)])

    def __contains__(self, key: UUID) -> bool:
        return str(key) in self._index

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[UUID]:
        for uuid in self._index:
            yield UUID(uuid)


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
        self._index[str(value)] = True

    def discard(self, value: Path) -> None:
        del self._index[str(value)]

    def __contains__(self, value: Path) -> bool:
        return str(value) in self._index

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[Path]:
        for path in self._index:
            yield Path(path)


_RecordType = TypeVar("_RecordType", bound=DataClassJsonMixin)


@dataclass(frozen=True, slots=True)
class LocatedRecord(Generic[_LocationType, _RecordType]):
    location: _LocationType
    record: _RecordType


class _Index(
    Mapping[UUID, _RecordType],
    Generic[_LocationType, _RecordType],
    ABC,
):
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

    @property
    @abstractmethod
    def _location_type(self) -> Type[_LocationType]:
        pass

    @cached_property
    def _index(self) -> _LocationIndex[_LocationType]:
        return _LocationIndex(
            data_directory=self.data_directory,
            focused=self.focused,
            service=self.service,
            index_name=self._index_name,
            location_type=self._location_type,
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

    @abstractmethod
    def locate(
            self,
            key: UUID
    ) -> LocatedRecord[_LocationType, _RecordType] | None:
        pass

    def __len__(self) -> int:
        return len(self._index)

    def __iter__(self) -> Iterator[UUID]:
        return iter(self._index)


class _JsonLineIndex(_Index[Location, _RecordType]):
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
                    record_location = Location(
                        relative_path=path.relative_to(self.data_directory),
                        offset=offset,
                    )
                    # noinspection PyTypeChecker
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
        pool = ThreadPool(min(10, cpu_count()))

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

    def locate(self, key: UUID) -> LocatedRecord[Location, _RecordType] | None:
        if key not in self._index:
            return None
        location = self._index[key]
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                return LocatedRecord(location, self._schema.loads(line))

    def __getitem__(self, key: UUID) -> _RecordType:
        return self.locate(key).record


@dataclass(frozen=True)
class _WarcIndex(_Index[Location, _RecordType]):

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
            record_location = Location(
                relative_path=path.relative_to(self.data_directory),
                offset=offset,
            )
            # noinspection PyTypeChecker
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
        pool = ThreadPool(min(10, cpu_count()))

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

    def locate(
            self,
            key: UUID,
    ) -> LocatedRecord[Location, _RecordType] | None:
        if key not in self._index:
            return None
        location: Location = self._index[key]
        path = self.data_directory / location.relative_path
        with path.open("rb") as file:
            file.seek(location.offset)
            stream = GZipStream(PythonIOStreamAdapter(file))
            record: WarcRecord = next(ArchiveIterator(stream))
            return LocatedRecord(location, self._read_record(record))

    def __getitem__(self, key: UUID) -> _RecordType:
        return self.locate(key).record


@dataclass(frozen=True)
class ArchivedUrlIndex(_JsonLineIndex[ArchivedUrl]):
    _record_type = ArchivedUrl
    _index_name = "archived-urls"
    _location_type = Location

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedQueryUrlIndex(_JsonLineIndex[ArchivedQueryUrl]):
    _record_type = ArchivedQueryUrl
    _index_name = "archived-query-urls"
    _location_type = Location

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedRawSerpIndex(_WarcIndex[ArchivedRawSerp]):
    _index_name = "archived-raw-serps"
    _schema = ArchivedQueryUrl.schema()
    _location_type = Location

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
    _location_type = Location

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False
    service: str | None = None


@dataclass(frozen=True)
class ArchivedSearchResultSnippetIndex(
    _Index[ArchivedSnippetLocation, ArchivedSearchResultSnippet]
):
    _schema = ArchivedParsedSerp.schema()
    _index_name = "archived-search-result-snippets"
    _location_type = ArchivedSnippetLocation

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
                        snippet_location = ArchivedSnippetLocation(
                            relative_path=path.relative_to(
                                self.data_directory),
                            offset=offset,
                            index=snippet_index,
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
        pool = ThreadPool(min(10, cpu_count()))

        def index_path(path: Path):
            self._index_path(path)
            progress.update()

        pool.map(index_path, paths)

    def locate(
            self,
            key: UUID,
    ) -> LocatedRecord[ArchivedSnippetLocation, _RecordType] | None:
        if key not in self._index:
            return None
        # noinspection PyTypeChecker
        location: ArchivedSnippetLocation = self._index[key]
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                record: ArchivedParsedSerp = self._schema.loads(line)
                return LocatedRecord(
                    location,
                    record.results[location.index],
                )

    def __getitem__(self, key: UUID) -> ArchivedSearchResultSnippet:
        return self.locate(key).record


@dataclass(frozen=True)
class ArchivedRawSearchResultIndex(_WarcIndex[ArchivedRawSearchResult]):
    _index_name = "archived-raw-search-results"
    _schema = ArchivedSearchResultSnippet.schema()
    _location_type = Location

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
