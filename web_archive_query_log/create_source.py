import pandas as pd
from ast import literal_eval
from typing import Mapping, Sequence
from pathlib import Path
from web_archive_query_log.config_model import Source
from web_archive_query_log.queries.parse import QueryParameter, FragmentParameter, PathSuffix, QueryParser

# Constants
DOMAIN_DF = pd.read_csv(str(Path("web_archive_query_log/services/domains.csv").resolve()), sep=";", low_memory=False)
URL_DF = pd.read_csv(str(Path("web_archive_query_log/services/url_prefixes.csv").resolve()), sep=";")
PARSER_DF = pd.read_csv(str(Path("web_archive_query_log/services/query_parsers.csv").resolve()), sep=";")
PARSER_MAP = {"qp": QueryParameter,
             "fp": FragmentParameter,
             "ps": PathSuffix}



def create_sources(service_names: Sequence[str]) -> Mapping[str, Sequence[Source]]:
    map = {}
    for name in service_names:
        map[name] = get_service_sources(name)
    return map

def get_service_sources(service_name='google') -> Sequence[Source]:
    """
    Create sources for all domain and url_prefix/parser combinations for one service
    :param service_name:    Name of the service for which to create sources
    :return:                List of sources
    """
    source_list = []
    domains = get_domains(service_name)
    num_parsers = PARSER_DF[service_name].count()

    for d in domains:
        for row in range(num_parsers):
            source = Source(
                url_prefix=f"{d}/{get_url_prefix(service_name, row)}",
                query_parser=get_parser(service_name, row),
                serp_parsers=[]
            )
            source_list.append(source)

    return source_list


def get_domains(service_name='google') -> list:
    return list(DOMAIN_DF[service_name].dropna())

def get_url_prefix(service_name='google', row=0) -> str:
    """
    Get an url_prefix for a specified service and row.
    The row is needed to match between url_prefix and query_parser.
    :param service_name:    Name of the service for which to get the prefix
    :param row:             Row in the df column; To match with correct query_parser
    :return:                The url_prefix (can be an empty string if the cell is empty)
    """
    col = URL_DF[service_name]
    if col.count() > row:
        return col[row]
    return ""

def get_parser(service_name='google', row=0) -> QueryParser | None:
    """
    Get the parser for a specified service and row.
    The row is needed to match between query_parser and url_prefix
    :param service_name:    Name of the service for which to get the prefix
    :param row:             Row in the df column; To match with correct url_prefix
    :return:                The QueryParser with correct key or None if the cell is empty
    """
    col = PARSER_DF[service_name]
    if col.count() > row:
        parse_dict = literal_eval(col[row])
        parser = PARSER_MAP[parse_dict["type"]]
        return parser(parse_dict["key"])
    return None