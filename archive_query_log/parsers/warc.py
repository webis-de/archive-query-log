from contextlib import contextmanager
from typing import Iterator

from warc_s3 import WarcS3Store, WarcS3Location
from warcio.recordloader import ArcWarcRecord

from archive_query_log.orm import WarcLocation


@contextmanager
def open_warc(
        warc_store: WarcS3Store,
        warc_location: WarcLocation,
) -> Iterator[ArcWarcRecord]:
    with warc_store.read(WarcS3Location(
            key=warc_location.file,
            offset=warc_location.offset,
            length=warc_location.length,
    )) as record:
        yield record
