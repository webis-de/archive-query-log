"""Tests for archive detail router endpoints"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_list_archives(client: TestClient, mock_elasticsearch):
    """Test GET /archives"""
    response = client.get("/archives")

    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "archives" in data
    assert isinstance(data["archives"], list)
    assert data["total"] == 2  # Mock returns 2 archives


@pytest.mark.asyncio
async def test_list_archives_with_limit(client: TestClient, mock_elasticsearch):
    """Test GET /archives with limit parameter"""
    response = client.get("/archives?limit=50")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "archives" in data
    assert len(data["archives"]) == 2


@pytest.mark.asyncio
async def test_list_archives_invalid_limit(client: TestClient, mock_elasticsearch):
    """Test GET /archives with invalid limit"""
    response = client.get("/archives?limit=0")

    # Should fail validation
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_archives_returns_archive_structure(
    client: TestClient, mock_elasticsearch
):
    """Test that list_archives returns proper archive metadata"""
    response = client.get("/archives")

    assert response.status_code == 200
    data = response.json()

    # Should have archives in response
    assert "archives" in data
    assert data["total"] == 2  # Mock returns 2 archives
    assert len(data["archives"]) == 2

    # Check first archive structure
    archive = data["archives"][0]
    required_fields = ["id", "name", "memento_api_url", "cdx_api_url", "serp_count"]
    for field in required_fields:
        assert field in archive, f"Missing field: {field}"

    # Check field types
    assert isinstance(archive["id"], str)
    assert isinstance(archive["name"], str)
    assert isinstance(archive["memento_api_url"], str)
    assert isinstance(archive["serp_count"], int)
    assert archive["serp_count"] >= 0


@pytest.mark.asyncio
async def test_internet_archive_details(client: TestClient, mock_elasticsearch):
    """Test that Internet Archive is correctly identified in list"""
    response = client.get("/archives")

    assert response.status_code == 200
    data = response.json()

    # Find Internet Archive in the list
    internet_archive = next(
        (a for a in data["archives"] if "web.archive.org" in a["memento_api_url"]), None
    )

    assert internet_archive is not None, "Internet Archive not found in list"
    assert "Internet Archive" in internet_archive["name"]
    assert internet_archive["cdx_api_url"] == "https://web.archive.org/cdx/search/csv"
    assert internet_archive["homepage"] == "https://web.archive.org"
    assert internet_archive["serp_count"] == 80  # Mock returns 80 for IA


@pytest.mark.asyncio
async def test_archive_list_sorted_by_count(client: TestClient, mock_elasticsearch):
    """Test that archives are sorted by SERP count (descending)"""
    response = client.get("/archives")

    assert response.status_code == 200
    data = response.json()
    archives = data["archives"]

    # Check that archives are sorted by count descending
    if len(archives) > 1:
        for i in range(len(archives) - 1):
            assert (
                archives[i]["serp_count"] >= archives[i + 1]["serp_count"]
            ), "Archives should be sorted by count in descending order"
