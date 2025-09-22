from itertools import islice
from pathlib import Path
from typing import TypeVar, Annotated, Iterable

from annotated_types import Ge
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore
from elasticsearch_pydantic import BaseDocument

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
