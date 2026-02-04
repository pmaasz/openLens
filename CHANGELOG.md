# Changelog

All notable changes to the openlens project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
