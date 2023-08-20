from re import compile as pattern, IGNORECASE
from typing import Sequence, Protocol, runtime_checkable, Any, Mapping, Union

from marshmallow.fields import Field

from archive_query_log.legacy.model import (
    ArchivedUrl, ArchivedSearchResultSnippet, ArchivedRawSerp)


@runtime_checkable
class QueryParser(Protocol):
    def parse(self, url: "ArchivedUrl") -> str | None:
        ...


@runtime_checkable
class PageParser(Protocol):
    def parse(self, url: "ArchivedUrl") -> int | None:
        ...


@runtime_checkable
class OffsetParser(Protocol):
    def parse(self, url: "ArchivedUrl") -> int | None:
        ...


@runtime_checkable
class InterpretedQueryParser(Protocol):
    def parse(self, raw_serp: "ArchivedRawSerp") -> str | None:
        ...


@runtime_checkable
class ResultsParser(Protocol):
    def parse(
            self,
            raw_serp: "ArchivedRawSerp",
    ) -> Sequence["ArchivedSearchResultSnippet"] | None:
        ...


class QueryParserField(Field):
    def _deserialize(
            self,
            value: Mapping[str, Any],
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> QueryParser:
        parser_type = value["type"]
        if parser_type == "query_parameter":
            from archive_query_log.legacy.queries.parse import \
                QueryParameterQueryParser
            return QueryParameterQueryParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "fragment_parameter":
            from archive_query_log.legacy.queries.parse import \
                FragmentParameterQueryParser
            return FragmentParameterQueryParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "path_segment":
            from archive_query_log.legacy.queries.parse import \
                PathSegmentQueryParser
            return PathSegmentQueryParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                remove_patterns=(
                    [
                        pattern(remove_pattern, IGNORECASE)
                        for remove_pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
                space_patterns=(
                    [
                        pattern(space_pattern, IGNORECASE)
                        for space_pattern in value["space_patterns"]
                    ]
                    if "space_patterns" in value
                    else []
                ),
            )
        elif parser_type == "fragment_segment":
            from archive_query_log.legacy.queries.parse import \
                FragmentSegmentQueryParser
            return FragmentSegmentQueryParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                remove_patterns=(
                    [
                        pattern(remove_pattern, IGNORECASE)
                        for remove_pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
                space_patterns=(
                    [
                        pattern(space_pattern, IGNORECASE)
                        for space_pattern in value["space_patterns"]
                    ]
                    if "space_patterns" in value
                    else []
                ),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class PageOffsetParserField(Field):
    def _deserialize(
            self,
            value: Mapping[str, Any],
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> Union[PageParser | OffsetParser]:
        parser_type = value["type"]
        if parser_type == "query_parameter":
            from archive_query_log.legacy.queries.parse import \
                QueryParameterPageOffsetParser
            return QueryParameterPageOffsetParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "fragment_parameter":
            from archive_query_log.legacy.queries.parse import \
                FragmentParameterPageOffsetParser
            return FragmentParameterPageOffsetParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "path_segment":
            from archive_query_log.legacy.queries.parse import \
                PathSegmentPageOffsetParser
            return PathSegmentPageOffsetParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                delimiter=value["delimiter"] if "delimiter" in value else "/",
                remove_patterns=(
                    [
                        pattern(remove_pattern, IGNORECASE)
                        for remove_pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
            )
        elif parser_type == "fragment_segment":
            from archive_query_log.legacy.queries.parse import \
                FragmentSegmentPageOffsetParser
            return FragmentSegmentPageOffsetParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                delimiter=value["delimiter"] if "delimiter" in value else "/",
                remove_patterns=(
                    [
                        pattern(remove_pattern, IGNORECASE)
                        for remove_pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class InterpretedQueryParserField(Field):
    def _deserialize(
            self,
            value: Mapping[str, Any],
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> InterpretedQueryParser:
        parser_type = value["type"]
        if parser_type == "html_selector":
            from archive_query_log.legacy.results.parse import \
                HtmlSelectorInterpretedQueryParser
            return HtmlSelectorInterpretedQueryParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                query_selector=value["query_selector"],
                query_attribute=(
                    value["query_attribute"]
                    if "query_attribute" in value
                    else "value"
                ),
                query_text=(
                    value["query_text"]
                    if "query_text" in value
                    else False
                ),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class ResultsParserField(Field):
    def _deserialize(
            self,
            value: Mapping[str, Any],
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> ResultsParser:
        parser_type = value["type"]
        if parser_type == "html_selector":
            from archive_query_log.legacy.results.parse import \
                HtmlSelectorResultsParser
            return HtmlSelectorResultsParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
                results_selector=value["results_selector"],
                url_selector=value["url_selector"],
                url_attribute=(
                    value["url_attribute"]
                    if "url_attribute" in value
                    else "href"
                ),
                title_selector=value["title_selector"],
                snippet_selector=(
                    value["snippet_selector"]
                    if "snippet_selector" in value
                    else None
                ),
            )
        elif parser_type == "chatnoir":
            from archive_query_log.legacy.results.chatnoir import \
                ChatNoirResultsParser
            return ChatNoirResultsParser(
                url_pattern=pattern(value["url_pattern"], IGNORECASE),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
