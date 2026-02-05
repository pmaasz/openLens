# Ray Tracing Guide for OpenLens

## Overview
The OpenLens application now includes a powerful ray tracing simulation that allows you to visualize how light rays travel through optical lenses. This guide explains how to use the ray tracing features in the GUI.

## Using Ray Tracing in the GUI

### Step 1: Select or Create a Lens
1. Open the OpenLens application
2. Go to the **"Lens Selection"** tab
3. Either:
   - Select an existing lens from the list, OR
   - Create a new lens using the **"Editor"** tab

### Step 2: Configure Simulation Parameters
1. Navigate to the **"Simulation"** tab
2. Set the simulation parameters:
   - **Number of Rays**: How many light rays to trace (recommended: 10-20)
     - Fewer rays = faster rendering, clearer visualization
     - More rays = more detailed, denser visualization
   - **Ray Angle**: Controls the type of ray source
     - `0°` = Parallel rays (collimated beam, like sunlight)
     - `>0°` = Point source rays (diverging from a point)

### Step 3: Run the Simulation
1. Click the **"Run Simulation"** button
2. The visualization will display:
   - **Lens outline** (light blue filled area with blue border)
   - **Optical axis** (dashed gray line)
   - **Ray paths** (colored lines showing light propagation)
     - Red = Edge rays (at the top and bottom of the lens)
     - Green = Center ray (along the optical axis)
     - Orange = Interior rays
   - **Focal point** (green circle, if rays converge)

### Step 4: Interpret the Results
The status bar will show:
- Number of rays traced
- Focal point location (if found)
- Any errors or warnings

## Understanding Ray Behavior

### Converging Lenses (Positive Focal Length)
**Examples**: Biconvex, Plano-Convex, Meniscus (with appropriate curvatures)

**Parallel Ray Behavior**:
- Rays entering parallel to the optical axis converge to a focal point
- Focal point location indicates the lens power
- Closer focal point = stronger lens

**Point Source Behavior**:
- Rays from a nearby point source are refocused to form an image
- Ray paths show how the lens bends light

### Diverging Lenses (Negative Focal Length)
**Examples**: Biconcave, Plano-Concave

**Parallel Ray Behavior**:
- Rays entering parallel spread out (diverge) after passing through
- No real focal point is formed
- Rays appear to originate from a virtual focal point behind the lens

**Point Source Behavior**:
- Source rays diverge even more after passing through
- Used for vision correction (nearsightedness) or beam expansion

## Optical Principles Demonstrated

### Snell's Law
The ray tracer implements Snell's law of refraction:
```
n₁ × sin(θ₁) = n₂ × sin(θ₂)
```
Where:
- n₁, n₂ = refractive indices of the two media
- θ₁, θ₂ = angles of incidence and refraction

### Ray Path Segments
Each ray visualization shows:
1. **Initial path**: Ray approaching the lens (straight line)
2. **First refraction**: Ray enters the lens (bends at front surface)
3. **Internal path**: Ray travels through lens material
4. **Second refraction**: Ray exits the lens (bends at back surface)
5. **Final path**: Ray continues after the lens

### Spherical Aberration
You may notice that edge rays don't converge to exactly the same point as center rays. This is **spherical aberration**, a real optical phenomenon where rays at different heights focus at different distances.

## Tips for Best Results

1. **Start Simple**: Begin with parallel rays (angle = 0°) to understand basic lens behavior
2. **Moderate Ray Count**: 10-15 rays provides good visualization without clutter
3. **Compare Lenses**: Try different lens types to see how curvature affects ray paths
4. **Edge Ray Analysis**: Watch the red edge rays to see maximum refraction effects
5. **Use Clear Simulation**: Click "Clear Simulation" to reset before trying new parameters

## Example Scenarios

### Scenario 1: Measuring Focal Length
1. Select a biconvex lens
2. Set rays = 10, angle = 0°
3. Run simulation
4. The green dot shows the focal point location
5. Compare measured focal length with theoretical value (shown in status)

### Scenario 2: Point Source Imaging
1. Select any converging lens
2. Set rays = 11, angle = 10° (or higher)
3. Run simulation
4. Observe how rays from a point source are refocused

### Scenario 3: Diverging Lens Behavior
1. Select a biconcave lens
2. Set rays = 15, angle = 0°
3. Run simulation
4. Notice rays spreading out after the lens
5. No focal point is formed (negative focal length)

## Advanced Features

### Aberrations Analysis
After running a simulation, you can:
1. Switch to the **"Aberrations"** tab
2. Click **"Analyze Aberrations"**
3. View detailed optical quality metrics including:
   - Spherical aberration
   - Chromatic aberration
   - Coma, astigmatism, distortion
   - Overall lens quality score

### Batch Analysis
Use the `demo_ray_tracing.py` script to generate multiple visualizations:
```bash
python3 demo_ray_tracing.py
```
This creates PNG images in the `ray_tracing_demos/` directory.

## Troubleshooting

**Problem**: "Simulation visualizer not available"
- **Solution**: Ensure matplotlib and numpy are installed: `pip install matplotlib numpy`

**Problem**: Rays go straight through without bending
- **Solution**: Check that the lens has non-zero curvatures and valid refractive index

**Problem**: No focal point found for converging lens
- **Solution**: This may indicate high spherical aberration or the focal point is outside the simulation bounds

**Problem**: Visualization is cluttered
- **Solution**: Reduce the number of rays to 5-10 for clearer paths

## Technical Details

### Ray Tracing Algorithm
- Uses geometric ray tracing with Snell's law
- Calculates surface normals from lens curvatures
- Propagates rays through air → glass → air transitions
- Detects ray-surface intersections analytically
- Handles total internal reflection

### Performance
- Typical simulation: <100ms for 20 rays
- Real-time updates in GUI
- Scales linearly with number of rays

### Coordinate System
- X-axis: Optical axis (position along light path)
- Y-axis: Height above optical axis
- Origin: Typically at lens center
- Units: millimeters (mm)

## References

For more information about the ray tracing implementation, see:
- `RAYTRACING_IMPLEMENTATION.md` - Technical implementation details
- `src/ray_tracer.py` - Source code with documentation
- `tests/test_ray_tracer.py` - Unit tests with examples

## Feedback and Issues

If you encounter issues or have suggestions for the ray tracing features, please report them in the project's issue tracker.

---

**Happy Ray Tracing!** 🔬✨
