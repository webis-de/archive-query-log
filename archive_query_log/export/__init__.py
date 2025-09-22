from typing import TypeAlias, TypeVar, Literal

from elasticsearch_pydantic import BaseDocument

from archive_query_log.export.base import Exporter
from archive_query_log.export.jsonl import JSONLExporter

_D = TypeVar("_D", bound=BaseDocument)

ExportFormat: TypeAlias = Literal["jsonl"]


def get_exporter(
    document_type: type[_D],
    format: ExportFormat,
) -> Exporter[_D]:
    if format == "jsonl":
        return JSONLExporter(document_type)
    raise ValueError(f"Unknown export format: {format}")
