#!/usr/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
from typing import Iterable, Set
from zipfile import ZipFile

import networkx as nx

from .dependency_graph import build_dependency_graph
from . import create_data_path, find_newest_data_path, pathlib_walk

def find_script_data_files(data_nodes: Set[str], alpha: float) -> Iterable[Path]:
    alpha_str = f'{alpha:.2f}'
    for node in data_nodes:
        node = node.replace('param', alpha_str)
        print('Searching for data paths with label', node)
        try:
            input_path = find_newest_data_path(node)
            for parent_dir, dirpaths, filepaths in pathlib_walk(input_path):
                yield from filepaths
        except FileNotFoundError:
            print('\tNo paths found; skipping')

def main(script_file: Path, alpha: float):
    graph, labels = build_dependency_graph(script_file.parent)
    nodes = set(nx.dfs_preorder_nodes(graph, script_file))
    data_nodes = nodes & labels

    data_path = create_data_path('archive_script_data_dependencies')
    with open(data_path / 'script_filename.txt', 'w') as f:
        print(script_file.name, file=f)

    zip_path = data_path / 'data.zip'
    print('Archiving data to', zip_path)
    with ZipFile(str(zip_path), 'w') as z:
        for file_path in find_script_data_files(data_nodes, alpha):
            arcname = str(file_path.relative_to(script_file.parent))
            z.write(str(file_path), arcname)

if __name__ == '__main__':
    p = ArgumentParser()
    p.add_argument('script_file', type=Path)
    args = p.parse_args()

    main(args.script_file, args.alpha)
