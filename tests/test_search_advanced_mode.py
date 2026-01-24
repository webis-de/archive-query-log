"""
Integration tests for Advanced Search Mode in search router

Tests the /api/serps endpoint with advanced_mode parameter.
"""


class TestAdvancedSearchMode:
    """Test advanced search mode in the unified search endpoint"""

    def test_advanced_mode_boolean_and(self, client):
        """Test AND operator in advanced mode"""
        response = client.get(
            "/api/serps",
            params={"query": "climate AND change", "advanced_mode": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True
        assert "results" in data

    def test_advanced_mode_boolean_or(self, client):
        """Test OR operator in advanced mode"""
        response = client.get(
            "/api/serps",
            params={"query": "solar OR wind", "advanced_mode": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True
        assert "results" in data

    def test_advanced_mode_phrase_search(self, client):
        """Test phrase search with quotes"""
        response = client.get(
            "/api/serps",
            params={"query": '"climate change"', "advanced_mode": "true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True
        assert data["query"] == '"climate change"'

    def test_advanced_mode_wildcard_asterisk(self, client):
        """Test wildcard search with *"""
        response = client.get(
            "/api/serps", params={"query": "climat*", "advanced_mode": "true"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_mode_wildcard_question(self, client):
        """Test wildcard search with ?"""
        response = client.get(
            "/api/serps", params={"query": "cl?mate", "advanced_mode": "true"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_mode_complex_query(self, client):
        """Test complex boolean query with parentheses"""
        response = client.get(
            "/api/serps",
            params={
                "query": "(renewable OR solar) AND energy",
                "advanced_mode": "true",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_mode_with_filters(self, client):
        """Test advanced mode combined with provider and year filters"""
        response = client.get(
            "/api/serps",
            params={
                "query": "climate AND change",
                "advanced_mode": "true",
                "year": "2023",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_mode_false(self, client):
        """Test that advanced_mode=false uses simple search"""
        response = client.get(
            "/api/serps",
            params={"query": "climate AND change", "advanced_mode": "false"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is False
        # In simple mode, "AND" should be treated as a literal word

    def test_advanced_mode_default_false(self, client):
        """Test that advanced_mode defaults to false"""
        response = client.get("/api/serps", params={"query": "climate"})
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is False

    def test_advanced_mode_pagination(self, client):
        """Test advanced mode with pagination"""
        response = client.get(
            "/api/serps",
            params={
                "query": "climate*",
                "advanced_mode": "true",
                "page": "2",
                "page_size": "20",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 20
        assert data["advanced_mode"] is True


class TestAdvancedSearchModeValidation:
    """Test validation and error handling for advanced search"""

    def test_empty_query_advanced_mode(self, client):
        """Test empty query in advanced mode - should handle gracefully"""
        response = client.get(
            "/api/serps", params={"query": "", "advanced_mode": "true"}
        )
        # Depending on implementation, might be 400 or return empty results
        assert response.status_code in [200, 400, 422]

    def test_only_operators_advanced_mode(self, client):
        """Test query with only operators"""
        response = client.get(
            "/api/serps", params={"query": "AND OR", "advanced_mode": "true"}
        )
        # Should handle gracefully, not crash
        assert response.status_code == 200


class TestAdvancedSearchComparison:
    """Compare results between simple and advanced mode"""

    def test_simple_vs_advanced_single_term(self, client):
        """Single term should work similarly in both modes"""
        simple_response = client.get(
            "/api/serps", params={"query": "climate", "advanced_mode": "false"}
        )
        advanced_response = client.get(
            "/api/serps", params={"query": "climate", "advanced_mode": "true"}
        )

        assert simple_response.status_code == 200
        assert advanced_response.status_code == 200

        # Both should return results (though counts may differ slightly)
        assert simple_response.json()["total"] > 0
        assert advanced_response.json()["total"] > 0

    def test_literal_and_vs_boolean_and(self, client):
        """
        Test difference between literal "AND" word vs boolean AND operator
        """
        # Simple mode: "AND" is a literal word to search for
        simple_response = client.get(
            "/api/serps",
            params={"query": "climate AND change", "advanced_mode": "false"},
        )

        # Advanced mode: "AND" is a boolean operator
        advanced_response = client.get(
            "/api/serps",
            params={"query": "climate AND change", "advanced_mode": "true"},
        )

        # Both should succeed but may have different result counts
        assert simple_response.status_code == 200
        assert advanced_response.status_code == 200


class TestAdvancedSearchWithProviderFilter:
    """Test advanced mode combined with provider filtering"""

    def test_advanced_boolean_with_provider(self, client):
        """Test boolean query with provider filter"""
        response = client.get(
            "/api/serps",
            params={
                "query": "climate AND energy",
                "advanced_mode": "true",
                "provider_id": "f205fc44-d918-4b79-9a7f-c1373a6ff9f2",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_phrase_with_year(self, client):
        """Test phrase search with year filter"""
        response = client.get(
            "/api/serps",
            params={
                "query": '"renewable energy"',
                "advanced_mode": "true",
                "year": "2023",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True

    def test_advanced_wildcard_with_status_code(self, client):
        """Test wildcard search with status code filter"""
        response = client.get(
            "/api/serps",
            params={
                "query": "climat*",
                "advanced_mode": "true",
                "status_code": "200",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["advanced_mode"] is True
