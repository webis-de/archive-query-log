from pathlib import Path

from click import group, option, Choice, Path as PathType

from archive_query_log.cli.util import validate_split_domains, pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Provider


@group()
def providers() -> None:
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
    "accommodation",
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
    "multi-content",
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


@providers.command()
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
@pass_config
def add(
        config: Config,
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
    from archive_query_log.providers import add_provider
    Provider.init(using=config.es.client)
    add_provider(
        config=config,
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


@providers.command("import")
@option("-s", "--services-file", "services_path",
        type=PathType(path_type=Path, exists=True, file_okay=True,
                      dir_okay=False, readable=True, resolve_path=True,
                      allow_dash=False),
        default=Path("data") / "selected-services.yaml")
@option("-c", "--cache-dir", "cache_path",
        type=PathType(path_type=Path, exists=False, file_okay=False,
                      dir_okay=True, readable=True, writable=True,
                      resolve_path=True, allow_dash=False),
        default=Path("data") / "cache" / "provider-names")
@option("--review", type=int)
@option("--no-merge", is_flag=True, default=False, type=bool)
@option("--auto-merge", is_flag=True, default=False, type=bool)
@pass_config
def import_(
        config: Config,
        services_path: Path,
        cache_path: Path,
        review: int | None,
        no_merge: bool,
        auto_merge: bool,
) -> None:
    from archive_query_log.imports.yaml import import_providers
    Provider.init(using=config.es.client)
    import_providers(
        config=config,
        services_path=services_path,
        cache_path=cache_path,
        review=review,
        no_merge=no_merge,
        auto_merge=auto_merge,
    )
