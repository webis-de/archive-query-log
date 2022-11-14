from typing import Mapping, Sequence

from internet_archive_query_log.config_model import Source
from internet_archive_query_log.parse import QueryParameter, PathSuffix, \
    FragmentParameter, BingSerpParser
from internet_archive_query_log.sites import WIKIPEDIA_SITES, AMAZON_SITES, \
    EBAY_SITES, STACKEXCHANGE_SITES

SOURCES: Mapping[str, Sequence[Source]] = {
    "google": [
        # TODO Test
        # TODO Add all global pages
        #  (see https://www.google.com/supported_domains).
        Source(
            "google.com/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
        # Note that images.google.com and shopping.google.com
        # all redirects to google.com.
        Source(
            "news.google.com/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            "play.google.com/store/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            "photos.google.com/search/",
            PathSuffix("search/"),
            serp_parsers=[],
        ),
        Source(
            "podcasts.google.com/search/",
            PathSuffix("search/"),
            serp_parsers=[],
        ),
        Source(
            "google.com/finance/quote/",
            PathSuffix("finance/quote/"),
            serp_parsers=[],
        ),
        Source(
            "google.com/maps/search/",
            PathSuffix("maps/search/", single_segment=True),
            serp_parsers=[],
        ),
        Source(
            "google.de/maps/search/",
            PathSuffix("maps/search/", single_segment=True),
            serp_parsers=[],
        ),
        Source(
            "earth.google.com/web/search/",
            PathSuffix("web/search/", single_segment=True),
            serp_parsers=[],
        ),
    ],
    "bing": [
        # TODO Add all global pages.
        Source(
            "bing.com/search?",
            QueryParameter("q"),
            serp_parsers=[BingSerpParser()],
        ),
    ],
    "yahoo": [
        # TODO Test
        # TODO Add all global pages.
        Source(
            "yahoo.com/search?",
            QueryParameter("p"),
            serp_parsers=[],
        ),
        Source(
            "search.yahoo.com/search?",
            QueryParameter("p"),
            serp_parsers=[],
        ),
        Source(
            "de.search.yahoo.com/search?",
            QueryParameter("p"),
            serp_parsers=[],
        ),
    ],
    "duckduckgo": [
        Source(
            "duckduckgo.com/?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "internet-archive": [
        Source(
            "archive.org/search.php?",
            QueryParameter("query"),
            serp_parsers=[],
        ),
    ],
    "wikipedia": [
        Source(
            f"{site}/w/index.php?",
            QueryParameter("search"),
            serp_parsers=[],
        )
        for site in WIKIPEDIA_SITES
    ],
    "amazon": [
        Source(
            f"{site}/s?",
            QueryParameter("k"),
            serp_parsers=[],
        )
        for site in AMAZON_SITES
    ],
    "ebay": [
                Source(
                    f"{site}/?",
                    QueryParameter("_nkw"),
                    serp_parsers=[],
                )
                for site in EBAY_SITES
            ] + [

                Source(
                    f"{site}/sch/i.html?",
                    QueryParameter("_nkw"),
                    serp_parsers=[],
                )
                for site in EBAY_SITES
            ],
    "lastfm": [
        Source(
            "last.fm/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "twitter": [
        Source(
            "twitter.com/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "facebook": [
        Source(
            "facebook.com/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "pubmed": [
        Source(
            "pubmed.gov/?",
            QueryParameter("term"),
            serp_parsers=[],
        ),
        Source(
            "pubmed.ncbi.nlm.nih.gov/?",
            QueryParameter("term"),
            serp_parsers=[],
        ),
    ],
    "google-scholar": [
        Source(
            "scholar.google.com/scholar?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "dblp": [
        Source(
            "dblp.org/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            "dblp.uni-trier.de/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "github": [
        Source(
            "github.com/search?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "stackexchange": [
        Source(f"{site}/search?",
               QueryParameter("q"),
               serp_parsers=[],
               )
        for site in STACKEXCHANGE_SITES
    ],
    "chatnoir": [
        Source(
            "chatnoir.eu/?",
            QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "argsme": [
        Source(
            "args.me/?query=",
            QueryParameter("query"),
            serp_parsers=[],
        ),
    ],
    # No archived queries found for:
    "netspeak": [
        Source(
            "netspeak.org/?q=",
            FragmentParameter("q"),
            serp_parsers=[],
        ),
    ],
    # TODO Add more search engines
    #  - https://en.wikipedia.org/wiki/List_of_search_engines).
    #  - https://www.ebay-kleinanzeigen.de/
    #  - https://www.youtube.com/
    #  - https://www.semanticscholar.org/
    #  - https://webis.de/publications.html
}
