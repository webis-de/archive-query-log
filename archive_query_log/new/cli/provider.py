from datetime import datetime
from uuid import uuid5

from click import group, argument, option, echo, Choice

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
