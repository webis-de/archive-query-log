from pathlib import Path
from typing import Mapping

from click import group, argument, Choice, Path as PathParam, option, BOOL

from internet_archive_query_log import DATA_DIRECTORY_PATH, \
    CDX_API_URL
from internet_archive_query_log.config import Config, QuerySource
from internet_archive_query_log.parse import QueryParameter, FragmentParameter
from internet_archive_query_log.queries import InternetArchiveQueries
from internet_archive_query_log.util import URL

_CONFIGS: Mapping[str, Config] = {
    "google": Config(
        query_sources=(
            # TODO Add all global pages.
            QuerySource("google.com/search?", QueryParameter("q")),
        )
    ),
    "bing": Config(
        query_sources=(
            # TODO Add all global pages.
            QuerySource("bing.com/search?", QueryParameter("q")),
        )
    ),
    "yahoo": Config(
        query_sources=(
            # TODO Add all global pages.
            QuerySource("yahoo.com/search?", QueryParameter("p")),
            QuerySource("search.yahoo.com/search?", QueryParameter("p")),
            # QuerySource("en.search.yahoo.com/search?", QueryParameter("p")),
            QuerySource("de.search.yahoo.com/search?", QueryParameter("p")),
        )
    ),
    "duckduckgo": Config(
        query_sources=(
            QuerySource("duckduckgo.com/?", QueryParameter("q")),
        )
    ),
    "wikipedia": Config(
        query_sources=(
            # TODO Add all global pages.
            QuerySource(
                "en.wikipedia.org/w/index.php?",
                QueryParameter("search"),
            ),
            QuerySource(
                "de.wikipedia.org/w/index.php?",
                QueryParameter("search"),
            ),
        )
    ),
    "amazon": Config(
        query_sources=(
            # TODO Add all global pages.
            QuerySource("amazon.com/s?", QueryParameter("k")),
            QuerySource("amazon.de/s?", QueryParameter("k")),
        )
    ),
    "ebay": Config(
        query_sources=(
            # TODO Are there global pages?
            QuerySource("ebay.com/?", QueryParameter("_nkw")),
            QuerySource("ebay.com/sch/i.html?", QueryParameter("_nkw")),
        )
    ),
    "lastfm": Config(
        query_sources=(
            QuerySource("last.fm/search?", QueryParameter("q")),
        )
    ),
    "twitter": Config(
        query_sources=(
            QuerySource("twitter.com/search?", QueryParameter("q")),
        )
    ),
    "facebook": Config(
        query_sources=(
            QuerySource("facebook.com/search/?", QueryParameter("q")),
            QuerySource("facebook.com/search?", QueryParameter("q")),
            QuerySource("facebook.com/search/top/?", QueryParameter("q")),
            QuerySource("facebook.com/search/top?", QueryParameter("q")),
            QuerySource("facebook.com/search/posts/?", QueryParameter("q")),
            QuerySource("facebook.com/search/posts?", QueryParameter("q")),
            QuerySource("facebook.com/search/people/?", QueryParameter("q")),
            QuerySource("facebook.com/search/people?", QueryParameter("q")),
            QuerySource("facebook.com/search/photos/?", QueryParameter("q")),
            QuerySource("facebook.com/search/photos?", QueryParameter("q")),
            QuerySource("facebook.com/search/videos/?", QueryParameter("q")),
            QuerySource("facebook.com/search/videos?", QueryParameter("q")),
            QuerySource("facebook.com/search/pages/?", QueryParameter("q")),
            QuerySource("facebook.com/search/pages?", QueryParameter("q")),
            QuerySource("facebook.com/search/places/?", QueryParameter("q")),
            QuerySource("facebook.com/search/places?", QueryParameter("q")),
            QuerySource("facebook.com/search/groups/?", QueryParameter("q")),
            QuerySource("facebook.com/search/groups?", QueryParameter("q")),
            QuerySource("facebook.com/search/events/?", QueryParameter("q")),
            QuerySource("facebook.com/search/events?", QueryParameter("q")),
        )
    ),
    "pubmed": Config(
        query_sources=(
            QuerySource("pubmed.gov/?", QueryParameter("term")),
            QuerySource("pubmed.ncbi.nlm.nih.gov/?", QueryParameter("term")),
        )
    ),
    "google-scholar": Config(
        query_sources=(
            QuerySource("scholar.google.com/scholar?", QueryParameter("q")),
        )
    ),
    "dblp": Config(
        query_sources=(
            QuerySource("dblp.org/search?", QueryParameter("q")),
            QuerySource("dblp.uni-trier.de/search?", QueryParameter("q")),
        )
    ),
    "github": Config(
        query_sources=(
            QuerySource("github.com/search?", QueryParameter("q")),
            QuerySource("github.com/search/?", QueryParameter("q")),
        )
    ),
    "stackexchange": Config(
        query_sources=(
            # TODO Add other sites (see https://stackexchange.com/sites).
            QuerySource("stackoverflow.com/search?", QueryParameter("q")),
            QuerySource("serverfault.com/search?", QueryParameter("q")),
        )
    ),
    "chatnoir": Config(
        query_sources=(
            QuerySource("chatnoir.eu/?", QueryParameter("q")),
        )
    ),
    "argsme": Config(
        query_sources=(
            QuerySource("args.me/search.html?", QueryParameter("query")),
        )
    ),
    "netspeak": Config(
        query_sources=(
            QuerySource("netspeak.org/#", FragmentParameter("q")),
        )
    ),
    # TODO Add more search engines
    #  (see https://en.wikipedia.org/wiki/List_of_search_engines).
}


@group()
def internet_archive_query_log():
    pass


@internet_archive_query_log.command("fetch-queries")
@argument(
    "search-engine",
    type=Choice(sorted(_CONFIGS.keys()), case_sensitive=False),
)
@option(
    "-d", "--data-dir",
    type=PathParam(
        exists=True,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH
)
@option(
    "-u", "--api-url", "--cdx-api-url",
    type=URL,
    default=CDX_API_URL,
)
@option(
    "-n", "--num-pages",
    is_flag=True,
    type=BOOL,
    default=False,
)
def fetch_queries(
        search_engine: str,
        data_dir: Path,
        api_url: str,
        num_pages: bool
) -> None:
    config = _CONFIGS[search_engine]
    for source in config.query_sources:
        queries = InternetArchiveQueries(
            url_prefix=source.url_prefix,
            parser=source.parser,
            data_directory_path=data_dir,
            cdx_api_url=api_url,
        )
        if num_pages:
            print(f"{source.url_prefix}: {queries.num_pages} pages")
            continue
        queries.fetch()


if __name__ == "__main__":
    internet_archive_query_log()
