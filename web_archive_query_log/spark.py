from pathlib import Path
from socket import gethostname
from time import sleep
from typing import Tuple

from pyspark import SparkConf
from pyspark import SparkContext


def number_of_lines(file_path: Path) -> Tuple[int, str]:
    sleep(10)  # Simulate slowness.
    with file_path.open("r") as file:
        num_lines = sum(1 for _ in file)
    return num_lines, gethostname()


if __name__ == "__main__":
    data_dir = Path("/mnt/ceph/storage/data-in-progress/data-teaching")
    input_dir = data_dir / "projects/project-admin-knowledge-base-tutorials"
    input_files = list(input_dir.glob("input_*.txt"))

    conf = SparkConf()
    conf.set("spark.master", "yarn")
    conf.set("spark.submit.deployMode", "cluster")
    conf.set("spark.submit.appName", "web-archive-query-log-test")
    conf.set("spark.executor.instances", "3")
    print("Creating Spark context.")
    sc = SparkContext(conf=conf, master="yarn")
    sc.setLogLevel("DEBUG")
    print("Spark context created.")

    rdd = sc.parallelize(input_files, len(input_files))
    rdd = rdd.map(number_of_lines)
    print("Results:", rdd.collect())
