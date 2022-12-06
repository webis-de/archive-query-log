from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Sized, Iterable, Iterator

from fastwarc import GZipStream, FileStream, ArchiveIterator, WarcRecordType, \
    WarcRecord
from fastwarc.stream_io import IOStream
from marshmallow import Schema

from web_archive_query_log.model import ArchivedSerpUrl, ArchivedSerpContent


@dataclass(frozen=True)
class ArchivedSerpContents(Sized, Iterable[ArchivedSerpContent]):
    """
    Read archived SERP contents from a directory of WARC files.
    """

    path: Path
    """
    Path where the SERP contents are stored in WARC format.
    """

    def __post_init__(self):
        self._check_urls_path()

    def _check_urls_path(self):
        if not self.path.exists() or not self.path.is_dir():
            raise ValueError(
                f"URLs path must be a directory: {self.path}"
            )

    def _streams(self) -> Iterator[IOStream]:
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
        return ArchivedSerpUrl.schema()

    def _read_serp_content(self, record: WarcRecord) -> ArchivedSerpContent:
        archived_serp_url = self._archived_serp_url_schema.loads(
            record.headers["Archived-URL"]
        )
        content_type = record.http_charset
        if content_type is None:
            content_type = "utf8"
        return ArchivedSerpContent(
            url=archived_serp_url.url,
            timestamp=archived_serp_url.timestamp,
            query=archived_serp_url.query,
            page_num=archived_serp_url.page_num,
            content=record.reader.read(),
            encoding=content_type,
        )

    def __iter__(self) -> Iterator[ArchivedSerpContent]:
        for stream in self._streams():
            for record in ArchiveIterator(
                    stream,
                    record_types=WarcRecordType.response,
                    parse_http=True,
            ):
                yield self._read_serp_content(record)
