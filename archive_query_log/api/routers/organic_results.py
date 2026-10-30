"""
Routes for getting organic results of SERPs.
"""

from typing import Annotated
from uuid import UUID

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
    return OrganicResult.mget(
        docs=[str(id) for id in ids],
        using=elasticsearch,
        index=config.es.index_organic_results,
        missing="raise",
    )


@router.get("/{id}", operation_id="get_organic_result_by_id")
@limiter.limit("120/minute")
def get_by_id(
    request: Request,
    config: ConfigDependency,
    elasticsearch: ElasticsearchDependency,
    id: UUID,
) -> OrganicResult:
    """
    Get an organic result by its ID.
    """
    organic_result: OrganicResult = OrganicResult.get(
        id=str(id),
        using=elasticsearch,
        index=config.es.index_organic_results,
    )
    return organic_result
