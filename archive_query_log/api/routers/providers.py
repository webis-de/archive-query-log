"""
Routers for getting search providers and related statistics.
"""

from functools import cached_property
from typing import Annotated, Iterable
from uuid import UUID

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import (
    Query,
    Bool,
    Match,
    MatchAll,
    MatchPhrasePrefix,
    Ids,
)
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel, Field
from slowapi.util import get_remote_address
from slowapi.extension import Limiter

from archive_query_log.api.dependencies import ConfigDependency, ElasticsearchDependency
from archive_query_log.config import Config
from archive_query_log.orm import Provider


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class _FilterParams(BaseModel):
    exclude_id: Annotated[
        UUID | None,
        Field(description="Exclude specific search provider ID."),
    ] = None

    @cached_property
    def elasticsearch_query(self) -> Query:
        filters: list[Query] = []
        # Exclude specific search provider ID.
        if self.exclude_id is not None:
            filters.append(~Ids(values=[str(self.exclude_id)]))
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
        return Match(name=self.query)
        # TODO: Implement advanced queries.


def _prepare_search(
    config: Config,
    elasticsearch: Elasticsearch,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
) -> Search:
    # Prepare search.
    search: Search = Provider.search(
        using=elasticsearch,
        index=config.es.index_providers,
    )
    # Build filters and query.
    search = search.filter(filter_params.elasticsearch_query)
    search = search.query(query_params.elasticsearch_query)
    return search


@router.get("/", operation_id="search_providers")
@limiter.limit("30/minute")
def search(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
    size: int = 10,
    from_: int = 0,
) -> list[Provider]:
    """
    Search for search providers matching the given query and filters, with pagination.
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
    return list(response)


@router.get("/count")
@limiter.limit("30/minute")
def count(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    filter_params: Annotated[_FilterParams, Depends()],
    query_params: Annotated[_QueryParams, Depends()],
) -> int:
    """
    Count search providers matching the given query and filters.
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
    Suggest search provider search queries based on a preliminar query.
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
        search = search.filter(MatchPhrasePrefix(name=query_params.query))
    # Configure pagination.
    search = search[:size]
    # Execute search and handle response.
    response: Iterable[Provider] = search.execute()
    return [hit.name for hit in response]


@router.get("/{id}")
@limiter.limit("120/minute")
def get_by_id(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    id: UUID,
    exclude_hidden: bool = False,
) -> Provider | None:
    """
    Get a search provider by its ID.
    """
    provider: Provider = Provider.get(
        id=str(id),
        using=elasticsearch,
        index=config.es.index_providers,
    )
    # TODO: Enable once implemented in ORM.
    # if exclude_hidden and provider.hidden:
    #     return None
    return provider
