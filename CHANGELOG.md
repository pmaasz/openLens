# Changelog

All notable changes to the openlens project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-02-04

### Added
- **Ray Tracing Visualization Engine**
  - Complete Snell's law implementation for refraction at lens surfaces
  - Ray class for tracking light ray position, direction, and path
  - LensRayTracer class for tracing rays through single lens elements
  - Parallel ray tracing (collimated beam mode)
  - Point source ray tracing with adjustable angles
  - Automatic focal point detection from ray convergence
  - Support for different wavelengths (foundation for chromatic dispersion)
  - Lens outline generation for visualization
  - Total internal reflection handling
  
- **Interactive Ray Tracing Simulation**
  - Integrated into Simulation tab in GUI
  - Control number of rays (1-50)
  - Control ray angle for point source mode
  - Visual display of ray paths through lens
  - Focal point visualization with marker and indicator line
  - Color-coded rays (edge rays in red, center rays in orange)
  - Real-time Snell's law physics simulation
  - "Run Simulation" and "Clear Simulation" buttons
  
- **Testing:**
  - 25+ comprehensive tests for ray tracer
  - Ray class tests (propagation, refraction, Snell's law)
  - LensRayTracer tests (parallel rays, point source, focal point)
  - Physical correctness tests (focal length accuracy, reversibility)
  - Edge case tests (rays missing lens, total internal reflection)
  
- **Visualization Features:**
  - Lens cross-section overlay on ray paths
  - Optical axis reference line
  - Focal point marker and label
  - Equal aspect ratio for accurate geometry
  - Grid and labels for measurement
  - Legend showing focal point location

### Changed
- Enhanced Simulation tab to support interactive ray tracing
- Updated GUI to include ray tracer import and availability check
- Improved simulation view with lens outline and ray paths
- Clear simulation now properly resets display

### Technical Details
- Implements geometric optics ray tracing
- Accurate spherical surface intersection calculations
- Proper handling of plano surfaces (flat)
- Quadratic equation solver for ray-sphere intersections
- Sign convention matches ISO 10110 standards

---

## [1.1.0] - 2026-02-04

### Added
- **Comprehensive Lens Aberrations Calculator**
  - Five primary (Seidel) aberrations: spherical, coma, astigmatism, field curvature, distortion
  - Chromatic aberration calculation with material-specific Abbe numbers
  - Diffraction-limited resolution (Airy disk diameter)
  - Numerical aperture and F-number calculations
  - Automatic quality assessment and scoring system
  - Aberrations analysis panel in Simulation tab
  - Field angle control for off-axis aberrations
  - Formatted aberration summary with interpretation
  - Material database with Abbe numbers (BK7, Fused Silica, Crown Glass, Flint Glass, SF11, Sapphire)
  
- **New Module:** `src/aberrations.py`
  - `AberrationsCalculator` class for complete aberration analysis
  - `analyze_lens_quality()` function for quality assessment
  - Mathematical formulas based on Seidel aberration theory
  
- **Testing:**
  - 20+ new tests for aberrations calculator
  - Test coverage for all aberration types
  - Material dependency tests
  - Field angle dependency tests
  - Quality analysis tests
  
- **Documentation:**
  - FEATURE_ABERRATIONS.md - Complete implementation guide
  - Mathematical foundations and formulas
  - Usage examples
  - Integration documentation

### Changed
- Enhanced Simulation tab with aberrations analysis section
- Improved GUI layout to accommodate new aberrations display
- Updated import structure to support optional aberrations module

### Technical Details
- Implements third-order (Seidel) aberration theory
- Uses thick lens formulas for accurate calculations
- Supports field angles from 0° to wide-field applications
- Quality scoring system (0-100) with automatic issue detection

---

## [1.0.0] - 2026-02-04

### Added
- Initial release of openlens
- **Optical Design Features:**
  - Define lens geometry: radii of curvature, thickness, diameter
  - Support for common optical materials (BK7, Fused Silica, Crown Glass, etc.)
  - Support for all lens types: Biconvex, Biconcave, Plano-Convex, Plano-Concave, Meniscus
  
- **Real-Time Calculations:**
  - Automatic focal length calculation using lensmaker's equation
  - Optical power display in diopters
  - Instant updates with auto-save functionality
  
- **3D Visualization:**
  - Interactive 3D rendering of lens cross-section
  - Real-time visualization updates
  - Rotate and zoom capabilities
  - Color-coded surfaces for easy identification
  - Dual-mode visualization (2D/3D toggle)
  
- **Data Management:**
  - Save/load lens designs to JSON format
  - Duplicate existing lenses for variations
  - Full edit history with timestamps
  - Automatic saving on field changes
  
- **Two Interfaces:**
  - GUI version with full-featured graphical interface
  - CLI version for command-line operations
  
- **STL Export:**
  - Export lens designs to STL format for 3D printing
  - Configurable mesh resolution
  
- **Comprehensive Testing:**
  - 39 functional tests covering all features
  - Validated optical calculations
  - Error handling and edge case testing
  - GUI and core functionality tests
  
- **Documentation:**
  - Complete README with usage instructions
  - Testing documentation (TESTING.md)
  - Project summary documentation
  - Setup verification scripts
  
### Technical Details
- Python 3.6+ support
- Zero required dependencies (tkinter included with Python)
- Optional matplotlib and numpy for 3D visualization
- Cross-platform support (Linux, Windows, macOS)
- Modular architecture with separate GUI, CLI, and core modules

### Known Limitations
- Single lens elements only (multi-element systems not supported)
- Basic lensmaker's equation (aberrations not calculated)
- Requires display server for GUI (X11, Wayland, etc.)

---

## Future Releases

See the README Contributing section for planned enhancements:
- Lens aberration calculations
- Visual ray tracing diagrams
- Import/export to other formats (Zemax, etc.)
- Multi-element lens systems
- Coating specifications
