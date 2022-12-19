import yaml
from typing import Mapping
from pandas import concat, DataFrame
from web_archive_query_log.cli.external import load_services, load_domains, service_domains, load_url_prefixes, \
    load_query_parsers, query_parser, load_page_offset_parsers, page_offset_parser_series
from web_archive_query_log import DATA_DIRECTORY_PATH

services_file = DATA_DIRECTORY_PATH / "selected-services.yaml"

def get_spreadsheet_data(first_service="google", last_service="hrblock") -> DataFrame:
    services = load_services()
    idx_first = services["name"].ne(first_service).idxmin()
    idx_last = services["name"].ne(last_service).idxmin()
    services = services.loc[idx_first:idx_last, :]

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
                query_parsers["name"].str.endswith(service["name"])
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
    services["page_parsers"] = page_offset_parser_series(page_offset_parsers, services, count="pages")
    services["offset_parsers"] = page_offset_parser_series(page_offset_parsers, services, count="results")

    return services


def update_yaml_file(first_service="google", last_service="hrblock"):
    services = get_spreadsheet_data(first_service=first_service, last_service=last_service)
    with open(services_file, "r") as stream:
        yaml_list = yaml.safe_load(stream)

    i = 0
    start_update = False
    while not start_update:
        elem = yaml_list[i]
        if elem["name"] == first_service:
            start_update = True
        else:
            i+=1

    while True:
        elem = yaml_list[i]
        name = elem["name"]
        offset_parsers = elem["offset_parsers"]
        page_parsers = elem["page_parsers"]
        query_parsers = elem["query_parsers"]

        # If no parsers are set, update the element using the services df
        if len(offset_parsers) + len(page_parsers) < 1:
            yaml_list[i] = set_page_offset_parsers(service_elem=elem, services=services)
        if len(query_parsers) == 0:
            set_query_parsers(service_elem=elem, services=services)
        i += 1
        if name == last_service:
            break

    with services_file.open("wt") as file:
        yaml.dump(yaml_list, stream=file, sort_keys=False)



def set_page_offset_parsers(service_elem: dict, services: DataFrame) -> Mapping:
    name = service_elem["name"]
    row = services.loc[services["name"] == name, :]
    service_elem.update({"page_parsers": row["page_parsers"].values[0],
                         "offset_parsers": row["offset_parsers"].values[0]})
    return service_elem

def set_query_parsers(service_elem: dict, services: DataFrame) -> Mapping:
    name = service_elem["name"]
    row = services.loc[services["name"] == name, :]
    service_elem.update({"query_parsers": row["query_parsers"].values[0]})
    return service_elem

