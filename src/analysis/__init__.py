
import math
import statistics
from typing import List, Tuple, Optional, Dict, Any

# Expose SpotDiagram
try:
    from .spot_diagram import SpotDiagram
except ImportError:
    try:
        from src.analysis.spot_diagram import SpotDiagram
    except ImportError:
        # Fallback for direct execution
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        from spot_diagram import SpotDiagram

# Try to expose other analysis modules if they exist
try:
    from .beam_synthesis import PSFCalculator, WavefrontSensor
except ImportError:
    pass

try:
    from .psf_mtf import MTFCalculator
except ImportError:
    pass
