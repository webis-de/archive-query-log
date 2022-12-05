from typing import Sequence, Protocol, runtime_checkable, Any, Mapping

from marshmallow.fields import Field

from web_archive_query_log.model import ArchivedUrl, SearchResult, \
    ArchivedSerpContent


@runtime_checkable
class PageNumberParser(Protocol):
    def parse(self, url: "ArchivedUrl") -> int | None:
        ...


@runtime_checkable
class QueryParser(Protocol):
    def parse(self, url: "ArchivedUrl") -> str | None:
        ...


@runtime_checkable
class ResultsParser(Protocol):
    def parse(
            self,
            content: "ArchivedSerpContent",
    ) -> Sequence["SearchResult"] | None:
        ...


@runtime_checkable
class ResultQueryParser(Protocol):
    def parse(
            self,
            content: "ArchivedSerpContent",
    ) -> str | None:
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
            from web_archive_query_log.queries.parse import QueryParameter
            return QueryParameter(key=value["parameter"])
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import FragmentParameter
            return FragmentParameter(key=value["parameter"])
        elif parser_type == "path_suffix":
            from web_archive_query_log.queries.parse import PathSuffix
            return PathSuffix(
                prefix=value["path_prefix"],
                single_segment=value.get("single_segment", False),
            )
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class PageNumberParserField(Field):
    def _deserialize(
            self,
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> PageNumberParser:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "query_parameter":
            from web_archive_query_log.queries.parse import QueryParameter
            return QueryParameter(key=value["parameter"])
        elif parser_type == "fragment_parameter":
            from web_archive_query_log.queries.parse import FragmentParameter
            return FragmentParameter(key=value["parameter"])
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
        if parser_type == "google":
            # TODO
            raise NotImplementedError()
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")


class ResultQueryParserField(Field):
    def _deserialize(
            self,
            value: Any,
            attr: str | None,
            data: Mapping[str, Any] | None,
            **kwargs,
    ) -> ResultQueryParser:
        value: Mapping[str, Any]
        parser_type = value["type"]
        if parser_type == "form":
            # TODO
            raise NotImplementedError()
        else:
            raise ValueError(f"Unknown parser type: {parser_type}")
