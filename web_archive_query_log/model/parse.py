from re import compile, IGNORECASE
from typing import Sequence, Protocol, runtime_checkable, Any, Mapping, Union

from marshmallow.fields import Field

from web_archive_query_log.model import ArchivedUrl, ArchivedSerpResult, \
    ArchivedRawSerp


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
    def parse(self, content: "ArchivedRawSerp") -> str | None:
        ...


@runtime_checkable
class ResultsParser(Protocol):
    def parse(
            self,
            raw_serp: "ArchivedRawSerp",
    ) -> Sequence["ArchivedSerpResult"] | None:
        ...


class QueryParserField(Field):
    def _deserialize(
            self,
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> QueryParser:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "query_parameter":
            from web_archive_query_log.queries.parse import \
                QueryParameterQueryParser
            return QueryParameterQueryParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import \
                FragmentParameterQueryParser
            return FragmentParameterQueryParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "path_segment":
            from web_archive_query_log.queries.parse import \
                PathSegmentQueryParser
            return PathSegmentQueryParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                remove_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
                space_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["space_patterns"]
                    ]
                    if "space_patterns" in value
                    else []
                ),
            )
        elif parser_type == "fragment_segment":
            from web_archive_query_log.queries.parse import \
                FragmentSegmentQueryParser
            return FragmentSegmentQueryParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                remove_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
                space_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["space_patterns"]
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
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> Union[PageParser | OffsetParser]:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "query_parameter":
            from web_archive_query_log.queries.parse import \
                QueryParameterPageOffsetParser
            return QueryParameterPageOffsetParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import \
                FragmentParameterPageOffsetParser
            return FragmentParameterPageOffsetParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                parameter=value["parameter"],
            )
        elif parser_type == "path_segment":
            from web_archive_query_log.queries.parse import \
                PathSegmentPageOffsetParser
            return PathSegmentPageOffsetParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                delimiter=value["delimiter"] if "delimiter" in value else "/",
                remove_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["remove_patterns"]
                    ]
                    if "remove_patterns" in value
                    else []
                ),
            )
        elif parser_type == "fragment_segment":
            from web_archive_query_log.queries.parse import \
                FragmentSegmentPageOffsetParser
            return FragmentSegmentPageOffsetParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
                segment=value["segment"],
                delimiter=value["delimiter"] if "delimiter" in value else "/",
                remove_patterns=(
                    [
                        compile(pattern, IGNORECASE)
                        for pattern in value["remove_patterns"]
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
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> InterpretedQueryParser:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "chatnoir":
            from web_archive_query_log.results.chatnoir import \
                ChatNoirInterpretedQueryParser
            return ChatNoirInterpretedQueryParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class ResultsParserField(Field):
    def _deserialize(
            self,
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> ResultsParser:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "bing":
            from web_archive_query_log.results.bing import BingResultsParser
            return BingResultsParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
            )
        if parser_type == "chatnoir":
            from web_archive_query_log.results.chatnoir import \
                ChatNoirResultsParser
            return ChatNoirResultsParser(
                url_pattern=compile(value["url_pattern"], IGNORECASE),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
