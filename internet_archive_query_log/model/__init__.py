from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from typing import Sequence
from urllib.parse import SplitResult, urlsplit

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested


@dataclass(frozen=True, slots=True)
class Domain(DataClassJsonMixin):
    domain: str


@dataclass(frozen=True, slots=True)
class ArchivedUrl(DataClassJsonMixin):
    """
    Archived URL.
    """
    url: str
    timestamp: int

    @cached_property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

    @cached_property
    def split_url(self) -> SplitResult:
        return urlsplit(self.url)

    @cached_property
    def archive_timestamp(self) -> str:
        return self.datetime.strftime("%Y%m%d%H%M%S")

    @property
    def archive_url(self) -> str:
        return f"https://web.archive.org/web/" \
               f"{self.archive_timestamp}/{self.url}"

    @property
    def raw_archive_url(self) -> str:
        return f"https://web.archive.org/web/" \
               f"{self.archive_timestamp}id_/{self.url}"


@dataclass(frozen=True, slots=True)
class ArchivedSerpUrl(ArchivedUrl, DataClassJsonMixin):
    """
    Archived URL of a search engine query and the SERP it points to.
    """
    url: str
    timestamp: int
    query: str


@dataclass(frozen=True, slots=True)
class ArchivedSerpContent(ArchivedSerpUrl, DataClassJsonMixin):
    """
    Archived content of a search engine query and the SERP it points to.
    """
    content: bytes
    encoding: str


@dataclass(frozen=True, slots=True)
class SearchResult(DataClassJsonMixin):
    """
    Single retrieved result from a query's archived SERP.
    """
    url: str
    title: str
    snippet: str | None = None


@dataclass(frozen=True, slots=True)
class ArchivedSerp(ArchivedSerpUrl, DataClassJsonMixin):
    """
    Archived search engine result page (SERP) corresponding to a query.
    """
    results: Sequence[SearchResult] = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(SearchResult.schema()))
        )
    )
