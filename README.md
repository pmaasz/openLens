# openlens

<div align="center">

**An interactive optical lens design and simulation tool for single glass lens elements**

[![Python](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-41%20passing-brightgreen.svg)](docs/TESTING.md)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Documentation](#documentation) • [Testing](#testing) • [Contributing](#contributing)

</div>

---

## What is openlens?

openlens is a desktop application for designing and analyzing **single glass optical lenses**. Whether you're a student learning optics, an engineer designing optical systems, or a hobbyist exploring lens physics, openlens provides an intuitive interface to:

- Design optical lenses with precise physical parameters
- Calculate optical properties using the lensmaker's equation
- Experiment with different glass materials and geometries
- Store and manage your lens designs
- Visualize how lens parameters affect focal length and optical power

## Features

### 🔬 **Optical Design**
- Define lens geometry: radii of curvature, thickness, diameter
- Select from common optical materials (BK7, Fused Silica, Crown Glass, etc.)
- Support for all lens types: Biconvex, Biconcave, Plano-Convex, Plano-Concave, Meniscus

### 📊 **Real-Time Calculations**
- Automatic focal length calculation using lensmaker's equation
- Optical power display in diopters
- Instant updates as you modify parameters

### 🌈 **Ray Tracing Simulation** (New in v1.2!)
- Visual ray tracing through lens elements
- Snell's law physics simulation
- Parallel rays (collimated beam) and point source modes
- Automatic focal point detection and display
- Interactive controls for number of rays and angles
- See light actually bending through your lens design!

### 🔬 **Aberrations Analysis** (New in v1.1!)
- Calculate five primary (Seidel) aberrations
- Chromatic aberration with material-specific Abbe numbers
- Spherical aberration, coma, astigmatism, field curvature, distortion
- Automatic quality assessment and scoring
- Diffraction-limited resolution (Airy disk)
- Numerical aperture and F-number calculations
- Professional-grade optical analysis

### 🎨 **3D Visualization**
- Interactive 3D rendering of lens cross-section
- Real-time visualization updates
- Visualize spherical surfaces and lens geometry
- Rotate and zoom to inspect lens design
- Requires: matplotlib and numpy (optional)

### 💾 **Data Management**
- Save/load lens designs to JSON format
- Duplicate existing lenses for variations
- Full edit history with timestamps
- Import/export lens libraries

### 🖥️ **Two Interfaces**
- **GUI Version**: Full-featured graphical interface with forms and real-time calculations
- **CLI Version**: Command-line interface for quick operations and scripting

### ✅ **Fully Tested**
- 85+ functional tests covering all features
- Validated optical calculations
- Aberrations calculations verified
- Ray tracing physics validated
- Error handling and edge case testing

---

## Installation

### Prerequisites

**Core Requirements:**
- **Python 3.6 or higher**
- **tkinter** (for GUI version - usually included with Python)
- **X11 display server** (Linux) or native display (Windows/Mac)

**Optional Dependencies:**

| Package | Version | Features Enabled |
|---------|---------|------------------|
| matplotlib | ≥3.3.0 | 3D visualization, ray tracing plots |
| numpy | ≥1.19.0 | Numerical operations, ray tracing, STL export |
| scipy | ≥1.5.0 | Advanced diffraction calculations, image simulation |
| Pillow (PIL) | ≥8.0.0 | Image loading for image simulator |

**Note:** All optional dependencies are gracefully handled - the application will run with reduced functionality if they are not installed.

### Installing tkinter

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install python3-tk
```

**On Fedora/RHEL:**
```bash
sudo dnf install python3-tkinter
```

**On Arch Linux:**
```bash
sudo pacman -S tk
```

**On Windows/Mac:**
tkinter is included with Python by default.

### Method 1: Automated Setup (Recommended)

Use the provided setup script to automatically create and configure the virtual environment:

**Linux/macOS:**
```bash
./setup_venv.sh
source venv/bin/activate

# Install optional dependencies for full features (recommended)
pip install matplotlib numpy

# For advanced features (diffraction, image simulation)
pip install scipy Pillow
```

**Windows:**
```cmd
setup_venv.bat
venv\Scripts\activate

REM Install optional dependencies for full features (recommended)
pip install matplotlib numpy

REM For advanced features (diffraction, image simulation)
pip install scipy Pillow
```

The script will:
- Check Python installation
- Create virtual environment
- Verify tkinter availability
- Display activation instructions

**What works without optional dependencies:**
- ✅ All core lens calculations (focal length, optical power)
- ✅ Lens creation, editing, and management
- ✅ GUI interface
- ✅ Data persistence (JSON)
- ✅ Ray tracing (if numpy/matplotlib installed)
- ✅ Aberrations calculations
- ❌ 3D visualization (requires matplotlib + numpy)
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

3. **Install optional dependencies:**
   
   **For full features (recommended):**
   ```bash
   pip install matplotlib numpy
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

4. **Verify Python and tkinter:**
   ```bash
   python3 --version
   # Should show Python 3.6 or higher
   
   python3 -c "import tkinter; print('tkinter available')"
   ```

5. **Run the application:**
   ```bash
   # GUI version (recommended)
   python3 openlens.py
   
   # OR CLI version
   python3 -m src.lens_editor
   ```

6. **When done, deactivate virtual environment (if used):**
   ```bash
   deactivate
   ```

---

## Usage

### GUI Version (Recommended)

Launch the graphical interface:

```bash
python3 openlens.py
```

**Interface Overview:**

```
┌──────────────────────────────────────────────────────────────┐
│  openlens - Optical Lens Editor                             │
├─────────────────┬────────────────────────────────────────────┤
│ Optical Lenses  │  Optical Lens Properties                   │
│                 │                                            │
│ • Lens 1        │  ID: [                ]                    │
│ • Lens 2        │  Name: [                ]                  │
│ • Lens 3        │  ─────────────────────────                 │
│                 │  Radius of Curvature 1: [100.0] mm         │
│ [New] [Delete]  │  Radius of Curvature 2: [-100.0] mm        │
│ [Duplicate]     │  Center Thickness: [5.0] mm                │
│                 │  Diameter: [50.0] mm                       │
│                 │  Refractive Index: [1.5168]                │
│                 │  Type: [Biconvex ▼]                        │
│                 │  Material: [BK7 ▼]                         │
│                 │  ─────────────────────────                 │
│                 │  Created At: [2026-02-02T12:00:00]         │
│                 │  Modified At: [2026-02-02T12:30:00]        │
│                 │                                            │
│                 │  [Save] [Clear] [Calculate] [Auto-Update]  │
│                 │                                            │
│                 │  ┌──── Calculated Properties ────┐         │
│                 │  │ Focal Length: 97.58 mm        │         │
│                 │  │ Optical Power: 10.25 D        │         │
│                 │  └───────────────────────────────┘         │
└─────────────────┴────────────────────────────────────────────┘
```

**Workflow:**
1. Click **"New"** to create a new lens
2. Fill in the lens properties (name, radii, material, etc.)
3. Click **"Calculate Focal Length"** to see optical properties
4. Click **"Save"** to store the lens
5. Select a lens from the list to edit it
6. Use **"Duplicate"** to create variations of existing lenses

### Command-Line Version

Launch the terminal interface:

```bash
python3 -m src.lens_editor
```

**Menu Options:**
```
--- Menu ---
1. Create new lens
2. List all lenses
3. View lens details
4. Modify lens
5. Delete lens
6. Exit
```

**Example Session:**
```bash
$ python3 -m src.lens_editor

==================================================
   openlens - Optical Lens Creation Tool
==================================================

--- Menu ---
1. Create new lens
Select option: 1

=== Create New Optical Lens ===
Lens name: My Biconvex Lens
Radius of curvature 1 (mm) [100.0]: 100
Radius of curvature 2 (mm) [-100.0]: -100
Center thickness (mm) [5.0]: 5
Diameter (mm) [50.0]: 50
Refractive index [1.5168]: 1.5168
Type (Biconvex/Biconcave/etc) [Biconvex]: Biconvex
Material (BK7/Fused Silica/etc) [BK7]: BK7

✓ Lens created successfully!

Optical Lens Details:
  Name: My Biconvex Lens
  Focal Length: 97.58mm
  Material: BK7
  ...
```

---

## 3D Visualization

The GUI includes an interactive 3D visualization panel that displays the lens geometry in real-time.

### Features
- **Real-time rendering**: Updates automatically when you select or modify a lens
- **Interactive view**: Rotate, zoom, and pan the 3D model
- **Color-coded surfaces**: 
  - Blue: Front surface (R1)
  - Green: Back surface (R2)
  - Gray: Lens edge
  - Red dashed line: Optical axis

### Requirements
The 3D visualization requires matplotlib and numpy:
```bash
pip install matplotlib numpy
```

If these libraries are not installed, the application will still work but the 3D panel will show an installation message.

### Using the Visualization
1. Select or create a lens in the editor
2. The 3D view updates automatically
3. Click **"Update 3D View"** to manually refresh
4. Use mouse to rotate the view:
   - Left-click + drag: Rotate
   - Right-click + drag: Zoom
   - Middle-click + drag: Pan

### Testing the Visualization
Test the 3D rendering separately:
```bash
python test_visualization.py
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

### File Format

Lenses are stored in `lenses.json` in JSON format:

```json
[
  {
    "id": "20260202123456789012",
    "name": "My Biconvex Lens",
    "radius_of_curvature_1": 100.0,
    "radius_of_curvature_2": -100.0,
    "thickness": 5.0,
    "diameter": 50.0,
    "refractive_index": 1.5168,
    "type": "Biconvex",
    "material": "BK7",
    "created_at": "2026-02-02T12:00:00.123456",
    "modified_at": "2026-02-02T12:30:00.654321"
  }
]
```

### Backup and Export

To backup your lens library:
```bash
cp lenses.json lenses_backup_$(date +%Y%m%d).json
```

To share lenses with others, simply copy the `lenses.json` file.

---

## Testing

openlens includes comprehensive functional tests to ensure accuracy and reliability.

### Run All Tests

```bash
python3 tests/run_all_tests.py
```

### Test Coverage

- **41 total tests** covering:
  - ✅ Lens creation and properties
  - ✅ Optical calculations (lensmaker's equation)
  - ✅ Data persistence and JSON serialization
  - ✅ GUI operations and validation
  - ✅ Error handling and edge cases
  - ✅ Input validation

### Individual Test Suites

```bash
# Core functionality tests (24 tests)
python3 test_lens_editor.py

# GUI functionality tests (17 tests)
python3 test_gui.py
```

For detailed testing documentation, see [TESTING.md](docs/TESTING.md).

---

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
├── openlens.py              # Main entry point
├── src/                     # Source code directory
│   ├── __init__.py
│   ├── lens_editor.py       # CLI application
│   ├── lens_editor_gui.py   # GUI application
│   ├── lens_visualizer.py   # 3D visualization
│   └── stl_export.py        # STL export functionality
├── tests/                   # Test directory
│   ├── __init__.py
│   ├── run_all_tests.py     # Test runner
│   ├── test_lens_editor.py  # Core tests
│   ├── test_gui.py          # GUI tests
│   └── test_visualization.py # Visualization tests
├── lenses.json              # Data storage (auto-created)
├── verify_setup.py          # Setup verification script
├── README.md                # This file
├── docs/                    # Documentation
│   ├── PROJECT_SUMMARY.md   # Project overview
│   └── TESTING.md           # Testing documentation
```

---

## Troubleshooting

### Issue: "No display name and no $DISPLAY environment variable"

**Error:** `_tkinter.TclError: no display name and no $DISPLAY environment variable`

This occurs when running on a headless server or via SSH without X11 forwarding.

**Solutions:**
- **If using SSH**: Connect with X11 forwarding: `ssh -X user@host`
- **If running locally**: Ensure your display server is running (restart your desktop environment if needed)
- **For remote headless servers**: Use a virtual display:
  ```bash
  sudo apt-get install xvfb
  xvfb-run python3 openlens.py
  ```
- **WSL users**: Install an X server like VcXsrv or X410, then:
  ```bash
  export DISPLAY=:0
  python3 openlens.py
  ```

### Issue: tkinter not found

**Error:** `ModuleNotFoundError: No module named 'tkinter'`

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch Linux
sudo pacman -S tk

# macOS - reinstall Python from python.org
```

### Issue: Tests failing

**Solution:**
```bash
# Ensure you're in the project directory
cd /path/to/openLens

# Run tests with verbose output
python3 tests/run_all_tests.py
```

### Issue: Lenses not saving

**Solution:**
- Check write permissions in the directory
- Ensure `lenses.json` is not open in another program
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

### Areas for Enhancement

- [ ] Additional optical aberrations (higher-order)
- [ ] Import/export to other formats (Zemax, CODE V, etc.)
- [ ] Advanced multi-element optimization
- [ ] Polarization ray tracing
- [ ] Thermal analysis
- [ ] Manufacturing tolerancing

### Quick Start for Contributors

```bash
# 1. Fork the repository
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/openLens.git
cd openLens

# 3. Create a branch
git checkout -b feature/my-feature

# 4. Make changes and test
python3 tests/run_all_tests.py

# 5. Submit a pull request
```

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed instructions.

---

## License

This project is open source and available under the MIT License.

---

## Acknowledgments

- Lensmaker's equation implementation based on geometric optics principles
- Material refractive indices from standard optical glass catalogs
- Built with Python and tkinter

---

## Documentation

### Available Documentation

- **[README.md](README.md)** - This file: Getting started, features, usage
- **[API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)** - Complete API reference for library use
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design diagrams
- **[CONTRIBUTING.md](docs/CONTRIBUTING.md)** - Contributing guidelines and development workflow
- **[TESTING.md](docs/TESTING.md)** - Testing strategy and test coverage

### Quick Links

| I want to... | Read this... |
|--------------|--------------|
| Use openlens as a desktop app | [Usage](#usage) section above |
| Use openlens in my Python code | [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) |
| Understand the code structure | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Contribute to the project | [CONTRIBUTING.md](docs/CONTRIBUTING.md) |
| Run or write tests | [TESTING.md](docs/TESTING.md) |

---

## Contact & Support

For questions, issues, or suggestions:
- **Bug reports**: Create an issue with the `bug` label
- **Feature requests**: Create an issue with the `enhancement` label
- **Questions**: Open a discussion or issue with the `question` label
- **Security issues**: Contact maintainers directly (see repository)

### Useful Links
- [GitHub Issues](../../issues) - Report bugs and request features
- [API Documentation](docs/API_DOCUMENTATION.md) - Using openlens as a library
- [Architecture Guide](docs/ARCHITECTURE.md) - Understanding the codebase
- [Contributing Guide](docs/CONTRIBUTING.md) - How to contribute

---

<div align="center">

**Happy Lens Designing! 🔬**

*openlens - Making optical design accessible*

</div>
