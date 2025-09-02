from pathlib import Path
from typing import Annotated, TypeAlias, Literal

from cyclopts import App, Parameter
from cyclopts.types import ResolvedExistingFile
from cyclopts.validators import Number

from archive_query_log.config import Config
from archive_query_log.orm import (
    UrlQueryParserType,
    UrlQueryParser,
    UrlPageParserType,
    UrlPageParser,
    UrlOffsetParser,
    UrlOffsetParserType,
    WarcQueryParserType,
    WarcQueryParser,
    WarcSnippetsParserType,
    WarcSnippetsParser,
    WarcDirectAnswersParserType,
    WarcDirectAnswersParser,
    # WarcMainContentParserType,
    # WarcMainContentParser,
)

parsers = App(
    name="parsers",
    alias="p",
    help="Manage URL and WARC parsers.",
)


_DEFAULT_SERVICES_FILE = Path("data/selected-services.yaml")


url_query = App(
    name="url-query",
    alias="uq",
    help="Manage URL query parsers.",
)
parsers.command(url_query)


_UrlQueryParserType: TypeAlias = Literal[
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_query.command(name="add")
def url_query_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _UrlQueryParserType,
    parameter: str | None = None,
    segment: int | None = None,
    remove_pattern_regex: str | None = None,
    space_pattern_regex: str | None = None,
    config: Config,
) -> None:
    """
    Add a new URL query parser.
    """
    from archive_query_log.parsers.url_query import add_url_query_parser

    parser_type_strict: UrlQueryParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlQueryParser.init(using=config.es.client, index=config.es.index_url_query_parsers)
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


@url_query.command(name="import")
def url_query_import(
    *,
    services_path: Annotated[
        ResolvedExistingFile, Parameter(alias=["-s", "--services-file"])
    ] = _DEFAULT_SERVICES_FILE,
    config: Config,
) -> None:
    """
    Import URL query parsers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_url_query_parsers

    UrlQueryParser.init(using=config.es.client, index=config.es.index_url_query_parsers)
    import_url_query_parsers(config, services_path)


url_page = App(
    name="url-page",
    alias="up",
    help="Manage URL page parsers.",
)
parsers.command(url_page)


_UrlPageParserType: TypeAlias = Literal[
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_page.command(name="add")
def url_page_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _UrlPageParserType,
    parameter: str | None = None,
    segment: int | None = None,
    remove_pattern_regex: str | None = None,
    space_pattern_regex: str | None = None,
    config: Config,
) -> None:
    """
    Add a new URL page parser.
    """
    from archive_query_log.parsers.url_page import add_url_page_parser

    parser_type_strict: UrlPageParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlPageParser.init(using=config.es.client, index=config.es.index_url_page_parsers)
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


@url_page.command(name="import")
def url_page_import(
    *,
    services_path: Annotated[
        ResolvedExistingFile, Parameter(alias=["-s", "--services-file"])
    ] = _DEFAULT_SERVICES_FILE,
    config: Config,
) -> None:
    """
    Import URL page parsers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_url_page_parsers

    UrlPageParser.init(using=config.es.client, index=config.es.index_url_page_parsers)
    import_url_page_parsers(config, services_path)


url_offset = App(
    name="url-offset",
    alias="uo",
    help="Manage URL offset parsers.",
)
parsers.command(url_offset)


_UrlOffsetParserType: TypeAlias = Literal[
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


@url_offset.command(name="add")
def url_offset_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _UrlOffsetParserType,
    parameter: str | None = None,
    segment: int | None = None,
    remove_pattern_regex: str | None = None,
    space_pattern_regex: str | None = None,
    config: Config,
) -> None:
    """
    Add a new URL offset parser.
    """
    from archive_query_log.parsers.url_offset import add_url_offset_parser

    parser_type_strict: UrlOffsetParserType
    if parser_type == "query-parameter":
        parser_type_strict = "query_parameter"
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment-parameter":
        parser_type_strict = "fragment_parameter"
        if parameter is not None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path-segment":
        parser_type_strict = "path_segment"
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    UrlOffsetParser.init(
        using=config.es.client, index=config.es.index_url_offset_parsers
    )
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


@url_offset.command(name="import")
def url_offset_import(
    *,
    services_path: Annotated[
        ResolvedExistingFile, Parameter(alias=["-s", "--services-file"])
    ] = _DEFAULT_SERVICES_FILE,
    config: Config,
) -> None:
    """
    Import URL offset parsers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_url_offset_parsers

    UrlOffsetParser.init(
        using=config.es.client, index=config.es.index_url_offset_parsers
    )
    import_url_offset_parsers(config, services_path)


warc_query = App(
    name="warc-query",
    alias="wq",
    help="Manage WARC query parsers.",
)
parsers.command(warc_query)


_WarqQueryParserType: TypeAlias = Literal["xpath"]


@warc_query.command(name="add")
def warc_query_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _WarqQueryParserType,
    xpath: str | None = None,
    remove_pattern_regex: str | None = None,
    space_pattern_regex: str | None = None,
    config: Config,
) -> None:
    """
    Add a new WARC query parser.
    """
    from archive_query_log.parsers.warc_query import add_warc_query_parser

    parser_type_strict: WarcQueryParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcQueryParser.init(
        using=config.es.client, index=config.es.index_warc_query_parsers
    )
    add_warc_query_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        xpath=xpath,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
    )


@warc_query.command(name="import")
def warc_query_import(
    *,
    services_path: Annotated[
        ResolvedExistingFile, Parameter(alias=["-s", "--services-file"])
    ] = _DEFAULT_SERVICES_FILE,
    config: Config,
) -> None:
    """
    Import WARC query parsers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_warc_query_parsers

    WarcQueryParser.init(
        using=config.es.client, index=config.es.index_warc_query_parsers
    )
    import_warc_query_parsers(config, services_path)


warc_snippets = App(
    name="warc-snippets",
    alias="ws",
    help="Manage WARC snippets parsers.",
)
parsers.command(warc_snippets)


_WarcSnippetsParserType: TypeAlias = Literal["xpath"]


@warc_snippets.command(name="add")
def warc_snippets_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _WarcSnippetsParserType,
    xpath: str | None = None,
    url_xpath: str | None = None,
    title_xpath: str | None = None,
    text_xpath: str | None = None,
    config: Config,
) -> None:
    """
    Add a new WARC snippets parser.
    """
    from archive_query_log.parsers.warc_snippets import add_warc_snippets_parser

    parser_type_strict: WarcSnippetsParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcSnippetsParser.init(
        using=config.es.client, index=config.es.index_warc_snippets_parsers
    )
    add_warc_snippets_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        xpath=xpath,
        url_xpath=url_xpath,
        title_xpath=title_xpath,
        text_xpath=text_xpath,
    )


@warc_snippets.command(name="import")
def warc_snippets_import(
    *,
    services_path: Annotated[
        ResolvedExistingFile, Parameter(alias=["-s", "--services-file"])
    ] = Path("data") / "selected-services.yaml",
    config: Config,
) -> None:
    """
    Import WARC snippets parsers from a YAML search services file.
    """
    from archive_query_log.imports.yaml import import_warc_snippets_parsers

    WarcSnippetsParser.init(
        using=config.es.client, index=config.es.index_warc_snippets_parsers
    )
    import_warc_snippets_parsers(config, services_path)


warc_direct_answers = App(
    name="warc-direct-answers",
    alias="wda",
    help="Manage WARC direct answers parsers.",
)
parsers.command(warc_direct_answers)


_WarcDirectAnswersParserType: TypeAlias = Literal["xpath"]


@warc_direct_answers.command(name="add")
def warc_direct_answers_add(
    *,
    provider_id: str | None = None,
    url_pattern_regex: str | None = None,
    priority: Annotated[float, Number(gte=0)] | None = None,
    parser_type: _WarcDirectAnswersParserType,
    xpath: str | None = None,
    url_xpath: str | None = None,
    text_xpath: str | None = None,
    config: Config,
) -> None:
    """
    Add a new WARC direct answers parser.
    """
    from archive_query_log.parsers.warc_direct_answers import (
        add_warc_direct_answers_parser,
    )

    parser_type_strict: WarcDirectAnswersParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise ValueError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcDirectAnswersParser.init(
        using=config.es.client, index=config.es.index_warc_direct_answers_parsers
    )
    add_warc_direct_answers_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
        xpath=xpath,
        url_xpath=url_xpath,
        text_xpath=text_xpath,
    )


# warc_main_content = App(
#     name="warc-main-content",
#     alias="wmc",
#     help="Manage WARC main content parsers.",
# )
# parsers.command(warc_main_content)


# _WarcMainContentParserType = Literal["resiliparse"]


# @warc_main_content.command(name="add")
# def warc_main_content_add(
#     *,
#     provider_id: str | None = None,
#     url_pattern_regex: str | None = None,
#     priority: Annotated[float, Number(gte=0)] | None = None,
#     parser_type: _WarcMainContentParserType,
#     config: Config,
# ) -> None:
#     """
#     Add a new WARC main content parser.
#     """
#     from archive_query_log.parsers.warc_main_content import add_warc_main_content_parser

#     parser_type_strict: WarcMainContentParserType
#     if parser_type == "resiliparse":
#         parser_type_strict = "resiliparse"
#     else:
#         raise ValueError(f"Invalid parser type: {parser_type}")
#     WarcMainContentParser.init(
#         using=config.es.client, index=config.es.index_warc_direct_answers_parsers
#     )
#     add_warc_main_content_parser(
#         config=config,
#         provider_id=provider_id,
#         url_pattern_regex=url_pattern_regex,
#         priority=priority,
#         parser_type=parser_type_strict,
#     )
