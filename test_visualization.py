#!/usr/bin/env python3
"""
Test script for 3D lens visualization
Creates a test window with a sample lens
"""

import tkinter as tk
from tkinter import ttk
from lens_visualizer import LensVisualizer

def test_visualization():
    """Test the 3D visualization with sample lenses"""
    root = tk.Tk()
    root.title("OpenLense - 3D Visualization Test")
    root.geometry("800x700")
    
    # Main frame
    main_frame = ttk.Frame(root, padding="10")
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    ttk.Label(main_frame, text="3D Lens Visualization Test", 
             font=('Arial', 14, 'bold')).pack(pady=10)
    
    # Controls frame
    controls = ttk.Frame(main_frame)
    controls.pack(fill=tk.X, pady=10)
    
    ttk.Label(controls, text="R1:").grid(row=0, column=0, padx=5)
    r1_var = tk.StringVar(value="100")
    ttk.Entry(controls, textvariable=r1_var, width=10).grid(row=0, column=1, padx=5)
    
    ttk.Label(controls, text="R2:").grid(row=0, column=2, padx=5)
    r2_var = tk.StringVar(value="-100")
    ttk.Entry(controls, textvariable=r2_var, width=10).grid(row=0, column=3, padx=5)
    
    ttk.Label(controls, text="Thickness:").grid(row=0, column=4, padx=5)
    thickness_var = tk.StringVar(value="5")
    ttk.Entry(controls, textvariable=thickness_var, width=10).grid(row=0, column=5, padx=5)
    
    ttk.Label(controls, text="Diameter:").grid(row=0, column=6, padx=5)
    diameter_var = tk.StringVar(value="50")
    ttk.Entry(controls, textvariable=diameter_var, width=10).grid(row=0, column=7, padx=5)
    
    # Visualization frame
    viz_frame = ttk.LabelFrame(main_frame, text="3D View", padding="10")
    viz_frame.pack(fill=tk.BOTH, expand=True, pady=10)
    
    visualizer = LensVisualizer(viz_frame, width=8, height=6)
    
    def update_view():
        try:
            r1 = float(r1_var.get())
            r2 = float(r2_var.get())
            thickness = float(thickness_var.get())
            diameter = float(diameter_var.get())
            visualizer.draw_lens(r1, r2, thickness, diameter)
        except ValueError as e:
            print(f"Invalid input: {e}")
    
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(pady=10)
    
    ttk.Button(btn_frame, text="Update View", command=update_view).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Biconvex", 
              command=lambda: (r1_var.set("100"), r2_var.set("-100"), 
                              thickness_var.set("5"), update_view())).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Plano-Convex", 
              command=lambda: (r1_var.set("100"), r2_var.set("10000"), 
                              thickness_var.set("5"), update_view())).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Clear", 
              command=visualizer.clear).pack(side=tk.LEFT, padx=5)
    
    # Draw initial lens
    update_view()
    
    root.mainloop()

if __name__ == "__main__":
    print("Starting 3D Visualization Test...")
    print("Testing matplotlib and numpy integration...")
    test_visualization()
