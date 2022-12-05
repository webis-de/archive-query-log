from typing import Mapping, Sequence

from web_archive_query_log.config_model import Source
from web_archive_query_log.queries.parse import QueryParameter, PathSuffix, \
    FragmentParameter
from web_archive_query_log.results.bing import BingSearchResultsParser
from web_archive_query_log.sites import WIKIPEDIA_SITES, AMAZON_SITES, \
    EBAY_SITES, STACKEXCHANGE_SITES
from web_archive_query_log.create_source import get_service_names, create_sources

# Load all services that have parsers and create the services for them
service_names = get_service_names()
SOURCES: Mapping[str, Sequence[Source]] = create_sources(service_names)
