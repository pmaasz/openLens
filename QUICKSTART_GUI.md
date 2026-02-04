# QUICK START: How to See Ray Tracing in the GUI

## Step-by-Step Instructions

### 1. Launch the Application
```bash
python3 openlens.py
```

### 2. Select or Create a Lens

**Option A: Use Existing Lens**
- Click the **"Lens Selection"** tab
- Double-click any lens in the list (e.g., "Sample Biconvex")

**Option B: Create New Lens**
- Click the **"Editor"** tab
- The form should already have default values
- Just click "Save Lens" to create a test lens
- Or modify the values first:
  - Radius 1: `100`
  - Radius 2: `-100`
  - Thickness: `10`
  - Diameter: `50`
  - Material: `BK7`

### 3. Go to Simulation Tab
- Click the **"Simulation"** tab
- You should now see:
  - A dark gray/black plot area with grid lines
  - X-axis labeled "Position (mm)"
  - Y-axis labeled "Height (mm)"
  - Title saying "Ray Tracing Simulation"
  - A horizontal dashed line (optical axis)

### 4. Set Simulation Parameters
- **Number of Rays**: Enter `11` (or any number between 5-20)
- **Ray Angle**: Enter `0` for parallel rays

### 5. Click "Run Simulation"
- Click the **"Run Simulation"** button
- You should immediately see:
  - **Blue lens shape** in the middle
  - **Colored rays** (red at edges, orange in middle)
  - **Ray paths** showing how light bends through the lens
  - **Status message** at bottom: "Ray tracing complete: 11 rays traced"

### 6. Try Different Configurations

**Experiment 1: More Rays**
- Change "Number of Rays" to `15`
- Click "Run Simulation" again
- See more detailed ray pattern

**Experiment 2: Point Source**
- Change "Ray Angle" to `10`
- Click "Run Simulation"
- See rays emanating from a point source (yellow star)

**Experiment 3: Different Lens**
- Go back to "Lens Selection"
- Select a different lens
- Return to "Simulation" tab
- Click "Run Simulation"
- Compare ray behavior

### 7. Clear and Reset
- Click **"Clear Simulation"** to reset the plot
- Try a new lens or new parameters

## What You Should See

### For Converging Lens (Biconvex, Plano-Convex):
```
   ray → → → → ╱╲ → → • (focal point)
   ray → → → ╱    ╲ → /
   ray → → ╱  lens  ╲ ←
```
- Rays converge to a green dot (focal point)
- Green vertical line at focal point
- Status shows: "Focal point at XXX mm"

### For Diverging Lens (Biconcave):
```
   ray → → → → ╲╱ → → → →
   ray → → → ╲    ╱ → → →
   ray → → ╲  lens  ╱ → →
```
- Rays spread apart after lens
- No focal point shown
- Rays diverge outward

## Troubleshooting

### Problem: "Thin black bar" instead of plot
**Solution**: 
- Make sure you're using the LATEST version of the code
- Run: `git pull` to get latest fixes
- Restart the application

### Problem: "Simulation visualizer not available"
**Solution**:
```bash
pip install matplotlib numpy
```

### Problem: Canvas is blank/gray
**Solution**:
- Make sure you've selected a lens first
- Check that lens has non-zero curvatures
- Try clicking "Run Simulation" again

### Problem: Rays go straight through
**Solution**:
- Lens might have zero curvature (flat)
- Create a lens with R1=100, R2=-100
- Make sure material refractive index > 1.0

### Problem: Status says "rays traced" but nothing visible
**Solution**:
- The canvas might not be updating
- Try clicking "Clear Simulation" then "Run Simulation" again
- Resize the window slightly to force a redraw

## Expected Performance

- Simulation should complete in < 1 second
- Canvas should update immediately after clicking "Run Simulation"
- You should see smooth ray paths (not jagged)
- Colors should be visible on dark background

## Test If It's Working

Run this test script separately:
```bash
python3 test_gui_simulation.py
```

This opens a simple window with just the simulation canvas.
Click "Run Simulation" and you should see rays immediately.
If this works but the main GUI doesn't, there might be a tab switching issue.

## Still Not Working?

1. Check Python version: `python3 --version` (should be 3.8+)
2. Check matplotlib: `python3 -c "import matplotlib; print(matplotlib.__version__)"`
3. Check if you're in venv: `which python3`
4. Look for error messages in terminal
5. Try: `rm -rf __pycache__ src/__pycache__` then restart

## Contact

If you still see a thin black bar after these steps, provide:
- Screenshot of the simulation tab
- Terminal output when starting the application
- Output of: `python3 test_gui_simulation.py`
