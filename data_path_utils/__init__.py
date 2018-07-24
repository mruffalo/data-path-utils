from datetime import datetime
from os import PathLike, scandir
from pathlib import Path
from subprocess import DEVNULL, Popen, check_output
from typing import Iterable, Sequence, Tuple

TIMESTAMP_FORMAT = '%Y%m%d-%H%M%S'

DATA_PATH = Path('data')
OUTPUT_PATH = Path('output')
SLURM_PATH = Path('slurm_generated')

data_producer_names = set()
data_consumer_names = set()

def producer(function):
    data_producer_names.add(function.__name__)
    return function

def consumer(function):
    data_consumer_names.add(function.__name__)
    return function

def replace_extension(path: PathLike, new_extension: str) -> Path:
    """
    new_extension can include a leading . or not; doesn't matter

    >>> p = Path('file.txt')
    >>> replace_extension(p, 'csv')
    PosixPath('file.csv')
    >>> replace_extension(p, '.csv')
    PosixPath('file.csv')
    """
    fixed_new_extension = new_extension.lstrip('.')
    p = Path(path)
    return p.parent / (p.stem + '.' + fixed_new_extension)

def append_to_filename(path: Path, addition: str) -> Path:
    """
    >>> p = Path('file.txt')
    >>> append_to_filename(p, '-appended')
    PosixPath('file-appended.txt')
    """
    new_filename = f'{path.stem}{addition}{path.suffix}'
    return path.parent / new_filename

def get_now_str() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)

def ensure_dir(path: Path):
    try:
        path.mkdir(parents=True)
    except FileExistsError:
        pass
    return path

def ensure_parent_dir(path: Path):
    return ensure_dir(path.parent)

GIT_FILENAMES = {
    'revision': 'revision.txt',
    'staged_patch': 'staged.patch',
    'unstaged_patch': 'unstaged.patch',
}
GIT_FILENAME_SET = frozenset(GIT_FILENAMES.values())

def git_revision() -> str:
    command = ['git', 'rev-parse', 'HEAD']
    revision = check_output(command, stderr=DEVNULL).decode().strip()
    return revision

def git_staged_changes_exist() -> bool:
    command = ['git', 'diff-index', '--quiet', '--cached', 'HEAD']
    p = Popen(command, stdout=DEVNULL, stderr=DEVNULL)
    p.wait()
    return bool(p.returncode)

def git_staged_patch() -> str:
    command = ['git', 'diff', '--cached']
    patch = check_output(command, stderr=DEVNULL).decode()
    return patch

def git_unstaged_changes_exist() -> bool:
    command = ['git', 'diff-files', '--quiet']
    p = Popen(command, stdout=DEVNULL, stderr=DEVNULL)
    p.wait()
    return bool(p.returncode)

def git_unstaged_patch() -> str:
    command = ['git', 'diff']
    patch = check_output(command, stderr=DEVNULL).decode()
    return patch

def write_git_metadata(data_path: Path):
    with open(data_path / GIT_FILENAMES['revision'], 'w') as f:
        print(git_revision(), file=f)

    if git_staged_changes_exist():
        with open(data_path / GIT_FILENAMES['staged_patch'], 'w') as f:
            print(git_staged_patch(), file=f)

    if git_unstaged_changes_exist():
        with open(data_path / GIT_FILENAMES['unstaged_patch'], 'w') as f:
            print(git_unstaged_patch(), file=f)

def create_paths(base_paths: Sequence[Path], label: str, print_path=True) -> Sequence[Path]:
    new_paths = []
    for base_path in base_paths:
        path = base_path / '{}_{}'.format(label, get_now_str())
        ensure_dir(path)
        new_paths.append(path)
        if print_path:
            print('Created:', path)
    return new_paths

def create_output_path(label: str, print_path=True) -> Path:
    return create_paths([OUTPUT_PATH], label, print_path)[0]

@producer
def create_data_path(label: str, print_path=True) -> Path:
    data_path = create_paths([DATA_PATH], label, print_path)[0]
    try:
        write_git_metadata(data_path)
    except Exception:
        # Writing Git commit/patch information is a bonus. If we fail,
        # the user probably doesn't have Git available, so it isn't even
        # worth reporting this.
        pass
    return data_path

def create_data_output_paths(label: str, print_path=True) -> Tuple[Path, Path]:
    """
    :return: a 2-tuple:
     [0] data path
     [1] output path
    """
    paths: Tuple[Path, Path] = tuple(create_paths([DATA_PATH, OUTPUT_PATH], label, print_path))
    try:
        write_git_metadata(paths[0])
    except Exception:
        # Writing Git commit/patch information is a bonus. If we fail,
        # the user probably doesn't have Git available, so it isn't even
        # worth reporting this.
        pass
    return paths

def create_slurm_path(description: str, print_path=True) -> Path:
    return create_paths([SLURM_PATH], description, print_path)[0]

def contains_only_git_metadata(path: Path) -> bool:
    filenames = {f.name for f in path.iterdir()}
    return not (filenames - GIT_FILENAME_SET)

def find_all_paths(base_path: Path, label: str) -> Iterable[Path]:
    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        try:
            pieces = child.name.rsplit('_', maxsplit=1)
            if pieces[0] != label:
                continue

            # Skip empty directories, or those containing only Git data
            if contains_only_git_metadata(child):
                continue

            yield child
        except (IndexError, ValueError):
            continue

@consumer
def find_all_data_paths(label: str) -> Iterable[Path]:
    yield from find_all_paths(DATA_PATH, label)

def find_newest_path(base_path: Path, label: str) -> Path:
    candidates = []

    for child in find_all_paths(base_path, label):
        try:
            pieces = child.name.rsplit('_', maxsplit=1)
            dt = datetime.strptime(pieces[1], TIMESTAMP_FORMAT)
            candidates.append((dt, child))
        except (IndexError, ValueError):
            continue

    if not candidates:
        raise FileNotFoundError('No data paths exist with label "{}"'.format(label))

    return max(candidates)[1]

@consumer
def find_newest_data_path(label: str) -> Path:
    return find_newest_path(DATA_PATH, label)

Walk_Result = Tuple[Path, Sequence[Path], Sequence[Path]]

def pathlib_walk(top, topdown=True, onerror=None, followlinks=False) -> Iterable[Walk_Result]:
    dirs = []
    nondirs = []

    top = Path(top)
    try:
        scandir_it = scandir(top)
    except OSError as error:
        if onerror is not None:
            onerror(error)
        return

    while True:
        try:
            try:
                entry = next(scandir_it)
            except StopIteration:
                break
        except OSError as error:
            if onerror is not None:
                onerror(error)
            return

        try:
            is_dir = entry.is_dir()
        except OSError:
            is_dir = False

        p = Path(entry.path)
        if is_dir:
            dirs.append(p)
        else:
            nondirs.append(p)

        if not topdown and is_dir:
            if followlinks:
                walk_into = True
            else:
                try:
                    is_symlink = entry.is_symlink()
                except OSError:
                    is_symlink = False
                walk_into = not is_symlink

            if walk_into:
                yield from pathlib_walk(entry.path, topdown, onerror, followlinks)

    if topdown:
        yield top, dirs, nondirs

        for new_path in dirs:
            if followlinks or not new_path.is_symlink():
                yield from pathlib_walk(new_path, topdown, onerror, followlinks)
    else:
        yield top, dirs, nondirs

def pathlib_walk_glob(base_path: Path, pattern: str) -> Iterable[Path]:
    for dirpath, _, filepaths in pathlib_walk(base_path):
        for filepath in filepaths:
            if filepath.match(pattern):
                yield filepath
