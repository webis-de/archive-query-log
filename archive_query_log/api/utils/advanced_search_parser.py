"""
Advanced Search Query Parser

Parses advanced search queries with support for:
- Boolean operators: AND, OR (case-insensitive)
- Phrase search: "exact phrase"
- Wildcards: * (multiple chars), ? (single char)
- Grouping with parentheses

Examples:
- climate AND change -> both terms must be present
- "climate change" -> exact phrase
- clim* -> matches climate, climatic, etc.
- (renewable OR solar) AND energy -> complex boolean logic
"""

# TODO: Replace this with a proper parser package if needed (e.g., pyparsing) for more complex queries: https://github.com/pyparsing/pyparsing/blob/master/examples/searchparser.py

from typing import List
from enum import Enum

from elasticsearch_dsl.query import Query, MatchPhrase, Wildcard, Match, MatchAll


class TokenType(Enum):
    """Token types for query parsing"""

    WORD = "word"
    PHRASE = "phrase"
    AND = "and"
    OR = "or"
    LPAREN = "lparen"
    RPAREN = "rparen"
    EOF = "eof"


class Token:
    """Represents a token in the query"""

    def __init__(self, type_: TokenType, value: str) -> None:
        self.type = type_
        self.value = value

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r})"


class AdvancedSearchParser:
    """
    Parser for advanced search queries.

    Converts user query string with boolean operators, phrases, and wildcards
    into Elasticsearch query DSL.
    """

    def __init__(self, query: str) -> None:
        self.query = query
        self.tokens: List[Token] = []
        self.current_token_index = 0

    def tokenize(self) -> List[Token]:
        """
        Tokenize the input query into operators, phrases, and words.

        Returns:
            List of tokens
        """
        tokens = []
        i = 0
        query = self.query.strip()

        while i < len(query):
            # Skip whitespace
            if query[i].isspace():
                i += 1
                continue

            # Quoted phrase
            if query[i] == '"':
                i += 1
                phrase = ""
                while i < len(query) and query[i] != '"':
                    phrase += query[i]
                    i += 1
                if i < len(query):  # Skip closing quote
                    i += 1
                tokens.append(Token(TokenType.PHRASE, phrase))
                continue

            # Left parenthesis
            if query[i] == "(":
                tokens.append(Token(TokenType.LPAREN, "("))
                i += 1
                continue

            # Right parenthesis
            if query[i] == ")":
                tokens.append(Token(TokenType.RPAREN, ")"))
                i += 1
                continue

            # Word or operator
            word = ""
            while i < len(query) and not query[i].isspace() and query[i] not in '()"':
                word += query[i]
                i += 1

            if word:
                # Check if it's an operator
                word_upper = word.upper()
                if word_upper == "AND":
                    tokens.append(Token(TokenType.AND, word_upper))
                elif word_upper == "OR":
                    tokens.append(Token(TokenType.OR, word_upper))
                else:
                    tokens.append(Token(TokenType.WORD, word))

        tokens.append(Token(TokenType.EOF, ""))
        self.tokens = tokens
        return tokens

    def _current_token(self) -> Token:
        """Get current token"""
        if self.current_token_index < len(self.tokens):
            return self.tokens[self.current_token_index]
        return Token(TokenType.EOF, "")

    def _consume_token(self) -> None:
        """Move to next token"""
        self.current_token_index += 1

    def _convert_wildcard_to_es(self, word: str) -> str:
        """
        Convert user-friendly wildcards to Elasticsearch wildcards.
        * -> * (multiple chars)
        ? -> ? (single char)
        """
        return word

    def _build_term_query(self, term: str, is_phrase: bool = False) -> Query:
        """
        Build Elasticsearch query for a single term or phrase.

        Args:
            term: The search term
            is_phrase: Whether this is a phrase search

        Returns:
            Elasticsearch query clause
        """
        # Check if term contains wildcards
        has_wildcard = "*" in term or "?" in term

        if is_phrase:
            # Phrase search - exact match
            return MatchPhrase(url_query=term)
        elif has_wildcard:
            # Wildcard search
            return Wildcard(url_query=self._convert_wildcard_to_es(term))
        else:
            # Regular term search
            return Match(url_query=term)

    def _parse_primary(self) -> Query:
        """
        Parse a primary expression (word, phrase, or parenthesized expression).

        Returns:
            Elasticsearch query clause
        """
        token = self._current_token()

        if token.type == TokenType.WORD:
            self._consume_token()
            return self._build_term_query(token.value, is_phrase=False)

        elif token.type == TokenType.PHRASE:
            self._consume_token()
            return self._build_term_query(token.value, is_phrase=True)

        elif token.type == TokenType.LPAREN:
            self._consume_token()
            expr = self._parse_or()
            if self._current_token().type == TokenType.RPAREN:
                self._consume_token()
            return expr

        else:
            # Empty or invalid - return match all
            return MatchAll()

    def _parse_and(self) -> Query:
        """
        Parse AND expressions.

        Returns:
            Elasticsearch query clause
        """
        left = self._parse_primary()

        while self._current_token().type == TokenType.AND:
            self._consume_token()
            right = self._parse_primary()

            # Combine with bool must (AND logic)
            left = left & right

        return left

    def _parse_or(self) -> Query:
        """
        Parse OR expressions.

        Returns:
            Elasticsearch query clause
        """
        left = self._parse_and()

        while self._current_token().type == TokenType.OR:
            self._consume_token()
            right = self._parse_and()

            # Combine with bool should (OR logic)
            left = left | right

        return left

    def parse(self) -> Query:
        """
        Parse the query and generate Elasticsearch query DSL.

        Returns:
            Elasticsearch query clause
        """
        self.tokenize()
        self.current_token_index = 0

        if not self.tokens or len(self.tokens) == 1:  # Only EOF token
            return MatchAll()

        return self._parse_or()


def parse_advanced_query(query: str) -> Query:
    """
    Parse an advanced search query into Elasticsearch query DSL.

    Args:
        query: User query string with boolean operators, phrases, wildcards

    Returns:
        Elasticsearch query clause

    Examples:
        >>> parse_advanced_query('climate AND change')
        {'bool': {'must': [{'match': {'url_query': 'climate'}},
                           {'match': {'url_query': 'change'}}]}}

        >>> parse_advanced_query('"climate change"')
        {'match_phrase': {'url_query': 'climate change'}}

        >>> parse_advanced_query('clim*')
        {'wildcard': {'url_query': 'clim*'}}
    """
    parser = AdvancedSearchParser(query)
    return parser.parse()
