from itertools import islice
from pathlib import Path
from typing import TypeVar, Annotated, Iterable

from annotated_types import Ge
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore
from elasticsearch_pydantic import BaseDocument
from ray.data import read_datasource, Dataset
from ray_elasticsearch import ElasticsearchDatasource

from archive_query_log.config import Config
from archive_query_log.export.base import Exporter, ExportFormat

_D = TypeVar("_D", bound=BaseDocument)


def get_exporter(
    document_type: type[_D],
    format: ExportFormat,
) -> Exporter[_D]:
    if format == "jsonl":
        from archive_query_log.export.jsonl import JsonlExporter

        return JsonlExporter(document_type)
    raise ValueError(f"Unknown export format: {format}")


def export_local(
    document_type: type[_D],
    index: str,
    format: ExportFormat,
    sample_size: Annotated[int, Ge(ge=1)],
    output_path: Path,
    config: Config,
) -> None:
    # Find the appropriate exporter for the given format.
    exporter = get_exporter(document_type, format)

    # Fetch the documents from Elasticsearch and sample them.
    search: Search = document_type.search(
        using=config.es.client,
        index=index,
    )
    search = search.query(FunctionScore(functions=[RandomScore()]))
    documents: Iterable[_D] = search.scan()
    documents = islice(documents, sample_size)

    exporter.export_local(documents, output_path)


def export_ray(
    document_type: type[_D],
    index: str,
    format: ExportFormat,
    output_path: Path,
    config: Config,
) -> None:
    # Find the appropriate exporter for the given format.
    exporter = get_exporter(document_type, format)

    # Create a Ray dataset from the Elasticsearch index.
    datasource = ElasticsearchDatasource(
        hosts=f"https://{config.es.host}:{config.es.port}",
        http_auth=(config.es.username, config.es.password),
        timeout=60,
        max_retries=config.es.max_retries,
        retry_on_status=(502, 503, 504),
        retry_on_timeout=True,
        keep_alive="10m",
        index=index,
        schema=document_type,
    )
    dataset: Dataset = read_datasource(
        datasource=datasource,
        override_num_blocks=100,
    )
    
    # Export the documents using the selected exporter.
    exporter.export_ray(dataset, output_path)
