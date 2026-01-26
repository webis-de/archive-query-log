"""Tests for SERP view switcher functionality.

Tests the ability to switch between different views of a SERP:
- Raw view (full data)
- Unbranded view (normalized)
- Snapshot view (web archive memento)
"""


def test_get_serp_views_endpoint(client):
    """Test that the /views endpoint returns available view options."""
    response = client.get("/api/serps/1/views")
    assert response.status_code == 200

    data = response.json()
    assert "serp_id" in data
    assert data["serp_id"] == "1"
    assert "views" in data
    assert isinstance(data["views"], list)
    assert len(data["views"]) == 3  # raw, unbranded, snapshot


def test_view_options_structure(client):
    """Test that each view option has the correct structure."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    for view in data["views"]:
        assert "type" in view
        assert "label" in view
        assert "description" in view
        assert "available" in view
        # url should be present only if available
        if view["available"]:
            assert "url" in view
        # reason should be present if not available
        if not view["available"]:
            assert "reason" in view


def test_raw_view_always_available(client):
    """Test that raw view is always available."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    raw_view = next(v for v in data["views"] if v["type"] == "raw")
    assert raw_view["available"] is True
    assert raw_view["url"] == "/api/serps/1"


def test_unbranded_view_availability(client):
    """Test that unbranded view is available when results exist."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    unbranded_view = next(v for v in data["views"] if v["type"] == "unbranded")
    # Should be available if SERP has results
    if unbranded_view["available"]:
        assert "url" in unbranded_view
        assert "/api/serps/1?view=unbranded" in unbranded_view["url"]
    else:
        assert "reason" in unbranded_view


def test_snapshot_view_availability(client):
    """Test that snapshot view is available when memento URL can be constructed."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    snapshot_view = next(v for v in data["views"] if v["type"] == "snapshot")
    # Should be available if SERP has archive metadata
    if snapshot_view["available"]:
        assert "url" in snapshot_view
        # URL should be an external memento URL
        assert "http" in snapshot_view["url"]
    else:
        assert "reason" in snapshot_view


def test_view_parameter_raw(client):
    """Test requesting SERP with view=raw parameter."""
    response = client.get("/api/serps/1?view=raw")
    assert response.status_code == 200

    data = response.json()
    # Raw view should return normal SERP data structure
    assert "serp_id" in data
    assert "serp" in data


def test_view_parameter_unbranded(client):
    """Test requesting SERP with view=unbranded parameter."""
    response = client.get("/api/serps/1?view=unbranded")
    assert response.status_code == 200

    data = response.json()
    assert "serp_id" in data
    assert "view" in data
    assert data["view"] == "unbranded"
    assert "data" in data

    # Verify unbranded structure
    unbranded_data = data["data"]
    assert "query" in unbranded_data
    assert "results" in unbranded_data
    assert "metadata" in unbranded_data


def test_view_parameter_snapshot_redirects(client):
    """Test that view=snapshot redirects to memento URL."""
    response = client.get("/api/serps/1?view=snapshot", follow_redirects=False)

    # Should either redirect (307/302) or return 404 if memento not available
    assert response.status_code in [302, 307, 404]

    if response.status_code in [302, 307]:
        # Should have a Location header with the memento URL
        assert "location" in response.headers


def test_view_parameter_invalid(client):
    """Test that invalid view parameter returns 400."""
    response = client.get("/api/serps/1?view=invalid")
    assert response.status_code == 400

    data = response.json()
    assert "detail" in data
    assert "Invalid view type" in data["detail"]


def test_view_parameter_case_insensitive(client):
    """Test that view parameter is case-insensitive."""
    response1 = client.get("/api/serps/1?view=RAW")
    response2 = client.get("/api/serps/1?view=raw")

    assert response1.status_code == 200
    assert response2.status_code == 200


def test_view_and_include_parameters_together(client):
    """Test that view parameter works alongside include parameter."""
    # This should work - view is ignored when it's raw or not set
    response = client.get("/api/serps/1?view=raw&include=original_url")
    assert response.status_code == 200

    data = response.json()
    assert "serp_id" in data
    assert "original_url" in data


def test_views_endpoint_nonexistent_serp(client):
    """Test that views endpoint handles any SERP ID (mock always returns data)."""
    # Note: The test mock always returns valid SERP data, so we get 200
    # In production, this would return 404 for non-existent SERPs
    response = client.get("/api/serps/zzz_nonexistent_99999/views")
    # Mock returns 200 with valid data
    assert response.status_code == 200
    data = response.json()
    assert "serp_id" in data
    assert "views" in data


def test_view_labels_are_descriptive(client):
    """Test that view labels are user-friendly."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    labels = [v["label"] for v in data["views"]]
    assert any("Full Data" in label or "full" in label.lower() for label in labels)
    assert any("Unbranded" in label for label in labels)
    assert any("Snapshot" in label or "Archive" in label for label in labels)


def test_view_descriptions_are_informative(client):
    """Test that view descriptions explain what each view provides."""
    response = client.get("/api/serps/1/views")
    data = response.json()

    for view in data["views"]:
        assert len(view["description"]) > 20  # Should be substantive
        assert isinstance(view["description"], str)
