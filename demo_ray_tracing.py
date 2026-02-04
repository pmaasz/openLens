#!/usr/bin/env python3
"""
Demo script to visualize ray tracing through different lens types.
This script generates visual representations of how light rays behave
when passing through various lens configurations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from lens_editor import Lens
from ray_tracer import LensRayTracer
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for saving images

def create_demo_lenses():
    """Create a variety of lens types for demonstration"""
    lenses = []
    
    # 1. Biconvex lens (converging)
    lenses.append(Lens(
        name="Biconvex Converging",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=10.0,
        diameter=50.0,
        material="BK7"
    ))
    
    # 2. Plano-convex lens
    lenses.append(Lens(
        name="Plano-Convex",
        radius_of_curvature_1=150.0,
        radius_of_curvature_2=0.0,  # Flat back
        thickness=8.0,
        diameter=50.0,
        material="BK7"
    ))
    
    # 3. Biconcave lens (diverging)
    lenses.append(Lens(
        name="Biconcave Diverging",
        radius_of_curvature_1=-100.0,
        radius_of_curvature_2=100.0,
        thickness=5.0,
        diameter=50.0,
        material="BK7"
    ))
    
    # 4. Meniscus lens (converging)
    lenses.append(Lens(
        name="Meniscus Converging",
        radius_of_curvature_1=80.0,
        radius_of_curvature_2=-200.0,
        thickness=8.0,
        diameter=50.0,
        material="BK7"
    ))
    
    return lenses

def plot_ray_tracing(lens, num_rays=11, ray_type="parallel", save_path=None):
    """
    Plot ray tracing through a lens
    
    Args:
        lens: Lens object
        num_rays: Number of rays to trace
        ray_type: "parallel" or "point_source"
        save_path: Path to save the figure (optional)
    """
    # Create ray tracer
    tracer = LensRayTracer(lens)
    
    # Create figure with dark theme
    fig, ax = plt.subplots(figsize=(14, 8), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    # Trace rays based on type
    if ray_type == "parallel":
        rays = tracer.trace_parallel_rays(num_rays=num_rays)
        focal_point = tracer.find_focal_point(rays)
        title_suffix = "Parallel Rays (Collimated Beam)"
    else:
        source_x = -100.0
        source_y = 0.0
        rays = tracer.trace_point_source_rays(source_x, source_y, num_rays=num_rays, max_angle=20)
        focal_point = None
        title_suffix = "Point Source Rays"
        # Draw source point
        ax.plot(source_x, source_y, 'y*', markersize=20, label='Light Source', zorder=10)
    
    # Get lens outline
    lens_outline = tracer.get_lens_outline()
    
    # Draw lens
    if lens_outline:
        xs = [p[0] for p in lens_outline]
        ys = [p[1] for p in lens_outline]
        ax.fill(xs, ys, color='lightblue', alpha=0.4, label='Lens Body', zorder=3)
        ax.plot(xs, ys, color='#4fc3f7', linewidth=2.5, zorder=4)
    
    # Draw optical axis
    x_coords = [p[0] for ray in rays for p in ray.path]
    x_min = min(x_coords + [-120])
    x_max = max(x_coords + [150])
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.4, label='Optical Axis')
    
    # Draw rays with color gradient
    colors = plt.cm.hot(range(0, 256, 256//len(rays)))
    
    for i, ray in enumerate(rays):
        if len(ray.path) > 1:
            xs = [p[0] for p in ray.path]
            ys = [p[1] for p in ray.path]
            
            # Highlight edge and center rays
            if i == 0 or i == len(rays)-1:
                color = '#ff4444'  # Red for edge rays
                linewidth = 2.0
                alpha = 0.9
                label = 'Edge Rays' if i == 0 else None
            elif i == len(rays)//2:
                color = '#44ff44'  # Green for center ray
                linewidth = 2.0
                alpha = 0.9
                label = 'Center Ray'
            else:
                color = '#ffaa44'  # Orange for other rays
                linewidth = 1.5
                alpha = 0.6
                label = None
            
            ax.plot(xs, ys, color=color, linewidth=linewidth, alpha=alpha, 
                   label=label, zorder=5)
    
    # Draw focal point if found
    if focal_point:
        fx, fy = focal_point
        ax.plot(fx, fy, 'go', markersize=15, markeredgecolor='white',
               markeredgewidth=2, label=f'Focal Point\n({fx:.1f} mm)', zorder=6)
        
        # Draw vertical line at focal point
        ax.axvline(x=fx, color='green', linestyle=':', linewidth=2, alpha=0.6)
        
        # Calculate and display focal length
        focal_length = lens.calculate_focal_length()
        if focal_length:
            ax.text(0.02, 0.98, f'Theoretical f: {focal_length:.1f} mm\nMeasured f: {fx:.1f} mm',
                   transform=ax.transAxes, fontsize=11, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='#2e2e2e', alpha=0.8, edgecolor='#4fc3f7'),
                   color='#e0e0e0')
    else:
        focal_length = lens.calculate_focal_length()
        if focal_length:
            divergence_text = "Diverging lens" if focal_length < 0 else "Rays diverge (no focus)"
            ax.text(0.02, 0.98, f'Theoretical f: {focal_length:.1f} mm\n{divergence_text}',
                   transform=ax.transAxes, fontsize=11, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='#2e2e2e', alpha=0.8, edgecolor='#ff4444'),
                   color='#e0e0e0')
    
    # Set labels and title
    ax.set_xlabel('Position (mm)', fontsize=12, color='#e0e0e0', weight='bold')
    ax.set_ylabel('Height (mm)', fontsize=12, color='#e0e0e0', weight='bold')
    ax.set_title(f'Ray Tracing: {lens.name}\n{title_suffix} ({num_rays} rays)',
                fontsize=14, color='#e0e0e0', weight='bold', pad=20)
    
    # Style the plot
    ax.legend(loc='upper right', fontsize=10, facecolor='#2e2e2e', 
             edgecolor='#3f3f3f', labelcolor='#e0e0e0', framealpha=0.9)
    ax.grid(True, alpha=0.3, color='#3f3f3f', linestyle='-', linewidth=0.5)
    ax.set_aspect('equal')
    
    # Update tick colors
    ax.tick_params(colors='#e0e0e0', labelsize=10)
    for spine in ax.spines.values():
        spine.set_color('#3f3f3f')
        spine.set_linewidth(1.5)
    
    # Add lens specification text
    spec_text = (f'Diameter: {lens.diameter} mm\n'
                f'Thickness: {lens.thickness} mm\n'
                f'Material: {lens.material}\n'
                f'R1: {lens.radius_of_curvature_1} mm\n'
                f'R2: {lens.radius_of_curvature_2} mm')
    ax.text(0.98, 0.02, spec_text,
           transform=ax.transAxes, fontsize=9, verticalalignment='bottom',
           horizontalalignment='right',
           bbox=dict(boxstyle='round', facecolor='#2e2e2e', alpha=0.8, edgecolor='#3f3f3f'),
           color='#e0e0e0', family='monospace')
    
    plt.tight_layout()
    
    # Save or show
    if save_path:
        plt.savefig(save_path, dpi=150, facecolor='#1e1e1e', bbox_inches='tight')
        print(f"✓ Saved: {save_path}")
    else:
        plt.show()
    
    plt.close()

def main():
    """Generate ray tracing demonstrations for multiple lens types"""
    print("="*70)
    print("RAY TRACING VISUALIZATION DEMO")
    print("="*70)
    print()
    
    # Create output directory
    output_dir = "ray_tracing_demos"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}/")
    print()
    
    # Get demo lenses
    lenses = create_demo_lenses()
    
    # Generate visualizations for each lens
    for lens in lenses:
        print(f"Processing: {lens.name}")
        print(f"  Focal length: {lens.calculate_focal_length():.1f} mm" if lens.calculate_focal_length() else "  No optical power")
        
        # Parallel rays visualization
        filename_parallel = f"{output_dir}/{lens.name.lower().replace(' ', '_')}_parallel.png"
        plot_ray_tracing(lens, num_rays=15, ray_type="parallel", save_path=filename_parallel)
        
        # Point source visualization
        filename_point = f"{output_dir}/{lens.name.lower().replace(' ', '_')}_point_source.png"
        plot_ray_tracing(lens, num_rays=13, ray_type="point_source", save_path=filename_point)
        
        print()
    
    print("="*70)
    print("✓ All visualizations generated successfully!")
    print(f"✓ Check the '{output_dir}/' directory for PNG images")
    print("="*70)
    print()
    print("USAGE IN GUI:")
    print("1. Select a lens from the 'Lens Selection' tab")
    print("2. Go to the 'Simulation' tab")
    print("3. Set 'Number of Rays' (e.g., 10-20)")
    print("4. Set 'Ray Angle' (0° for parallel, >0° for point source)")
    print("5. Click 'Run Simulation' to see ray tracing")
    print("="*70)

if __name__ == "__main__":
    main()
