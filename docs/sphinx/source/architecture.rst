Architecture
============

This document provides a comprehensive architectural overview of the OpenLens 
optical design system.

.. contents:: Table of Contents
   :local:
   :depth: 2

System Overview
---------------

OpenLens is a modular optical design system consisting of:

1. **Core Lens Engine** - Fundamental lens calculations and data structures
2. **Analysis Modules** - Ray tracing, aberrations, performance metrics
3. **Material System** - Optical material database with dispersion models
4. **User Interfaces** - GUI and CLI frontends
5. **Export Systems** - STL, image rendering, data export

Design Philosophy
^^^^^^^^^^^^^^^^^

- **Modularity**: Independent modules with clear interfaces
- **Extensibility**: Easy to add new materials, lens types, or analysis methods
- **Accuracy**: Physics-based calculations with validated algorithms
- **Usability**: Both programmatic API and interactive interfaces

Architecture Diagrams
---------------------

High-Level System Architecture
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────────┐
   │                        User Interfaces                          │
   ├──────────────────────┬──────────────────────────────────────────┤
   │   GUI (Tkinter)      │   CLI Interface    │   Python API        │
   │   lens_editor_gui.py │   lens_editor.py   │   Direct Import     │
   └──────────────────────┴────────────────────┴─────────────────────┘
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                         Core Layer                              │
   ├─────────────────────────────────────────────────────────────────┤
   │                                                                 │
   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
   │  │     Lens     │  │ LensManager  │  │   Material   │         │
   │  │    Class     │  │   (Storage)  │  │   Database   │         │
   │  └──────────────┘  └──────────────┘  └──────────────┘         │
   │                                                                 │
   └─────────────────────────────────────────────────────────────────┘
                                    │
                       ┌────────────┼────────────┐
                       ▼            ▼            ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                      Analysis Modules                           │
   ├──────────────────┬──────────────────┬───────────────────────────┤
   │   Ray Tracing    │   Aberrations    │   Performance Metrics     │
   │  ray_tracer.py   │ aberrations.py   │  performance_metrics.py   │
   ├──────────────────┼──────────────────┼───────────────────────────┤
   │   Diffraction    │   Chromatic      │   Image Simulator         │
   │ diffraction.py   │chromatic_*.py    │  image_simulator.py       │
   └──────────────────┴──────────────────┴───────────────────────────┘
                                    │
                       ┌────────────┼────────────┐
                       ▼            ▼            ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                      Utility Modules                            │
   ├──────────────────┬──────────────────┬───────────────────────────┤
   │  Visualization   │   STL Export     │   Data Export             │
   │lens_visualizer.py│  stl_export.py   │  export_formats.py        │
   ├──────────────────┼──────────────────┼───────────────────────────┤
   │ Coating Designer │   Optimizer      │   Preset Library          │
   │coating_designer.py│ optimizer.py    │  preset_library.py        │
   └──────────────────┴──────────────────┴───────────────────────────┘
                                    │
                                    ▼
   ┌─────────────────────────────────────────────────────────────────┐
   │                      Data Persistence                           │
   ├─────────────────────────────────────────────────────────────────┤
   │         lenses.json  │  Configuration Files  │  Exports         │
   └─────────────────────────────────────────────────────────────────┘

Core Module Dependencies
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

                       ┌─────────────────┐
                       │  lens_editor.py │
                       │   (Core Lens)   │
                       └────────┬────────┘
                                │
                   ┌────────────┼────────────┐
                   ▼            ▼            ▼
           ┌──────────┐  ┌──────────┐  ┌──────────┐
           │ Material │  │   Ray    │  │Aberration│
           │ Database │  │  Tracer  │  │Calculator│
           └──────────┘  └──────────┘  └──────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │Optical System   │
                       │(Multi-element)  │
                       └─────────────────┘

Data Flow
^^^^^^^^^

Lens Creation and Analysis
""""""""""""""""""""""""""

.. code-block:: text

   ┌─────────┐
   │  User   │
   └────┬────┘
        │
        │ 1. Input Parameters
        ▼
   ┌─────────────────┐
   │  Lens Creator   │  ◄───── Material Database
   │ (GUI/CLI/API)   │
   └────┬────────────┘
        │
        │ 2. Validate & Create Lens Object
        ▼
   ┌─────────────────┐
   │   Lens Class    │
   │  - Properties   │
   │  - Calculations │
   └────┬────────────┘
        │
        │ 3. Analysis Request
        ├──────────────────┬────────────────┬──────────────────┐
        ▼                  ▼                ▼                  ▼
   ┌──────────┐    ┌─────────────┐  ┌──────────┐      ┌──────────┐
   │Focal     │    │Ray Tracer   │  │Aberration│      │Chromatic │
   │Length    │    │             │  │Calculator│      │Analyzer  │
   │Calc      │    │             │  │          │      │          │
   └────┬─────┘    └──────┬──────┘  └─────┬────┘      └─────┬────┘
        │                 │               │                 │
        │ 4. Results      │               │                 │
        └─────────────────┴───────────────┴─────────────────┘
                          │
                          ▼
                 ┌────────────────┐
                 │ Quality Report │
                 │   & Metrics    │
                 └────────┬───────┘
                          │
                          │ 5. Display/Export
                          ▼
                    ┌──────────┐
                    │  Output  │
                    │  (UI/File)│
                    └──────────┘

GUI Architecture
^^^^^^^^^^^^^^^^

.. code-block:: text

   ┌──────────────────────────────────────────────────────────────┐
   │                    Main Window (Tkinter)                     │
   ├──────────────────────────────────────────────────────────────┤
   │                                                              │
   │  ┌────────────────┐  ┌────────────────────────────────────┐ │
   │  │  Lens List     │  │    Property Panel                  │ │
   │  │  (Listbox)     │  │                                    │ │
   │  │                │  │  ┌─────────────────────────────┐   │ │
   │  │  • Lens 1      │  │  │  Entry Fields               │   │ │
   │  │  • Lens 2      │  │  │  - Name                     │   │ │
   │  │  • Lens 3      │  │  │  - R1, R2                   │   │ │
   │  │                │  │  │  - Thickness, Diameter      │   │ │
   │  │  [New]         │  │  │  - Material, Type           │   │ │
   │  │  [Delete]      │  │  └─────────────────────────────┘   │ │
   │  │  [Duplicate]   │  │                                    │ │
   │  │                │  │  ┌─────────────────────────────┐   │ │
   │  │                │  │  │  Calculated Properties      │   │ │
   │  │                │  │  │  - Focal Length: _____ mm   │   │ │
   │  └────────────────┘  │  │  - Optical Power: ____ D    │   │ │
   │         │            │  └─────────────────────────────┘   │ │
   │         │            │                                    │ │
   │         │            │  [Save] [Clear] [Calculate]       │ │
   │         │            └────────────────────────────────────┘ │
   │         │                                                   │
   │         └───────────────────────┐                          │
   │                                 │                          │
   │  ┌──────────────────────────────┴──────────────────────┐   │
   │  │          Tabbed Analysis Panel                      │   │
   │  ├─────────┬──────────┬──────────┬─────────────────────┤   │
   │  │ 3D View │Ray Trace │Aberration│Performance│Coating  │   │
   │  ├─────────┴──────────┴──────────┴─────────────────────┤   │
   │  │                                                      │   │
   │  │  [Dynamic Content Based on Selected Tab]            │   │
   │  │                                                      │   │
   │  └──────────────────────────────────────────────────────┘   │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘

   Event Flow:
     User Input → Validation → Update Lens Object → Trigger Calculations
        ↓                                                    ↓
     Display Errors                                    Update Results

Ray Tracing Pipeline
^^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   ┌─────────────┐
   │Initial Rays │
   │ (Parallel   │
   │  or Point)  │
   └──────┬──────┘
          │
          ▼
   ┌──────────────────────┐
   │ For Each Ray:        │
   │ 1. Check Aperture    │──→ Ray Blocked
   │ 2. Find Intersection │      ↓
   └──────┬───────────────┘   [Stop]
          │
          ▼
   ┌──────────────────────┐
   │ Surface Intersection │
   │ - Solve sphere eq    │
   │ - Calculate normal   │
   └──────┬───────────────┘
          │
          ▼
   ┌──────────────────────┐
   │ Apply Snell's Law    │
   │ n₁ sin θ₁ = n₂ sin θ₂│
   │ - Refract ray        │
   │ - Update direction   │
   └──────┬───────────────┘
          │
          ▼
   ┌──────────────────────┐
   │ Propagate Through    │
   │ Lens Thickness       │
   └──────┬───────────────┘
          │
          ▼
   ┌──────────────────────┐
   │ Second Surface       │
   │ - Intersection       │
   │ - Refraction         │
   └──────┬───────────────┘
          │
          ▼
   ┌──────────────────────┐
   │ Propagate to         │
   │ Image Plane          │
   └──────┬───────────────┘
          │
          ▼
   ┌──────────────────────┐
   │ Store Ray Path       │
   │ - All intersection   │
   │   points             │
   │ - Final direction    │
   └──────────────────────┘

Module Organization
-------------------

Directory Structure
^^^^^^^^^^^^^^^^^^^

.. code-block:: text

   openLens/
   │
   ├── openlens.py                    # Main entry point
   │
   ├── src/                           # Source code
   │   │
   │   ├── __init__.py               # Package initialization
   │   │
   │   ├── Core Modules:
   │   ├── lens.py                   # Lens class and calculations
   │   ├── lens_editor.py            # LensManager, CLI application
   │   ├── lens_editor_gui.py        # GUI application
   │   ├── material_database.py     # Optical materials
   │   ├── validation.py             # Input validation
   │   ├── constants.py              # Constants and configuration
   │   ├── services.py               # Service layer
   │   │
   │   ├── Analysis Modules:
   │   ├── ray_tracer.py             # Ray tracing engine
   │   ├── aberrations.py            # Seidel aberrations
   │   ├── chromatic_analyzer.py    # Chromatic aberration
   │   ├── diffraction.py            # Diffraction calculations
   │   ├── performance_metrics.py   # MTF, PSF, etc.
   │   │
   │   ├── Visualization:
   │   ├── lens_visualizer.py        # 3D rendering
   │   ├── interactive_ray_tracer.py # Interactive ray trace display
   │   ├── image_simulator.py        # Image formation
   │   │
   │   ├── Design Tools:
   │   ├── optical_system.py         # Multi-element systems
   │   ├── coating_designer.py       # Thin film coatings
   │   ├── optimizer.py              # Lens optimization
   │   ├── mechanical_designer.py   # Mechanical mounts
   │   │
   │   ├── Utilities:
   │   ├── stl_export.py             # 3D model export
   │   ├── export_formats.py         # Various export formats
   │   ├── preset_library.py         # Preset lenses
   │   ├── lens_comparator.py        # Compare lenses
   │   ├── polarization.py           # Polarization effects
   │   │
   │   └── gui/                      # GUI components package
   │       ├── __init__.py
   │       ├── tooltip.py            # Tooltip widget
   │       ├── theme.py              # Theme management
   │       ├── storage.py            # Persistence utilities
   │       ├── main_window.py        # Main window implementation
   │       └── tabs/                 # Tab implementations
   │           ├── __init__.py
   │           ├── base_tab.py       # Abstract base class
   │           ├── selection_tab.py  # Lens selection
   │           ├── editor_tab.py     # Lens editor
   │           ├── simulation_tab.py # Ray tracing
   │           └── aberrations_tab.py # Aberration analysis
   │
   ├── tests/                         # Test suite
   │   ├── run_all_tests.py
   │   ├── test_lens_editor.py
   │   ├── test_gui.py
   │   ├── test_ray_tracer.py
   │   └── test_aberrations.py
   │
   ├── docs/                          # Documentation
   │   └── sphinx/                   # Sphinx documentation
   │
   └── lenses.json                    # Data storage

Core Components
---------------

1. Lens Class
^^^^^^^^^^^^^

**File:** ``src/lens.py``, ``src/lens_editor.py``

**Responsibilities:**

- Store lens physical parameters
- Calculate optical properties (focal length, power)
- Serialize/deserialize to JSON
- Manage wavelength/temperature dependencies

**Key Methods:**

.. code-block:: python

   calculate_focal_length()     # Lensmaker's equation
   calculate_optical_power()    # Power in diopters
   to_dict() / from_dict()      # JSON serialization
   update_refractive_index()    # Dispersion handling

**Design Pattern:** Data Transfer Object (DTO)

2. Material Database
^^^^^^^^^^^^^^^^^^^^

**File:** ``src/material_database.py``

**Responsibilities:**

- Store optical material properties
- Calculate wavelength-dependent refractive index
- Temperature compensation
- Abbe number calculations

**Key Features:**

- Sellmeier dispersion formula
- Thermal coefficients (dn/dT)
- Standard optical glasses (BK7, SF11, etc.)
- Extensible material catalog

**Design Pattern:** Singleton + Repository Pattern

3. Ray Tracer
^^^^^^^^^^^^^

**File:** ``src/ray_tracer.py``

**Responsibilities:**

- Trace rays through optical surfaces
- Apply Snell's law refraction
- Handle aperture stops
- Find focal points

**Algorithm:**

1. Generate initial rays (parallel or point source)
2. For each ray:
   
   - Check aperture intersection
   - Find sphere intersection
   - Calculate surface normal
   - Apply Snell's law: ``n₁ sin θ₁ = n₂ sin θ₂``
   - Continue to next surface

3. Store ray paths for visualization

**Design Pattern:** Strategy Pattern (different ray sources)

4. Aberrations Calculator
^^^^^^^^^^^^^^^^^^^^^^^^^

**File:** ``src/aberrations.py``

**Responsibilities:**

- Calculate five Seidel aberrations
- Chromatic aberration (axial and lateral)
- Diffraction limit (Airy disk)
- Quality assessment and scoring

**Aberrations Computed:**

- **Spherical**: SA = (1/8) × (h⁴/f³) × ...
- **Coma**: Tangential coma at off-axis angles
- **Astigmatism**: Sagittal vs tangential focus difference
- **Field Curvature**: Petzval curvature
- **Distortion**: Percent image distortion

**Design Pattern:** Calculator Pattern

5. GUI Application
^^^^^^^^^^^^^^^^^^

**File:** ``src/lens_editor_gui.py``, ``src/gui/``

**Responsibilities:**

- User interface (Tkinter)
- Event handling
- Real-time calculations
- Visualization integration

**Components:**

- **Lens List Panel**: Browse/select lenses
- **Property Editor**: Input fields with validation
- **Results Display**: Calculated properties
- **Tabbed Panels**: 3D view, ray tracing, aberrations
- **Menu Bar**: File operations, help

**Design Pattern:** Model-View-Controller (MVC)

6. Optical System
^^^^^^^^^^^^^^^^^

**File:** ``src/optical_system.py``

**Responsibilities:**

- Manage multi-element systems
- Calculate system focal length
- Trace rays through multiple elements
- Element positioning and spacing

**Use Cases:**

- Doublet lenses (achromatic)
- Triplet designs
- Complex objective systems
- Telescope/microscope systems

**Design Pattern:** Composite Pattern

Design Patterns
---------------

1. Singleton Pattern
^^^^^^^^^^^^^^^^^^^^

- **MaterialDatabase**: Single instance shared across application
- **Usage**: ``get_material_database()`` returns singleton

2. Factory Pattern
^^^^^^^^^^^^^^^^^^

- **Lens Creation**: ``Lens.from_dict()`` creates lens from data
- **Preset Lenses**: ``preset_library.py`` creates standard designs

3. Strategy Pattern
^^^^^^^^^^^^^^^^^^^

- **Ray Sources**: Parallel rays vs point source
- **Export Formats**: STL, JSON, CSV

4. Observer Pattern
^^^^^^^^^^^^^^^^^^^

- **GUI Updates**: Property changes trigger recalculation
- **Auto-update Mode**: Real-time calculation updates

5. Repository Pattern
^^^^^^^^^^^^^^^^^^^^^

- **LensManager**: Abstracts data storage (JSON)
- **Future**: Could support SQL, cloud storage

6. Calculator Pattern
^^^^^^^^^^^^^^^^^^^^^

- **Aberrations**: Encapsulated calculation logic
- **Performance Metrics**: Separate calculators per metric

Extension Points
----------------

Adding New Materials
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # In material_database.py
   materials = {
       "Your_Material": {
           "refractive_index": 1.6234,
           "abbe_number": 57.5,
           "sellmeier_coefficients": {...},
           "thermal_coefficient": 2.5e-6
       }
   }

Adding New Analysis Modules
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Create new module: my_analysis.py
   class MyAnalyzer:
       def __init__(self, lens):
           self.lens = lens
       
       def analyze(self):
           # Your analysis logic
           return results

   # Integrate in GUI:
   # Add tab in lens_editor_gui.py
   # Import and instantiate MyAnalyzer

Adding New Lens Types
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # Extend Lens class
   def classify_lens_type(self):
       # Add new classification logic
       if self.is_my_new_type():
           return "MyNewType"
       # ... existing types

Adding Export Formats
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   # In export_formats.py
   def export_to_my_format(lens, filename):
       # Format-specific export logic
       with open(filename, 'w') as f:
           # Write data

Performance Considerations
--------------------------

Optimization Strategies
^^^^^^^^^^^^^^^^^^^^^^^

1. **Caching**: 
   
   - Lens calculations cached until properties change
   - Material database uses memoization

2. **Lazy Evaluation**:
   
   - Ray tracing only on demand
   - Aberrations calculated when requested

3. **Vectorization**:
   
   - NumPy arrays for ray tracing (batch processing)
   - Vectorized Snell's law calculations

4. **Progressive Rendering**:
   
   - 3D visualization uses level-of-detail
   - Ray count adjustable for speed vs accuracy

Memory Management
^^^^^^^^^^^^^^^^^

- Lens storage: ~1KB per lens (JSON)
- Ray tracing: ~100 bytes per ray × number of rays
- 3D meshes: ~10KB per lens at medium resolution

Security Considerations
-----------------------

Input Validation
^^^^^^^^^^^^^^^^

- All user inputs sanitized
- File operations validated (path traversal prevention)
- Numeric bounds checking

Data Integrity
^^^^^^^^^^^^^^

- JSON schema validation
- Checksum for exported files
- Backup before overwrite

Future Architecture Plans
-------------------------

Planned Enhancements
^^^^^^^^^^^^^^^^^^^^

1. **Plugin System**: 
   
   - Dynamic module loading
   - Third-party analysis tools

2. **Cloud Integration**:
   
   - Remote material databases
   - Lens library sharing

3. **GPU Acceleration**:
   
   - CUDA ray tracing
   - Parallel aberration calculations

4. **Web Interface**:
   
   - Browser-based GUI
   - REST API backend

5. **Machine Learning**:
   
   - Lens optimization with ML
   - Aberration prediction

References
----------

Optical Design Resources
^^^^^^^^^^^^^^^^^^^^^^^^

- **Optics textbooks**: Hecht, Born & Wolf
- **Lens design**: Smith, Kingslake
- **Ray tracing**: Spencer & Murty
- **Aberration theory**: Seidel, Hopkins

Software Architecture
^^^^^^^^^^^^^^^^^^^^^

- **Design Patterns**: Gang of Four
- **Clean Architecture**: Robert Martin
- **Modular Python**: Brett Slatkin
