"""
Routes for getting organic results of SERPs.
"""

from typing import Annotated
from uuid import UUID

from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Ids, Term
from fastapi import APIRouter, Query as QueryParam, Request
from slowapi.util import get_remote_address
from slowapi.extension import Limiter

from archive_query_log.api.dependencies import ConfigDependency, ElasticsearchDependency
from archive_query_log.orm import OrganicResult


router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/", operation_id="get_organic_results_by_ids")
@limiter.limit("120/minute")
def get_by_ids(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    ids: Annotated[
        list[UUID],
        QueryParam(
            description="IDs of the organic results to get (e.g., as referenced by a SERP).",
            min_length=1,
            max_length=100,
        ),
    ],
) -> list[OrganicResult]:
    """
    Get multiple organic results by their IDs (skipping unknown IDs).
    """
    # Search by IDs (instead of getting the documents directly), to always exclude hidden organic results (e.g., spam, porn, etc.).
    search: Search = OrganicResult.search(
        using=elasticsearch,
        index=config.es.index_organic_results,
    )
    search = search.filter(Ids(values=[str(id) for id in ids])).filter(
        ~Term(hidden=True)
    )
    response = search[: len(ids)].execute()
    # Restore the order of the given IDs.
    organic_results: dict[UUID, OrganicResult] = {hit.id: hit for hit in response}
    return [organic_results[id] for id in ids if id in organic_results]


@router.get("/{id}", operation_id="get_organic_result_by_id")
@limiter.limit("120/minute")
def get_by_id(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    id: UUID,
) -> OrganicResult | None:
    """
    Get an organic result by its ID.
    """
    # Search by ID (instead of getting the document directly), to always exclude hidden organic results (e.g., spam, porn, etc.).
    search: Search = OrganicResult.search(
        using=elasticsearch,
        index=config.es.index_organic_results,
    )
    search = search.filter(Ids(values=[str(id)])).filter(~Term(hidden=True))
    response = search[:1].execute()
    if not response.hits:
        return None
    return response.hits[0]
