from pathlib import Path

from click import group, option, Choice, Path as PathType, UsageError, \
    FloatRange

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import UrlQueryParserType, \
    UrlQueryParser, UrlPageParserType, UrlPageParser, \
    UrlOffsetParser, UrlOffsetParserType, WarcQueryParserType, \
    WarcQueryParser, WarcSnippetsParserType, WarcSnippetsParser, \
    WarcDirectAnswersParserType, WarcDirectAnswersParser, \
    WarcMainContentParserType, WarcMainContentParser


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
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_URL_QUERY_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_query_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
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


@url_query.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_query_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_url_query_parsers
    UrlQueryParser.init(using=config.es.client, index=config.es.index_url_query_parsers)
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
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_URL_PAGE_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_page_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
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


@url_page.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_page_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_url_page_parsers
    UrlPageParser.init(using=config.es.client, index=config.es.index_url_page_parsers)
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
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_URL_OFFSET_PARSER_TYPE), required=True)
@option("--parameter", type=str)
@option("--segment", type=int)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def url_offset_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
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
    UrlOffsetParser.init(using=config.es.client, index=config.es.index_url_offset_parsers)
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
    UrlOffsetParser.init(using=config.es.client, index=config.es.index_url_offset_parsers)
    import_url_offset_parsers(config, services_path)


@parsers.group()
def warc_query() -> None:
    pass


CHOICES_WARC_QUERY_PARSER_TYPE = [
    "xpath",
]


@warc_query.command("add")
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_WARC_QUERY_PARSER_TYPE), required=True)
@option("--xpath", type=str)
@option("--remove-pattern-regex", type=str)
@option("--space-pattern-regex", type=str)
@pass_config
def warc_query_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
        xpath: str | None,
        remove_pattern_regex: str | None,
        space_pattern_regex: str | None,
) -> None:
    from archive_query_log.parsers.warc_query import add_warc_query_parser
    parser_type_strict: WarcQueryParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise UsageError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcQueryParser.init(using=config.es.client, index=config.es.index_warc_query_parsers)
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


@warc_query.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def warc_query_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_warc_query_parsers
    WarcQueryParser.init(using=config.es.client, index=config.es.index_warc_query_parsers)
    import_warc_query_parsers(config, services_path)


@parsers.group()
def warc_snippets() -> None:
    pass


CHOICES_WARC_SNIPPETS_PARSER_TYPE = [
    "xpath",
]


@warc_snippets.command("add")
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_WARC_SNIPPETS_PARSER_TYPE), required=True)
@option("--xpath", type=str)
@option("--url-xpath", type=str)
@option("--title-xpath", type=str)
@option("--text-xpath", type=str)
@pass_config
def warc_snippets_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
        xpath: str | None,
        url_xpath: str | None,
        title_xpath: str | None,
        text_xpath: str | None,
) -> None:
    from archive_query_log.parsers.warc_snippets import \
        add_warc_snippets_parser
    parser_type_strict: WarcSnippetsParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise UsageError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcSnippetsParser.init(using=config.es.client, index=config.es.index_warc_snippets_parsers)
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


@warc_snippets.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def warc_snippets_import(config: Config, services_path: Path) -> None:
    from archive_query_log.imports.yaml import import_warc_snippets_parsers
    WarcSnippetsParser.init(using=config.es.client, index=config.es.index_warc_snippets_parsers)
    import_warc_snippets_parsers(config, services_path)


@parsers.group()
def warc_direct_answers() -> None:
    pass


CHOICES_WARC_DIRECT_ANSWERS_PARSER_TYPE = [
    "xpath",
]


@warc_direct_answers.command("add")
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_WARC_DIRECT_ANSWERS_PARSER_TYPE), required=True)
@option("--xpath", type=str)
@option("--url-xpath", type=str)
@option("--text-xpath", type=str)
@pass_config
def warc_direct_answers_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
        xpath: str | None,
        url_xpath: str | None,
        text_xpath: str | None,
) -> None:
    from archive_query_log.parsers.warc_direct_answers import \
        add_warc_direct_answers_parser
    parser_type_strict: WarcDirectAnswersParserType
    if parser_type == "xpath":
        parser_type_strict = "xpath"
        if xpath is None:
            raise UsageError("No XPath given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcDirectAnswersParser.init(using=config.es.client, index=config.es.index_warc_direct_answers_parsers)
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


@parsers.group()
def warc_main_content() -> None:
    pass


CHOICES_WARC_MAIN_CONTENT_PARSER_TYPE = [
    "resiliparse",
]


@warc_main_content.command("add")
@option("--provider-id", type=str)
@option("--url-pattern-regex", type=str)
@option("--priority", type=FloatRange(min=0, min_open=False))
@option("--parser-type",
        type=Choice(CHOICES_WARC_MAIN_CONTENT_PARSER_TYPE), required=True)
@pass_config
def warc_main_content_add(
        config: Config,
        provider_id: str | None,
        url_pattern_regex: str | None,
        priority: float | None,
        parser_type: str,
) -> None:
    from archive_query_log.parsers.warc_main_content import \
        add_warc_main_content_parser
    parser_type_strict: WarcMainContentParserType
    if parser_type == "resiliparse":
        parser_type_strict = "resiliparse"
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    WarcMainContentParser.init(using=config.es.client, index=config.es.index_warc_direct_answers_parsers)
    add_warc_main_content_parser(
        config=config,
        provider_id=provider_id,
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type_strict,
    )
