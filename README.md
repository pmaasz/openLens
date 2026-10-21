# openLens

<div align="center">

**An interactive optical design and simulation tool for single lenses and multi-element systems**

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/pmaasz/openLens/actions/workflows/ci.yml/badge.svg)](https://github.com/pmaasz/openLens/actions/workflows/ci.yml)

</div>

---

## What is openlens?

openlens is a desktop application for designing and analyzing **glass optical
lenses and multi-element systems**. Whether you're a student learning optics, an
engineer designing optical systems, or a hobbyist exploring lens physics,
openlens provides an intuitive interface to:

- Design single lenses or assemblies with precise physical parameters
- Calculate first-order properties with thick-lens and paraxial models
- Experiment with different glass materials, surface profiles, and geometries
- Assign camera mounts and compute working flange distance
- Store and manage lenses, assemblies, and tolerance sets in SQLite
- Trace rays and inspect aberrations, spots, PSF/MTF, and wavefront error
- Export mechanical and manufacturing data as STL, STEP, or ISO 10110 drawings

## Documentation

The documentation is divided by audience:

- **User documentation** - [Getting Started](docs/sphinx/source/getting_started.rst)
  and the [User Guide](docs/sphinx/source/user_guide.rst).
- **Technical documentation** - [Architecture](docs/sphinx/source/architecture.rst),
  [Contributing](docs/sphinx/source/contributing.rst), and the
  [API reference](docs/sphinx/source/api/index.rst).
- **Scientific documentation** - [optical model](docs/sphinx/source/scientific/optics.rst),
  [image quality](docs/sphinx/source/scientific/image_quality.rst), and
  [thermal/mechanical effects](docs/sphinx/source/scientific/thermal_mechanical.rst).

Build the full Sphinx site with `cd docs/sphinx && make html`.

## Features

### **Optical Design**
- Single lenses and multi-element assemblies with air gaps and an aperture stop
- Spherical, conic, parabolic, and Fresnel surface profiles
- Clear apertures, bevels, and per-surface coating stacks
- Camera mounts with working-flange-distance calculation
- Material catalog with Sellmeier dispersion and thermal data
- Biconvex, biconcave, plano-convex, plano-concave, and meniscus lenses

### **Ray Tracing Simulation**
- 2-D and 3-D ray tracing with Snell's law and total internal reflection
- Parallel fans, point sources, off-axis fields, and multiple wavelengths
- Ghost reflections and stray-light paths
- Automatic focal-point detection and interactive controls

### **Aberrations and Image Quality**
- Five primary (Seidel) aberrations and chromatic estimates
- Spot diagrams, ray fans, field curves, and encircled energy
- PSF, MTF, wavefront error, Strehl ratio, and Airy-disk metrics
- Explicit `None` results when a trace or wavefront sample fails

### **3D Visualization**
- Interactive 2-D and 3-D lens and assembly views
- Real-time ray-path and optical-layout visualization
- Mechanical assembly visualization

### **Professional Capabilities**
- **Optimization:** Simplex and global search, plus desensitization for manufacturability.
- **Tolerancing:** Monte Carlo analysis and inverse sensitivity to predict manufacturing yield.
- **Advanced analysis:** Ghost analysis, beam synthesis, and diffraction PSF/MTF.
- **Interoperability:** STL, STEP, ISO 10110 drawings, reports, and JSON interchange.

---

## Installation

### Standalone executables (no Python required)

Every [release](https://github.com/pmaasz/openLens/releases/latest) includes
standalone builds for the desktop platforms:

| Platform | Download |
|----------|----------|
| Windows | `OpenLens-<version>-Windows.exe` |
| macOS (Apple silicon) | `OpenLens-<version>-macOS-arm64.zip` |
| macOS (Intel) | `OpenLens-<version>-macOS-x64.zip` |
| Linux | `OpenLens-<version>-Linux` |

Unzip a macOS download and drag `OpenLens.app` to Applications. The builds are
not code-signed, so the first launch needs **right-click -> Open** (or
**System Settings -> Privacy & Security -> Open Anyway**). On Linux, make the
downloaded file executable with `chmod +x`.

### Prerequisites

**Core Requirements:**
- **Python 3.10 or higher** (CI tests 3.10-3.12; `python_requires` in `setup.py` is the authority)
- **PySide6 ≥ 6.2** (GUI framework - installed via pip)
- **X11 display server** (Linux) or native display (Windows/Mac)

**Recommended Dependencies:**

| Package | Version | Features Enabled |
|---------|---------|------------------|
| numpy | ≥1.19.0 | Numerical operations, ray tracing, STL export |
| matplotlib | ≥3.3.0 | Plots, analysis dialogs |

**Optional Dependencies:**

| Package | Version | Features Enabled |
|---------|---------|------------------|
| scipy | ≥1.5.0 | Advanced diffraction calculations, image simulation |
| Pillow (PIL) | ≥8.0.0 | Image loading for image simulator |

**Note:** The recommended/optional dependencies are gracefully handled - the application will run with reduced functionality if they are not installed.

### Installing PySide6

```bash
pip install PySide6
```
(or simply `pip install -r requirements.txt`)

### Method 1: Automated Setup (Recommended)

Use the provided setup script to automatically create and configure the virtual environment:

**Linux/macOS:**
```bash
./setup_venv.sh
source venv/bin/activate

# Install OpenLens in editable mode
pip install -e .

# Install optional dependencies for full features (recommended)
pip install -e .[visualization]

# For advanced features (diffraction, image simulation)
pip install scipy Pillow
```

**Windows:**
```cmd
setup_venv.bat
venv\Scripts\activate

REM Install OpenLens in editable mode
pip install -e .

REM Install optional dependencies for full features (recommended)
pip install -e .[visualization]

REM For advanced features (diffraction, image simulation)
pip install scipy Pillow
```

The script will:
- Check Python installation
- Create virtual environment
- Display activation instructions

**What works without optional dependencies:**
- ✅ All core lens calculations (focal length, optical power)
- ✅ Lens creation, editing, and management
- ✅ GUI interface (PySide6)
- ✅ Data persistence (SQLite)
- ⚠️ Ray tracing and analysis plots need numpy/matplotlib
- ❌ Advanced diffraction calculations with Bessel functions (requires scipy)
- ❌ Image simulation (requires scipy + Pillow)

### Method 2: Manual Setup

1. **Clone or download the repository:**
   ```bash
   git clone <repository-url>
   cd openLens
   ```

2. **Set up virtual environment (recommended):**
   ```bash
   # Create virtual environment
   python3 -m venv venv

   # Activate virtual environment
   # On Linux/macOS:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate
   ```

3. **Install OpenLens and optional dependencies:**

   ```bash
   # Install the package and its required PySide6 dependency
   pip install -e .

   # Full plotting and numerical features (recommended)
   pip install -e .[visualization]
   ```

   **For advanced features:**
   ```bash
   pip install scipy Pillow
   ```

   **Or install all optional dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   Note: The application works without these, with features gracefully disabled.

4. **Verify Python and PySide6:**
   ```bash
   python3 --version
   # Should show Python 3.10 or higher

   python3 -c "import PySide6; print('PySide6 available')"
   ```

5. **Run the application:**
   ```bash
   # GUI version (recommended)
   python3 -m openlens

   # OR CLI version
   python3 -m openlens.lens_editor
   ```

6. **When done, deactivate virtual environment (if used):**
   ```bash
   deactivate
   ```

---

## Lens Properties Explained

### Physical Properties

| Property | Description | Units | Sign Convention |
|----------|-------------|-------|----------------|
| **Radius of Curvature 1 (R1)** | Front surface radius | mm | Positive = convex, Negative = concave |
| **Radius of Curvature 2 (R2)** | Back surface radius | mm | Positive = convex, Negative = concave |
| **Center Thickness** | Thickness at optical center | mm | Always positive |
| **Diameter** | Physical lens diameter | mm | Always positive |
| **Refractive Index (n)** | Material's refractive index | dimensionless | > 1.0 |

### Lens Types

<details>
<summary><b>Click to expand lens type descriptions</b></summary>

- **Biconvex**: Both surfaces curve outward (R1 > 0, R2 < 0)
  - Use: General magnification, converging light

- **Biconcave**: Both surfaces curve inward (R1 < 0, R2 > 0)
  - Use: Diverging light, beam expansion

- **Plano-Convex**: One flat, one convex surface (R1 or R2 = ∞)
  - Use: Focusing, collimation

- **Plano-Concave**: One flat, one concave surface
  - Use: Light divergence, beam expansion

- **Meniscus Convex**: Crescent shape, thicker at center
  - Use: Correcting aberrations

- **Meniscus Concave**: Crescent shape, thinner at center
  - Use: Special optical applications

</details>

### Common Optical Materials

| Material | Refractive Index (n) | Typical Uses |
|----------|---------------------|--------------|
| **BK7** (Borosilicate Crown Glass) | 1.5168 | General purpose optics |
| **Fused Silica** | 1.4585 | UV applications, high precision |
| **Crown Glass** | 1.52 | Low-cost optics |
| **Flint Glass** | 1.6 - 1.7 | High refractive power |
| **SF11** (Dense Flint) | 1.78 | Compact optical systems |
| **Sapphire** | 1.77 | Durable, scratch-resistant |

---

## The Lensmaker's Equation

openlens uses the **thick lens lensmaker's equation** to calculate focal length:

```
1/f = (n-1) * [1/R1 - 1/R2 + (n-1)*d/(n*R1*R2)]
```

**Where:**
- `f` = focal length (mm)
- `n` = refractive index of the lens material
- `R1` = radius of curvature of the front surface (mm)
- `R2` = radius of curvature of the back surface (mm)
- `d` = center thickness (mm)

**Sign Convention:**
- Positive radius → surface curves toward object (convex)
- Negative radius → surface curves away from object (concave)
- Positive focal length → converging lens
- Negative focal length → diverging lens

**Optical Power:**
```
P = 1/f  (in mm⁻¹)
P = 1000/f  (in diopters, D)
```

---

## Data Storage

### Database Format

Lenses and optical systems are stored in `openlens.db` using SQLite for robust, relational data management. This ensures data integrity and supports complex relationships between lenses and assemblies.

### Exporting and Sharing

While the main database is SQLite, use **File → Save As...** to export the
active lens or assembly as JSON for sharing. **File → Export** provides STL,
STEP, ISO 10110, and report output.

To backup your entire lens library, simply copy the database file:
```bash
cp openlens.db openlens_backup_$(date +%Y%m%d).db
```

---

## Testing

openlens includes comprehensive functional tests to ensure accuracy and reliability.

### Run All Tests

```bash
python3 -m unittest discover -s tests -t .

# Skip slow/integration suites for a quick pass
OPENLENS_SKIP_SLOW=1 python3 -m unittest discover -s tests -t .

# Parallel execution (requires pytest + pytest-xdist: pip install -e .[dev])
pytest -n auto tests/
```

## Examples

### Example 1: Standard Biconvex Lens

**Design a basic converging lens:**
- Material: BK7 (n = 1.5168)
- R1: 100 mm (convex)
- R2: -100 mm (convex)
- Thickness: 5 mm
- Diameter: 50 mm

**Result:** Focal length ≈ 97.6 mm

### Example 2: Plano-Convex Lens

**Design a simple focusing lens:**
- Material: Fused Silica (n = 1.4585)
- R1: 50 mm (convex)
- R2: ∞ (flat) - use a very large value like 10000
- Thickness: 4 mm
- Diameter: 25 mm

**Result:** Focal length ≈ 109 mm

### Example 3: High-Power Lens

**Design a strong converging lens:**
- Material: SF11 (n = 1.78)
- R1: 30 mm (strongly convex)
- R2: -40 mm (strongly convex)
- Thickness: 8 mm
- Diameter: 20 mm

**Result:** Short focal length for compact systems

---

## Project Structure

```
openLens/
├── openlens/__main__.py              # PySide6 GUI entry point (main window)
├── openlens/                     # Source package
│   ├── __init__.py
│   ├── lens.py              # Core Lens model
│   ├── optical_system.py    # Multi-element systems
│   ├── lens_editor.py       # CLI application + LensManager
│   ├── ray_tracer.py        # 2D/3D ray tracing engine
│   ├── aberrations.py       # Seidel aberrations
│   ├── optimizer.py         # Lens optimization engine
│   ├── tolerancing.py       # Monte Carlo / sensitivity analysis
│   ├── database.py          # SQLite persistence
│   ├── validation.py        # Input validation
│   ├── services.py          # Service layer
│   ├── constants.py         # Constants and configuration
│   ├── gui/                 # GUI implementation (widgets/, tabs/, dialogs/, theme.py)
│   ├── analysis/            # Spot diagram, PSF/MTF, ghost, wavefront
│   └── io/                  # STEP / ISO 10110 export
├── tests/                   # unittest test suites (~56 files)
├── openlens.db              # Data storage (SQLite, created on first run)
├── requirements.txt         # Runtime dependencies
└── setup.py                 # Package distribution (pip install -e .)
```

---

## Troubleshooting

### Issue: "No display name and no $DISPLAY environment variable" / Qt platform plugin errors

This occurs when running on a headless server or via SSH without X11 forwarding.

**Solutions:**
- **If using SSH**: Connect with X11 forwarding: `ssh -X user@host`
- **If running locally**: Ensure your display server is running (restart your desktop environment if needed)
- **For remote headless servers**: Use a virtual display:
  ```bash
  sudo apt-get install xvfb
  xvfb-run python3 -m openlens
  ```
  or force Qt's offscreen platform for testing:
  ```bash
  QT_QPA_PLATFORM=offscreen python3 -m openlens
  ```
- **WSL users**: Install an X server like VcXsrv or X410, then:
  ```bash
  export DISPLAY=:0
  python3 -m openlens
  ```

### Issue: PySide6 not found

**Error:** `ModuleNotFoundError: No module named 'PySide6'`

**Solution:**
```bash
pip install PySide6
# or
pip install -r requirements.txt
```

### Issue: Lenses not saving

**Solution:**
- Check write permissions in the directory
- Ensure `openlens.db` is not locked by another process
- Check disk space

### Issue: 3D visualization not working

**Solution:**
```bash
# Install required dependencies
pip install matplotlib numpy

# Or if using venv:
source venv/bin/activate
pip install matplotlib numpy
```

---

## Contributing

Contributions are welcome! We appreciate bug fixes, new features, documentation improvements, and more.

### How to Contribute

Please read our comprehensive [Contributing Guidelines](docs/CONTRIBUTING.md) for:
- Code of conduct
- Development setup
- Coding standards
- Testing requirements
- Pull request process
- Issue guidelines

### Quick Start for Contributors

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/openLens.git
cd openLens

# 3. Create a branch (branch names start with the ticket number)
git checkout -b 223-vertex-collapse

# 4. Make changes and test
python3 -m unittest discover -s tests -t .

# 5. Submit a pull request
```

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed instructions.

---

## License

This project is open source and available under the MIT License.

---

## Contact & Support

For questions, issues, or suggestions:
- **Bug reports**: Create an issue with the `bug` label
- **Feature requests**: Create an issue with the `enhancement` label
- **Questions**: Open a discussion or issue with the `question` label
- **Security issues**: Contact maintainers directly (see repository)

---

<div align="center">

**Happy Lens Designing! 🔬**

*openlens - Making optical design accessible*

</div>
