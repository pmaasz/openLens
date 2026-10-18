#!/usr/bin/env python3
"""
openlens - Optical Lens Design and Simulation Tool
Setup configuration for package distribution
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_file(filename):
    with open(os.path.join(os.path.dirname(__file__), filename), encoding='utf-8') as f:
        return f.read()

def get_version():
    """Extract version from src/__init__.py.

    That file is the single definition of the version: release-please bumps it
    (.github/release-please-config.json) and `openlens --version` reads it. This
    used to fall back to "0.1.0" if the line was missing or reformatted, which
    silently shipped a package claiming to be far older than it was - and, since
    the manifest drives every future release, quietly stalled them too. A
    packaging build with no version is a build to fix, not to paper over.
    """
    init_py = read_file(os.path.join('src', '__init__.py'))
    for line in init_py.splitlines():
        if line.startswith('__version__'):
            return line.split('=')[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "No __version__ assignment found in src/__init__.py; refusing to build "
        "a distribution with a wrong version."
    )

setup(
    name='openlens',
    version=get_version(),
    description='An interactive optical lens design and simulation tool (PySide6-based)',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    author='Philip',
    author_email='',
    url='https://github.com/pmaasz/openLens',
    license='MIT',

    packages=find_packages(exclude=['tests', 'tests.*']),

    # openlens.py is the GUI's entry point (openlens=openlens:main). It is a
    # top-level module, and find_packages() only finds packages - directories
    # with __init__.py - so without this it was absent from every non-editable
    # install and the `openlens` command did not exist.
    py_modules=['openlens'],

    include_package_data=True,

    # CI tests 3.10, 3.11 and 3.12. Claiming 3.7-3.9 advertised support that
    # is never exercised, and 3.7 is long past end of life.
    python_requires='>=3.10',

    # Core dependencies. numpy is here because openlens.py imports
    # src.analysis.plots at module load and that module imports numpy
    # unconditionally - so a plain `pip install openlens` raised ImportError at
    # startup. matplotlib stays optional: it is imported lazily inside
    # functions, under try/except.
    install_requires=[
        'PySide6>=6.0',
        'numpy>=1.19.0',
    ],
    
    # Optional dependencies for visualization / development
    extras_require={
        'visualization': ['matplotlib>=3.3.0', 'numpy>=1.19.0'],
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'pytest-qt>=4.2.0',
            'pytest-xdist>=3.0.0',
            'black>=22.0.0',
            'pylint>=2.12.0',
            'flake8>=4.0.0',
            'pre-commit>=2.20.0',
        ],
    },
    
    # Console scripts - entry points for command-line execution
    entry_points={
        'console_scripts': [
            'openlens=openlens:main',
            'openlens-cli=src.lens_editor:main',
        ],
    },
    
    classifiers=[
        # 0.x, so "Production/Stable" overstates it. Beta is the honest claim.
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Topic :: Scientific/Engineering :: Physics',
        'Topic :: Scientific/Engineering :: Visualization',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        # Only the versions CI actually tests. 3.7 was listed twice, and
        # 3.7-3.9 were advertised without ever being exercised.
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Operating System :: OS Independent',
        'Environment :: X11 Applications',
    ],

    keywords='optics lens optical-design simulation physics education lensmaker',

    project_urls={
        'Documentation': 'https://github.com/pmaasz/openLens/blob/master/README.md',
        'Source': 'https://github.com/pmaasz/openLens',
        'Bug Reports': 'https://github.com/pmaasz/openLens/issues',
    },
)
