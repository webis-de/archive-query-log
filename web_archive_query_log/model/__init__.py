from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from hashlib import md5
from typing import Sequence
from urllib.parse import SplitResult, urlsplit

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested

from web_archive_query_log.model.parser import PageNumberParser
from web_archive_query_log.queries import QueryParser
from web_archive_query_log.results import SearchResultsParser


@dataclass(frozen=True, slots=True)
class Source(DataClassJsonMixin):
    name: str
    """
    Service name (corresponds to ``alexa_domain`` without 
    the ``alexa_public_suffix``).
    """
    public_suffix: str
    """
    Public suffix (https://publicsuffix.org/) of ``alexa_domain``.
    """
    alexa_domain: str
    """
    Domain as it appears in Alexa top-1M ranks.
    """
    alexa_rank: int
    """
    Rank from fused Alexa top-1M rankings.
    """
    category: str
    """
    Category of the service (manual annotation).
    """
    notes: str
    """
    Notes about the service (manual annotation).
    """
    input_field: bool
    """
    Whether the service has an input field.
    """
    search_form: bool
    """
    Whether the service has a search form element.
    """
    search_div: bool
    """
    Whether the service has a search div element.
    """
    domains: Sequence[str]
    """
    Known domains of the service, including the main domain.
    """
    query_parsers: Sequence[QueryParser]
    """
    Query parsers in order of precedence.
    """
    page_num_parsers: Sequence[PageNumberParser]
    """
    Page number parsers in order of precedence.
    """
    serp_parsers: Sequence[SearchResultsParser]
    """
    SERP parsers in order of precedence.
    """


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
    def url_md5(self) -> str:
        return md5(self.url.encode()).hexdigest()

    @cached_property
    def datetime(self) -> datetime:
        return datetime.fromtimestamp(self.timestamp)

    @cached_property
    def split_url(self) -> SplitResult:
        return urlsplit(self.url)

    @cached_property
    def url_domain(self) -> str:
        return self.split_url.netloc

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
