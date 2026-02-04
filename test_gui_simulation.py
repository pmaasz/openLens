#!/usr/bin/env python3
"""
Test script to verify GUI simulation tab is working
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import tkinter as tk
from tkinter import ttk
from lens_editor import Lens
from ray_tracer import LensRayTracer

# Check if matplotlib is available
try:
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False
    print("ERROR: matplotlib not available!")
    sys.exit(1)

print("="*70)
print("TESTING GUI SIMULATION TAB")
print("="*70)

# Create a test window
root = tk.Tk()
root.title("Simulation Test")
root.geometry("800x600")

# Create a frame for the simulation
sim_frame = ttk.LabelFrame(root, text="Ray Tracing Test", padding="10")
sim_frame.pack(fill='both', expand=True, padx=10, pady=10)

# Create matplotlib canvas
print("Creating matplotlib figure...")
sim_figure = Figure(figsize=(10, 5), dpi=100, facecolor='#1e1e1e')
sim_figure.subplots_adjust(left=0.08, right=0.95, top=0.93, bottom=0.10)
sim_ax = sim_figure.add_subplot(111, facecolor='#1e1e1e')

# Draw initial empty plot
sim_ax.set_xlim(-100, 150)
sim_ax.set_ylim(-30, 30)
sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.3)
sim_ax.set_xlabel('Position (mm)', fontsize=10, color='#e0e0e0')
sim_ax.set_ylabel('Height (mm)', fontsize=10, color='#e0e0e0')
sim_ax.set_title('Ray Tracing Test - Click "Run" to trace rays', 
                 fontsize=12, color='#e0e0e0')
sim_ax.grid(True, alpha=0.2, color='#3f3f3f')
sim_ax.set_aspect('equal')

# Style
sim_ax.tick_params(colors='#e0e0e0', labelsize=9)
sim_ax.spines['bottom'].set_color('#3f3f3f')
sim_ax.spines['top'].set_color('#3f3f3f')
sim_ax.spines['left'].set_color('#3f3f3f')
sim_ax.spines['right'].set_color('#3f3f3f')

# Create canvas
print("Creating canvas widget...")
sim_canvas = FigureCanvasTkAgg(sim_figure, sim_frame)
sim_canvas_widget = sim_canvas.get_tk_widget()
sim_canvas_widget.pack(fill='both', expand=True, padx=5, pady=5)

# Draw
print("Drawing canvas...")
sim_canvas.draw()

print("✓ Canvas created successfully!")
print()

# Create test lens
test_lens = Lens(name="Test Biconvex",
                radius_of_curvature_1=100,
                radius_of_curvature_2=-100,
                thickness=10,
                diameter=50,
                material="BK7")

def run_test_simulation():
    """Run a test simulation"""
    print("Running simulation...")
    
    # Create tracer
    tracer = LensRayTracer(test_lens)
    
    # Trace rays
    rays = tracer.trace_parallel_rays(num_rays=11)
    focal_point = tracer.find_focal_point(rays)
    outline = tracer.get_lens_outline()
    
    print(f"  Traced {len(rays)} rays")
    print(f"  Focal point: {focal_point}")
    
    # Clear and redraw
    sim_ax.clear()
    sim_ax.set_facecolor('#1e1e1e')
    
    # Draw lens
    if outline:
        xs = [p[0] for p in outline]
        ys = [p[1] for p in outline]
        sim_ax.fill(xs, ys, color='lightblue', alpha=0.3, label='Lens')
        sim_ax.plot(xs, ys, color='blue', linewidth=2)
    
    # Draw optical axis
    sim_ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    
    # Draw rays
    for i, ray in enumerate(rays):
        xs = [p[0] for p in ray.path]
        ys = [p[1] for p in ray.path]
        color = 'red' if i == 0 or i == len(rays)-1 else 'orange'
        alpha = 0.8 if i == len(rays)//2 else 0.6
        sim_ax.plot(xs, ys, color=color, linewidth=1.5, alpha=alpha)
    
    # Draw focal point
    if focal_point:
        fx, fy = focal_point
        sim_ax.plot(fx, fy, 'go', markersize=10, label=f'Focal Point ({fx:.1f} mm)', zorder=5)
        sim_ax.axvline(x=fx, color='green', linestyle=':', linewidth=1, alpha=0.5)
    
    # Style
    sim_ax.set_xlabel('Position (mm)', fontsize=10, color='#e0e0e0')
    sim_ax.set_ylabel('Height (mm)', fontsize=10, color='#e0e0e0')
    sim_ax.set_title(f'Ray Tracing: {test_lens.name}\n{len(rays)} rays traced',
                    fontsize=11, color='#e0e0e0')
    sim_ax.legend(loc='best', fontsize=9, facecolor='#2e2e2e', 
                 edgecolor='#3f3f3f', labelcolor='#e0e0e0')
    sim_ax.grid(True, alpha=0.3, color='#3f3f3f')
    sim_ax.set_aspect('equal')
    sim_ax.tick_params(colors='#e0e0e0', labelsize=9)
    
    # Refresh
    print("  Drawing to canvas...")
    sim_canvas.draw()
    print("✓ Simulation complete!")

# Add control button
btn_frame = ttk.Frame(root)
btn_frame.pack(pady=5)

run_btn = ttk.Button(btn_frame, text="Run Simulation", command=run_test_simulation)
run_btn.pack(side=tk.LEFT, padx=5)

quit_btn = ttk.Button(btn_frame, text="Quit", command=root.quit)
quit_btn.pack(side=tk.LEFT, padx=5)

print()
print("="*70)
print("Window opened. Click 'Run Simulation' to test ray tracing.")
print("="*70)
print()

# Run GUI
root.mainloop()
