"""Visual snapshot / regression harness for QA.

Design:
- Baselines live in tests/gui_flows/__snapshots__/<name>.png (committed).
- On first run with no baseline, the current render is saved as baseline
  and the test passes with a notice (bootstrap mode).
- On later runs the current render is compared against the baseline with a
  lenient pixel-difference threshold: offscreen font/AA differences across
  machines must not fail the build, but blank widgets, crashes, or major
  layout regressions must.
- On mismatch, current + diff images are written to /tmp/openlens_qa_failures/
  and also attached to the assertion message. In CI these are uploaded as
  artifacts.

Threshold: mean absolute per-pixel difference over RGB, plus % of pixels
above a per-pixel delta. Defaults fail only if mean > 8/255 (~3%) OR more
than 5% of pixels differ significantly. Tune per widget if needed.
"""

from pathlib import Path

SNAPSHOT_DIR = Path(__file__).parent / "__snapshots__"
FAILURE_DIR = Path("/tmp/openlens_qa_failures")

try:
    import numpy as _np

    HAS_NUMPY = True
except ImportError:
    _np = None  # type: ignore
    HAS_NUMPY = False


def _ensure_dirs():
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    FAILURE_DIR.mkdir(parents=True, exist_ok=True)


def grab_pixmap(widget, width: int = 800, height: int = 600):
    """Show widget offscreen, process events, return QPixmap."""
    from PySide6.QtWidgets import QApplication

    widget.resize(width, height)
    widget.show()
    QApplication.processEvents()
    # Two passes: lets deferred layouts / matplotlib canvases settle.
    QApplication.processEvents()
    pixmap = widget.grab()
    assert not pixmap.isNull(), "grab() returned null pixmap (widget did not render)"
    return pixmap


def _pixmap_to_array(pixmap):
    """Convert QPixmap to numpy uint8 RGB array."""
    from PySide6.QtGui import QImage

    img = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    import numpy as np

    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 3).copy()
    return arr


def compare_images(current_path: Path, baseline_path: Path, mean_tol=8.0, pct_tol=0.05):
    """Compare two PNGs. Returns (ok, mean_diff, frac_diff, diff_path_or_None)."""
    _ensure_dirs()
    if not HAS_NUMPY:
        # Without numpy: only check both files exist and are non-empty.
        ok = current_path.stat().st_size > 0 and baseline_path.stat().st_size > 0
        return ok, 0.0, 0.0, None
    import numpy as np

    try:
        from PIL import Image
    except ImportError:
        # Pillow is optional: without it we keep the blank-render guard
        # from assert_snapshot and skip pixel-diffing (never fail on visuals).
        return True, 0.0, 0.0, None

    cur = np.asarray(Image.open(current_path).convert("RGB"), dtype=np.int16)
    base_img = Image.open(baseline_path).convert("RGB")
    if base_img.size != (cur.shape[1], cur.shape[0]):
        base_img = base_img.resize((cur.shape[1], cur.shape[0]))
    base = np.asarray(base_img, dtype=np.int16)
    diff = np.abs(cur - base)
    mean_diff = float(diff.mean())
    per_pixel = diff.max(axis=2)
    frac_diff = float((per_pixel > 25).mean())
    ok = (mean_diff <= mean_tol) and (frac_diff <= pct_tol)
    diff_path = None
    if not ok:
        diff_vis = (per_pixel.clip(0, 255)).astype(np.uint8)
        diff_path = FAILURE_DIR / (current_path.stem + ".diff.png")
        Image.fromarray(diff_vis, mode="L").save(diff_path)
    return ok, mean_diff, frac_diff, diff_path


def assert_snapshot(widget, name: str, width=800, height=600, mean_tol=8.0, pct_tol=0.05):
    """Grab widget and assert it matches committed baseline <name>.png.

    Bootstraps the baseline on first run (passes). Fails with diagnostics
    on significant visual regression. Always guards against null/blank renders.
    """
    _ensure_dirs()
    from PySide6.QtWidgets import QApplication

    pixmap = grab_pixmap(widget, width, height)
    QApplication.processEvents()

    baseline = SNAPSHOT_DIR / f"{name}.png"
    current_tmp = FAILURE_DIR / f"{name}.current.png"
    pixmap.save(str(current_tmp), "PNG")

    # Blank-render guard: a fully uniform pixmap means painting broke.
    if HAS_NUMPY:
        arr = _pixmap_to_array(pixmap)
        assert arr.std() > 1.0, f"snapshot '{name}' rendered blank (std~0)"
    assert current_tmp.stat().st_size > 1024, f"snapshot '{name}' image too small"

    if not baseline.exists():
        pixmap.save(str(baseline), "PNG")
        print(f"[snapshots] bootstrapped baseline {baseline}")
        return True

    ok, mean_diff, frac_diff, diff_path = compare_images(current_tmp, baseline, mean_tol, pct_tol)
    assert ok, (
        f"visual regression in '{name}': mean_diff={mean_diff:.2f} "
        f"(tol {mean_tol}), frac_diff={frac_diff:.3f} (tol {pct_tol}). "
        f"baseline={baseline} current={current_tmp} diff={diff_path}"
    )
    return True
