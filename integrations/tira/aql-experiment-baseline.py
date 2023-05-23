#!/usr/bin/env python3

from argparse import ArgumentParser
from json import dump
from pathlib import Path

from pandas import concat, read_json


def parse_args():
    parser = ArgumentParser(description="Archive Query Log Demo")

    parser.add_argument(
        '--input',
        type=Path,
        help="The directory with the input data "
             "(i.e., a directory containing serps and results).",
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="The output will be stored in this directory.",
        required=True,
    )

    return parser.parse_args()


def main(input_dir: Path, output_dir: Path):
    paths = input_dir.glob("serps/part*.gz")
    df = concat([read_json(path, lines=True) for path in paths])
    with (output_dir / "results.json").open("w") as file:
        dump(df["search_provider_name"].value_counts().to_dict(), file)


if __name__ == "__main__":
    args = parse_args()
    main(args.input, args.output)
