#!/usr/bin/env python3
from argparse import ArgumentParser
from pathlib import Path
from typing import Set

import networkx as nx

from .dependency_graph import build_dependency_graph

COLORS = ['\033[00;32m', '\033[00;33m']
NO_COLOR = '\033[00m'

def get_script_dependencies(graph: nx.DiGraph, script: Path, data_labels: Set[str]):
    nodes = set(nx.dfs_preorder_nodes(graph, script))
    subgraph = graph.subgraph(nodes)

    node_types = ['script', 'data']
    max_node_type_length = max(len(t) for t in node_types)

    for node in nx.topological_sort(subgraph, reverse=True):
        sel = int(node in data_labels)
        yield '{}{:>{}}: {}{}'.format(
            COLORS[sel],
            node_types[sel],
            max_node_type_length,
            node,
            NO_COLOR,
        )

if __name__ == '__main__':
    p = ArgumentParser()
    p.add_argument('script_filename', type=Path)
    args = p.parse_args()

    script_dir = Path(args.script_filename).parent
    graph, labels = build_dependency_graph(script_dir)
    for dependency in get_script_dependencies(graph, args.script_filename, labels):
        print(dependency)
