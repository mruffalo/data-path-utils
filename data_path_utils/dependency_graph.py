#!/usr/bin/env python3
from argparse import ArgumentParser
import ast
from pathlib import Path
from pprint import pprint
from subprocess import check_call
from typing import Optional, Sequence, Set, Tuple

import networkx as nx

from . import create_output_path, replace_extension

PYTHON_FILE_PATTERN = '*.py'

data_producer_name = 'create_data_path'
data_consumer_name = 'find_newest_data_path'

def get_label_string(node: ast.JoinedStr) -> str:
    strings = []
    for str_piece in node.values:
        if isinstance(str_piece, ast.Str):
            strings.append(str_piece.s)
        elif isinstance(str_piece, ast.FormattedValue):
            if isinstance(str_piece.value, ast.Attribute):
                strings.append(str_piece.value.attr)
            elif isinstance(str_piece.value, ast.Name):
                strings.append(str_piece.value.id, str_piece.value.id)
    return ''.join(strings)

def get_argument_label(func_call_node) -> Optional[str]:
    labels = []
    for child in ast.walk(func_call_node):
        # Should be at most one string descendent of this node
        # If there are zero, need to backtrack a few lines
        if isinstance(child, ast.JoinedStr):
            labels.append(get_label_string(child))
            break
        elif isinstance(child, ast.Str):
            labels.append(child.s)
    count = len(labels)
    if count == 1:
        return labels[0]
    elif count > 1:
        raise ValueError(f'Unhandled case: multiple strings under call to {data_consumer_name}')

    return None

def get_argument_name(func_call_node) -> str:
    return func_call_node.args[0].id

def find_first_str_value(node) -> str:
    for child in ast.walk(node):
        if isinstance(child, ast.JoinedStr):
            return get_label_string(child)
        elif isinstance(child, ast.Str):
            return child.s

def get_assignment_value(root_ast_node, assignment_name: str) -> str:
    for node in ast.walk(root_ast_node):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if target.id == assignment_name:
                    return find_first_str_value(node.value)

def parse_python_file(file_path: Path) -> Tuple[Sequence[str], Sequence[str]]:
    """
    :param file_path: Python file to parse
    :return: 2-tuple of sequences of strings:
     [0] Labels of this file's dependencies (anything it calls 'find_newest_data_path' to use,
       e.g. 'build_hippie_network')
     [1] Labels provided by this file (any string argument to 'create_data_path')
    """
    labels_consumed = []
    labels_produced = []

    with file_path.open() as f:
        parsed = ast.parse(f.read())

    for node in ast.walk(parsed):
        if isinstance(node, ast.Call):
            name = None
            func = node.func
            if hasattr(func, 'id'):
                name = func.id
            elif hasattr(func, 'attr'):
                name = func.attr
            if name == data_consumer_name:
                label = get_argument_label(node)
                labels_consumed.append(label)
            elif name == data_producer_name:
                label = get_argument_label(node)
                if label is None:
                    # 'create_data_path' not called with a string constant
                    # figure out name of variable it's called with, the get value
                    # of that variable
                    argument_name = get_argument_name(node)
                    label = get_assignment_value(parsed, argument_name)
                    labels_produced.append(label)
                else:
                    # Easy case: create_data_path called with a string constant
                    labels_produced.append(label)

    return labels_consumed, labels_produced

def build_dependency_graph(script_dir: Path) -> Tuple[nx.DiGraph, Set[str]]:
    g = nx.DiGraph()
    labels = set()
    for script_path in script_dir.glob(PYTHON_FILE_PATTERN):
        try:
            labels_consumed, labels_produced = parse_python_file(script_path)
        except Exception:
            print(f'Failed to parse "{script_path}"')
            raise

        labels.update(labels_consumed, labels_produced)
        for label in labels_consumed:
            g.add_edge(script_path, label)
        for label in labels_produced:
            g.add_edge(label, script_path)

    return g, labels

def plot_network(g: nx.DiGraph, labels: Set[str], output_path: Path):
    p = nx.drawing.nx_pydot.to_pydot(g)
    for label in labels:
        for node in p.get_node(label):
            node.set_shape('box')
    dot_file = output_path / 'graph.dot'
    p.write(str(dot_file))

    command = [
        'dot',
        '-Tpdf',
        '-o',
        str(replace_extension(dot_file, 'pdf')),
        str(dot_file),
    ]
    print('Running', ' '.join(command))
    check_call(command)

def main():
    p = ArgumentParser()
    p.add_argument('script_dir', type=Path, nargs='?', default=Path())
    args = p.parse_args()

    graph, labels = build_dependency_graph(args.script_dir)
    pprint(graph.nodes())

    output_path = create_output_path('dependency_graph')
    plot_network(graph, labels, output_path)

if __name__ == '__main__':
    main()
