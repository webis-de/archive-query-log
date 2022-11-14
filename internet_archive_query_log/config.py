from typing import Mapping, Sequence

from internet_archive_query_log.config_model import QuerySource
from internet_archive_query_log.parse import QueryParameter, PathSuffix, \
    FragmentParameter
from internet_archive_query_log.sites import WIKIPEDIA_SITES, AMAZON_SITES, \
    EBAY_SITES, STACKEXCHANGE_SITES

SOURCES: Mapping[str, Sequence[QuerySource]] = {
    "google": [
        # TODO Test
        # TODO Add all global pages
        #  (see https://www.google.com/supported_domains).
        QuerySource(
            "google.com/search?",
            QueryParameter("q"),
        ),
        # Note that images.google.com and shopping.google.com
        # all redirects to google.com.
        QuerySource(
            "news.google.com/search?",
            QueryParameter("q"),
        ),
        QuerySource(
            "play.google.com/store/search?",
            QueryParameter("q"),
        ),
        QuerySource(
            "photos.google.com/search/", PathSuffix("search/"),
        ),
        QuerySource(
            "podcasts.google.com/search/", PathSuffix("search/"),
        ),
        QuerySource(
            "google.com/finance/quote/",
            PathSuffix("finance/quote/"),
        ),
        QuerySource(
            "google.com/maps/search/",
            PathSuffix("maps/search/", single_segment=True),
        ),
        QuerySource(
            "google.de/maps/search/",
            PathSuffix("maps/search/", single_segment=True),
        ),
        QuerySource(
            "earth.google.com/web/search/",
            PathSuffix("web/search/", single_segment=True),
        ),
    ],
    "bing": [
        # TODO Add all global pages.
        QuerySource(
            "bing.com/search?",
            QueryParameter("q"),
        ),
    ],
    "yahoo": [
        # TODO Test
        # TODO Add all global pages.
        QuerySource(
            "yahoo.com/search?",
            QueryParameter("p"),
        ),
        QuerySource(
            "search.yahoo.com/search?",
            QueryParameter("p"),
        ),
        QuerySource(
            "de.search.yahoo.com/search?",
            QueryParameter("p"),
        ),
    ],
    "duckduckgo": [
        QuerySource(
            "duckduckgo.com/?",
            QueryParameter("q"),
        ),
    ],
    "internet-archive": [
        QuerySource(
            "archive.org/search.php?",
            QueryParameter("query"),
        ),
    ],
    "wikipedia": [
        QuerySource(
            f"{site}/w/index.php?",
            QueryParameter("search"),
        )
        for site in WIKIPEDIA_SITES
    ],
    "amazon": [
        QuerySource(f"{site}/s?",
                    QueryParameter("k"),
                    )
        for site in AMAZON_SITES
    ],
    "ebay": [
                QuerySource(f"{site}/?",
                            QueryParameter("_nkw"),
                            )
                for site in EBAY_SITES
            ] + [

                QuerySource(f"{site}/sch/i.html?",
                            QueryParameter("_nkw"),
                            )
                for site in EBAY_SITES
            ],
    "lastfm": [
        QuerySource(
            "last.fm/search?",
            QueryParameter("q"),
        ),
    ],
    "twitter": [
        QuerySource(
            "twitter.com/search?",
            QueryParameter("q"),
        ),
    ],
    "facebook": [
        QuerySource(
            "facebook.com/search?",
            QueryParameter("q"),
        ),
    ],
    "pubmed": [
        QuerySource(
            "pubmed.gov/?",
            QueryParameter("term"),
        ),
        QuerySource(
            "pubmed.ncbi.nlm.nih.gov/?",
            QueryParameter("term"),
        ),
    ],
    "google-scholar": [
        QuerySource(
            "scholar.google.com/scholar?",
            QueryParameter("q"),
        ),
    ],
    "dblp": [
        QuerySource(
            "dblp.org/search?",
            QueryParameter("q"),
        ),
        QuerySource(
            "dblp.uni-trier.de/search?",
            QueryParameter("q"),
        ),
    ],
    "github": [
        QuerySource(
            "github.com/search?",
            QueryParameter("q"),
        ),
    ],
    "stackexchange": [
        QuerySource(f"{site}/search?",
                    QueryParameter("q"),
                    )
        for site in STACKEXCHANGE_SITES
    ],
    "chatnoir": [
        QuerySource(
            "chatnoir.eu/?",
            QueryParameter("q"),
        ),
    ],
    "argsme": [
        QuerySource(
            "args.me/?query=",
            QueryParameter("query"),
        ),
    ],
    # No archived queries found for:
    "netspeak": [
        QuerySource(
            "netspeak.org/?q=",
            FragmentParameter("q"),
        ),
    ],
    # TODO Add more search engines
    #  - https://en.wikipedia.org/wiki/List_of_search_engines).
    #  - https://www.ebay-kleinanzeigen.de/
    #  - https://www.youtube.com/
    #  - https://www.semanticscholar.org/
    #  - https://webis.de/publications.html
}
