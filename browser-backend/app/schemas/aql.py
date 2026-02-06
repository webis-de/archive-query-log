from pydantic import BaseModel
from typing import Optional
from enum import Enum


# ---------------------------------------------------------
# View Type Enums
# ---------------------------------------------------------
class SERPViewType(str, Enum):
    """Different view modes for displaying archived SERPs"""

    raw = "raw"  # Original full SERP data as stored
    unbranded = "unbranded"  # Provider-agnostic normalized view
    snapshot = "snapshot"  # Web archive memento/snapshot view


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


# ---------------------------------------------------------
# SERP View Schemas
# ---------------------------------------------------------
class SERPView(BaseModel):
    """Metadata about a specific SERP view option"""

    type: SERPViewType
    label: str
    description: str
    available: bool
    url: Optional[str] = None
    reason: Optional[str] = None  # Reason if not available


class SERPViewOptions(BaseModel):
    """Available view options for a SERP"""

    serp_id: str
    current_view: SERPViewType
    views: list[SERPView]
