# openlens v1.0.0 - Initial Release

## 🎉 Welcome to openlens!

We're excited to announce the first stable release of **openlens** - an interactive optical lens design and simulation tool for single glass lens elements.

## ✨ What's Included

### Core Features
- **Optical Design**: Define lens geometry with precise parameters (radii of curvature, thickness, diameter)
- **Material Library**: Support for common optical materials (BK7, Fused Silica, Crown Glass, Flint Glass, SF11, Sapphire)
- **Lens Types**: All standard types supported - Biconvex, Biconcave, Plano-Convex, Plano-Concave, Meniscus
- **Real-Time Calculations**: Automatic focal length and optical power calculations using the lensmaker's equation
- **Auto-Save**: Intelligent auto-save functionality - no more lost work!

### Visualization
- **3D Rendering**: Interactive 3D visualization of lens cross-sections
- **Dual-Mode Display**: Toggle between 2D and 3D views
- **Real-Time Updates**: See changes as you design
- **Color-Coded**: Surfaces color-coded for easy identification

### User Interfaces
- **GUI Application**: Full-featured graphical interface with forms, tabs, and real-time feedback
- **CLI Tool**: Command-line interface for quick operations and scripting

### Data Management
- **JSON Storage**: Simple, human-readable lens design files
- **Import/Export**: Share lens designs with colleagues
- **Duplication**: Create variations of existing designs quickly
- **Edit History**: Full timestamps on creation and modification

### STL Export
- **3D Printing Ready**: Export lens designs to STL format
- **Configurable**: Adjust mesh resolution for your needs

### Quality Assurance
- **39 Passing Tests**: Comprehensive test suite covering all functionality
- **Validated Calculations**: Optical calculations verified against known results
- **Error Handling**: Robust error detection and user feedback

## 📦 Installation

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd openLens

# Run the automated setup
./setup_venv.sh
source venv/bin/activate

# Install optional visualization support
pip install matplotlib numpy

# Launch the application
python3 openlens.py
```

### From PyPI (if published)
```bash
pip install openlens[visualization]
openlens
```

## 🚀 Getting Started

### GUI Version
```bash
python3 openlens.py
```

1. Click "New" to create a lens
2. Enter your design parameters
3. Watch the focal length calculate in real-time
4. View your lens in 3D
5. Your work auto-saves automatically

### CLI Version
```bash
python3 -m src.lens_editor
```

## 📊 What You Can Do

- Design converging and diverging lenses
- Calculate focal lengths from 10mm to 10,000mm
- Visualize lens geometry in 3D
- Export designs for 3D printing
- Build a library of reusable lens designs
- Learn optics principles through experimentation

## 🔬 Technical Details

- **Language**: Python 3.6+
- **Dependencies**: None required (tkinter included with Python)
- **Optional**: matplotlib and numpy for 3D visualization
- **Platforms**: Linux, Windows, macOS
- **Architecture**: Modular design with clean separation of concerns

## 📚 Documentation

- [README.md](README.md) - Complete usage guide
- [TESTING.md](docs/TESTING.md) - Testing documentation
- [PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) - Project overview
- [CHANGELOG.md](CHANGELOG.md) - Version history

## 🐛 Known Issues

None currently! If you find a bug, please report it in the issue tracker.

## 🤝 Contributing

We welcome contributions! Areas for enhancement:
- Lens aberration calculations
- Ray tracing visualization
- Multi-element lens systems
- Additional export formats (Zemax, etc.)
- Coating specifications

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with Python, tkinter, and the principles of geometric optics.

## 📈 Stats

- 📝 **Lines of Code**: ~2,500
- ✅ **Tests**: 39 passing
- 🎨 **Features**: 15+
- 📦 **Dependencies**: 0 required, 2 optional
- 🌟 **Lens Types**: 6 supported
- 🔬 **Materials**: 6 included

---

**Happy Lens Designing! 🔬**

*openlens - Making optical design accessible to everyone*
