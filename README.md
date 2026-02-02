# OpenLense

<div align="center">

**An interactive optical lens design and simulation tool for single glass lens elements**

[![Python](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-41%20passing-brightgreen.svg)](TESTING.md)

[Features](#features) • [Installation](#installation) • [Usage](#usage) • [Documentation](#documentation) • [Testing](#testing)

</div>

---

## What is OpenLense?

OpenLense is a desktop application for designing and analyzing **single glass optical lenses**. Whether you're a student learning optics, an engineer designing optical systems, or a hobbyist exploring lens physics, OpenLense provides an intuitive interface to:

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

### 💾 **Data Management**
- Save/load lens designs to JSON format
- Duplicate existing lenses for variations
- Full edit history with timestamps
- Import/export lens libraries

### 🖥️ **Two Interfaces**
- **GUI Version**: Full-featured graphical interface with forms and real-time calculations
- **CLI Version**: Command-line interface for quick operations and scripting

### ✅ **Fully Tested**
- 41 functional tests covering all features
- Validated optical calculations
- Error handling and edge case testing

---

## Installation

### Prerequisites

- **Python 3.6 or higher**
- **tkinter** (for GUI version - usually included with Python)
- **No external dependencies!** All functionality uses Python standard library

### Quick Start

1. **Clone or download the repository:**
   ```bash
   git clone <repository-url>
   cd openLense
   ```

2. **Check requirements (optional):**
   ```bash
   cat requirements.txt
   # Note: No pip install needed - all dependencies are in standard library
   ```

3. **Verify Python installation:**
   ```bash
   python3 --version
   # Should show Python 3.6 or higher
   ```

4. **Check tkinter (for GUI):**
   ```bash
   python3 -c "import tkinter; print('tkinter available')"
   ```

   If tkinter is not available, install it:
   - **Ubuntu/Debian**: `sudo apt-get install python3-tk`
   - **Fedora**: `sudo dnf install python3-tkinter`
   - **macOS**: Included with Python from python.org
   - **Windows**: Included with standard Python installation

5. **Run the application:**
   ```bash
   # GUI version (recommended)
   python3 lens_editor_gui.py
   
   # OR CLI version
   python3 lens_editor.py
   ```

### Alternative: Make Scripts Executable

```bash
chmod +x lens_editor_gui.py lens_editor.py
./lens_editor_gui.py  # Run GUI
./lens_editor.py      # Run CLI
```

---

## Usage

### GUI Version (Recommended)

Launch the graphical interface:

```bash
python3 lens_editor_gui.py
```

**Interface Overview:**

```
┌──────────────────────────────────────────────────────────────┐
│  OpenLense - Optical Lens Editor                             │
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
python3 lens_editor.py
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
$ python3 lens_editor.py

==================================================
   OpenLense - Optical Lens Creation Tool
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

OpenLense uses the **thick lens lensmaker's equation** to calculate focal length:

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

OpenLense includes comprehensive functional tests to ensure accuracy and reliability.

### Run All Tests

```bash
python3 run_all_tests.py
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

For detailed testing documentation, see [TESTING.md](TESTING.md).

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
openLense/
├── lens_editor.py           # CLI application
├── lens_editor_gui.py       # GUI application
├── test_lens_editor.py      # Core tests
├── test_gui.py              # GUI tests
├── run_all_tests.py         # Test runner
├── lenses.json              # Data storage (auto-created)
├── README.md                # This file
└── TESTING.md               # Testing documentation
```

---

## Troubleshooting

### Issue: tkinter not found

**Error:** `ModuleNotFoundError: No module named 'tkinter'`

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# macOS - reinstall Python from python.org
```

### Issue: Tests failing

**Solution:**
```bash
# Ensure you're in the project directory
cd /path/to/openLense

# Run tests with verbose output
python3 run_all_tests.py
```

### Issue: Lenses not saving

**Solution:**
- Check write permissions in the directory
- Ensure `lenses.json` is not open in another program
- Check disk space

---

## Contributing

Contributions are welcome! Areas for enhancement:

- [ ] Lens aberration calculations
- [ ] Visual ray tracing diagrams
- [ ] Import/export to other formats (Zemax, etc.)
- [ ] Multi-element lens systems
- [ ] Coating specifications
- [ ] 3D lens visualization

---

## License

This project is open source and available under the MIT License.

---

## Acknowledgments

- Lensmaker's equation implementation based on geometric optics principles
- Material refractive indices from standard optical glass catalogs
- Built with Python and tkinter

---

## Contact & Support

For questions, issues, or suggestions:
- Create an issue in the repository
- Check [TESTING.md](TESTING.md) for testing details
- Review the code comments for implementation details

---

<div align="center">

**Happy Lens Designing! 🔬**

*OpenLense - Making optical design accessible*

</div>
