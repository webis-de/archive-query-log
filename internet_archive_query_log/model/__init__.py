from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested


@dataclass(frozen=True, slots=True)
class Domain(DataClassJsonMixin):
    domain: str


@dataclass(frozen=True, slots=True)
class ArchivedUrl(Domain, DataClassJsonMixin):
    """
    Archived snapshot of a URL.
    """
    url: str
    domain: str = field(init=False)
    timestamp: int

    @property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

    @property
    def archive_url(self) -> str:
        timestamp = self.datetime.strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}/{self.url}"

    @property
    def raw_archive_url(self) -> str:
        timestamp = self.datetime.strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}id_/{self.url}"


@dataclass(frozen=True, slots=True)
class ArchivedSerpUrl(ArchivedUrl, DataClassJsonMixin):
    """
    Archived snapshot of a search engine query and the SERP it points to.
    """
    url: str
    timestamp: int
    query: str


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
    Search engine result page (SERP) corresponding to a query.
    """
    results: Sequence[SearchResult] = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(SearchResult.schema()))
        )
    )
