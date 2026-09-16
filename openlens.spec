# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for OpenLens.

Bundles ALL runtime dependencies -- required AND optional -- so the
standalone executable has full functionality without `pip install`:

  Required:  PySide6
  Optional:  numpy, matplotlib, scipy, Pillow
  (see requirements.txt and src/dependencies.py)

PyInstaller static analysis cannot see the guarded / function-level /
string-based optional imports used throughout src/ (e.g. `__import__`
in src/dependencies.py, `from scipy.ndimage import ...` inside
functions, `from PIL import Image` inside dialogs), so they are listed
explicitly via collect_all() + hiddenimports below.

Build locally with:
    pyinstaller --noconfirm --clean openlens.spec
CI (release.yaml) mirrors these collects via CLI flags so the
per-platform APP_NAME (OpenLens-<tag>-<suffix>) keeps working.
"""

from PyInstaller.utils.hooks import collect_all

# Packages that must be bundled in full (binaries + data + hiddenimports).
# collect_all returns (datas, binaries, hiddenimports) per package.
_bundled_packages = ("PySide6", "numpy", "matplotlib", "scipy", "PIL")

_datas = []
_binaries = []
_hiddenimports = []

for _pkg in _bundled_packages:
    try:
        _d, _b, _h = collect_all(_pkg)
    except Exception as _e:  # optional dep not installed: warn, keep going
        print(f"WARNING: could not collect '{_pkg}': {_e}")
        continue
    _datas += _d
    _binaries += _b
    _hiddenimports += _h

# Dynamic / function-level imports PyInstaller cannot detect statically.
# Keep in sync with src/dependencies.py, src/image_simulator.py,
# src/diffraction.py, src/gui/dialogs/*, src/gui/widgets/lens_viz_3d.py.
_hiddenimports += [
    "numpy",
    "matplotlib",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt5agg",
    "matplotlib.figure",
    "matplotlib.axes",
    "matplotlib.patches",
    "matplotlib.pyplot",
    "scipy",
    "scipy.special",
    "scipy.ndimage",
    "scipy.signal",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
]


a = Analysis(
    ['openlens.py'],
    pathex=[],
    binaries=_binaries,
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OpenLens',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
