from datetime import datetime
from pathlib import Path
from typing import Sequence, MutableMapping
from uuid import uuid4

from click import group, option, echo, Choice, Path as PathType, prompt
from diskcache import Index
from whois import whois
from whois.parser import PywhoisError
from yaml import safe_load

from archive_query_log import DATA_DIRECTORY_PATH
from archive_query_log.new.cli.validation import validate_split_domains
from archive_query_log.new.config import CONFIG
from archive_query_log.new.utils.es import create_index


@group()
def provider():
    pass


CHOICES_WEBSITE_TYPE = [
    "blog",
    "career-jobs",
    "child-safe-search",
    "comparison",
    "corporate",
    "database",
    "dating",
    "download",
    "e-commerce",
    "education",
    "forum",
    "gambling",
    "gaming",
    "governmental",
    "manga-anime",
    "media-sharing",
    "news-and-boulevard",
    "ngo",
    "political",
    "pornography",
    'question-and-answer',
    "religious",
    "review",
    "search-engine",
    "service",
    "social-media",
    "spam-malware",
    "sports",
    "streaming",
    "torrent",
    "web-portal",
    "wiki",
]
CHOICES_CONTENT_TYPE = [
    "accomodation",
    "argument",
    "article",
    "audio",
    "code",
    "comic",
    "design",
    "domain",
    "e-mail",
    "flight",
    "font",
    "game",
    "image",
    "job-listing",
    "multicontent",
    "post",
    "presentation",
    "product",
    "real-estate-listing",
    "recipe",
    "scientific-content",
    "software",
    "text-document",
    "video",
    "website",
]


def _add_provider(
        name: str | None,
        description: str | None,
        notes: str | None,
        exclusion_reason: str | None,
        website_type: str | None,
        content_type: str | None,
        has_input_field: bool | None,
        has_search_form: bool | None,
        has_search_div: bool | None,
        domains: set[str],
        url_path_prefixes: set[str],
        no_merge: bool = False,
        auto_merge: bool = False,
) -> None:
    existing_provider_result = CONFIG.es.search(
        index=CONFIG.es_index_providers.name,
        query={
            "terms": {
                "domains.keyword": list(domains)
            }
        }
    )

    existing_provider_hits = existing_provider_result["hits"]
    if existing_provider_hits["total"]["value"] > 0:
        existing_provider = existing_provider_hits["hits"][0]["_source"]
        existing_provider_domains = set(existing_provider["domains"])
        domains_intersection = existing_provider_domains & domains
        echo(f"Provider {existing_provider['id']} already exists with "
             f"conflicting domains: {', '.join(domains_intersection)}")
        if no_merge:
            return
        if auto_merge:
            should_merge = True
        else:
            add_to_existing = prompt("Merge with existing provider? "
                                     "[y/N]", type=str, default="n",
                                     show_default=False)
            should_merge = add_to_existing.lower() == "y"
        if not should_merge:
            return

        provider_id = existing_provider["id"]
        interface_annotations = existing_provider["interface_annotations"]
        if name is None:
            name = existing_provider["name"]
        if description is None:
            description = existing_provider["description"]
        if notes is None:
            notes = existing_provider["notes"]
        if exclusion_reason is None:
            exclusion_reason = existing_provider["exclusion_reason"]
        if website_type is None:
            website_type = existing_provider["website_type"]
        if content_type is None:
            content_type = existing_provider["content_type"]
        if has_input_field is None:
            has_input_field = interface_annotations["has_input_field"]
        if has_search_form is None:
            has_search_form = interface_annotations["has_search_form"]
        if has_search_div is None:
            has_search_div = interface_annotations["has_search_div"]
        domains = domains | existing_provider_domains
        url_path_prefixes = (
                url_path_prefixes | existing_provider["url_path_prefixes"])
        print(f"Update provider {provider_id}.")
    else:
        provider_id = str(uuid4())
        print(f"Add new provider {provider_id}.")

    document = {
        "id": provider_id,
        "name": name,
        "description": description,
        "notes": notes,
        "exclusion_reason": exclusion_reason,
        "website_type": website_type,
        "content_type": content_type,
        "interface_annotations": {
            "has_input_field": has_input_field,
            "has_search_form": has_search_form,
            "has_search_div": has_search_div,
        },
        "domains": list(domains),
        "url_path_prefixes": list(url_path_prefixes),
        "last_modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    CONFIG.es.index(
        index=CONFIG.es_index_providers.name,
        id=provider_id,
        document=document,
    )


@provider.command()
@option("--name", type=str)
@option("--description", type=str)
@option("--notes", type=str)
@option("--exclusion-reason", "--exclusion", type=str)
@option("--website-type", type=Choice(CHOICES_WEBSITE_TYPE))
@option("--content-type", type=Choice(CHOICES_CONTENT_TYPE))
@option("--input-field/--no-input-field", "has_input_field",
        type=bool)
@option("--search-form/--no-search-form", "has_search_form",
        type=bool)
@option("--search-div/--no-search-div", "has_search_div",
        type=bool)
@option("--domains", "--domain", type=str, multiple=True,
        required=True, callback=validate_split_domains)
@option("--url-path-prefixes", "--url-path-prefix", type=str,
        multiple=True, required=True, metavar="PREFIXES")
def add(
        name: str | None,
        description: str | None,
        notes: str | None,
        exclusion_reason: str | None,
        website_type: str | None,
        content_type: str | None,
        has_input_field: bool | None,
        has_search_form: bool | None,
        has_search_div: bool | None,
        domains: list[str],
        url_path_prefixes: list[str],
) -> None:
    create_index(CONFIG.es_index_providers)
    _add_provider(
        name=name,
        description=description,
        notes=notes,
        exclusion_reason=exclusion_reason,
        website_type=website_type,
        content_type=content_type,
        has_input_field=has_input_field,
        has_search_form=has_search_form,
        has_search_div=has_search_div,
        domains=set(domains),
        url_path_prefixes=set(url_path_prefixes),
    )
    echo(f"Refresh index {CONFIG.es_index_providers.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_providers.name)
    echo("Done.")


def _provider_name(i: int, main_domain: str,
                   provider_names: MutableMapping[str, str],
                   review: bool) -> str | None:
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
            if type(main_org) is list:
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


@provider.command()
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=DATA_DIRECTORY_PATH / "selected-services.yaml")
@option("-c", "--cache-dir", "cache_path",
        type=PathType(path_type=Path, exists=False, file_okay=False,
                      dir_okay=True, readable=True, writable=True,
                      resolve_path=True, allow_dash=False),
        default=DATA_DIRECTORY_PATH / "provider-names")
@option("--review", type=int)
@option("--no-merge", is_flag=True, default=False, type=bool)
@option("--auto-merge", is_flag=True, default=False, type=bool)
def import_providers(services_path: Path, cache_path: Path,
                     review: int | None, no_merge: bool,
                     auto_merge: bool) -> None:
    create_index(CONFIG.es_index_providers)

    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services)} service definitions.")

    provider_names: MutableMapping[str, str] = Index(str(cache_path))

    ask_for_name = True
    for i, service in enumerate(services):
        if "domains" not in service:
            raise ValueError(f"Service #{i} from {services_path} "
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

        description = None
        notes = service.get("notes", None)
        exclusion_reason = service.get("excluded", None)
        website_type = None
        content_type = None
        has_input_field = None
        has_search_form = None
        has_search_div = None
        domains = set(service["domains"])
        url_path_prefixes = set(service["focused_url_prefixes"])

        _add_provider(
            name=name,
            description=description,
            notes=notes,
            exclusion_reason=exclusion_reason,
            website_type=website_type,
            content_type=content_type,
            has_input_field=has_input_field,
            has_search_form=has_search_form,
            has_search_div=has_search_div,
            domains=domains,
            url_path_prefixes=url_path_prefixes,
            no_merge=no_merge,
            auto_merge=auto_merge,
        )
        CONFIG.es.indices.refresh(index=CONFIG.es_index_providers.name)

    echo("Done.")
