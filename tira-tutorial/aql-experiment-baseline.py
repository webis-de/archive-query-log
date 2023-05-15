#!/usr/bin/env python3
import argparse
import pandas as pd
from glob import glob
import json


def parse_args():
    parser = argparse.ArgumentParser(description='Archive Query Log Demo')

    parser.add_argument('--input', type=str, help='The directory with the input data (i.e., a directory containing serps and results).', required=True)
    parser.add_argument('--output', type=str, help='The output will be stored in this directory.', required=True)
    
    return parser.parse_args()


def main(input_dir, output_dir):
    df = pd.concat([pd.read_json(i, lines=True) for i in glob(f'{input_dir}/serps/part*.gz')])
    json.dump(df.service.value_counts().to_dict(), open(output_dir + '/results.json', 'w'))

if __name__ == '__main__':
    args = parse_args()
    main(args.input, args.output)
    
