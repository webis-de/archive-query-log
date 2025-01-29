from pathlib import Path
from typing import MutableMapping
from typing import Sequence, Iterable
from warnings import warn

from click import echo
from click import prompt
from diskcache import Index
from elasticsearch_dsl.query import Terms
from tqdm.auto import tqdm
from whois import whois
from whois.parser import PywhoisError
from yaml import safe_load

from archive_query_log.config import Config
from archive_query_log.orm import Provider
from archive_query_log.parsers.url_offset import add_url_offset_parser
from archive_query_log.parsers.url_page import add_url_page_parser
from archive_query_log.parsers.url_query import add_url_query_parser
from archive_query_log.parsers.warc_query import add_warc_query_parser
from archive_query_log.parsers.warc_snippets import add_warc_snippets_parser
from archive_query_log.parsers.xml import xpaths_from_css_selector, \
    text_xpath, merge_xpaths
from archive_query_log.providers import add_provider
from archive_query_log.utils.es import safe_iter_scan


def _provider_name(
        i: int,
        main_domain: str,
        provider_names: MutableMapping[str, str],
        review: bool,
) -> str | None:
    provider_name_suggest: str | None
    if main_domain in provider_names:
        if not review:
            return provider_names[main_domain]
        else:
            provider_name_suggest = provider_names[main_domain]
    else:
        try:
            main_domain_info = whois(main_domain)
        except PywhoisError:
            main_domain_info = None
        if main_domain_info is not None:
            main_org: str | list[str] | None = main_domain_info.org
            if isinstance(main_org, list):
                main_org = main_org[0]
            if main_org is not None:
                for restricted_phrase in ["redacted", "privacy",
                                          "domain protection", "not disclosed",
                                          "identity protection",
                                          "domains by proxy"]:
                    if restricted_phrase in main_org.casefold():
                        main_org = None
                        break
            if main_org is not None:
                for suffix in ["Inc", "LLC", "Ltd", "LTD", "GmbH", "AG", "S.A",
                               "SE", "Co", "Pty", "B.V", "S.L", "S.R.L",
                               "S.A.S",
                               "SAS", "AB", "&"]:
                    main_org = main_org.removesuffix(f", {suffix}.")
                    main_org = main_org.removesuffix(f", {suffix}")
                    main_org = main_org.removesuffix(f" {suffix}.")
                    main_org = main_org.removesuffix(f" {suffix}")
            provider_name_suggest = main_org
        else:
            provider_name_suggest = None
    provider_name = prompt(
        f"Please enter search provider #{i} name (https://{main_domain})",
        type=str, default=provider_name_suggest,
        show_default=provider_name_suggest != " ")
    if provider_name.strip() == "":
        return None
    provider_names[main_domain] = provider_name
    return provider_name


def import_providers(
        config: Config,
        services_path: Path,
        cache_path: Path,
        review: int | None,
        no_merge: bool,
        auto_merge: bool,
) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    provider_names: MutableMapping[str, str] = Index(str(cache_path))

    if auto_merge or no_merge:
        # noinspection PyTypeChecker
        services = tqdm(
            services,
            desc="Import providers",
            unit="provider",
        )

    num_services = len(services_list)

    ask_for_name = True
    service: dict
    for i, service in enumerate(services):
        if "domains" not in service:
            raise ValueError(f"Service definition #{i} from {services_path} "
                             f"has no domains: {service}")

        if ("query_parsers" not in service or
                len(service["query_parsers"]) == 0):
            continue

        main_domain = service["domains"][0]
        if ask_for_name:
            name = _provider_name(i, main_domain, provider_names,
                                  review is not None and review <= i)
            if name is None:
                ask_for_name = False
        else:
            name = None

        add_provider(
            config=config,
            name=name,
            description=None,
            notes=service.get("notes"),
            exclusion_reason=service.get("excluded"),
            domains=set(service["domains"]),
            url_path_prefixes=set(service["focused_url_prefixes"]),
            priority=num_services - i,
            no_merge=no_merge,
            auto_merge=auto_merge,
        )


def import_url_query_parsers(config: Config, services_path: Path) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import parsers for providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "query_parsers" not in service:
            continue

        query_parsers = service["query_parsers"]
        num_query_parsers = len(query_parsers)

        providers = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
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
                add_url_query_parser(
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


def import_url_page_parsers(config: Config, services_path: Path) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import parsers for providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "page_parsers" not in service:
            continue

        page_parsers = service["page_parsers"]
        num_page_parsers = len(page_parsers)

        providers = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
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
                add_url_page_parser(
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


def import_url_offset_parsers(config: Config, services_path: Path) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import parsers for providers",
        unit="provider",
    )
    for i, service in enumerate(services):
        if "domains" not in service or "offset_parsers" not in service:
            continue

        offset_parsers = service["offset_parsers"]
        num_offset_parsers = len(offset_parsers)

        providers = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
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
                add_url_offset_parser(
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


def import_warc_query_parsers(config: Config, services_path: Path) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import parsers for providers",
        unit="provider",
    )
    for service in services:
        if ("domains" not in service or
                "interpreted_query_parsers" not in service):
            continue

        interpreted_query_parsers = service["interpreted_query_parsers"]
        num_interpreted_query_parsers = len(interpreted_query_parsers)

        providers = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
            .query(Terms(domains=service["domains"]))
            .scan()
        )
        providers = safe_iter_scan(providers)
        for provider in providers:
            for k, interpreted_query_parser in (
                    enumerate(interpreted_query_parsers)):
                if interpreted_query_parser["type"] != "html_selector":
                    continue
                remove_patterns = (
                    interpreted_query_parser.get("remove_patterns"))
                if remove_patterns is not None:
                    remove_pattern_regex = "|".join(remove_patterns)
                else:
                    remove_pattern_regex = None
                space_patterns = interpreted_query_parser.get("space_patterns")
                if space_patterns is not None:
                    space_pattern_regex = "|".join(space_patterns)
                else:
                    space_pattern_regex = None
                query_selector = interpreted_query_parser["query_selector"]

                query_text = interpreted_query_parser.get("query_text", False)
                query_attribute = interpreted_query_parser.get(
                    "query_attribute", "value" if not query_text else None)

                query_xpaths = xpaths_from_css_selector(query_selector)
                query_xpaths = [
                    "//" +
                    text_xpath(
                        query_xpath,
                        attribute=query_attribute,
                        text=query_text,
                    )
                    for query_xpath in query_xpaths
                ]
                query_xpath = merge_xpaths(query_xpaths)

                add_warc_query_parser(
                    config=config,
                    provider_id=provider.meta.id,
                    url_pattern_regex=interpreted_query_parser.get(
                        "url_pattern"),
                    priority=num_interpreted_query_parsers - k,
                    parser_type="xpath",
                    xpath=query_xpath,
                    remove_pattern_regex=remove_pattern_regex,
                    space_pattern_regex=space_pattern_regex,
                )


def import_warc_snippets_parsers(config: Config, services_path: Path) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    # noinspection PyTypeChecker
    services = tqdm(
        services,
        desc="Import parsers for providers",
        unit="provider",
    )
    for service in services:
        if ("domains" not in service or "results_parsers" not in service):
            continue

        results_parsers = service["results_parsers"]
        num_results_parsers = len(results_parsers)

        providers = (
            Provider.search(using=config.es.client, index=config.es.index_providers)
            .query(Terms(domains=service["domains"]))
            .scan()
        )
        providers = safe_iter_scan(providers)
        for provider in providers:
            for k, results_parser in enumerate(results_parsers):
                if results_parser["type"] != "html_selector":
                    continue
                results_selector = results_parser["results_selector"]
                url_selector = results_parser.get("url_selector")
                title_selector = results_parser.get("title_selector")
                snippet_selector = results_parser.get("snippet_selector")

                results_xpaths = xpaths_from_css_selector(results_selector)
                results_xpaths = [
                    "//" + result_xpath
                    for result_xpath in results_xpaths
                ]
                results_xpath = merge_xpaths(results_xpaths)

                if url_selector is not None:
                    url_xpaths = xpaths_from_css_selector(url_selector)
                    url_xpaths = [
                        text_xpath(xpath, attribute="href")
                        for xpath in url_xpaths
                    ]
                    url_xpath = merge_xpaths(url_xpaths)
                else:
                    url_xpath = None

                if title_selector is not None:
                    title_xpaths = xpaths_from_css_selector(title_selector)
                    title_xpaths = [
                        text_xpath(xpath, text=True)
                        for xpath in title_xpaths
                    ]
                    title_xpath = merge_xpaths(title_xpaths)
                else:
                    title_xpath = None

                if snippet_selector is not None:
                    snippet_xpaths = xpaths_from_css_selector(snippet_selector)
                    snippet_xpaths = [
                        text_xpath(xpath, text=True)
                        for xpath in snippet_xpaths
                    ]
                    snippet_xpath = merge_xpaths(snippet_xpaths)
                else:
                    snippet_xpath = None

                add_warc_snippets_parser(
                    config=config,
                    provider_id=provider.meta.id,
                    url_pattern_regex=results_parser.get("url_pattern"),
                    priority=num_results_parsers - k,
                    parser_type="xpath",
                    xpath=results_xpath,
                    url_xpath=url_xpath,
                    title_xpath=title_xpath,
                    text_xpath=snippet_xpath,
                )
