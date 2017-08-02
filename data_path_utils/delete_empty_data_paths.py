#!/usr/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
from shutil import rmtree

from . import DATA_PATH, contains_only_git_metadata

def delete_empty_data_paths(path: Path):
    # Support running directly in `data` directory
    data_path = path / DATA_PATH
    if data_path.is_dir():
        path = data_path

    to_delete = [
        child for child in path.iterdir()
        if (child.is_dir() and contains_only_git_metadata(child))
    ]
    for p in to_delete:
        print('Deleting', p)
        rmtree(p)

def main():
    p = ArgumentParser()
    p.add_argument('path', type=Path, nargs='?', default=Path())
    args = p.parse_args()

    delete_empty_data_paths(args.path)

if __name__ == '__main__':
    main()
