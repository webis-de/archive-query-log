"""
Routes for getting SERPs and related statistics.
"""

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from functools import cached_property
from typing import Annotated, Iterable, Literal, Callable
from uuid import UUID

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from elasticsearch_dsl.aggs import (
    Terms as TermsAggregation,
    DateHistogram,
    AutoDateHistogram,
    Cardinality,
)
from elasticsearch_dsl.query import (
    Query,
    Bool,
    Match,
    MatchAll,
    MatchPhrasePrefix,
    Term,
    Range,
    Ids,
)
from fastapi import APIRouter, Query as QueryParam, Request, Depends
from pydantic import BaseModel, Field, HttpUrl, computed_field
from slowapi.util import get_remote_address
from slowapi.extension import Limiter

from archive_query_log.api.dependencies import (
    ConfigDependency,
    ElasticsearchDependency,
)
from archive_query_log.api.utils.advanced_search_parser import parse_advanced_query
from archive_query_log.api.utils.url_cleaner import remove_tracking_parameters
from archive_query_log.config import Config
from archive_query_log.orm import Serp, Provider, Archive, WebSearchResultBlock


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class EnrichedSerp(Serp):
    # TODO: Add additional fields for related SERPs, etc. that can be included on demand in the response of the unified SERP detail endpoint.

    @computed_field  # type: ignore[prop-decorator]
    @property
    def capture_url_without_tracking(self) -> HttpUrl:
        return HttpUrl(remove_tracking_parameters(self.capture.url))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def unfurl_url(self) -> HttpUrl:
        return HttpUrl(f"https://dfir.blog/unfurl/?url={self.capture.url}")

    # TODO: Parsed unfurl data


class _FilterParams(BaseModel):
    archive_id: Annotated[
        UUID | None,
        Field(description="Include only SERPs from the specified web archive ID."),
    ] = None
    provider_id: Annotated[
        UUID | None,
        Field(description="Include only SERPs from the specified search provider ID."),
    ] = None
    from_timestamp: Annotated[
        datetime | None,
        Field(description="Include only SERPs from the specified timestamp."),
    ] = None
    to_timestamp: Annotated[
        datetime | None,
        Field(description="Include only SERPs before the specified timestamp."),
    ] = None
    status_code: Annotated[
        int | None,
        Field(description="Include only SERPs with the specified HTTP status code."),
    ] = None
    exclude_id: Annotated[
        UUID | None,
        Field(description="Exclude a specific SERP ID."),
    ] = None
    exclude_hidden: Annotated[
        bool,
        Field(description="Exclude hidden SERPs (e.g., spam, porn, etc.)"),
    ] = False

    @cached_property
    def elasticsearch_query(self) -> Query:
        filters: list[Query] = []
        # Include only SERPs from the given web archive (by its UUID).
        if self.archive_id:
            filters.append(Term(archive__id=str(self.archive_id)))
        # Include only SERPs from the given search provider (by its UUID).
        if self.provider_id:
            filters.append(Term(provider__id=str(self.provider_id)))
        # Filter by capture timestamp range.
        if self.from_timestamp or self.to_timestamp:
            range = {}
            if self.from_timestamp:
                range["gte"] = self.from_timestamp.isoformat()
            if self.to_timestamp:
                range["lt"] = self.to_timestamp.isoformat()
            filters.append(Range(capture__timestamp=range))
        # Include only SERPs with this HTTP status code.
        if self.status_code:
            filters.append(Term(capture__status_code=self.status_code))
        # Exclude a specific SERP ID.
        if self.exclude_id:
            filters.append(~Ids(ids=[str(self.exclude_id)]))
        # Exclude hidden SERPs.
        if self.exclude_hidden:
            filters.append(~Term(hidden=True))
        return MatchAll() if not filters else Bool(filter=filters)


class _QueryParams(BaseModel):
    query: str | None = None
    query_language: Annotated[
        bool,
        Field(description="Enable advanced query language."),
    ] = False
    fuzzy_matching: Annotated[
        bool,
        Field(description="Enable fuzzy matching (e.g., for typos)."),
    ] = False
    multi_field_matching: Annotated[
        bool,
        Field(description="Enable multi-field matching."),
    ] = False

    @cached_property
    def elasticsearch_query(self) -> Query:
        if self.query is None:
            return MatchAll()
        # Choose query type based on advanced_mode, fuzzy, and expand_synonyms
        if self.query_language:
            # Parse query based on operators, phrases, and wildcards.
            # TODO: Also allow fuzzy and expansion within the parsed query (e.g., apply fuzziness to individual terms)
            return parse_advanced_query(self.query)
        else:
            # Simple term matching with optional fuzzy matching (e.g., for typos)
            return Match(
                url_query={
                    "query": self.query,
                    "fuzziness": "AUTO" if self.fuzzy_matching else "0",
                }
            )
        # TODO: Implement multi-field matching (e.g., also match against URL etc.)


def _prepare_search(
    config: Config,
    elasticsearch: Elasticsearch,
    filter_params: _FilterParams,
    query_params: _QueryParams,
    # TODO: Add sorting by capture timestamp.
) -> Search:
    # Prepare search.
    search: Search = Serp.search(
        using=elasticsearch,
        index=config.es.index_serps,
    )
    # Build filters and query.
    search = search.filter(filter_params.elasticsearch_query)
    search = search.query(query_params.elasticsearch_query)
    return search


@router.get("/", operation_id="search_serps")
@limiter.limit("15/minute")
def search(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    size: Annotated[int, Field(gt=0, le=1000)] = 10,
    from_: Annotated[int, Field(ge=0)] = 0,
) -> list[EnrichedSerp]:
    """
    Search for SERPs matching the given query and filters, with pagination.
    """
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    # Configure pagination.
    search = search[from_ : from_ + size]
    # Execute search and handle response.
    response = search.execute()
    return [EnrichedSerp(**serp.model_dump()) for serp in response]


@router.get("/count")
@limiter.limit("15/minute")
def count(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
) -> int:
    """
    Count SERPs matching the given query and filters.
    """
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    return search.count()


@router.get("/suggestions")
@limiter.limit("120/minute")
def suggest_queries(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    size: Annotated[int, Field(gt=0, le=100)] = 10,
) -> list[str]:
    """
    Suggest SERP search queries based on a preliminar query.
    """
    # FIXME: This currently just returns some matching queries. It would be more performant to use an actual ES completion suggester on a dedicated indexed field: https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-suggesters#completion-suggester
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    # Add additional prefix filtering for suggestions (e.g., to only include queries starting with the given prefix).
    if query_params.query:
        search = search.filter(MatchPhrasePrefix(url_query=query_params.query))
    # Configure pagination.
    search = search[:size]
    # Execute search and handle response.
    response: Iterable[Serp] = search.execute()
    return [hit.url_query for hit in response]


@router.get("/count-unique")
@limiter.limit("15/minute")
def count_unique(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
) -> int:
    """
    Count unique SERP's (by parsed query) among the SERPs matching the given filters and query.
    """
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    search.aggs.metric(
        "unique_queries",
        Cardinality(
            field="url_query.keyword",
            precision_threshold=40000,
        ),
    )
    response = search.execute()
    return response.aggregations.unique_queries.value


class ArchiveBucket(BaseModel):
    archive: Archive
    count: int


@router.get("/top-archives")
@limiter.limit("15/minute")
def top_archives(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    size: Annotated[int, Field(gt=0, le=100)] = 5,
) -> list[ArchiveBucket]:
    """
    Get the most common web archives among the SERPs matching the given filters and query.
    """
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    search.aggs.bucket(
        "top_archives",
        TermsAggregation(field="archive.id", size=size),
    )
    response = search.execute()
    archives = Archive.mget(
        docs=[bucket.key for bucket in response.aggregations.top_archives.buckets],
        using=elasticsearch,
        index=config.es.index_archives,
    )
    return [
        ArchiveBucket(archive=archive, count=bucket.doc_count)
        for archive, bucket in zip(archives, response.aggregations.top_archives.buckets)
    ]


class ProviderBucket(BaseModel):
    provider: Provider
    count: int


@router.get("/top-providers")
@limiter.limit("15/minute")
def top_providers(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    size: Annotated[int, Field(gt=0, le=100)] = 5,
) -> list[ProviderBucket]:
    """
    Get the most common search providers among the SERPs matching the given filters and query.
    """
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    search.aggs.bucket(
        "top_providers",
        TermsAggregation(field="provider.id", size=size),
    )
    response = search.execute()
    providers = Provider.mget(
        docs=[bucket.key for bucket in response.aggregations.top_providers.buckets],
        using=elasticsearch,
        index=config.es.index_providers,
    )
    return [
        ProviderBucket(provider=provider, count=bucket.doc_count)
        for provider, bucket in zip(
            providers, response.aggregations.top_providers.buckets
        )
    ]


class DateHistogramBucket(BaseModel):
    from_timestamp: datetime
    to_timestamp: datetime
    count: int


@router.get("/date-histogram")
@limiter.limit("15/minute")
def date_histogram(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    interval: Annotated[
        Literal[
            "day",
            "1d",
            "week",
            "1w",
            "month",
            "1M",
            "quarter",
            "1q",
            "year",
            "1y",
        ]
        | None,
        Field(description="Histogram interval."),
    ] = None,
    num_buckets: Annotated[int | None, Field(gt=0, le=1000)] = None,
) -> Iterable[DateHistogramBucket]:
    """
    Get a date histogram of the SERPs matching the given filters and query.

    Either specify a fixed calendar interval (e.g., day, week, month) or a target number of buckets (for automatic interval selection).
    """
    if interval is not None and num_buckets is not None:
        raise ValueError(
            "Cannot specify both `interval` and `num_buckets`. Please choose only one."
        )
    search = _prepare_search(
        config=config,
        elasticsearch=elasticsearch,
        filter_params=filter_params,
        query_params=query_params,
    )
    if interval is not None:
        search.aggs.bucket(
            "date_histogram",
            DateHistogram(
                field="capture.timestamp",
                calendar_interval=interval,
            ),
        )
    else:
        search.aggs.bucket(
            "date_histogram",
            AutoDateHistogram(
                field="capture.timestamp",
                buckets=num_buckets,
                minimum_interval="day",
            ),
        )
    response = search.execute()

    end_timestamp_fn_mapping: dict[str, Callable[[datetime], datetime]] = {
        "day": lambda timestamp: timestamp + timedelta(days=+1),
        "week": lambda timestamp: timestamp + timedelta(weeks=+1),
        "month": lambda timestamp: timestamp + relativedelta(month=+1),
        "quarter": lambda timestamp: timestamp + relativedelta(month=+3),
        "year": lambda timestamp: timestamp + relativedelta(year=+1),
    }
    end_timestamp_fn_mapping["1d"] = end_timestamp_fn_mapping["day"]
    end_timestamp_fn_mapping["1w"] = end_timestamp_fn_mapping["week"]
    end_timestamp_fn_mapping["1M"] = end_timestamp_fn_mapping["month"]
    end_timestamp_fn_mapping["1q"] = end_timestamp_fn_mapping["quarter"]
    end_timestamp_fn_mapping["1y"] = end_timestamp_fn_mapping["year"]
    end_timestamp_fn: Callable[[datetime], datetime] = end_timestamp_fn_mapping[
        interval
        if interval is not None
        else response.aggregations.date_histogram.interval
    ]

    buckets = (
        (bucket.key, bucket.doc_count)
        for bucket in response.aggregations.date_histogram.buckets
    )

    return [
        DateHistogramBucket(
            from_timestamp=start_timestamp,
            to_timestamp=end_timestamp_fn(start_timestamp),
            count=count,
        )
        for (start_timestamp, count) in buckets
    ]


class EnrichedSerpWithResults(EnrichedSerp):
    results: list[WebSearchResultBlock] | None


class SerpComparisonResult(BaseModel):
    serps: list[EnrichedSerpWithResults]


@router.get("/compare")
@limiter.limit("15/minute")
def compare(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    ids: Annotated[
        list[UUID],
        QueryParam(
            description="IDs of the SERPs to compare.",
            min_length=2,
        ),
    ],
) -> SerpComparisonResult:
    """
    Compare multiple SERPs.
    """
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate IDs are not allowed.")

    # Fetch SERPs by IDs.
    serps: list[Serp] = Serp.mget(
        docs=[str(id) for id in ids],
        using=elasticsearch,
        index=config.es.index_serps,
    )
    # Enrich SERPs.
    enriched_serps: list[EnrichedSerp] = [
        EnrichedSerp(**serp.model_dump()) for serp in serps
    ]

    # Load information on SERP results.
    enriched_serps_with_results: list[EnrichedSerpWithResults] = []
    for serp in enriched_serps:
        results: list[WebSearchResultBlock] | None = None
        if serp.warc_web_search_result_blocks is not None:
            results = WebSearchResultBlock.mget(
                docs=[str(block.id) for block in serp.warc_web_search_result_blocks],
                using=elasticsearch,
                index=config.es.index_web_search_result_blocks,
            )
        enriched_serps_with_results.append(
            EnrichedSerpWithResults(**serp.model_dump(), results=results)
        )

    # TODO: Analyze result sets and compute pairwise rank correlations etc. based on domain or similar.

    return SerpComparisonResult(serps=enriched_serps_with_results)


@router.get("/{id}")
@limiter.limit("120/minute")
def get_by_id(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    id: UUID,
    exclude_hidden: Annotated[
        bool,
        Field(description="Exclude hidden SERPs (e.g., spam, porn, etc.)."),
    ] = False,
) -> EnrichedSerp | None:
    """
    Get a SERP by its ID.
    """
    serp: Serp = Serp.get(
        id=str(id),
        using=elasticsearch,
        index=config.es.index_serps,
    )
    # TODO: Enable once implemented in ORM.
    # if exclude_hidden and serp.hidden:
    #     return None
    enriched_serp = EnrichedSerp(**serp.model_dump())
    return enriched_serp
