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


class ProviderAutocompleteRequest(BaseModel):
    prefix: str
    limit: int = 10


class SERPSearchByYearRequest(BaseModel):
    query: str
    provider_id: Optional[str] = None
    year: int
    limit: int = 50
