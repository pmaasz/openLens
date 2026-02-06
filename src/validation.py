"""
Input validation utilities for openlens

Centralized validation functions to ensure data integrity
and provide consistent error messages.
"""

import os
from pathlib import Path
from typing import Union, Tuple, Optional

# Try relative import first (for package), fall back to absolute
try:
    from .constants import (
        MIN_RADIUS_OF_CURVATURE, MAX_RADIUS_OF_CURVATURE,
        MIN_THICKNESS, MAX_THICKNESS,
        MIN_DIAMETER, MAX_DIAMETER,
        MIN_REFRACTIVE_INDEX, MAX_REFRACTIVE_INDEX,
        EPSILON
    )
except ImportError:
    from constants import (
        MIN_RADIUS_OF_CURVATURE, MAX_RADIUS_OF_CURVATURE,
        MIN_THICKNESS, MAX_THICKNESS,
        MIN_DIAMETER, MAX_DIAMETER,
        MIN_REFRACTIVE_INDEX, MAX_REFRACTIVE_INDEX,
        EPSILON
    )


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


def validate_radius(radius: float, allow_negative: bool = True, 
                   param_name: str = "radius") -> float:
    """
    Validate radius of curvature.
    
    Args:
        radius: Radius value to validate (mm)
        allow_negative: Whether negative values are allowed (for concave surfaces)
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated radius value
    
    Raises:
        ValidationError: If radius is invalid
    """
    if not isinstance(radius, (int, float)):
        raise ValidationError(f"{param_name} must be a number, got {type(radius)}")
    
    if abs(radius) < EPSILON:
        raise ValidationError(f"{param_name} cannot be zero")
    
    if not allow_negative and radius < 0:
        raise ValidationError(f"{param_name} must be positive")
    
    if abs(radius) < MIN_RADIUS_OF_CURVATURE:
        raise ValidationError(
            f"{param_name} magnitude must be at least {MIN_RADIUS_OF_CURVATURE} mm"
        )
    
    if abs(radius) > MAX_RADIUS_OF_CURVATURE:
        raise ValidationError(
            f"{param_name} magnitude must be at most {MAX_RADIUS_OF_CURVATURE} mm"
        )
    
    return float(radius)


def validate_thickness(thickness: float, param_name: str = "thickness") -> float:
    """
    Validate lens thickness.
    
    Args:
        thickness: Thickness value to validate (mm)
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated thickness value
    
    Raises:
        ValidationError: If thickness is invalid
    """
    if not isinstance(thickness, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if thickness <= 0:
        raise ValidationError(f"{param_name} must be positive")
    
    if thickness < MIN_THICKNESS:
        raise ValidationError(
            f"{param_name} must be at least {MIN_THICKNESS} mm"
        )
    
    if thickness > MAX_THICKNESS:
        raise ValidationError(
            f"{param_name} must be at most {MAX_THICKNESS} mm"
        )
    
    return float(thickness)


def validate_diameter(diameter: float, param_name: str = "diameter") -> float:
    """
    Validate lens diameter.
    
    Args:
        diameter: Diameter value to validate (mm)
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated diameter value
    
    Raises:
        ValidationError: If diameter is invalid
    """
    if not isinstance(diameter, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if diameter <= 0:
        raise ValidationError(f"{param_name} must be positive")
    
    if diameter < MIN_DIAMETER:
        raise ValidationError(
            f"{param_name} must be at least {MIN_DIAMETER} mm"
        )
    
    if diameter > MAX_DIAMETER:
        raise ValidationError(
            f"{param_name} must be at most {MAX_DIAMETER} mm"
        )
    
    return float(diameter)


def validate_refractive_index(n: float, param_name: str = "refractive index") -> float:
    """
    Validate refractive index.
    
    Args:
        n: Refractive index to validate
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated refractive index
    
    Raises:
        ValidationError: If refractive index is invalid
    """
    if not isinstance(n, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if n < MIN_REFRACTIVE_INDEX:
        raise ValidationError(
            f"{param_name} must be at least {MIN_REFRACTIVE_INDEX}"
        )
    
    if n > MAX_REFRACTIVE_INDEX:
        raise ValidationError(
            f"{param_name} must be at most {MAX_REFRACTIVE_INDEX}"
        )
    
    return float(n)


def validate_wavelength(wavelength: float, param_name: str = "wavelength") -> float:
    """
    Validate wavelength.
    
    Args:
        wavelength: Wavelength in nanometers
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated wavelength
    
    Raises:
        ValidationError: If wavelength is invalid
    """
    if not isinstance(wavelength, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if wavelength <= 0:
        raise ValidationError(f"{param_name} must be positive")
    
    if wavelength < 200 or wavelength > 3000:
        raise ValidationError(
            f"{param_name} must be between 200 and 3000 nm (visible to near-IR range)"
        )
    
    return float(wavelength)


def validate_temperature(temperature: float, param_name: str = "temperature") -> float:
    """
    Validate temperature.
    
    Args:
        temperature: Temperature in Celsius
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated temperature
    
    Raises:
        ValidationError: If temperature is invalid
    """
    if not isinstance(temperature, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if temperature < -273.15:
        raise ValidationError(
            f"{param_name} cannot be below absolute zero (-273.15°C)"
        )
    
    if temperature < -100 or temperature > 200:
        raise ValidationError(
            f"{param_name} should be between -100°C and 200°C for typical optics. "
            f"Got {temperature}°C"
        )
    
    return float(temperature)


def validate_positive_number(value: float, param_name: str = "value") -> float:
    """
    Validate that a number is positive.
    
    Args:
        value: Value to validate
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated value
    
    Raises:
        ValidationError: If value is not positive
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if value <= 0:
        raise ValidationError(f"{param_name} must be positive")
    
    return float(value)


def validate_non_negative_number(value: float, param_name: str = "value") -> float:
    """
    Validate that a number is non-negative.
    
    Args:
        value: Value to validate
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated value
    
    Raises:
        ValidationError: If value is negative
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if value < 0:
        raise ValidationError(f"{param_name} cannot be negative")
    
    return float(value)


def validate_range(value: float, min_val: float, max_val: float,
                  param_name: str = "value") -> float:
    """
    Validate that a value is within a specified range.
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        param_name: Parameter name for error messages
    
    Returns:
        float: Validated value
    
    Raises:
        ValidationError: If value is outside range
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{param_name} must be a number")
    
    if value < min_val or value > max_val:
        raise ValidationError(
            f"{param_name} must be between {min_val} and {max_val}, got {value}"
        )
    
    return float(value)


def validate_lens_name(name: str) -> str:
    """
    Validate lens name.
    
    Args:
        name: Lens name to validate
    
    Returns:
        str: Validated name (or "Untitled" if empty)
    
    Raises:
        ValidationError: If name is invalid type
    """
    if not isinstance(name, str):
        raise ValidationError(f"Name must be a string, got {type(name)}")
    
    name = name.strip()
    
    if not name:
        return "Untitled"
    
    if len(name) > 100:
        raise ValidationError("Name must be 100 characters or less")
    
    return name


def safe_float_conversion(value: Union[str, int, float], 
                         default: float = 0.0,
                         param_name: str = "value") -> Tuple[bool, float]:
    """
    Safely convert a value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        param_name: Parameter name for logging
    
    Returns:
        Tuple[bool, float]: (success, converted_value)
    """
    if isinstance(value, (int, float)):
        return True, float(value)
    
    if isinstance(value, str):
        try:
            return True, float(value)
        except ValueError:
            return False, default
    
    return False, default


def validate_lens_parameters(radius1: float, radius2: float, 
                            thickness: float, diameter: float,
                            refractive_index: float) -> dict:
    """
    Validate all lens parameters at once.
    
    Args:
        radius1: Front surface radius (mm)
        radius2: Back surface radius (mm)
        thickness: Center thickness (mm)
        diameter: Lens diameter (mm)
        refractive_index: Refractive index
    
    Returns:
        dict: Dictionary of validated parameters
    
    Raises:
        ValidationError: If any parameter is invalid
    """
    return {
        'radius1': validate_radius(radius1, allow_negative=True, param_name="R1"),
        'radius2': validate_radius(radius2, allow_negative=True, param_name="R2"),
        'thickness': validate_thickness(thickness),
        'diameter': validate_diameter(diameter),
        'refractive_index': validate_refractive_index(refractive_index)
    }


def check_physical_feasibility(radius1: float, radius2: float, 
                               thickness: float, diameter: float) -> Tuple[bool, Optional[str]]:
    """
    Check if lens parameters are physically feasible.
    
    Args:
        radius1: Front surface radius (mm)
        radius2: Back surface radius (mm)
        thickness: Center thickness (mm)
        diameter: Lens diameter (mm)
    
    Returns:
        Tuple[bool, Optional[str]]: (is_feasible, warning_message)
    """
    warnings = []
    
    # Check if thickness is reasonable compared to radii
    min_radius = min(abs(radius1), abs(radius2))
    if thickness > 0.5 * min_radius:
        warnings.append(
            f"Thickness ({thickness:.1f}mm) is very large compared to "
            f"minimum radius ({min_radius:.1f}mm). Lens may be impractical."
        )
    
    # Check if diameter is reasonable compared to radii
    if diameter > 0.8 * min_radius:
        warnings.append(
            f"Diameter ({diameter:.1f}mm) is large compared to "
            f"minimum radius ({min_radius:.1f}mm). Edge effects may be significant."
        )
    
    # Check for very thin lenses relative to diameter
    if thickness < 0.02 * diameter:
        warnings.append(
            f"Lens is very thin ({thickness:.1f}mm) relative to "
            f"diameter ({diameter:.1f}mm). May be fragile."
        )
    
    if warnings:
        return False, " ".join(warnings)
    
    return True, None


def validate_file_path(file_path: Union[str, Path], 
                       must_exist: bool = False,
                       create_parent: bool = False,
                       param_name: str = "file_path") -> Path:
    """
    Validate and sanitize file path.
    
    Args:
        file_path: Path to validate
        must_exist: If True, file must already exist
        create_parent: If True, create parent directory if it doesn't exist
        param_name: Parameter name for error messages
    
    Returns:
        Path: Validated and resolved Path object
    
    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(file_path, (str, Path)):
        raise ValidationError(f"{param_name} must be a string or Path object")
    
    try:
        path = Path(file_path).resolve()
    except (ValueError, RuntimeError) as e:
        raise ValidationError(f"Invalid {param_name}: {e}")
    
    # Check if file must exist
    if must_exist and not path.exists():
        raise ValidationError(f"{param_name} does not exist: {path}")
    
    # Check parent directory
    parent = path.parent
    if not parent.exists():
        if create_parent:
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                raise ValidationError(
                    f"Cannot create directory for {param_name}: {e}"
                )
        else:
            raise ValidationError(
                f"Parent directory does not exist for {param_name}: {parent}"
            )
    
    # Check if parent is writable (for new files)
    if not must_exist and not os.access(parent, os.W_OK):
        raise ValidationError(
            f"Parent directory is not writable for {param_name}: {parent}"
        )
    
    return path


def validate_directory_path(dir_path: Union[str, Path],
                           must_exist: bool = True,
                           create_if_missing: bool = False,
                           param_name: str = "directory") -> Path:
    """
    Validate and sanitize directory path.
    
    Args:
        dir_path: Directory path to validate
        must_exist: If True, directory must already exist
        create_if_missing: If True, create directory if it doesn't exist
        param_name: Parameter name for error messages
    
    Returns:
        Path: Validated and resolved Path object
    
    Raises:
        ValidationError: If path is invalid
    """
    if not isinstance(dir_path, (str, Path)):
        raise ValidationError(f"{param_name} must be a string or Path object")
    
    try:
        path = Path(dir_path).resolve()
    except (ValueError, RuntimeError) as e:
        raise ValidationError(f"Invalid {param_name}: {e}")
    
    if path.exists():
        if not path.is_dir():
            raise ValidationError(f"{param_name} exists but is not a directory: {path}")
    else:
        if must_exist and not create_if_missing:
            raise ValidationError(f"{param_name} does not exist: {path}")
        
        if create_if_missing:
            try:
                path.mkdir(parents=True, exist_ok=True)
            except (OSError, PermissionError) as e:
                raise ValidationError(f"Cannot create {param_name}: {e}")
    
    # Check if directory is accessible
    if path.exists() and not os.access(path, os.R_OK):
        raise ValidationError(f"{param_name} is not readable: {path}")
    
    return path


def validate_json_file_path(file_path: Union[str, Path],
                           must_exist: bool = False,
                           param_name: str = "JSON file") -> Path:
    """
    Validate JSON file path.
    
    Args:
        file_path: Path to JSON file
        must_exist: If True, file must already exist
        param_name: Parameter name for error messages
    
    Returns:
        Path: Validated and resolved Path object
    
    Raises:
        ValidationError: If path is invalid or not a JSON file
    """
    path = validate_file_path(file_path, must_exist=must_exist, 
                             create_parent=True, param_name=param_name)
    
    if path.suffix.lower() != '.json':
        raise ValidationError(
            f"{param_name} must have .json extension, got: {path.suffix}"
        )
    
    return path


def validate_lens_data_schema(data: dict, lens_index: Optional[int] = None) -> dict:
    """
    Validate that a lens data dictionary has the expected schema.
    
    Args:
        data: Dictionary containing lens data
        lens_index: Optional index for error messages
    
    Returns:
        dict: The validated data dictionary
    
    Raises:
        ValidationError: If schema is invalid
    """
    if not isinstance(data, dict):
        idx_str = f" at index {lens_index}" if lens_index is not None else ""
        raise ValidationError(f"Lens data{idx_str} must be a dictionary, got {type(data)}")
    
    # Define required fields with their types
    required_fields = {
        'name': str,
        'radius_of_curvature_1': (int, float),
        'radius_of_curvature_2': (int, float),
        'thickness': (int, float),
        'diameter': (int, float),
        'refractive_index': (int, float)
    }
    
    # Optional fields with their types
    optional_fields = {
        'type': str,
        'material': str,
        'wavelength': (int, float),
        'temperature': (int, float),
        'id': str,
        'created_at': str,
        'modified_at': str
    }
    
    # Check required fields exist and have correct type
    idx_str = f" at index {lens_index}" if lens_index is not None else ""
    for field, expected_type in required_fields.items():
        if field not in data:
            raise ValidationError(f"Missing required field '{field}' in lens data{idx_str}")
        
        if not isinstance(data[field], expected_type):
            type_name = expected_type.__name__ if isinstance(expected_type, type) else 'number'
            raise ValidationError(
                f"Field '{field}'{idx_str} must be {type_name}, got {type(data[field]).__name__}"
            )
    
    # Check optional fields have correct type if present
    for field, expected_type in optional_fields.items():
        if field in data and not isinstance(data[field], expected_type):
            type_name = expected_type.__name__ if isinstance(expected_type, type) else 'number'
            raise ValidationError(
                f"Field '{field}'{idx_str} must be {type_name}, got {type(data[field]).__name__}"
            )
    
    return data


def validate_lenses_json_schema(data: list) -> list:
    """
    Validate that JSON data conforms to lenses array schema.
    
    Args:
        data: Parsed JSON data (should be list of lens dictionaries)
    
    Returns:
        list: The validated data list
    
    Raises:
        ValidationError: If schema is invalid
    """
    if not isinstance(data, list):
        raise ValidationError(
            f"Lenses JSON root must be an array, got {type(data).__name__}"
        )
    
    # Validate each lens in the array
    for i, lens_data in enumerate(data):
        validate_lens_data_schema(lens_data, lens_index=i)
    
    return data
