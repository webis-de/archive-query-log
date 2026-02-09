"""
Tests for Advanced Search Mode

Tests boolean operators, phrase search, and wildcards in the advanced search parser.
"""

from archive_query_log.browser.utils.advanced_search_parser import (
    parse_advanced_query,
    AdvancedSearchParser,
    TokenType,
)


class TestTokenizer:
    """Test the tokenization of advanced search queries"""

    def test_simple_word(self):
        parser = AdvancedSearchParser("climate")
        tokens = parser.tokenize()
        assert len(tokens) == 2  # word + EOF
        assert tokens[0].type == TokenType.WORD
        assert tokens[0].value == "climate"

    def test_multiple_words(self):
        parser = AdvancedSearchParser("climate change")
        tokens = parser.tokenize()
        assert len(tokens) == 3  # word + word + EOF
        assert tokens[0].value == "climate"
        assert tokens[1].value == "change"

    def test_and_operator(self):
        parser = AdvancedSearchParser("climate AND change")
        tokens = parser.tokenize()
        assert len(tokens) == 4  # word + AND + word + EOF
        assert tokens[0].type == TokenType.WORD
        assert tokens[1].type == TokenType.AND
        assert tokens[2].type == TokenType.WORD

    def test_or_operator(self):
        parser = AdvancedSearchParser("solar OR wind")
        tokens = parser.tokenize()
        assert tokens[1].type == TokenType.OR

    def test_case_insensitive_operators(self):
        parser = AdvancedSearchParser("test and value or result")
        tokens = parser.tokenize()
        assert tokens[1].type == TokenType.AND
        assert tokens[3].type == TokenType.OR

    def test_phrase_search(self):
        parser = AdvancedSearchParser('"climate change"')
        tokens = parser.tokenize()
        assert len(tokens) == 2  # phrase + EOF
        assert tokens[0].type == TokenType.PHRASE
        assert tokens[0].value == "climate change"

    def test_parentheses(self):
        parser = AdvancedSearchParser("(climate OR weather) AND change")
        tokens = parser.tokenize()
        assert tokens[0].type == TokenType.LPAREN
        assert tokens[4].type == TokenType.RPAREN

    def test_wildcard(self):
        parser = AdvancedSearchParser("clim*")
        tokens = parser.tokenize()
        assert tokens[0].type == TokenType.WORD
        assert tokens[0].value == "clim*"

    def test_question_mark_wildcard(self):
        parser = AdvancedSearchParser("cl?mate")
        tokens = parser.tokenize()
        assert tokens[0].value == "cl?mate"


class TestQueryParsing:
    """Test the parsing of queries into Elasticsearch DSL"""

    def test_simple_word(self):
        query = parse_advanced_query("climate")
        assert "match" in query
        assert query["match"]["url_query"] == "climate"

    def test_phrase_search(self):
        query = parse_advanced_query('"climate change"')
        assert "match_phrase" in query
        assert query["match_phrase"]["url_query"] == "climate change"

    def test_wildcard_search(self):
        query = parse_advanced_query("clim*")
        assert "wildcard" in query
        assert query["wildcard"]["url_query"] == "clim*"

    def test_and_operator(self):
        query = parse_advanced_query("climate AND change")
        assert "bool" in query
        assert "must" in query["bool"]
        assert len(query["bool"]["must"]) == 2

    def test_or_operator(self):
        query = parse_advanced_query("solar OR wind")
        assert "bool" in query
        assert "should" in query["bool"]
        assert len(query["bool"]["should"]) == 2
        assert query["bool"]["minimum_should_match"] == 1

    def test_complex_boolean(self):
        query = parse_advanced_query("(renewable OR solar) AND energy")
        assert "bool" in query
        # Should have AND at top level
        assert "must" in query["bool"]

    def test_multiple_and(self):
        query = parse_advanced_query("climate AND change AND global")
        assert "bool" in query
        assert "must" in query["bool"]
        assert len(query["bool"]["must"]) == 3

    def test_multiple_or(self):
        query = parse_advanced_query("solar OR wind OR hydro")
        assert "bool" in query
        assert "should" in query["bool"]
        assert len(query["bool"]["should"]) == 3

    def test_phrase_with_and(self):
        query = parse_advanced_query('"climate change" AND renewable')
        assert "bool" in query
        assert "must" in query["bool"]
        # First should be phrase, second should be match
        must_clauses = query["bool"]["must"]
        assert any("match_phrase" in clause for clause in must_clauses)
        assert any("match" in clause for clause in must_clauses)

    def test_wildcard_with_boolean(self):
        query = parse_advanced_query("clim* AND energy")
        assert "bool" in query
        must_clauses = query["bool"]["must"]
        assert any("wildcard" in clause for clause in must_clauses)
        assert any("match" in clause for clause in must_clauses)

    def test_empty_query(self):
        query = parse_advanced_query("")
        assert "match_all" in query

    def test_nested_parentheses(self):
        query = parse_advanced_query("((solar OR wind) AND energy) OR climate")
        assert "bool" in query
        # Top level should have OR (should)
        assert "should" in query["bool"]


class TestEdgeCases:
    """Test edge cases and potential issues"""

    def test_unclosed_quote(self):
        # Should handle gracefully - treat as phrase up to end
        query = parse_advanced_query('"climate change')
        assert "match_phrase" in query

    def test_unmatched_parenthesis(self):
        # Should handle gracefully
        query = parse_advanced_query("(climate AND change")
        # Should still parse the boolean
        assert "bool" in query or "match" in query

    def test_only_operators(self):
        parse_advanced_query("AND OR")
        # AND and OR without operands should be treated as words
        # (depends on implementation)
        # At minimum, should not crash

    def test_special_characters_in_phrase(self):
        query = parse_advanced_query('"test & value"')
        assert "match_phrase" in query
        assert query["match_phrase"]["url_query"] == "test & value"

    def test_mixed_case_in_phrase(self):
        query = parse_advanced_query('"Climate CHANGE"')
        assert query["match_phrase"]["url_query"] == "Climate CHANGE"

    def test_multiple_wildcards(self):
        query = parse_advanced_query("*test*")
        assert "wildcard" in query
        assert query["wildcard"]["url_query"] == "*test*"

    def test_question_mark_wildcard(self):
        query = parse_advanced_query("te?t")
        assert "wildcard" in query
        assert query["wildcard"]["url_query"] == "te?t"


class TestRealWorldQueries:
    """Test realistic search queries"""

    def test_research_query(self):
        query = parse_advanced_query(
            '("climate change" OR "global warming") AND (policy OR regulation)'
        )
        assert "bool" in query
        # Top level is AND
        assert "must" in query["bool"]

    def test_specific_term_exclusion_pattern(self):
        # Although we don't support NOT, test OR patterns
        query = parse_advanced_query("renewable AND (solar OR wind OR hydro)")
        assert "bool" in query

    def test_wildcard_variations(self):
        query = parse_advanced_query("climat* OR environment*")
        assert "bool" in query
        assert "should" in query["bool"]
        # Both should be wildcards
        for clause in query["bool"]["should"]:
            assert "wildcard" in clause

    def test_exact_phrase_with_filters(self):
        query = parse_advanced_query('"renewable energy" AND policy')
        assert "bool" in query
        assert "must" in query["bool"]

    def test_multiple_phrases(self):
        query = parse_advanced_query('"climate change" OR "global warming"')
        assert "bool" in query
        assert "should" in query["bool"]
        for clause in query["bool"]["should"]:
            assert "match_phrase" in clause
