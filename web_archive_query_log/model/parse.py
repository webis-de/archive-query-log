from typing import Sequence, Protocol, runtime_checkable, Any, Mapping, Union

from marshmallow.fields import Field

from web_archive_query_log.model import ArchivedUrl, SearchResult, \
    ArchivedSerpContent


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
    def parse(self, content: "ArchivedSerpContent") -> str | None:
        ...


@runtime_checkable
class ResultsParser(Protocol):
    def parse(
            self,
            content: "ArchivedSerpContent",
    ) -> Sequence["SearchResult"] | None:
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
            return QueryParameterQueryParser(parameter=value["parameter"])
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import \
                FragmentParameterQueryParser
            return FragmentParameterQueryParser(parameter=value["parameter"])
        elif parser_type == "path_suffix":
            from web_archive_query_log.queries.parse import \
                PathSuffixQueryParser
            return PathSuffixQueryParser(
                path_prefix=value["path_prefix"],
                single_segment=value.get("single_segment", False),
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
            return QueryParameterPageOffsetParser(parameter=value["parameter"])
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import \
                FragmentParameterPageOffsetParser
            return FragmentParameterPageOffsetParser(
                parameter=value["parameter"])
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
        if parser_type == "google":
            # TODO
            raise NotImplementedError()
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
            from web_archive_query_log.results.parse import BingResultsParser
            return BingResultsParser()
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
