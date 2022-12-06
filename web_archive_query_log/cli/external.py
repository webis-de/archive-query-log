from json import loads
from math import nan
from pathlib import Path
from re import compile, escape
from urllib.parse import quote

from click import argument
from pandas import DataFrame, read_csv, Series, concat
from yaml import dump

from web_archive_query_log import DATA_DIRECTORY_PATH
from web_archive_query_log.cli import main
from web_archive_query_log.cli.util import PathParam

sheets_id = "1LnIJYFBYQtZ32rxnT6RPGMOvuRIUQMoEx7tOS0z7Mi8"
sheet_services = "Services"
sheet_domains = "Domains"
sheet_url_prefixes = "URL Prefixes"
sheet_query_parsers = "Query Parsers"


@main.group("external")
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
    df["alexa_rank"].replace(99999, None, inplace=True)
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
    return f"[^/]+/{escape(url_prefix)}"


compile(r"[^/]+/images/search\?")


def load_url_prefixes() -> DataFrame:
    df = from_sheets(sheet_url_prefixes, transpose=True)
    df["value"].replace("NULL", "", inplace=True)
    df["pattern"] = df["value"].map(url_prefix_pattern)
    return df[["name", "pattern"]]


def load_query_parsers() -> DataFrame:
    df = from_sheets(sheet_query_parsers, transpose=True)
    df["query_parser"] = df["value"]
    return df[["name", "query_parser"]]


def service_domains(domains: DataFrame, service: Series) -> list[str]:
    return sorted(
        set(list(domains[domains["name"] == service["name"]]["domain"])) | {
            service["alexa_domain"]})


def query_parser(row: Series) -> dict:
    row = row.to_dict()
    row.update(loads(row["query_parser"]))
    if row["type"] == "qp":
        return {
            "pattern": row["pattern"],
            "type": "query_parameter",
            "parameter": row["key"]
        }
    elif row["type"] == "fp":
        return {
            "pattern": row["pattern"],
            "type": "fragment_parameter",
            "parameter": row["key"]
        }
    elif row["type"] == "ps":
        return {
            "pattern": row["pattern"],
            "type": "path_suffix",
            "path_prefix": row["key"]
        }
    else:
        raise NotImplementedError()


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
            query_parsers[query_parsers["name"].str.endswith(service["name"])
            ].iterrows()
        ), key=lambda qp: str(qp["pattern"]))
        for _, service in services.iterrows()
    ]
    services["page_num_parsers"] = [
        []
        for _, service in services.iterrows()
    ]
    services["results_parsers"] = [
        []
        for _, service in services.iterrows()
    ]
    services["result_query_parsers"] = [
        []
        for _, service in services.iterrows()
    ]
    services.replace({nan: None}, inplace=True)
    services_dict = services.to_dict(orient="records")
    with services_file.open("wt") as file:
        dump(services_dict, stream=file, sort_keys=False)
