"""
Dependency management utilities for openlens

Provides clean, centralized handling of optional dependencies
with consistent error messages and feature detection.
"""

import sys
from typing import Optional, Callable, Any


class DependencyManager:
    """Manages optional dependencies with graceful degradation"""
    
    def __init__(self):
        self._cache = {}
        self._warnings_shown = set()
    
    def check_dependency(self, module_name: str, 
                        feature_name: str = None,
                        install_cmd: str = None) -> bool:
        """
        Check if a dependency is available.
        
        Args:
            module_name: Name of the module to check
            feature_name: Human-readable feature name
            install_cmd: Installation command to suggest
        
        Returns:
            bool: True if module is available
        """
        if module_name in self._cache:
            return self._cache[module_name]
        
        try:
            __import__(module_name)
            self._cache[module_name] = True
            return True
        except ImportError:
            self._cache[module_name] = False
            
            # Show warning only once per module
            if module_name not in self._warnings_shown:
                self._warnings_shown.add(module_name)
                feature = feature_name or f"{module_name} features"
                install = install_cmd or f"pip install {module_name}"
                print(f"⚠ {feature} not available. Install with: {install}")
            
            return False
    
    def import_module(self, module_name: str, fallback: Any = None) -> Optional[Any]:
        """
        Import a module with fallback.
        
        Args:
            module_name: Module to import
            fallback: Value to return if import fails
        
        Returns:
            Module object or fallback value
        """
        try:
            return __import__(module_name)
        except ImportError:
            return fallback
    
    def require_dependency(self, module_name: str, feature_name: str):
        """
        Require a dependency or raise an error.
        
        Args:
            module_name: Required module name
            feature_name: Feature that requires the module
        
        Raises:
            ImportError: If module is not available
        """
        if not self.check_dependency(module_name):
            raise ImportError(
                f"{feature_name} requires {module_name}. "
                f"Install with: pip install {module_name}"
            )


# Global dependency manager instance
_dependency_manager = DependencyManager()


def check_numpy() -> bool:
    """Check if numpy is available"""
    return _dependency_manager.check_dependency(
        'numpy',
        feature_name='Numerical operations and ray tracing',
        install_cmd='pip install numpy>=1.19.0'
    )


def check_matplotlib() -> bool:
    """Check if matplotlib is available"""
    return _dependency_manager.check_dependency(
        'matplotlib',
        feature_name='3D visualization and plotting',
        install_cmd='pip install matplotlib>=3.3.0'
    )


def check_scipy() -> bool:
    """Check if scipy is available"""
    return _dependency_manager.check_dependency(
        'scipy',
        feature_name='Advanced diffraction and image processing',
        install_cmd='pip install scipy>=1.5.0'
    )


def check_pil() -> bool:
    """Check if PIL/Pillow is available"""
    return _dependency_manager.check_dependency(
        'PIL',
        feature_name='Image loading',
        install_cmd='pip install Pillow>=8.0.0'
    )


def require_numpy(feature: str = "This feature"):
    """Require numpy or raise error"""
    _dependency_manager.require_dependency('numpy', feature)


def require_matplotlib(feature: str = "This feature"):
    """Require matplotlib or raise error"""
    _dependency_manager.require_dependency('matplotlib', feature)


def require_scipy(feature: str = "This feature"):
    """Require scipy or raise error"""
    _dependency_manager.require_dependency('scipy', feature)


def get_dependency_status() -> dict:
    """
    Get status of all optional dependencies.
    
    Returns:
        dict: Status of each dependency
    """
    return {
        'numpy': check_numpy(),
        'matplotlib': check_matplotlib(),
        'scipy': check_scipy(),
        'PIL': check_pil()
    }


def print_dependency_status():
    """Print a summary of dependency availability"""
    status = get_dependency_status()
    
    print("\n" + "="*60)
    print("Optional Dependency Status")
    print("="*60)
    
    for dep, available in status.items():
        icon = "✓" if available else "✗"
        status_str = "Available" if available else "Not installed"
        print(f"  {icon} {dep:12} : {status_str}")
    
    print("="*60 + "\n")


# Feature flags based on available dependencies
NUMPY_AVAILABLE = None
MATPLOTLIB_AVAILABLE = None
SCIPY_AVAILABLE = None
PIL_AVAILABLE = None


def init_feature_flags():
    """Initialize feature flags (call once at startup)"""
    global NUMPY_AVAILABLE, MATPLOTLIB_AVAILABLE, SCIPY_AVAILABLE, PIL_AVAILABLE
    
    # Silent checks (warnings already shown by check functions)
    NUMPY_AVAILABLE = 'numpy' in sys.modules or check_numpy()
    MATPLOTLIB_AVAILABLE = 'matplotlib' in sys.modules or check_matplotlib()
    SCIPY_AVAILABLE = 'scipy' in sys.modules or check_scipy()
    PIL_AVAILABLE = 'PIL' in sys.modules or check_pil()


def import_optional(module_name: str, 
                   from_list: Optional[list] = None,
                   fallback: Any = None) -> Any:
    """
    Import module or objects from module with fallback.
    
    Args:
        module_name: Module to import
        from_list: List of objects to import from module
        fallback: Value to return if import fails
    
    Returns:
        Imported module/objects or fallback
    
    Example:
        # Import entire module
        np = import_optional('numpy', fallback=None)
        
        # Import specific objects
        j1 = import_optional('scipy.special', from_list=['j1'], fallback=None)
    """
    try:
        if from_list:
            module = __import__(module_name, fromlist=from_list)
            if len(from_list) == 1:
                return getattr(module, from_list[0])
            return tuple(getattr(module, name) for name in from_list)
        else:
            return __import__(module_name)
    except ImportError:
        return fallback


def with_numpy(func: Callable) -> Callable:
    """
    Decorator to mark functions that require numpy.
    
    Example:
        @with_numpy
        def calculate_matrix(data):
            import numpy as np
            return np.array(data)
    """
    def wrapper(*args, **kwargs):
        if not check_numpy():
            raise ImportError(f"{func.__name__} requires numpy")
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def with_scipy(func: Callable) -> Callable:
    """
    Decorator to mark functions that require scipy.
    
    Example:
        @with_scipy
        def calculate_bessel(x):
            from scipy.special import j1
            return j1(x)
    """
    def wrapper(*args, **kwargs):
        if not check_scipy():
            raise ImportError(f"{func.__name__} requires scipy")
        return func(*args, **kwargs)
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


# Initialize on module import
init_feature_flags()
