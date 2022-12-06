from pathlib import Path
from re import compile, UNICODE
from typing import Iterable

from apache_beam import Pipeline
from apache_beam.io import WriteToText
from apache_beam.options.pipeline_options import PipelineOptions
from apache_beam.transforms.combiners import Count
from apache_beam.transforms.core import ParDo, DoFn, MapTuple, Create

_WORD_PATTERN = compile(r"[\w\']+", UNICODE)


class ReadFile(DoFn):
    def process(self, element: Path, **kwargs) -> Iterable[str]:
        with element.open("r") as file:
            return file.readlines()


class ExtractWords(DoFn):
    def process(self, element: str, **kwargs) -> Iterable[str]:
        return _WORD_PATTERN.findall(element)


if __name__ == "__main__":
    data_dir = Path("/mnt/ceph/storage/data-in-progress/data-teaching")
    input_dir = data_dir / "projects/project-admin-knowledge-base-tutorials"
    input_files = list(input_dir.glob("input_*.txt"))
    output_path = Path(__file__).parent / "counts.txt"

    pipeline_opts=dict(
        runner='PortableRunner',
        # job_endpoint='localhost:8099',
        # job_endpoint='flink.srv.webis.de:8099',
        # artifact_endpoint='flink.srv.webis.de:8098',
        job_endpoint='141.54.132.203:8099',
        artifact_endpoint='141.54.132.203:8098',
        flink_version='1.13',
        # flink_master='localhost:8081',
        # flink_master='flink.srv.webis.de:80',
        # flink_master='141.54.132.202:8081',
        # environment_type='DOCKER',
        # environment_type='LOOPBACK',
        # flink_submit_uber_jar=True,
        checkpointing_interval=30000,
        externalized_checkpoints_enabled=True,
        environment_type='EXTERNAL',
        environment_config='localhost:50000',
        parallelism=100,
    )
    options = PipelineOptions.from_dictionary({
        # "flink_master": "141.54.132.202:8081",
        "flink_master": "localhost:8081",
        "runner": "FlinkRunner",
        "project": "web-archive-query-log",
        "job_name": "test-job",
    })
    with Pipeline(options=options) as pipeline:
        (
                pipeline |
                Create(input_files) |
                ParDo(ReadFile()) |
                ParDo(ExtractWords()) |
                Count.PerElement() |
                MapTuple(lambda word, count: f"{word}: {count}") |
                WriteToText(str(output_path))
        )
