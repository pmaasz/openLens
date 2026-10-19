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
    """Extract version from openlens/__init__.py.

    That file is the single definition of the version: release-please bumps it
    (.github/release-please-config.json) and `openlens --version` reads it. This
    used to fall back to "0.1.0" if the line was missing or reformatted, which
    silently shipped a package claiming to be far older than it was - and, since
    the manifest drives every future release, quietly stalled them too. A
    packaging build with no version is a build to fix, not to paper over.
    """
    init_py = read_file(os.path.join('openlens', '__init__.py'))
    for line in init_py.splitlines():
        if line.startswith('__version__'):
            return line.split('=')[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "No __version__ assignment found in openlens/__init__.py; refusing to "
        "build a distribution with a wrong version."
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

    # The importable package is `openlens`, not `src`. The source directory was
    # called `src`, and find_packages() happily installed it under that name
    # into site-packages - so every project on the machine that had a `src`
    # directory either shadowed it or was shadowed by it. Restricted by
    # include, so a stray top-level directory can never be shipped again by
    # accident: the only thing this distribution installs is `openlens`.
    packages=find_packages(include=['openlens', 'openlens.*']),

    include_package_data=True,

    # CI tests 3.10, 3.11 and 3.12. Claiming 3.7-3.9 advertised support that
    # is never exercised, and 3.7 is long past end of life.
    python_requires='>=3.10',

    # Core dependencies. Only the GUI framework: numpy, matplotlib, scipy and
    # Pillow are all soft, and every import of them is guarded with a
    # *_AVAILABLE flag so the application starts and its core optics run
    # without them.
    #
    # numpy used to be listed here, because openlens.analysis.plots and
    # openlens.image_simulator imported it unguarded and the GUI entry module
    # imports those at module level - so a plain `pip install openlens` raised
    # ImportError at startup. Those imports are guarded now (#476), and the
    # core works without it: Lens, the ray tracer and focal length all run.
    # Listing it here made
    # the guards dead code and silently narrowed what "optional" means.
    install_requires=[
        'PySide6>=6.0',
    ],

    # Optional dependencies for visualization / development
    extras_require={
        'visualization': ['matplotlib>=3.3.0', 'numpy>=1.19.0'],
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'pytest-qt>=4.2.0',
            'pytest-xdist>=3.0.0',
            # Pinned exactly: the formatting gate is only meaningful when the
            # local hook, this extra and CI all run the same version. The
            # pre-commit config pins the same release.
            'black==26.5.1',
            # One rule only (blind excepts, see ruff.toml); pinned like black
            # so the gate cannot shift under the repository.
            'ruff==0.17.1',
            'pylint>=2.12.0',
            'flake8>=4.0.0',
            'pre-commit>=2.20.0',
        ],
    },
    
    # Console scripts - entry points for command-line execution
    entry_points={
        'console_scripts': [
            # The GUI entry point lives inside the package as __main__.py, so
            # `python3 -m openlens` and the console script are the same module.
            # It used to be a top-level openlens.py, which both forced
            # py_modules and would have shadowed the package of the same name.
            'openlens=openlens.__main__:main',
            'openlens-cli=openlens.lens_editor:main',
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
