import yaml
from pandas import concat, DataFrame
from web_archive_query_log.cli.external import load_services, load_url_prefixes, load_page_offset_parsers, \
    page_offset_parser_series
from web_archive_query_log import DATA_DIRECTORY_PATH

services_file = DATA_DIRECTORY_PATH / "selected-services.yaml"

def get_page_offset_parsers(last_service="hrblock"):
    services = load_services()
    services = services.loc[:services["name"].ne(last_service).idxmin(), :]
    page_offset_parsers = concat(
        [
            load_url_prefixes(),
            load_page_offset_parsers()[["page_offset_parser"]]
        ],
        axis="columns")
    services["page_parsers"] = page_offset_parser_series(page_offset_parsers, services, count="pages")
    services["offset_parsers"] = page_offset_parser_series(page_offset_parsers, services, count="results")

    return services

def update_page_offset_parsers(last_service="hrblock"):
    services = get_page_offset_parsers(last_service)
    with open(services_file, "r") as stream:
        yaml_list = yaml.safe_load(stream)

    i = 0
    while True:
        elem = yaml_list[i]
        offset_parsers = elem["offset_parsers"]
        page_parsers = elem["page_parsers"]

        # If no parsers are set, update the element using the services df
        if len(offset_parsers) + len(page_parsers) < 1:
            yaml_list[i] = set_parsers(service_elem=elem, services=services)

        i+=1
        if elem["name"] == last_service:
            break

    with services_file.open("wt") as file:
        yaml.dump(yaml_list, stream=file, sort_keys=False)



def set_parsers(service_elem: dict, services: DataFrame):
    name = service_elem["name"]
    row = services.loc[services["name"] == name, :]

    service_elem.update({"page_parsers": row["page_parsers"].values[0],
                         "offset_parsers": row["offset_parsers"].values[0]})

    return service_elem


