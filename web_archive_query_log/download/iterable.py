from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Sized, Iterable, Iterator

from fastwarc import GZipStream, FileStream, ArchiveIterator, WarcRecordType, \
    WarcRecord
from marshmallow import Schema

from web_archive_query_log.model import ArchivedQueryUrl, ArchivedRawSerp


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

    def _streams(self) -> Iterator[GZipStream]:
        files = self.path.glob("*.warc.gz")
        for file in files:
            yield GZipStream(FileStream(str(file), "rb"))

    def __len__(self) -> int:
        return sum(
            1
            for stream in self._streams()
            for _ in ArchiveIterator(
                stream,
                record_types=WarcRecordType.response,
                parse_http=False,
            )
        )

    @cached_property
    def _archived_serp_url_schema(self) -> Schema:
        return ArchivedQueryUrl.schema()

    def _read_serp_content(self, record: WarcRecord) -> ArchivedRawSerp:
        archived_serp_url: ArchivedQueryUrl
        archived_serp_url = self._archived_serp_url_schema.loads(
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

    def __iter__(self) -> Iterator[ArchivedRawSerp]:
        for stream in self._streams():
            for record in ArchiveIterator(
                    stream,
                    record_types=WarcRecordType.response,
                    parse_http=True,
            ):
                yield self._read_serp_content(record)
