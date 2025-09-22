from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, TypeVar, Generic, Mapping, Any

from elasticsearch_pydantic import BaseDocument
from pandas import DataFrame
from ray.data import Dataset
from ray_elasticsearch import unwrap_documents

from archive_query_log.export.base import Exporter

_D = TypeVar("_D", bound=BaseDocument)


@dataclass(frozen=True)
class JSONLExporter(Exporter, Generic[_D]):
    document_type: type[_D]
    batch_size: int | None = None
    num_cpus: float | None = None
    num_gpus: float | None = None
    memory: float | None = None
    concurrency: int | tuple[int, int] | None = None
    ray_remote_args: Mapping[str, Any] = field(default_factory=dict)

    def export_local(
        self,
        documents: Iterable[_D],
        output_path: Path,
    ) -> None:
        with open(output_path, "wt") as file:
            for document in documents:
                file.write(document.model_dump_json() + "\n")

    def export_ray(
        self,
        dataset: Dataset,
        output_path: Path,
    ) -> None:
        @unwrap_documents(self.document_type)
        def map_batch(
            batch: DataFrame,
            documents: Iterable[_D],
        ) -> DataFrame:
            return DataFrame([doc.model_dump() for doc in documents])

        dataset = dataset.map_batches(
            map_batch,
            batch_format="pandas",
            batch_size=self.batch_size,
            num_cpus=self.num_cpus,
            num_gpus=self.num_gpus,
            memory=self.memory,
            concurrency=self.concurrency,
            **self.ray_remote_args,
        )
        dataset.write_json(
            str(output_path.resolve()),
            line_delimited=True,
        )


def get_exporter(document_type: type[_D]) -> Exporter[_D]:
    return JSONLExporter(document_type)
