"""Window-independent services used by the GUI.

The main window owns the Qt chrome, dialogs and status messages. The modules
in this package own the window-independent sequencing and are importable
without Qt so they can be tested headlessly.
"""

from .export_service import ExportResult, ExportService

__all__ = ["ExportResult", "ExportService"]
