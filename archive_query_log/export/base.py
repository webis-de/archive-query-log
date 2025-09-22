from pathlib import Path
from typing import Generic, Iterable, Protocol, TypeVar, TypeAlias, Literal

from elasticsearch_pydantic import BaseDocument
from ray.data import Dataset

ExportFormat: TypeAlias = Literal["jsonl"]

_D = TypeVar("_D", bound=BaseDocument, contravariant=True)


class Exporter(Protocol, Generic[_D]):
    def export_local(
        self,
        documents: Iterable[_D],
        output_path: Path,
    ) -> None: ...

    def export_ray(
        self,
        dataset: Dataset,
        output_path: Path,
    ) -> None: ...
