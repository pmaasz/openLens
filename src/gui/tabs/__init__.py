"""
OpenLens PySide6 Tabs Package
"""

from .base_tab import BaseTab
from .editor_tab import EditorTab
from .selection_tab import SelectionTab
from .simulation_tab import SimulationTab
from .performance_tab import PerformanceTab
from .assembly_tab import AssemblyTab
from .optimization_tab import OptimizationTab
from .tolerancing_tab import TolerancingTab

__all__ = [
    'BaseTab',
    'EditorTab', 
    'SelectionTab',
    'SimulationTab',
    'PerformanceTab',
    'AssemblyTab',
    'OptimizationTab',
    'TolerancingTab',
]
