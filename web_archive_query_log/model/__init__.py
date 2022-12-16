from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from hashlib import md5
from typing import Sequence
from urllib.parse import SplitResult, urlsplit

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested, String


@dataclass(frozen=True, slots=True)
class ArchivedUrl(DataClassJsonMixin):
    """
    A URL that is archived in the Wayback Machine (https://web.archive.org/).
    The archived snapshot can be retrieved using the ``archive_url``
    and ``raw_archive_url`` properties.

    Output of: 2-archived-urls
    Input of: 3-archived-query-urls
    """

    url: str
    """
    Original URL that was archived.
    """
    timestamp: int
    """
    Timestamp of the archived snapshot in the Wayback Machine.
    """

    @cached_property
    def split_url(self) -> SplitResult:
        """
        Original URL split into its components.
        """
        return urlsplit(self.url)

    @cached_property
    def url_domain(self) -> str:
        """
        Domain of the original URL.
        """
        return self.split_url.netloc

    @cached_property
    def url_md5(self) -> str:
        """
        MD5 hash of the original URL.
        """
        return md5(self.url.encode()).hexdigest()

    @cached_property
    def datetime(self) -> datetime:
        """
        Snapshot timestamp as a ``datetime`` object.
        """
        return datetime.fromtimestamp(self.timestamp)

    @cached_property
    def archive_timestamp(self) -> str:
        """
        Snapshot timestamp as a string in the format used
        by the Wayback Machine (``YYYYmmddHHMMSS``).
        """
        return self.datetime.strftime("%Y%m%d%H%M%S")

    @property
    def archive_url(self) -> str:
        """
        URL of the archived snapshot in the Wayback Machine.
        """
        return f"https://web.archive.org/web/" \
               f"{self.archive_timestamp}/{self.url}"

    @property
    def raw_archive_url(self) -> str:
        """
        URL of the archived snapshot's raw contents in the Wayback Machine.
        """
        return f"https://web.archive.org/web/" \
               f"{self.archive_timestamp}id_/{self.url}"


@dataclass(frozen=True, slots=True)
class ArchivedQueryUrl(ArchivedUrl, DataClassJsonMixin):
    """
    Archived URL of a search engine result page (SERP) for a query.

    Output of: 3-archived-query-urls
    Input of: 4-archived-raw-serps, 8-ir-corpus
    """

    query: str
    """
    Query that was used to retrieve the SERP.
    """
    page: int | None
    """
    Page number of the SERP, e.g., 1, 2, 3.

    Note: the page number should be zero-indexed, i.e.,
    the first result page has the page number 0.

    See also: ``results_page_offset``.
    """
    offset: int | None
    """
    Offset (start position) of the first result in the SERP, e.g., 10, 20.

    Note: the offset should be zero-indexed, i.e.,
    the first result page has the offset 0.

    See also ``results_page``.
    """


@dataclass(frozen=True, slots=True)
class ArchivedRawSerp(ArchivedQueryUrl, DataClassJsonMixin):
    """
    Snapshot content of an archived SERP.

    Output of: 4-archived-raw-serps
    Input of: 5-archived-parsed-serps
    """

    content: bytes
    """
    Raw byte content of the archived SERP's snapshot.
    """
    encoding: str
    """
    Encoding of the archived SERP's snapshot.
    """


@dataclass(frozen=True, slots=True)
class ArchivedSerpResult(DataClassJsonMixin):
    """
    Single retrieved result from a query's archived SERP.
    """

    url: str
    """
    URL that the result points to.
    """
    title: str
    """
    Title of the result.
    """
    snippet: str | None
    """
    Snippet of the result.
    Highlighting is normalized to ``<em>`` tags. Other HTML tags are removed.
    """


@dataclass(frozen=True, slots=True)
class ArchivedParsedSerp(ArchivedQueryUrl, DataClassJsonMixin):
    """
    Archived search engine result page (SERP) corresponding to a query.

    Output of: 5-archived-parsed-serps
    Input of: 6-archived-raw-search-results, 8-ir-corpus
    """

    results: Sequence[ArchivedSerpResult] = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(ArchivedSerpResult.schema()))
        )
    )
    """
    Retrieved results from the SERP in the same order as they appear.
    """
    interpreted_query: str | None
    """
    Interpreted query that is displayed or otherwise included in the SERP.

    Note: the interpreted result query can be different from the original query
    due to spelling correction etc.
    """


@dataclass(frozen=True, slots=True)
class ArchivedRawSearchResult(ArchivedUrl, DataClassJsonMixin):
    """
    Raw content of an archived search result.

    Output of: 6-archived-raw-search-results
    Input of: 7-archived-parsed-search-results
    """

    content: bytes
    """
    Raw byte content of the archived SERP's snapshot.
    """
    encoding: str
    """
    Encoding of the archived SERP's snapshot.
    """

    serp_title: str
    """
    Title of the result as it appeared on the SERP.
    """
    snippet: str | None
    """
    Snippet of the result as it appeared on the SERP.
    Highlighting is normalized to ``<em>`` tags. Other HTML tags are removed.
    """


@dataclass(frozen=True, slots=True)
class ArchivedParsedSearchResult(ArchivedUrl, DataClassJsonMixin):
    """
    Parsed representation of an archived search result.

    Output of: 7-archived-parsed-search-results
    Input of: 8-ir-corpus
    """
    # TODO
    pass


# flake8: noqa: E402
from web_archive_query_log.model.parse import QueryParser, \
    PageParser, OffsetParser, QueryParserField, PageOffsetParserField, \
    ResultsParserField, InterpretedQueryParserField, InterpretedQueryParser, \
    ResultsParser


@dataclass(frozen=True, slots=True)
class Service(DataClassJsonMixin):
    """
    An online service that has a search interface.

    Output of: service collection, service domains
    Input of: service URLs, query extraction
    """

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
    alexa_rank: int | None
    """
    Rank from fused Alexa top-1M rankings.
    """
    category: str | None
    """
    Category of the service (manual annotation).
    """
    notes: str | None
    """
    Notes about the service (manual annotation).
    """
    input_field: bool | None
    """
    Whether the service has an input field.
    """
    search_form: bool | None
    """
    Whether the service has a search form element.
    """
    search_div: bool | None
    """
    Whether the service has a search div element.
    """
    domains: Sequence[str] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(String())
        )
    )
    """
    Known domains of the service, including the main domain.
    """
    query_parsers: Sequence[QueryParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(QueryParserField())
        )
    )
    """
    Query parsers in order of precedence.
    """
    page_parsers: Sequence[PageParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(PageOffsetParserField())
        )
    )
    """
    Page number parsers in order of precedence.
    """
    offset_parsers: Sequence[OffsetParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(PageOffsetParserField())
        )
    )
    """
    Page number parsers in order of precedence.
    """
    interpreted_query_parsers: Sequence[InterpretedQueryParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(InterpretedQueryParserField())
        )
    )
    """
    Interpreted query parsers in order of precedence.
    The interpreted query is the query that is displayed 
    or otherwise included in the SERP.

    Note: the interpreted result query can be different from the original query
    due to spelling correction etc.
    """
    results_parsers: Sequence[ResultsParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(ResultsParserField())
        )
    )
    """
    SERP parsers in order of precedence.
    """
