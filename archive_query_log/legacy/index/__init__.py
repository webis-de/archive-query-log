from abc import ABC, abstractmethod
from csv import writer
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from json import loads, JSONDecodeError
from pathlib import Path
from shelve import open as shelf_open, Shelf  # nosec: B403
from shutil import copyfileobj
from typing import Iterator, TypeVar, Generic, Type, final, \
    ContextManager, Iterable
from uuid import UUID, uuid5, NAMESPACE_URL

from dataclasses_json import DataClassJsonMixin
from marshmallow import Schema
from tqdm.auto import tqdm
from warcio.archiveiterator import ArchiveIterator
from warcio.recordloader import ArcWarcRecord

from archive_query_log.legacy import DATA_DIRECTORY_PATH, LOGGER
from archive_query_log.legacy.model import ArchivedUrl, ArchivedQueryUrl, \
    ArchivedParsedSerp, ArchivedSearchResultSnippet, ArchivedRawSerp, \
    ArchivedRawSearchResult, CorpusJsonlLocation, CorpusJsonlSnippetLocation, \
    CorpusWarcLocation
from archive_query_log.legacy.util.text import count_lines, text_io_wrapper


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
        if not base_path.exists():
            return
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
        with (GzipFile(path, mode="rb") as gzip_file,
              text_io_wrapper(gzip_file) as file):
            for line in file:
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

        with index_path.open("wt") as index_file:
            index_writer = writer(index_file)
            index_writer.writerows(index)

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
            with path.open("rb") as file:
                records = ArchiveIterator(file, no_record_parse=True)
                record: ArcWarcRecord
                for record in records:
                    if record.rec_type != "response":
                        continue
                    offset = record.raw_stream.tell()
                    try:
                        record_url = loads(
                            record.rec_headers.get_header("Archived-URL"))
                    except JSONDecodeError:
                        LOGGER.error(
                            f"Could not index "
                            f"{record.rec_headers.get_header('Archived-URL')} "
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

        with index_path.open("wt") as index_file:
            index_writer = writer(index_file)
            index_writer.writerows(index)

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
        with (GzipFile(path, mode="rb") as gzip_file,
              text_io_wrapper(gzip_file) as file):
            for line in file:
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

        with index_path.open("wt") as index_file:
            index_writer = writer(index_file)
            index_writer.writerows(index)

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
    def path(self) -> Path:
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

    @cached_property
    def shelf_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.shelf")

    def index(self) -> None:
        # Index each path individually.
        indexable_paths: Iterable[Path]
        # noinspection PyTypeChecker
        indexable_paths = tqdm(
            self._indexable_paths(),
            total=sum(1 for _ in self._indexable_paths()),
            desc="Index paths",
            unit="path",
        )
        indexed_paths_list: list[Path] = []
        for indexable_path in indexable_paths:
            self._index(indexable_path)
            indexed_paths_list.append(indexable_path)
        indexed_paths: Iterable[Path] = indexed_paths_list

        # Merge all indexes into a single index.
        path = self.path
        num_lines = 0
        with path.open("wb") as aggregated_index_file:
            # noinspection PyTypeChecker
            indexed_paths = tqdm(
                indexed_paths,
                desc="Merge indices",
                unit="path",
            )
            for indexed_path in indexed_paths:
                index_path = self._index_path(indexed_path)
                if not index_path.exists():
                    continue
                with index_path.open("rb") as index_file:
                    copyfileobj(index_file, aggregated_index_file)
                with index_path.open("rb") as index_file:
                    num_lines += count_lines(index_file)


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
class _Index(
    Generic[_CorpusLocationType, _RecordType],
    ContextManager,
    ABC,
):
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
    def _index_shelf_path(self) -> Path:
        index_path = self.data_directory
        if self.focused:
            index_path /= "focused"
        if self.base_type == "archived-search-result-snippets":
            return index_path / "archived-parsed-serps" / \
                ".snippets.index.shelf"
        else:
            return index_path / self.base_type / ".index.shelf"

    @cached_property
    def _index_shelve(self) -> Shelf:
        return shelf_open(str(self._index_shelf_path), "r")  # nosec: B301

    def index(self) -> None:
        self._meta_index.index()

    @abstractmethod
    def _read_record(self, location: _CorpusLocationType) -> _RecordType:
        pass

    def __getitem__(
            self,
            item: UUID
    ) -> LocatedRecord[_CorpusLocationType, _RecordType]:
        csv_line = self._index_shelve[str(item)].split(",")
        location = self._to_corpus_location(csv_line)
        record = self._read_record(location)
        return LocatedRecord(location, record)

    def get(
            self,
            item: UUID
    ) -> LocatedRecord[_CorpusLocationType, _RecordType] | None:
        if str(item) not in self._index_shelve:
            return None
        return self[item]

    def __iter__(self) -> Iterator[UUID]:
        for uuid in self._index_shelve:
            yield UUID(uuid)

    def __exit__(self, *args) -> None:
        self._index_shelve.close()


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
            gzip_file.seek(location.byte_offset)
            with text_io_wrapper(gzip_file) as text_file:
                line = text_file.readline()
                return self._schema.loads(line)


@dataclass(frozen=True)
class _WarcIndex(_Index[CorpusWarcLocation, _RecordType]):

    def _to_corpus_location(self, csv_line: list) -> CorpusWarcLocation:
        return CorpusWarcLocation(
            relative_path=Path(csv_line[1]),
            byte_offset=int(csv_line[2]),
        )

    def _read_record(self, location: CorpusWarcLocation) -> _RecordType:
        path = self.data_directory / location.relative_path
        with path.open("rb") as file:
            file.seek(location.byte_offset)
            record: ArcWarcRecord = next(ArchiveIterator(file))
            return self._read_warc_record(record)

    @abstractmethod
    def _read_warc_record(self, record: ArcWarcRecord) -> _RecordType:
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

    def _read_warc_record(self, record: ArcWarcRecord) -> ArchivedRawSerp:
        header = record.rec_headers.get_header("Archived-URL")
        archived_url = self.schema.loads(
            record.rec_headers.get_header("Archived-URL"))
        if isinstance(archived_url, list):
            raise ValueError(f"Expected one URL in the header: {header}")
        content_type = record.http_headers.get_header("Content-Type")
        if content_type is None:
            content_type = "utf8"
        return ArchivedRawSerp(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            query=archived_url.query,
            page=archived_url.page,
            offset=archived_url.offset,
            content=record.content_stream().read(),
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
    ) -> ArchivedSearchResultSnippet:
        path = self.data_directory / location.relative_path
        with GzipFile(path, "rb") as gzip_file:
            gzip_file.seek(location.byte_offset)
            with text_io_wrapper(gzip_file) as text_file:
                line = text_file.readline()
                record = self.schema.loads(line)
                if isinstance(record, list):
                    raise ValueError(f"Expected one result per line: {line}")
                return record.results[location.index]


@dataclass(frozen=True)
class ArchivedRawSearchResultIndex(_WarcIndex[ArchivedRawSearchResult]):
    base_type = "archived-raw-search-results"
    schema = ArchivedSearchResultSnippet.schema()

    data_directory: Path = DATA_DIRECTORY_PATH
    focused: bool = False

    def _read_warc_record(
            self,
            record: ArcWarcRecord,
    ) -> ArchivedRawSearchResult:
        header = record.rec_headers.get_header("Archived-URL")
        archived_url = self.schema.loads(header)
        if isinstance(archived_url, list):
            raise ValueError(f"Expected one URL in the header: {header}")
        content_type = record.http_headers.get_header("Content-Type")
        if content_type is None:
            content_type = "utf8"
        return ArchivedRawSearchResult(
            url=archived_url.url,
            timestamp=archived_url.timestamp,
            rank=archived_url.rank,
            title=archived_url.title,
            snippet=archived_url.snippet,
            content=record.content_stream().read(),
            encoding=content_type,
        )
