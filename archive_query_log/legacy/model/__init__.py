from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from hashlib import md5
from pathlib import Path
from typing import Sequence, Any
from urllib.parse import SplitResult, urlsplit
from uuid import UUID, uuid5, NAMESPACE_URL

from dataclasses_json import DataClassJsonMixin, config
from marshmallow.fields import List, Nested, String, Field
from publicsuffixlist import PublicSuffixList

from archive_query_log.legacy.model.highlight import HighlightedText
from archive_query_log.legacy.util.serialization import HighlightedTextField


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
    def id(self) -> UUID:
        """
        Unique ID for this archived URL.
        """
        return uuid5(NAMESPACE_URL, f"{self.timestamp}:{self.url}")

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
        return md5(self.url.encode(), usedforsecurity=False).hexdigest()

    @cached_property
    def datetime(self) -> datetime:
        """
        Snapshot timestamp as a ``datetime`` object.
        """
        return datetime.fromtimestamp(self.timestamp, timezone.utc)

    @cached_property
    def archive_timestamp(self) -> str:
        """
        Snapshot timestamp as a string in the format used
        by the Wayback Machine (``YYYYmmddHHMMSS``).
        """
        return f"{self.datetime.year:04d}{self.datetime.month:02d}" \
               f"{self.datetime.day:02d}{self.datetime.hour:02d}" \
               f"{self.datetime.minute:02d}{self.datetime.second:02d}"

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
    Raw snapshot content of an archived SERP.

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
class ArchivedSearchResultSnippet(ArchivedUrl, DataClassJsonMixin):
    """
    Single retrieved result from a query's archived SERP.
    """

    rank: int
    """
    Rank of the result in the SERP.
    """
    title: HighlightedText | str = field(metadata=config(
        encoder=str,
        decoder=HighlightedText,
        mm_field=HighlightedTextField(),
    ))
    """
    Title of the result with optional highlighting.
    """
    snippet: HighlightedText | str | None = field(metadata=config(
        encoder=str,
        decoder=HighlightedText,
        mm_field=HighlightedTextField(allow_none=True),
    ))
    """
    Snippet of the result.
    Highlighting should be normalized to ``<em>`` tags. 
    Other HTML tags are removed.
    """

    @cached_property
    def id(self) -> UUID:
        """
        Unique ID for this archived URL.
        """
        return uuid5(NAMESPACE_URL, f"{self.rank}:{self.timestamp}:{self.url}")


@dataclass(frozen=True, slots=True)
class ArchivedParsedSerp(ArchivedQueryUrl, DataClassJsonMixin):
    """
    Archived search engine result page (SERP) corresponding to a query.

    Output of: 5-archived-parsed-serps
    Input of: 6-archived-raw-search-results, 8-ir-corpus
    """

    results: Sequence[ArchivedSearchResultSnippet] = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(ArchivedSearchResultSnippet.schema()))
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
class ArchivedRawSearchResult(ArchivedSearchResultSnippet, DataClassJsonMixin):
    """
    Raw content of an archived search result.

    Output of: 6-archived-raw-search-results
    Input of: 7-archived-parsed-search-results
    """

    content: bytes
    """
    Raw byte content of the archived search result's snapshot.
    """
    encoding: str
    """
    Encoding of the archived search result's snapshot.
    """


@dataclass(frozen=True, slots=True)
class ArchivedParsedSearchResult(ArchivedSearchResultSnippet,
                                 DataClassJsonMixin):
    """
    Parsed representation of an archived search result.

    Output of: 7-archived-parsed-search-results
    Input of: 8-ir-corpus
    """
    content_title: str | None
    """
    Title of the archived SERP's snapshot content.

    Note: the content title can be different from the snippet title due to ellipses etc.
    """
    content_plaintext: str | None
    """
    Plaintext of the archived SERP's snapshot content.
    """


# flake8: noqa: E402
from archive_query_log.legacy.model.parse import QueryParser, \
    PageParser, OffsetParser, QueryParserField, PageOffsetParserField, \
    ResultsParserField, InterpretedQueryParserField, InterpretedQueryParser, \
    ResultsParser

_public_suffix_list = PublicSuffixList()


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
    domains: Sequence[str] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(String())
        ),
    )
    """
    Known domains of the service, including the main domain.
    """
    focused_url_prefixes: Sequence[str] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(String())
        ),
        default=(),
    )
    """
    URL prefixes for a more focused pipeline which might miss some queries
    but executes faster.
    """
    query_parsers: Sequence[QueryParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(QueryParserField())
        ),
        default=(),
    )
    """
    Query parsers in order of precedence.
    """
    page_parsers: Sequence[PageParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(PageOffsetParserField())
        ),
        default=(),
    )
    """
    Page number parsers in order of precedence.
    """
    offset_parsers: Sequence[OffsetParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(PageOffsetParserField())
        ),
        default=(),
    )
    """
    Page number parsers in order of precedence.
    """
    interpreted_query_parsers: Sequence[InterpretedQueryParser] = field(
        metadata=config(
            decoder=tuple,
            mm_field=List(InterpretedQueryParserField())
        ),
        default=(),
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
        ),
        default=(),
    )
    """
    SERP parsers in order of precedence.
    """


class PathField(Field):
    def _serialize(
            self, value: Any, attr: str | None, obj: Any, **kwargs
    ) -> str:
        return str(value)

    def _deserialize(
            self, value: str, attr: str | None, data: Any, **kwargs: Any
    ) -> Path:
        return Path(value)


@dataclass(frozen=True, slots=True)
class CorpusJsonlLocation(DataClassJsonMixin):
    relative_path: Path = field(
        metadata=config(
            encoder=str,
            decoder=Path,
            mm_field=PathField(),
        )
    )
    """
    Path of the JSONL file relative to the corpus root path.
    """
    byte_offset: int
    """
    Position of the JSONL line's first byte in the decompressed JSONL file.
    """


@dataclass(frozen=True, slots=True)
class CorpusJsonlSnippetLocation(CorpusJsonlLocation, DataClassJsonMixin):
    index: int
    """
    Index of the snippet in the JSONL file entry's results list.
    """


@dataclass(frozen=True, slots=True)
class CorpusWarcLocation(DataClassJsonMixin):
    relative_path: Path = field(
        metadata=config(
            encoder=str,
            decoder=Path,
            mm_field=PathField(),
        )
    )
    """
    Path of the WARC file relative to the corpus root path.
    """
    byte_offset: int
    """
    Position of the WARC record's first byte in the compressed WARC file.
    """


@dataclass(frozen=True, slots=True)
class CorpusQueryUrl(DataClassJsonMixin):
    id: UUID
    """
    Unique ID based on the URL and timestamp.
    """
    url: str
    """
    Original URL that was archived.
    """
    timestamp: int
    """
    POSIX timestamp of the URL's archived snapshot in the Wayback Machine.
    """
    wayback_url: str
    """
    URL to access the archived snapshot in the Wayback Machine.
    """
    wayback_raw_url: str
    """
    URL to access the archived snapshot's raw contents in the Wayback Machine.
    """
    url_query: str | None
    """
    Query that was parsed from the URL.
    """
    url_page: int | None
    """
    SERP page number that was parsed from the URL, e.g., 1, 2, 3.

    Note: the page number should be zero-indexed, i.e.,
    the first result page has the page number 0.
    """
    url_offset: int | None
    """
    SERP results offset (start position) that was parsed from the URL, 
    e.g., 10, 20.

    Note: the offset should be zero-indexed, i.e.,
    the first result page has the offset 0.
    """
    serp_query: str | None
    """
    Interpreted query as displayed on (or otherwise included in) the SERP.

    Note: the interpreted result query can be different from the original query
    due to spelling correction etc.
    """
    archived_url_location: CorpusJsonlLocation
    """
    Location of the corresponding URL entry and JSONL file.
    """
    archived_query_url_location: CorpusJsonlLocation | None
    """
    Location of the corresponding query URL entry and JSONL file.
    """
    archived_raw_serp_location: CorpusWarcLocation | None
    """
    Location of the corresponding raw SERP entry and WARC file.
    """
    archived_parsed_serp_location: CorpusJsonlLocation | None
    """
    Location of the corresponding parsed SERP entry in the JSONL file.
    """


@dataclass(frozen=True, slots=True)
class CorpusSearchResult(DataClassJsonMixin):
    id: UUID
    """
    Unique ID for this archived URL.
    """
    url: str
    """
    Original URL that was archived.
    """
    timestamp: int
    """
    POSIX timestamp of the archived snapshot in the Wayback Machine.
    
    Note that there might not be a snapshot for the exact timestamp, 
    but the Wayback Machine will instead redirect 
    to the nearest available snapshot.
    """
    wayback_url: str
    """
    URL of the archived snapshot in the Wayback Machine.
    
    Note that there might not be a snapshot for the exact timestamp, 
    but the Wayback Machine will instead redirect 
    to the nearest available snapshot.
    """
    wayback_raw_url: str
    """
    URL of the archived snapshot's raw contents in the Wayback Machine.
    
    Note that there might not be a snapshot for the exact timestamp, 
    but the Wayback Machine will instead redirect 
    to the nearest available snapshot.
    """
    snippet_rank: int
    """
    Rank of the result in the SERP.
    """
    snippet_title: HighlightedText | str = field(metadata=config(
        encoder=str,
        decoder=HighlightedText,
        mm_field=HighlightedTextField(),
    ))
    """
    Snippet title of the result with optional highlighting.
    Highlighting should be normalized to ``<em>`` tags. 
    Other HTML tags are removed.
    """
    snippet_text: HighlightedText | str | None = field(metadata=config(
        encoder=str,
        decoder=HighlightedText,
        mm_field=HighlightedTextField(allow_none=True),
    ))
    """
    Snippet text of the result with optional highlighting.
    Highlighting should be normalized to ``<em>`` tags. 
    Other HTML tags are removed.
    """
    archived_snippet_location: CorpusJsonlSnippetLocation
    """
    Location of the corresponding snippet entry in the JSONL file.
    """
    archived_raw_search_result_location: CorpusWarcLocation | None
    """
    Location of the corresponding raw search result entry and WARC file.
    """
    archived_parsed_search_result_location: CorpusJsonlLocation | None
    """
    Location of the corresponding parsed search result entry in the JSONL file.
    """


@dataclass(frozen=True, slots=True)
class CorpusQuery(CorpusQueryUrl, DataClassJsonMixin):
    service: str
    """
    Name of the search engine service from which the query was fetched.
    """
    results: Sequence[CorpusSearchResult] | None = field(
        metadata=config(
            encoder=list,
            decoder=tuple,
            mm_field=List(Nested(CorpusSearchResult.schema()))
        )
    )
    """
    Retrieved results from the SERP in the same order as they appear.
    """


@dataclass(frozen=True, slots=True)
class CorpusDocument(CorpusSearchResult, DataClassJsonMixin):
    service: str
    """
    Name of the search engine service from which the snippet was fetched.
    """
    query: CorpusQueryUrl
    """
    Query and SERP that was used to retrieve this result.
    """
