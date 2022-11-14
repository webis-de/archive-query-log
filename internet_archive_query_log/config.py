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
            url_prefix="google.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
        # Note that images.google.com and shopping.google.com
        # all redirects to google.com.
        Source(
            url_prefix="news.google.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="play.google.com/store/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="photos.google.com/search/",
            query_parser=PathSuffix("search/"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="podcasts.google.com/search/",
            query_parser=PathSuffix("search/"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="google.com/finance/quote/",
            query_parser=PathSuffix("finance/quote/"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="google.com/maps/search/",
            query_parser=PathSuffix("maps/search/", single_segment=True),
            serp_parsers=[],
        ),
        Source(
            url_prefix="google.de/maps/search/",
            query_parser=PathSuffix("maps/search/", single_segment=True),
            serp_parsers=[],
        ),
        Source(
            url_prefix="earth.google.com/web/search/",
            query_parser=PathSuffix("web/search/", single_segment=True),
            serp_parsers=[],
        ),
    ],
    "bing": [
        # TODO Add all global pages.
        Source(
            url_prefix="bing.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[BingSerpParser()],
        ),
    ],
    "ecosia": [
        Source(
            url_prefix="ecosia.org/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="ecosia.org/search?method=index&",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        )
    ],
    "yahoo": [
        # TODO Test
        # TODO Add all global pages.
        Source(
            url_prefix="yahoo.com/search?",
            query_parser=QueryParameter("p"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="search.yahoo.com/search?",
            query_parser=QueryParameter("p"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="de.search.yahoo.com/search?",
            query_parser=QueryParameter("p"),
            serp_parsers=[],
        ),
    ],
    "duckduckgo": [
        Source(
            url_prefix="duckduckgo.com/?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "internet-archive": [
        Source(
            url_prefix="archive.org/search.php?",
            query_parser=QueryParameter("query"),
            serp_parsers=[],
        ),
    ],
    "wikipedia": [
        Source(
            url_prefix=f"{site}/w/index.php?",
            query_parser=QueryParameter("search"),
            serp_parsers=[],
        )
        for site in WIKIPEDIA_SITES
    ],
    "amazon": [
        Source(
            url_prefix=f"{site}/s?",
            query_parser=QueryParameter("k"),
            serp_parsers=[],
        )
        for site in AMAZON_SITES
    ],
    "ebay": [
                Source(
                    url_prefix=f"{site}/?",
                    query_parser=QueryParameter("_nkw"),
                    serp_parsers=[],
                )
                for site in EBAY_SITES
            ] + [
                Source(
                    url_prefix=f"{site}/sch/i.html?",
                    query_parser=QueryParameter("_nkw"),
                    serp_parsers=[],
                )
                for site in EBAY_SITES
            ],
    "lastfm": [
        Source(
            url_prefix="last.fm/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "twitter": [
        Source(
            url_prefix="twitter.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "facebook": [
        Source(
            url_prefix="facebook.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "pubmed": [
        Source(
            url_prefix="pubmed.gov/?",
            query_parser=QueryParameter("term"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="pubmed.ncbi.nlm.nih.gov/?",
            query_parser=QueryParameter("term"),
            serp_parsers=[],
        ),
    ],
    "google-scholar": [
        Source(
            url_prefix="scholar.google.com/scholar?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "dblp": [
        Source(
            url_prefix="dblp.org/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
        Source(
            url_prefix="dblp.uni-trier.de/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "github": [
        Source(
            url_prefix="github.com/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "stackexchange": [
        Source(
            url_prefix=f"{site}/search?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        )
        for site in STACKEXCHANGE_SITES
    ],
    "chatnoir": [
        Source(
            url_prefix="chatnoir.eu/?",
            query_parser=QueryParameter("q"),
            serp_parsers=[],
        ),
    ],
    "argsme": [
        Source(
            url_prefix="args.me/?query=",
            query_parser=QueryParameter("query"),
            serp_parsers=[],
        ),
    ],
    # No archived queries found for:
    "netspeak": [
        Source(
            url_prefix="netspeak.org/?q=",
            query_parser=FragmentParameter("q"),
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
