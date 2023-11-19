from pathlib import Path

from click import group, option, Choice, Path as PathType, UsageError

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import UrlQueryParserType, \
    UrlQueryParser, UrlPageParserType, UrlPageParser, \
    UrlOffsetParser, UrlOffsetParserType


@group()
def parsers() -> None:
    pass


@parsers.group()
def url_query() -> None:
    pass


CHOICES_URL_QUERY_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_query.command("add")
@option("--provider-id", type=str, required=True)
@option("--url-pattern-regex", type=str)
@option("--priority", type=int)
@option("--parser-type",
        type=Choice(CHOICES_URL_QUERY_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_query_add(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlQueryParserType,
        parameter: str | None,
        segment: int | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    from archive_query_log.parsers.url_query import add_url_query_parser
    parser_type_strict: UrlQueryParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise UsageError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise UsageError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise UsageError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlQueryParser.init(using=config.es.client)
    add_url_query_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )


@url_query.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_query_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_url_query_parsers
    UrlQueryParser.init(using=config.es.client)
    import_url_query_parsers(config, services_path)


@parsers.group()
def url_page() -> None:
    pass


CHOICES_URL_PAGE_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_page.command("add")
@option("--provider-id", type=str, required=True)
@option("--url-pattern-regex", type=str)
@option("--priority", type=int)
@option("--parser-type",
        type=Choice(CHOICES_URL_PAGE_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_page_add(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlPageParserType,
        parameter: str | None,
        segment: int | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    from archive_query_log.parsers.url_page import add_url_page_parser
    parser_type_strict: UrlPageParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise UsageError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise UsageError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise UsageError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlPageParser.init(using=config.es.client)
    add_url_page_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )


@url_page.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_page_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_url_page_parsers
    UrlPageParser.init(using=config.es.client)
    import_url_page_parsers(config, services_path)


@parsers.group()
def url_offset() -> None:
    pass


CHOICES_URL_OFFSET_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_offset.command("add")
@option("--provider-id", type=str, required=True)
@option("--url-pattern-regex", type=str)
@option("--priority", type=int)
@option("--parser-type",
        type=Choice(CHOICES_URL_OFFSET_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_offset_add(
        config: Config,
        provider_id: str,
        url_pattern_regex: str | None,
        priority: int | None,
        parser_type: UrlOffsetParserType,
        parameter: str | None,
        segment: int | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    from archive_query_log.parsers.url_offset import add_url_offset_parser
    parser_type_strict: UrlOffsetParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise UsageError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise UsageError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise UsageError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlOffsetParser.init(using=config.es.client)
    add_url_offset_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )


@url_offset.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_offset_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_url_offset_parsers
    UrlOffsetParser.init(using=config.es.client)
    import_url_offset_parsers(config, services_path)
