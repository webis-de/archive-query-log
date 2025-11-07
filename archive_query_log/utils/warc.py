from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol, Iterator

from warcio.recordloader import ArcWarcRecord
from warc_cache import WarcCacheStore, WarcCacheLocation
from warc_s3 import WarcS3Store, WarcS3Location

from archive_query_log.orm import WarcLocation


class WarcStore(Protocol):
    @contextmanager
    def read(self, location: WarcLocation) -> Iterator[ArcWarcRecord]: ...


@dataclass(frozen=True)
class WarcS3StoreWrapper(WarcStore):
    warc_store: WarcS3Store

    @contextmanager
    def read(self, location: WarcLocation) -> Iterator[ArcWarcRecord]:
        with self.warc_store.read(
            WarcS3Location(
                key=location.file,
                offset=location.offset,
                length=location.length,
            )
        ) as record:
            yield record


@dataclass(frozen=True)
class WarcCacheStoreWrapper(WarcStore):
    warc_store: WarcCacheStore

    @contextmanager
    def read(self, location: WarcLocation) -> Iterator[ArcWarcRecord]:
        yield next(
            self.warc_store.read(
                WarcCacheLocation(
                    key=location.file,
                    offset=location.offset,
                    length=location.length,
                )
            )
        )
