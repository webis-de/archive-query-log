from dataclasses import dataclass
from functools import cached_property
from json import JSONDecodeError
from pathlib import Path
from typing import Sized, Iterable, Iterator

from fastwarc import GZipStream, FileStream, ArchiveIterator, WarcRecordType, \
    WarcRecord
from marshmallow import Schema

from archive_query_log.legacy import LOGGER
from archive_query_log.legacy.model import ArchivedQueryUrl, ArchivedRawSerp


@dataclass(frozen=True)
class ArchivedRawSerps(Sized, Iterable[ArchivedRawSerp]):
    """
    Read archived raw SERP contents from a directory of WARC files.
    """

    path: Path
    """
    Path where the raw SERP contents are stored in WARC format.
    """

    def __post_init__(self):
        self._check_raw_serps_paths()

    def _check_raw_serps_paths(self):
        if not self.path.exists() or not self.path.is_dir():
            raise ValueError(
                f"Raw SERPs path must be a directory: {self.path}"
            )

    def _streams(self) -> Iterator[tuple[Path, GZipStream]]:
        files = self.path.glob("*.warc.gz")
        for file in files:
            yield file, GZipStream(FileStream(str(file), "rb"))

    def __len__(self) -> int:
        return sum(
            1
            for _, stream in self._streams()
            for _ in ArchiveIterator(
                stream,
                record_types=WarcRecordType.response,
                parse_http=False,
            )
        )

    @cached_property
    def _archived_serp_url_schema(self) -> Schema:
        return ArchivedQueryUrl.schema()

    def _read_serp_content(self, record: WarcRecord) -> ArchivedRawSerp | None:
        archived_serp_url: ArchivedQueryUrl
        record_url_header = record.headers["Archived-URL"]
        try:
            archived_serp_url = self._archived_serp_url_schema.loads(
                record_url_header
            )
        except JSONDecodeError:
            LOGGER.warning(f"Could not index {record_url_header} "
                           f"from record {record.record_id}.")
            return None
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

    def __iter__(self) -> Iterator[ArchivedRawSerp]:
        for path, stream in self._streams():
            failures = False
            for record in ArchiveIterator(
                    stream,
                    record_types=WarcRecordType.response,
                    parse_http=True,
            ):
                serp = self._read_serp_content(record)
                if serp is None:
                    failures = True
                    continue
                yield serp
            if failures:
                LOGGER.warning(f"Failed to index some records from {path}.")
