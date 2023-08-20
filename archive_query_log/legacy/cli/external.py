from json import loads
from math import nan
from pathlib import Path
from re import compile as pattern, escape
from urllib.parse import quote

from click import argument, group
from pandas import DataFrame, read_csv, Series, concat
from yaml import dump

from archive_query_log.legacy import DATA_DIRECTORY_PATH
from archive_query_log.legacy.cli.util import PathParam

sheets_id = "1LnIJYFBYQtZ32rxnT6RPGMOvuRIUQMoEx7tOS0z7Mi8"
sheet_services = "Services"
sheet_domains = "Domains"
sheet_url_prefixes = "URL Prefixes"
sheet_query_parsers = "Query Parsers"
sheet_page_parsers = "Page Parsers"


@group("external")
def external():
    pass


def from_sheets(sheet_name: str, transpose: bool = False) -> DataFrame:
    url = f"https://docs.google.com/spreadsheets/d/{sheets_id}/" \
          f"gviz/tq?tqx=out:csv&sheet={quote(sheet_name)}"
    if transpose:
        df = read_csv(
            url, low_memory=False, na_values=[""], keep_default_na=False,
        )
        return DataFrame([
            {
                "name": column,
                "value": value,
            }
            for column in df.columns
            for value in df[column].dropna()
        ])
    else:
        return read_csv(url)


def load_services() -> DataFrame:
    df = from_sheets(sheet_services)
    df = df[~df["service"].str.contains(".", regex=False)]
    df["name"] = df["service"]
    df["public_suffix"] = df["tld"]
    df["alexa_domain"] = df["name"] + "." + df["public_suffix"]
    df["alexa_rank"] = df["rank"]
    df["notes"] = df["Notes"]
    for col in ["has_input_field", "has_search_form", "has_search_div"]:
        df[col.removeprefix("has_")] = df[col].replace("FALSCH", False)
    df[col].replace("False", False, inplace=True)
    df[col].replace("True", True, inplace=True)
    df["alexa_rank"].astype(int, copy=False)
    df["alexa_rank"].replace(99999, nan, inplace=True)
    return df[["name", "public_suffix", "alexa_domain", "alexa_rank",
               "category", "notes", "input_field",
               "search_form", "search_div"]]


def load_domains() -> DataFrame:
    df = from_sheets(sheet_domains, transpose=True)
    df["domain"] = df["value"]
    return df[["name", "domain"]]


def url_prefix_pattern(url_prefix: str) -> str | None:
    if url_prefix == "":
        return None
    return f"^https?://[^/]+/{escape(url_prefix)}"


pattern(r"[^/]+/images/search\?")


def load_url_prefixes() -> DataFrame:
    df = from_sheets(sheet_url_prefixes, transpose=True)
    df["value"].replace("NULL", "", inplace=True)
    df["pattern"] = df["value"].map(url_prefix_pattern)
    return df[["name", "pattern"]]


def load_query_parsers() -> DataFrame:
    df = from_sheets(sheet_query_parsers, transpose=True)
    df["query_parser"] = df["value"]
    return df[["name", "query_parser"]]


def load_page_offset_parsers() -> DataFrame:
    df = from_sheets(sheet_page_parsers, transpose=True)
    df["value"].replace("NULL", "{}", inplace=True)
    df["page_offset_parser"] = df["value"]
    return df[["name", "page_offset_parser"]]


def service_domains(domains: DataFrame, service: Series) -> list[str]:
    return sorted(
        set(list(domains[domains["name"] == service["name"]]["domain"])) | {
            service["alexa_domain"]})


def query_parser(row: Series) -> dict:
    row_dict = row.to_dict()
    row_dict.update(loads(row_dict["query_parser"]))
    url_pattern = "" if row_dict["pattern"] is None else row_dict["pattern"]
    if row_dict["type"] == "qp":
        return {
            "url_pattern": url_pattern,
            "type": "query_parameter",
            "parameter": row_dict["key"]
        }
    elif row_dict["type"] == "fp":
        return {
            "url_pattern": url_pattern,
            "type": "fragment_parameter",
            "parameter": row_dict["key"]
        }
    elif row_dict["type"] == "ps":
        return {
            "url_pattern": url_pattern,
            "type": "path_suffix",
            "path_prefix": row_dict["key"]
        }
    else:
        raise NotImplementedError()


page_offset_parser_map = {"parameter": "query_parameter",
                          "suffix": "path_suffix",
                          "fragment": "fragment_parameter"}


def page_offset_parser(row: Series, count="results") -> dict:
    row_dict = row.to_dict()
    row_dict.update(loads(row_dict["page_offset_parser"]))
    if row_dict["count"] == count:
        url_pattern = "" if row_dict["pattern"] is None \
            else row_dict["pattern"]
        return {
            "url_pattern": url_pattern,
            "type": page_offset_parser_map[row_dict["type"]],
            "parameter": row_dict["key"]
        }
    else:
        raise NotImplementedError()


def page_offset_parser_series(page_offset_parsers, services, count):
    return [
        sorted((
            page_offset_parser(row, count=count)
            for _, row in
            page_offset_parsers[
                (page_offset_parsers["name"].str.fullmatch(service["name"])) &
                (page_offset_parsers["page_offset_parser"].str.contains(
                    f'"count": "{count}"'
                ))
                ].iterrows()
        ), key=lambda pp: str(pp["url_pattern"]))
        for _, service in services.iterrows()
    ]


@external.command("import-services")
@argument(
    "services-file",
    type=PathParam(
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=False,
        resolve_path=True,
        path_type=Path,
    ),
    default=DATA_DIRECTORY_PATH / "services.yaml",
)
def import_services(services_file: Path):
    services = load_services()
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
    services["page_parsers"] = page_offset_parser_series(
        page_offset_parsers, services, count="pages"
    )
    services["offset_parsers"] = page_offset_parser_series(
        page_offset_parsers, services, count="results"
    )
    services["interpreted_query_parsers"] = [
        []
        for _, service in services.iterrows()
    ]
    services["results_parsers"] = [
        []
        for _, service in services.iterrows()
    ]
    services.replace({nan: None}, inplace=True)
    services_dict = services.to_dict(orient="records")
    with services_file.open("wt") as file:
        dump(services_dict, stream=file, sort_keys=False)
