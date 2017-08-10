from pathlib import Path

# Always prefer setuptools over distutils
from setuptools import setup, find_packages

here = Path(__file__).parent.absolute()

# Get the long description from the README file
with open(here / 'README.rst', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='data-path-utils',
    version='0.4',
    description='Management of scripts that produce/consume data with specific labels',
    long_description=long_description,
    url='https://github.com/mruffalo/data-path-utils',
    author='Matt Ruffalo',
    author_email='matt.ruffalo@gmail.com',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Software Development',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='data-dependencies development',
    packages=find_packages(),
    python_requires='>=3.6',
    extras_require={
        'plotting': [
            'networkx',
            'pydotplus',
        ],
    },
    entry_points={
        'console_scripts': [
            'archive_script_data_dependencies=data_path_utils.archive_script_data_dependencies:main',
            'dependency_graph=data_path_utils.dependency_graph:main',
            'list_script_dependencies=data_path_utils.list_script_dependencies:main',
            'delete_empty_data_paths=data_path_utils.delete_empty_data_paths:main',
        ],
    },
)
