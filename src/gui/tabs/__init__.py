"""
OpenLens GUI Tabs Package

This package contains the tab components for the main application window.
"""

from .base_tab import BaseTab
from .selection_tab import SelectionTab
from .editor_tab import EditorTab
from .simulation_tab import SimulationTab
from .performance_tab import PerformanceTab
from .comparison_tab import ComparisonTab
from .export_tab import ExportTab

__all__ = [
    'BaseTab',
    'SelectionTab',
    'EditorTab',
    'SimulationTab',
    'PerformanceTab',
    'ComparisonTab',
    'ExportTab',
]
