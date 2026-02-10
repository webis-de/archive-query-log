"""Tests for the canonical archive detail endpoint using memento_api_url.

Covers the new route: /archives/{archive_id:path}
"""

from urllib.parse import quote
from fastapi.testclient import TestClient
import pytest


@pytest.mark.asyncio
async def test_archive_detail_canonical_success(client: TestClient):
    archive_id = "https://web.archive.org/web"
    encoded = quote(archive_id, safe="")

    resp = client.get(f"/archives/{encoded}")
    assert resp.status_code == 200
    data = resp.json()

    # basic shape
    for key in [
        "id",
        "name",
        "memento_api_url",
        "cdx_api_url",
        "homepage",
        "serp_count",
    ]:
        assert key in data

    assert data["id"] == archive_id
    assert data["memento_api_url"] == archive_id
    assert "Internet Archive" in data["name"]
    assert data["cdx_api_url"] == "https://web.archive.org/cdx/search/csv"
    assert data["homepage"] == "https://web.archive.org"
    assert data["serp_count"] == 80


@pytest.mark.asyncio
async def test_archive_detail_canonical_not_found(client: TestClient):
    archive_id = "https://unknown.example.org"
    encoded = quote(archive_id, safe="")

    resp = client.get(f"/archives/{encoded}")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "No results found"
