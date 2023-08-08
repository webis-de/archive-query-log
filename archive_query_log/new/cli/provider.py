from datetime import datetime
from pathlib import Path
from typing import Sequence, MutableMapping
from uuid import uuid5

from click import group, argument, option, echo, Choice, Path as PathType, \
    prompt
from diskcache import Index
from elasticsearch.helpers import parallel_bulk
from tqdm.auto import tqdm
from yaml import safe_load
from whois import whois

from archive_query_log import DATA_DIRECTORY_PATH
from archive_query_log.new.cli.validation import validate_domains
from archive_query_log.new.config import CONFIG
from archive_query_log.new.namespaces import NAMESPACE_PROVIDER
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


@provider.command()
@argument("name", type=str)
@option("-d", "--description", type=str)
@option("-w", "--website-type", type=Choice(CHOICES_WEBSITE_TYPE))
@option("-c", "--content-type", type=Choice(CHOICES_CONTENT_TYPE)
        )
@option("--input-field/--no-input-field", "has_input_field",
        type=bool)
@option("--search-form/--no-search-form", "has_search_form",
        type=bool)
@option("--search-div/--no-search-div", "has_search_div",
        type=bool)
@option("-D", "--domain", "domains", type=str, multiple=True,
        required=True, callback=validate_domains, metavar="DOMAIN")
@option("-u", "--url-path-prefix", "url_path_prefixes", type=str,
        multiple=True, required=True, metavar="PREFIX")
def add(
        name: str,
        description: str,
        website_type: str,
        content_type: str,
        has_input_field: bool,
        has_search_form: bool,
        has_search_div: bool,
        domains: list[str],
        url_path_prefixes: list[str],
) -> None:
    create_index(CONFIG.es_index_providers)
    provider_id = str(uuid5(NAMESPACE_PROVIDER, name))
    document = {
        "id": provider_id,
        "name": name,
        "description": description,
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
    echo(f"Add provider {provider_id}.")
    CONFIG.es.index(
        index=CONFIG.es_index_providers.name,
        id=provider_id,
        document=document,
    )
    echo(f"Refresh index {CONFIG.es_index_providers.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_providers.name)
    echo("Done.")


def _provider_name(main_domain: str,
                   provider_names: MutableMapping[str, str],
                   review: bool) -> str:
    if main_domain in provider_names:
        if not review:
            return provider_names[main_domain]
        else:
            provider_name_suggest = provider_names[main_domain]
    else:
        main_domain_info = whois(main_domain)
        main_org: str | None = main_domain_info.org
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
                           "SE", "Co", "Pty", "B.V", "S.L", "S.R.L", "S.A.S",
                           "SAS", "AB", "&"]:
                main_org = main_org.removesuffix(f", {suffix}.")
                main_org = main_org.removesuffix(f", {suffix}")
                main_org = main_org.removesuffix(f" {suffix}.")
                main_org = main_org.removesuffix(f" {suffix}")
        provider_name_suggest = main_org
    provider_name = prompt(
        f"Please enter the search provider name for https://{main_domain}",
        type=str, default=provider_name_suggest)
    if provider_name.strip() == "-":
        return
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
@option("--review/--no-review", "review", type=bool,
        default=False)
def import_providers(services_path: Path, cache_path: Path,
                     review: bool) -> None:
    echo("Load providers from services file.")
    with services_path.open("r") as file:
        services: Sequence[dict] = safe_load(file)
    echo(f"Found {len(services)} service definitions.")

    # noinspection PyTypeChecker
    # services = tqdm(services, desc="Convert services")

    provider_names: MutableMapping[str, str] = Index(str(cache_path))

    documents = []
    for i, service in enumerate(services):
        main_domain = service["alexa_domain"]
        print(i)
        provider_name = _provider_name(main_domain, provider_names, review)

        # document = {
        #     "id": provider_id,
        #     "name": name,
        #     "description": description,
        #     "website_type": website_type,
        #     "content_type": content_type,
        #     "interface_annotations": {
        #         "has_input_field": has_input_field,
        #         "has_search_form": has_search_form,
        #         "has_search_div": has_search_div,
        #     },
        #     "domains": list(domains),
        #     "url_path_prefixes": list(url_path_prefixes),
        #     "last_modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        # }
        # documents.append(document)

    raise NotImplementedError()

    create_index(CONFIG.es_index_providers)
    operations = (
        {
            "_op_type": "create",
            "_index": CONFIG.es_index_providers.name,
            "_id": document["id"],
            **document,
        }
        for document in documents
    )
    has_errors = False
    # noinspection PyTypeChecker
    for success, info in tqdm(
            parallel_bulk(
                CONFIG.es,
                operations,
                ignore_status=[409],
            ),
            desc="Adding providers",
            total=len(documents),
            unit="capture",
    ):
        if not success:
            if info["create"]["status"] != 409:
                echo("Indexing error:", info, err=True)
                has_errors = True
    if has_errors:
        raise RuntimeError("Indexing errors occurred.")

    echo(f"Refresh index {CONFIG.es_index_providers.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_providers.name)

    echo("Done.")
