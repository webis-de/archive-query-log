from abc import ABC, abstractmethod
from csv import writer
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from io import TextIOWrapper
from json import loads, JSONDecodeError
from pathlib import Path
from shutil import copyfileobj
from typing import Iterator, TypeVar, Generic, Type, IO, final
from uuid import UUID, uuid5, NAMESPACE_URL

from dataclasses_json import DataClassJsonMixin
from diskcache import Cache
from fastwarc import ArchiveIterator, FileStream, WarcRecord, \
    WarcRecordType
from fastwarc.stream_io import PythonIOStreamAdapter
from marshmallow import Schema
from tqdm.auto import tqdm

from web_archive_query_log import DATA_DIRECTORY_PATH, LOGGER
from web_archive_query_log.model import ArchivedUrl, ArchivedQueryUrl, \
    ArchivedParsedSerp, ArchivedSearchResultSnippet, ArchivedRawSerp, \
    ArchivedRawSearchResult, CorpusJsonlLocation, CorpusJsonlSnippetLocation, \
    CorpusWarcLocation


@dataclass(frozen=True)
class _MetaIndex:
    base_type: str
    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False

    @cached_property
    def base_path(self) -> Path:
        base_path = self.data_directory
        if self.focused:
            base_path /= "focused"
        if self.base_type == "archived-search-result-snippets":
            base_path /= "archived-parsed-serps"
        else:
            base_path /= self.base_type
        return base_path

    def _is_indexable_path(self, path: Path) -> bool:
        if self.base_type == "archived-urls":
            return path.is_file() and path.name.endswith(".jsonl.gz")
        elif self.base_type == "archived-query-urls":
            return path.is_file() and path.name.endswith(".jsonl.gz")
        elif self.base_type == "archived-raw-serps":
            return path.is_dir()
        elif self.base_type == "archived-parsed-serps":
            return path.is_file() and path.name.endswith(".jsonl.gz")
        elif self.base_type == "archived-search-result-snippets":
            return path.is_file() and path.name.endswith(".jsonl.gz")
        elif self.base_type == "archived-raw-search-results":
            return path.is_dir()
        elif self.base_type == "archived-parsed-search-results":
            return path.is_file() and path.name.endswith(".jsonl.gz")
        else:
            raise ValueError(f"Unknown base type: {self.base_type}")

    def _indexable_paths(self) -> Iterator[Path]:
        base_path = self.base_path
        for service_path in base_path.iterdir():
            if not service_path.is_dir():
                continue
            if service_path.name.startswith("."):
                continue
            for pattern_path in service_path.iterdir():
                if (not pattern_path.is_dir() or
                        pattern_path.name.startswith(".")):
                    continue
                for path in pattern_path.iterdir():
                    if self._is_indexable_path(path):
                        yield path

    def _index_path(self, path: Path) -> Path:
        if self.base_type == "archived-urls":
            return path.with_name(
                f"{path.name.removesuffix('.jsonl.gz')}.index"
            )
        elif self.base_type == "archived-query-urls":
            return path.with_name(
                f"{path.name.removesuffix('.jsonl.gz')}.index"
            )
        elif self.base_type == "archived-raw-serps":
            return path.with_name(
                f"{path.name}.index"
            )
        elif self.base_type == "archived-parsed-serps":
            return path.with_name(
                f"{path.name.removesuffix('.jsonl.gz')}.index"
            )
        elif self.base_type == "archived-search-result-snippets":
            return path.with_name(
                f"{path.name.removesuffix('.jsonl.gz')}.snippets.index"
            )
        elif self.base_type == "archived-raw-search-results":
            return path.with_name(
                f"{path.name}.index"
            )
        elif self.base_type == "archived-parsed-search-results":
            return path.with_name(
                f"{path.name.removesuffix('.jsonl.gz')}.index"
            )
        else:
            raise ValueError(f"Unknown base type: {self.base_type}")

    def _index_jsonl(self, path: Path) -> None:
        if not path.exists():
            return
        index_path = self._index_path(path)
        if index_path.exists():
            if (index_path.stat().st_size == 0 or
                    index_path.stat().st_mtime < path.stat().st_mtime):
                # Remove empty or stale index.
                index_path.unlink()
            else:
                # Index is up-to-date.
                return

        offset = 0
        index: list[tuple[str, str, str]] = []
        with GzipFile(path, mode="r") as gzip_file:
            gzip_file: IO[str]
            for line in gzip_file:
                try:
                    record = loads(line)
                except JSONDecodeError:
                    LOGGER.error(f"Could not index {line} at {path}.")
                    return
                record_id = uuid5(
                    NAMESPACE_URL,
                    f"{record['timestamp']}:{record['url']}",
                )
                index.append((
                    str(record_id),
                    str(path.relative_to(self.data_directory)),
                    str(offset),
                ))
                offset = gzip_file.tell()

        try:
            with index_path.open("wt") as index_file:
                index_writer = writer(index_file)
                index_writer.writerows(index)
        except Exception as e:
            LOGGER.error(e)

    def _index_warc(self, dir_path: Path) -> None:
        if not dir_path.exists():
            return
        index_path = self._index_path(dir_path)
        if index_path.exists():
            if (index_path.stat().st_size == 0 or
                    index_path.stat().st_mtime < dir_path.stat().st_mtime):
                # Remove empty or stale index.
                index_path.unlink()
            else:
                # Index is up-to-date.
                return

        index: list[tuple[str, str, str]] = []
        for path in dir_path.iterdir():
            if path.name.startswith("."):
                continue
            records = ArchiveIterator(
                FileStream(str(path), "rb"),
                record_types=WarcRecordType.response,
                parse_http=False,
            )
            for record in records:
                record: WarcRecord
                offset = record.stream_pos
                try:
                    record_url = loads(record.headers["Archived-URL"])
                except JSONDecodeError:
                    LOGGER.error(
                        f"Could not index "
                        f"{record.headers['Archived-URL']} "
                        f"at {path}."
                    )
                    return
                record_id = uuid5(
                    NAMESPACE_URL,
                    f"{record_url['timestamp']}:{record_url['url']}",
                )
                index.append((
                    str(record_id),
                    str(path.relative_to(self.data_directory)),
                    str(offset),
                ))

        try:
            with index_path.open("wt") as index_file:
                index_writer = writer(index_file)
                index_writer.writerows(index)
        except Exception as e:
            LOGGER.error(e)

    def _index_jsonl_snippets(self, path: Path) -> None:
        if not path.exists():
            return
        index_path = self._index_path(path)
        if index_path.exists():
            if (index_path.stat().st_size == 0 or
                    index_path.stat().st_mtime < path.stat().st_mtime):
                # Remove empty or stale index.
                index_path.unlink()
            else:
                # Index is up-to-date.
                return

        offset = 0
        index: list[tuple[str, str, str, str]] = []
        with GzipFile(path, mode="r") as gzip_file:
            gzip_file: IO[str]
            for line in gzip_file:
                try:
                    record = loads(line)
                except JSONDecodeError:
                    LOGGER.error(f"Could not index {line} at {path}.")
                    return
                for snippet_index, snippet in enumerate(record["results"]):
                    record_id = uuid5(
                        NAMESPACE_URL,
                        f"{record['timestamp']}:{snippet['url']}",
                    )
                    index.append((
                        str(record_id),
                        str(path.relative_to(self.data_directory)),
                        str(offset),
                        str(snippet_index)
                    ))
                offset = gzip_file.tell()

        try:
            with index_path.open("wt") as index_file:
                index_writer = writer(index_file)
                index_writer.writerows(index)
        except Exception as e:
            LOGGER.error(e)

    def _index(self, path: Path) -> None:
        if self.base_type == "archived-urls":
            self._index_jsonl(path)
        elif self.base_type == "archived-query-urls":
            self._index_jsonl(path)
        elif self.base_type == "archived-raw-serps":
            self._index_warc(path)
        elif self.base_type == "archived-parsed-serps":
            self._index_jsonl(path)
        elif self.base_type == "archived-search-result-snippets":
            self._index_jsonl_snippets(path)
        elif self.base_type == "archived-raw-search-results":
            self._index_warc(path)
        elif self.base_type == "archived-parsed-search-results":
            self._index_jsonl(path)
        else:
            raise ValueError(f"Unknown base type: {self.base_type}")

    @cached_property
    def _aggregated_index_path(self) -> Path:
        if self.base_type == "archived-urls":
            return self.base_path / ".index"
        elif self.base_type == "archived-query-urls":
            return self.base_path / ".index"
        elif self.base_type == "archived-raw-serps":
            return self.base_path / ".index"
        elif self.base_type == "archived-parsed-serps":
            return self.base_path / ".index"
        elif self.base_type == "archived-search-result-snippets":
            return self.base_path / ".snippets.index"
        elif self.base_type == "archived-raw-search-results":
            return self.base_path / ".index"
        elif self.base_type == "archived-parsed-search-results":
            return self.base_path / ".index"
        else:
            raise ValueError(f"Unknown base type: {self.base_type}")

    def index(self) -> None:
        # Index each path individually.
        paths = tqdm(
            self._indexable_paths(),
            total=sum(1 for _ in self._indexable_paths()),
            desc="Index paths",
            unit="path",
        )
        for path in paths:
            self._index(path)

        # Aggregate all indexes into a single index.
        aggregated_index_path = self._aggregated_index_path
        with aggregated_index_path.open("wb") as aggregated_index_file:
            paths = tqdm(
                self._indexable_paths(),
                total=sum(1 for _ in self._indexable_paths()),
                desc="Aggregate indices",
                unit="path",
            )
            for path in paths:
                index_path = self._index_path(path)
                if not index_path.exists():
                    continue
                with index_path.open("rb") as index_file:
                    copyfileobj(index_file, aggregated_index_file)


_CorpusLocationType = TypeVar(
    "_CorpusLocationType",
    CorpusJsonlLocation, CorpusJsonlSnippetLocation, CorpusWarcLocation
)
_RecordType = TypeVar("_RecordType", bound=DataClassJsonMixin)


@dataclass(frozen=True)
class LocatedRecord(Generic[_CorpusLocationType, _RecordType]):
    location: _CorpusLocationType
    record: _RecordType


_T = TypeVar("_T")


@dataclass(frozen=True)
class _Index(Generic[_CorpusLocationType, _RecordType], ABC):
    data_directory: Path
    focused: bool

    @property
    @abstractmethod
    def base_type(self) -> str:
        pass

    @cached_property
    def _meta_index(self) -> _MetaIndex:
        return _MetaIndex(self.base_type, self.data_directory, self.focused)

    @abstractmethod
    def _to_corpus_location(self, csv_line: list) -> _CorpusLocationType:
        pass

    @cached_property
    def _index_path(self) -> Path:
        index_path = self.data_directory
        if self.focused:
            index_path /= "focused"
        if self.base_type == "archived-search-result-snippets":
            return index_path / "archived-parsed-serps" / ".snippets.index"
        else:
            return index_path / self.base_type / ".index"

    @cached_property
    def _index(self) -> Cache:
        cache = Cache()
        index_path = self._index_path
        if not index_path.exists():
            LOGGER.warning(f"Index not found: {index_path}")
            return cache
        with index_path.open("rt") as index_file:
            index_file = tqdm(
                index_file,
                desc="Load index",
                unit="line",
            )
            for line in index_file:
                cache[line.split(",", maxsplit=1)[0]] = line
            # noinspection PyTypeChecker
            return cache

    def index(self) -> None:
        self._meta_index.index()

    @abstractmethod
    def _read_record(self, location: _CorpusLocationType) -> _RecordType:
        pass

    def __getitem__(
            self,
            item: UUID
    ) -> LocatedRecord[_CorpusLocationType, _RecordType]:
        csv_line = self._index[str(item)].split(",")
        location = self._to_corpus_location(csv_line)
        record = self._read_record(location)
        return LocatedRecord(location, record)

    def get(
            self,
            item: UUID
    ) -> LocatedRecord[_CorpusLocationType, _RecordType] | None:
        if str(item) not in self._index:
            return None
        return self[item]

    def __iter__(self) -> Iterator[UUID]:
        for uuid in self._index:
            yield UUID(uuid)


@dataclass(frozen=True)
class _JsonLineIndex(_Index[CorpusJsonlLocation, _RecordType]):
    @property
    @abstractmethod
    def record_type(self) -> Type[_RecordType]:
        pass

    @cached_property
    def _schema(self) -> Schema:
        return self.record_type.schema()

    def _to_corpus_location(self, csv_line: list) -> CorpusJsonlLocation:
        return CorpusJsonlLocation(
            relative_path=Path(csv_line[1]),
            byte_offset=int(csv_line[2]),
        )

    def _read_record(self, location: CorpusJsonlLocation) -> _RecordType:
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.byte_offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                return self._schema.loads(line)


@dataclass(frozen=True)
class _WarcIndex(_Index[CorpusWarcLocation, _RecordType]):

    def _to_corpus_location(self, csv_line: list) -> CorpusWarcLocation:
        return CorpusWarcLocation(
            relative_path=Path(csv_line[1]),
            byte_offset=int(csv_line[2]),
        )

    def _read_record(self, location: CorpusJsonlLocation) -> _RecordType:
        path = self.data_directory / location.relative_path
        with path.open("rb") as file:
            file.seek(location.byte_offset)
            stream = PythonIOStreamAdapter(file)
            record: WarcRecord = next(ArchiveIterator(stream))
            return self._read_warc_record(record)

    @abstractmethod
    def _read_warc_record(self, record: WarcRecord) -> _RecordType:
        pass


@dataclass(frozen=True)
class ArchivedUrlIndex(_JsonLineIndex[ArchivedUrl]):
    base_type = final("archived-urls")
    record_type = ArchivedUrl

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False


@dataclass(frozen=True)
class ArchivedQueryUrlIndex(_JsonLineIndex[ArchivedQueryUrl]):
    base_type = "archived-query-urls"
    record_type = ArchivedQueryUrl

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False


@dataclass(frozen=True)
class ArchivedRawSerpIndex(_WarcIndex[ArchivedRawSerp]):
    base_type = "archived-raw-serps"
    schema = ArchivedQueryUrl.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False

    def _read_warc_record(self, record: WarcRecord) -> ArchivedRawSerp:
        archived_url: ArchivedQueryUrl = self.schema.loads(
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
    base_type = "archived-parsed-serps"
    record_type = ArchivedParsedSerp

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False


@dataclass(frozen=True)
class ArchivedSearchResultSnippetIndex(
    _Index[CorpusJsonlSnippetLocation, ArchivedSearchResultSnippet]
):
    base_type = "archived-search-result-snippets"
    schema = ArchivedParsedSerp.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False

    def _to_corpus_location(
            self,
            csv_line: list
    ) -> CorpusJsonlSnippetLocation:
        return CorpusJsonlSnippetLocation(
            relative_path=Path(csv_line[1]),
            byte_offset=int(csv_line[2]),
            index=int(csv_line[3]),
        )

    def _read_record(
            self,
            location: CorpusJsonlSnippetLocation
    ) -> _RecordType:
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file: IO[bytes]
            gzip_file.seek(location.byte_offset)
            with TextIOWrapper(gzip_file) as text_file:
                line = text_file.readline()
                record: ArchivedParsedSerp = self.schema.loads(line)
                return record.results[location.index]


@dataclass(frozen=True)
class ArchivedRawSearchResultIndex(_WarcIndex[ArchivedRawSearchResult]):
    base_type = "archived-raw-search-results"
    schema = ArchivedSearchResultSnippet.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False

    def _read_warc_record(self, record: WarcRecord) -> ArchivedRawSearchResult:
        archived_url: ArchivedSearchResultSnippet = self.schema.loads(
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
    index = ArchivedUrlIndex(focused=True)
    index.index()
    print(index[UUID("712d7714-3a23-592c-807b-8e82a256c181")].record.id)
    index = ArchivedQueryUrlIndex(focused=True)
    index.index()
    print(index[UUID("935f36cd-623a-5a10-a01f-ddec1ecc59c5")].record.id)
    index = ArchivedRawSerpIndex(focused=True)
    index.index()
    print(index[UUID("b72ccc4a-18c9-5339-b0d3-59154b8faed9")].record.id)
    index = ArchivedParsedSerpIndex(focused=True)
    index.index()
    print(index[UUID("6e59a3a4-5343-5001-a51a-911dc0b2b032")].record.id)
    index = ArchivedSearchResultSnippetIndex(focused=True)
    index.index()
    print(index[UUID("96a3e930-dc8f-5369-88a4-8a4a60ca06fb")].record.id)
    index = ArchivedRawSearchResultIndex(focused=True)
    index.index()
    print(index[UUID("116c6f96-c76d-5a39-bc80-f2605d689885")].record.id)
