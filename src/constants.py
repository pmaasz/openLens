"""
Constants for openlens application

This module centralizes all magic numbers and configuration values
to improve code maintainability and clarity.
"""

# ==================== Optical Constants ====================

# Default wavelengths (in nanometers)
WAVELENGTH_D_LINE = 587.6  # Helium d-line (yellow)
WAVELENGTH_C_LINE = 656.3  # Hydrogen C-line (red)
WAVELENGTH_F_LINE = 486.1  # Hydrogen F-line (blue)
WAVELENGTH_GREEN = 550.0   # Green light

# Standard refractive indices
REFRACTIVE_INDEX_AIR = 1.0
REFRACTIVE_INDEX_BK7 = 1.5168
REFRACTIVE_INDEX_VACUUM = 1.0

# ==================== Default Lens Parameters ====================

# Default lens geometry (in mm)
DEFAULT_RADIUS_1 = 100.0
DEFAULT_RADIUS_2 = -100.0
DEFAULT_THICKNESS = 5.0
DEFAULT_DIAMETER = 50.0
DEFAULT_TEMPERATURE = 20.0  # degrees Celsius

# ==================== Ray Tracing Constants ====================

# Ray tracing defaults
DEFAULT_NUM_RAYS = 11
DEFAULT_RAY_HEIGHT_RANGE = (-20.0, 20.0)  # mm
DEFAULT_ANGLE_RANGE = (-30.0, 30.0)  # degrees

# Ray intersection tolerances
RAY_INTERSECTION_TOLERANCE = 1e-10
MAX_RAY_PROPAGATION_DISTANCE = 1000.0  # mm

# ==================== Aberration Constants ====================

# Aberration quality thresholds (dimensionless)
SPHERICAL_ABERRATION_EXCELLENT = 0.01
SPHERICAL_ABERRATION_GOOD = 0.05
SPHERICAL_ABERRATION_POOR = 0.20

COMA_EXCELLENT = 0.01
COMA_GOOD = 0.05
COMA_POOR = 0.15

# Diffraction limit factors
AIRY_DISK_FACTOR = 1.22  # First zero of Airy pattern
RAYLEIGH_CRITERION_FACTOR = 1.22

# ==================== GUI Constants ====================

# Color scheme (dark mode)
COLOR_BG_DARK = "#1e1e1e"
COLOR_BG_MEDIUM = "#2d2d2d"
COLOR_BG_LIGHT = "#3d3d3d"
COLOR_FG = "#e0e0e0"
COLOR_FG_DIM = "#888888"
COLOR_ACCENT = "#4a9eff"
COLOR_SUCCESS = "#4caf50"
COLOR_WARNING = "#ff9800"
COLOR_ERROR = "#f44336"
COLOR_HIGHLIGHT = "#2196F3"

# Font configurations
FONT_FAMILY = "Arial"
FONT_SIZE_NORMAL = 9
FONT_SIZE_LARGE = 11
FONT_SIZE_TITLE = 12

# Widget padding
PADDING_SMALL = 2
PADDING_MEDIUM = 5
PADDING_LARGE = 10
PADDING_XLARGE = 20

# Widget sizing
ENTRY_WIDTH = 15
BUTTON_WIDTH = 12
LISTBOX_WIDTH = 30
LISTBOX_HEIGHT = 15

# Tooltip offset
TOOLTIP_OFFSET_X = 25
TOOLTIP_OFFSET_Y = 25

# ==================== Validation Constants ====================

# Physical constraints
MIN_RADIUS_OF_CURVATURE = 1.0  # mm
MAX_RADIUS_OF_CURVATURE = 10000.0  # mm
MIN_THICKNESS = 0.1  # mm
MAX_THICKNESS = 100.0  # mm
MIN_DIAMETER = 1.0  # mm
MAX_DIAMETER = 500.0  # mm
MIN_REFRACTIVE_INDEX = 1.0
MAX_REFRACTIVE_INDEX = 3.0

# ==================== Calculation Constants ====================

# Numerical tolerances
EPSILON = 1e-10
SMALL_NUMBER = 1e-6
LARGE_NUMBER = 1e10

# Unit conversions
MM_TO_METERS = 0.001
METERS_TO_MM = 1000.0
NM_TO_MM = 1e-6
MM_TO_MICRONS = 1000.0

# ==================== File I/O Constants ====================

# Default filenames
DEFAULT_LENSES_FILE = "lenses.json"
DEFAULT_BACKUP_SUFFIX = ".backup"

# JSON formatting
JSON_INDENT = 2

# ==================== Performance Constants ====================

# Mesh resolution for 3D visualization
MESH_RESOLUTION_LOW = 20
MESH_RESOLUTION_MEDIUM = 50
MESH_RESOLUTION_HIGH = 100
MESH_RESOLUTION_ULTRA = 200

# Calculation limits
MAX_ITERATIONS = 1000
CONVERGENCE_TOLERANCE = 1e-6

# ==================== Material Database Constants ====================

# Standard glass types
MATERIAL_BK7 = "BK7"
MATERIAL_FUSED_SILICA = "Fused Silica"
MATERIAL_SF11 = "SF11"
MATERIAL_CROWN_GLASS = "Crown Glass"

# ==================== Lens Types ====================

LENS_TYPE_BICONVEX = "Biconvex"
LENS_TYPE_BICONCAVE = "Biconcave"
LENS_TYPE_PLANO_CONVEX = "Plano-Convex"
LENS_TYPE_PLANO_CONCAVE = "Plano-Concave"
LENS_TYPE_MENISCUS_CONVEX = "Meniscus Convex"
LENS_TYPE_MENISCUS_CONCAVE = "Meniscus Concave"

ALL_LENS_TYPES = [
    LENS_TYPE_BICONVEX,
    LENS_TYPE_BICONCAVE,
    LENS_TYPE_PLANO_CONVEX,
    LENS_TYPE_PLANO_CONCAVE,
    LENS_TYPE_MENISCUS_CONVEX,
    LENS_TYPE_MENISCUS_CONCAVE
]

# ==================== Quality Assessment Constants ====================

# Quality score thresholds (0-100)
QUALITY_EXCELLENT_THRESHOLD = 85
QUALITY_GOOD_THRESHOLD = 70
QUALITY_FAIR_THRESHOLD = 50

# Quality ratings
QUALITY_RATING_EXCELLENT = "Excellent"
QUALITY_RATING_GOOD = "Good"
QUALITY_RATING_FAIR = "Fair"
QUALITY_RATING_POOR = "Poor"

# ==================== Mathematical Constants ====================

# Already defined in math module, but documented here for reference
# import math
# PI = math.pi
# E = math.e

# Common factors
FWHM_TO_SIGMA = 2.355  # Full Width Half Maximum to standard deviation
DEGREES_TO_RADIANS = 0.017453292519943295  # pi/180
RADIANS_TO_DEGREES = 57.29577951308232  # 180/pi

# ==================== Status Messages ====================

MSG_LENS_CREATED = "Lens created successfully"
MSG_LENS_UPDATED = "Lens updated successfully"
MSG_LENS_DELETED = "Lens deleted successfully"
MSG_INVALID_INPUT = "Invalid input. Please check your values."
MSG_CALCULATION_ERROR = "Error during calculation"
MSG_FILE_SAVED = "File saved successfully"
MSG_FILE_LOADED = "File loaded successfully"

# ==================== Export Constants ====================

# Image export
IMAGE_DPI_LOW = 72
IMAGE_DPI_MEDIUM = 150
IMAGE_DPI_HIGH = 300
IMAGE_DPI_PRINT = 600

# STL export
STL_BINARY = True
STL_ASCII = False
