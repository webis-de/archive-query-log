from pathlib import Path
from typing import Sequence, Iterable
from uuid import uuid5
from warnings import warn

from click import group, option, echo, Choice, Path as PathType, UsageError
from elasticsearch_dsl.query import Terms
from tqdm.auto import tqdm
from yaml import safe_load

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_URL_QUERY_PARSER, \
    NAMESPACE_URL_PAGE_PARSER, NAMESPACE_URL_OFFSET_PARSER
from archive_query_log.orm import Provider, UrlQueryParserType, \
    InnerProviderId, UrlQueryParser, UrlPageParserType, UrlPageParser, \
    UrlOffsetParser, UrlOffsetParserType
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now


@group()
def parsers():
    pass


@parsers.group()
def url_query():
    pass


CHOICES_URL_QUERY_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


def _add_url_query_parser(
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
    if parser_type == "query_parameter":
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment_parameter":
        if parameter is None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path_segment":
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id,
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
        parser_type,
        parameter if parameter is not None else "",
        str(segment) if segment is not None else "",
        remove_pattern_regex if remove_pattern_regex is not None else "",
        space_pattern_regex if space_pattern_regex is not None else "",
    )
    parser_id = str(uuid5(
        NAMESPACE_URL_QUERY_PARSER,
        ":".join(parser_id_components),
    ))
    provider = UrlQueryParser(
        meta={"id": parser_id},
        provider=InnerProviderId(id=provider_id),
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
        last_modified=utc_now(),
    )
    provider.save(using=config.es.client)


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
    _add_url_query_parser(
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
    UrlQueryParser.index().refresh(using=config.es.client)


@url_query.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_query_import(config: Config, services_path: Path) -> None:
    UrlQueryParser.init(using=config.es.client)

    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "query_parsers" not in service:
            continue

        query_parsers = service["query_parsers"]
        num_query_parsers = len(query_parsers)

        providers = (
            Provider.search(using=config.es.client)
            .query(Terms(domains=service["domains"]))
            .scan()
        )
        providers = safe_iter_scan(providers)
        for provider in providers:
            for k, query_parser in enumerate(query_parsers):
                if query_parser["type"] == "fragment_segment":
                    warn(UserWarning(
                        f"Service definition #{i} "
                        f"query parser #{k} is of type "
                        f"'fragment_segment', which is not supported."))
                    continue
                remove_patterns = query_parser.get("remove_patterns")
                if remove_patterns is not None:
                    remove_pattern_regex = "|".join(remove_patterns)
                else:
                    remove_pattern_regex = None
                space_patterns = query_parser.get("space_patterns")
                if space_patterns is not None:
                    space_pattern_regex = "|".join(space_patterns)
                else:
                    space_pattern_regex = None
                segment_string = query_parser.get("segment")
                if segment_string is not None:
                    segment = int(segment_string)
                else:
                    segment = None
                _add_url_query_parser(
                    config=config,
                    provider_id=provider.meta.id,
                    url_pattern_regex=query_parser.get("url_pattern"),
                    priority=num_query_parsers - k,
                    parser_type=query_parser["type"],
                    parameter=query_parser.get("parameter"),
                    segment=segment,
                    remove_pattern_regex=remove_pattern_regex,
                    space_pattern_regex=space_pattern_regex,
                )


@parsers.group()
def url_page():
    pass


CHOICES_URL_PAGE_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


def _add_url_page_parser(
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
    if parser_type == "query_parameter":
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment_parameter":
        if parameter is None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path_segment":
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id,
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
        parser_type,
        parameter if parameter is not None else "",
        str(segment) if segment is not None else "",
        remove_pattern_regex if remove_pattern_regex is not None else "",
        space_pattern_regex if space_pattern_regex is not None else "",
    )
    parser_id = str(uuid5(
        NAMESPACE_URL_PAGE_PARSER,
        ":".join(parser_id_components),
    ))
    provider = UrlPageParser(
        meta={"id": parser_id},
        provider=InnerProviderId(id=provider_id),
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
        last_modified=utc_now(),
    )
    provider.save(using=config.es.client)


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
    _add_url_page_parser(
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
    UrlPageParser.index().refresh(using=config.es.client)


@url_page.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_page_import(config: Config, services_path: Path) -> None:
    UrlPageParser.init(using=config.es.client)

    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "page_parsers" not in service:
            continue

        page_parsers = service["page_parsers"]
        num_page_parsers = len(page_parsers)

        providers = (
            Provider.search(using=config.es.client)
            .query(Terms(domains=service["domains"]))
            .scan()
        )
        providers = safe_iter_scan(providers)
        for provider in providers:
            for k, page_parser in enumerate(page_parsers):
                if page_parser["type"] == "fragment_segment":
                    warn(UserWarning(
                        f"Service definition #{i} "
                        f"page parser #{k} is of type "
                        f"'fragment_segment', which is not supported."))
                    continue
                remove_patterns = page_parser.get("remove_patterns")
                if remove_patterns is not None:
                    remove_pattern_regex = "|".join(remove_patterns)
                else:
                    remove_pattern_regex = None
                space_patterns = page_parser.get("space_patterns")
                if space_patterns is not None:
                    space_pattern_regex = "|".join(space_patterns)
                else:
                    space_pattern_regex = None
                segment_string = page_parser.get("segment")
                if segment_string is not None:
                    segment = int(segment_string)
                else:
                    segment = None
                _add_url_page_parser(
                    config=config,
                    provider_id=provider.meta.id,
                    url_pattern_regex=page_parser.get("url_pattern"),
                    priority=num_page_parsers - k,
                    parser_type=page_parser["type"],
                    parameter=page_parser.get("parameter"),
                    segment=segment,
                    remove_pattern_regex=remove_pattern_regex,
                    space_pattern_regex=space_pattern_regex,
                )


@parsers.group()
def url_offset():
    pass


CHOICES_URL_OFFSET_PARSER_TYPE = [
    "query-parameter",
    "fragment-parameter",
    "path-segment",
]


def _add_url_offset_parser(
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
    if parser_type == "query_parameter":
        if parameter is None:
            raise ValueError("No query parameter given.")
    elif parser_type == "fragment_parameter":
        if parameter is None:
            raise ValueError("No fragment parameter given.")
    elif parser_type == "path_segment":
        if segment is None:
            raise ValueError("No path segment given.")
    else:
        raise ValueError(f"Invalid parser type: {parser_type}")
    parser_id_components = (
        provider_id,
        url_pattern_regex if url_pattern_regex is not None else "",
        str(priority) if priority is not None else "",
        parser_type,
        parameter if parameter is not None else "",
        str(segment) if segment is not None else "",
        remove_pattern_regex if remove_pattern_regex is not None else "",
        space_pattern_regex if space_pattern_regex is not None else "",
    )
    parser_id = str(uuid5(
        NAMESPACE_URL_OFFSET_PARSER,
        ":".join(parser_id_components),
    ))
    provider = UrlOffsetParser(
        meta={"id": parser_id},
        provider=InnerProviderId(id=provider_id),
        url_pattern_regex=url_pattern_regex,
        priority=priority,
        parser_type=parser_type,
        parameter=parameter,
        segment=segment,
        remove_pattern_regex=remove_pattern_regex,
        space_pattern_regex=space_pattern_regex,
        last_modified=utc_now(),
    )
    provider.save(using=config.es.client)


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
    _add_url_offset_parser(
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
    UrlOffsetParser.index().refresh(using=config.es.client)


@url_offset.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@pass_config
def url_offset_import(config: Config, services_path: Path) -> None:
    UrlOffsetParser.init(using=config.es.client)

    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "offset_parsers" not in service:
            continue

        offset_parsers = service["offset_parsers"]
        num_offset_parsers = len(offset_parsers)

        providers = (
            Provider.search(using=config.es.client)
            .query(Terms(domains=service["domains"]))
            .scan()
        )
        providers = safe_iter_scan(providers)
        for provider in providers:
            for k, offset_parser in enumerate(offset_parsers):
                if offset_parser["type"] == "fragment_segment":
                    warn(UserWarning(
                        f"Service definition #{i} "
                        f"offset parser #{k} is of type "
                        f"'fragment_segment', which is not supported."))
                    continue
                remove_patterns = offset_parser.get("remove_patterns")
                if remove_patterns is not None:
                    remove_pattern_regex = "|".join(remove_patterns)
                else:
                    remove_pattern_regex = None
                space_patterns = offset_parser.get("space_patterns")
                if space_patterns is not None:
                    space_pattern_regex = "|".join(space_patterns)
                else:
                    space_pattern_regex = None
                segment_string = offset_parser.get("segment")
                if segment_string is not None:
                    segment = int(segment_string)
                else:
                    segment = None
                _add_url_offset_parser(
                    config=config,
                    provider_id=provider.meta.id,
                    url_pattern_regex=offset_parser.get("url_pattern"),
                    priority=num_offset_parsers - k,
                    parser_type=offset_parser["type"],
                    parameter=offset_parser.get("parameter"),
                    segment=segment,
                    remove_pattern_regex=remove_pattern_regex,
                    space_pattern_regex=space_pattern_regex,
                )
