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

setup(
    name='openlens',
    version='1.0.0',
    description='An interactive optical lens design and simulation tool for single glass lens elements',
    long_description=read_file('README.md'),
    long_description_content_type='text/markdown',
    author='Philip',
    author_email='',
    url='https://github.com/philip/openlens',
    license='MIT',
    
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    
    python_requires='>=3.6',
    
    # Core dependencies (tkinter is assumed to be available)
    install_requires=[
    ],
    
    # Optional dependencies for 3D visualization
    extras_require={
        'visualization': ['matplotlib>=3.3.0', 'numpy>=1.19.0'],
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'black>=22.0.0',
            'pylint>=2.12.0',
            'flake8>=4.0.0',
        ],
    },
    
    # Console scripts - entry points for command-line execution
    entry_points={
        'console_scripts': [
            'openlens=src.lens_editor_gui:main',
            'openlens-cli=src.lens_editor:main',
        ],
    },
    
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Topic :: Scientific/Engineering :: Physics',
        'Topic :: Scientific/Engineering :: Visualization',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
        'Environment :: X11 Applications',
    ],
    
    keywords='optics lens optical-design simulation physics education lensmaker',
    
    project_urls={
        'Documentation': 'https://github.com/philip/openlens/blob/master/README.md',
        'Source': 'https://github.com/philip/openlens',
        'Bug Reports': 'https://github.com/philip/openlens/issues',
    },
)
