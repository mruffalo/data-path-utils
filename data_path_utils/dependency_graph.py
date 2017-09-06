#!/usr/bin/env python3
from argparse import ArgumentParser
import ast
import json
from pathlib import Path
from pprint import pprint
from subprocess import check_call
from typing import NamedTuple, Optional, Sequence, Set, Tuple

import networkx as nx

from . import (
    create_output_path,
    data_consumer_names,
    data_producer_names,
    replace_extension,
)

PYTHON_FILE_PATTERN = '*.py'

def get_label_string(node: ast.JoinedStr) -> str:
    strings = []
    for str_piece in node.values:
        if isinstance(str_piece, ast.Str):
            strings.append(str_piece.s)
        elif isinstance(str_piece, ast.FormattedValue):
            if isinstance(str_piece.value, ast.Attribute):
                strings.append(str_piece.value.attr)
            elif isinstance(str_piece.value, ast.Name):
                strings.append(str_piece.value.id)
    return ''.join(strings)

def get_argument_label(func_call_node) -> Optional[str]:
    labels = []
    for child in ast.walk(func_call_node):
        # Should be at most one string descendant of this node
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
        raise ValueError('Unhandled case: multiple strings under call to data consumer function')

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
                if hasattr(target, 'id') and (target.id == assignment_name):
                    return find_first_str_value(node.value)

# TODO refactor into a class instead of passing string_replacements around so much
def adjust_label(label: str, string_replacements: Sequence[Tuple[str, str]]) -> str:
    for bad, good in string_replacements:
        label = label.replace(bad, good)
    return label

def get_label(node, root, string_replacements: Sequence[Tuple[str, str]]) -> str:
    label = get_argument_label(node)
    if label is None:
        # 'create_data_path' not called with a string constant
        # figure out name of variable it's called with, the get value
        # of that variable
        argument_name = get_argument_name(node)
        label = get_assignment_value(root, argument_name)
        return adjust_label(label, string_replacements)
    else:
        # Easy case: create_data_path called with a string constant
        return adjust_label(label, string_replacements)

class DependencyData(NamedTuple):
    labels_consumed: Sequence[str]
    labels_produced: Sequence[str]
    # Labels consumed with the `find_all_data_paths` function. These edges
    # shouldn't be included when performing a topological sort.
    weak_labels_consumed: Sequence[str]
    imports: Sequence[Path]

    @classmethod
    def create(cls):
        """
        Convenience function that creates a new instance of this class, with
        all fields initialized to empty sequences.
        """
        return cls([], [], [], [])

def parse_python_file(file_path: Path, string_replacements: Sequence[Tuple[str, str]]) -> DependencyData:
    """
    :param file_path: Python file to parse
    :return: 2-tuple of sequences of strings:
     [0] Labels of this file's dependencies (anything it calls 'find_newest_data_path' to use,
       e.g. 'build_hippie_network')
     [1] Labels provided by this file (any string argument to 'create_data_path')
    """
    dd = DependencyData.create()

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
            if name in data_consumer_names:
                dd.labels_consumed.append(get_label(node, parsed, string_replacements))
            elif name in data_producer_names:
                dd.labels_produced.append(get_label(node, parsed, string_replacements))
        elif isinstance(node, ast.Import):
            for module_alias in node.names:
                maybe_file_path = file_path.parent / f'{module_alias.name}.py'
                if maybe_file_path.is_file():
                    dd.imports.append(maybe_file_path)
        elif isinstance(node, ast.ImportFrom):
            maybe_file_path = file_path.parent / f'{node.module}.py'
            if maybe_file_path.is_file():
                dd.imports.append(maybe_file_path)

    return dd

def read_string_replacement_file(script_dir: Path) -> Sequence[Tuple[str, str]]:
    replacements: Sequence[Tuple[str, str]] = []
    replacement_file = script_dir / 'string_replacements.json'
    if replacement_file.is_file():
        with open(replacement_file) as f:
            replacements = json.load(f)
    return replacements

def build_dependency_graph(script_dir: Path) -> Tuple[nx.DiGraph, Set[str]]:
    g = nx.DiGraph()
    labels = set()
    string_replacements = read_string_replacement_file(script_dir)
    for script_path in script_dir.glob(PYTHON_FILE_PATTERN):
        try:
            dependency_data = parse_python_file(script_path, string_replacements)
        except Exception:
            print(f'Failed to parse "{script_path}"')
            raise

        labels.update(dependency_data.labels_consumed, dependency_data.labels_produced)
        for label in dependency_data.labels_consumed:
            g.add_edge(script_path, label)
        for label in dependency_data.labels_produced:
            g.add_edge(label, script_path)
        for other_path in dependency_data.imports:
            g.add_edge(script_path, other_path)

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
