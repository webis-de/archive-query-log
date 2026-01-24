from pydantic import BaseModel
from typing import Optional


class SERPSearchBasic(BaseModel):
    query: str
    limit: int = 10


class ProviderSearch(BaseModel):
    name: str
    limit: int = 10


class SERPSearchAdvanced(BaseModel):
    query: str
    provider_id: Optional[str] = None
    from_timestamp: Optional[str] = None
    to_timestamp: Optional[str] = None
    status_code: Optional[int] = None
    limit: int = 10
    advanced_mode: bool = (
        False  # Enable advanced search with boolean operators, phrases, wildcards
    )


class ProviderAutocompleteRequest(BaseModel):
    prefix: str
    limit: int = 10


class SERPSearchByYearRequest(BaseModel):
    query: str
    provider_id: Optional[str] = None
    year: int
    limit: int = 50


# ---------------------------------------------------------
# Archive Schemas
# ---------------------------------------------------------
class ArchiveMetadata(BaseModel):
    """Web archive metadata including API endpoints and SERP count"""

    id: str
    name: str
    memento_api_url: str
    cdx_api_url: Optional[str] = None
    homepage: Optional[str] = None
    serp_count: int


class ArchiveList(BaseModel):
    """List of all available archives"""

    total: int
    archives: list[ArchiveMetadata]
