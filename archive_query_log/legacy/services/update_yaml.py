from typing import Sequence

import pandas as pd
import yaml
from pandas import concat, DataFrame

from archive_query_log.legacy import DATA_DIRECTORY_PATH
from archive_query_log.legacy.cli.external import \
    load_services, load_domains, \
    service_domains, load_url_prefixes, \
    load_query_parsers, query_parser, load_page_offset_parsers, \
    page_offset_parser_series

services_file = DATA_DIRECTORY_PATH / "selected-services_overwrite.yaml"


def get_spreadsheet_data(
        first_service="google", last_service="hrblock"
) -> DataFrame:
    """
    Get parser information from the Google spreadsheet as a dataframe
    :param first_service:   First service to obtain data for (including)
    :param last_service:    Last service to obtain data for (including)
    :return:                Dataframe with parser information for each service
    """
    services = load_services()
    idx_first = services["name"].ne(first_service).idxmin()
    idx_last = services["name"].ne(last_service).idxmin()
    services = services.loc[idx_first:idx_last, :]  # type: ignore

    domains = load_domains()
    services["domains"] = [
        service_domains(domains, row)
        for _, row in services.iterrows()
    ]
    query_parsers = concat(
        [
            load_url_prefixes(),
            load_query_parsers()[["query_parser"]]
        ],
        axis="columns")
    query_parsers.dropna(inplace=True)
    services["query_parsers"] = [
        sorted((
            query_parser(row)
            for _, row in
            query_parsers[
                query_parsers["name"].str.fullmatch(service["name"])
            ].iterrows()
        ), key=lambda qp: str(qp["url_pattern"]))
        for _, service in services.iterrows()
    ]
    page_offset_parsers = concat(
        [
            load_url_prefixes(),
            load_page_offset_parsers()[["page_offset_parser"]]
        ],
        axis="columns")
    services["page_parsers"] = page_offset_parser_series(
        page_offset_parsers, services, count="pages")
    services["offset_parsers"] = page_offset_parser_series(
        page_offset_parsers, services, count="results")

    return services


def update_yaml_file(
        first_service="google", last_service="hrblock", overwrite=False
):
    """
    Update the local yaml file with the data from the Google spreadsheet
    :param first_service:   First service to update (including)
    :param last_service:    Last service to update (including)
    :param overwrite:       False: Only add parsers for service
                                that don't have one
                            True:   Overwrite the yaml entries
                                using the spreadsheet
    """
    services = get_spreadsheet_data(
        first_service=first_service, last_service=last_service)
    with open(services_file, "r", encoding="utf8") as stream:
        yaml_list = yaml.safe_load(stream)
    update_func = overwrite_parsers if overwrite else update_empty_parsers
    i = 0
    start_update = False
    while not start_update:
        elem = yaml_list[i]
        if elem["name"] == first_service:
            start_update = True
        else:
            i += 1

    while True:
        elem = yaml_list[i]
        name = elem["name"]
        update_func(service_elem=elem, services=services)
        i += 1
        if name == last_service:
            break

    with services_file.open("wt") as file:
        yaml.dump(yaml_list, stream=file, sort_keys=False)


def update_empty_parsers(service_elem: dict, services: DataFrame):
    offset_parsers = service_elem["offset_parsers"]
    page_parsers = service_elem["page_parsers"]
    query_parsers = service_elem["query_parsers"]

    # If no parsers are set, update the element using the services df
    if len(offset_parsers) + len(page_parsers) < 1:
        set_page_offset_parsers(service_elem=service_elem, services=services)
    if len(query_parsers) == 0:
        set_query_parsers(service_elem=service_elem, services=services)


def overwrite_parsers(service_elem: dict, services: DataFrame):
    set_page_offset_parsers(service_elem=service_elem, services=services)
    set_query_parsers(service_elem=service_elem, services=services)


def set_page_offset_parsers(service_elem: dict, services: DataFrame) -> None:
    name = service_elem["name"]
    row = services.loc[services["name"] == name, :]
    service_elem.update({"page_parsers": row["page_parsers"].values[0],
                         "offset_parsers": row["offset_parsers"].values[0]})


def set_query_parsers(service_elem: dict, services: DataFrame) -> None:
    name = service_elem["name"]
    row = services.loc[services["name"] == name, :]
    service_elem.update({"query_parsers": row["query_parsers"].values[0]})


def update_ranks(df: pd.DataFrame, yaml_list: Sequence[dict]):
    for i, elem in enumerate(yaml_list):
        name = elem["name"]
        rank_df = df.loc[df["service"] == name, "rank"]
        if len(rank_df) > 0:
            rank = int(rank_df.values[0])
        else:
            rank = 999999
        yaml_list[i]["alexa_rank"] = rank

    return yaml_list


def sort_by_rank(yaml_list: Sequence[dict]):
    return sorted(yaml_list, key=lambda d: d['alexa_rank'])
