"""
OpenLens Image Simulation Dialog
Side-by-side comparison of original and simulated image
"""

import os
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QFileDialog, QMessageBox)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar

class ImageSimulationDialog(QDialog):
    """Dialog for image simulation with side-by-side comparison."""
    
    def __init__(self, system, parent=None):
        super().__init__(parent)
        self._system = system
        self._original_image = None
        self._simulated_image = None
        
        self.setWindowTitle(f"Image Simulation - {system.name}")
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        self._import_btn = QPushButton("Import Image")
        self._import_btn.clicked.connect(self._on_import_image)
        self._run_btn = QPushButton("Run Simulation")
        self._run_btn.clicked.connect(self._on_run_simulation)
        self._run_btn.setEnabled(False)
        
        ctrl_layout.addWidget(self._import_btn)
        ctrl_layout.addWidget(self._run_btn)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)
        
        # Visualization
        self.figure = Figure(figsize=(10, 6), dpi=100)
        theme = getattr(parent, '_theme', 'dark') if parent else 'dark'
        if theme == 'dark':
            self.figure.patch.set_facecolor('#1e1e1e')
            
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        
        # Buttons
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
        
        # Initialize plots
        self._ax_orig = self._setup_axes(self.figure.add_subplot(121), "Original Image")
        self._ax_sim = self._setup_axes(self.figure.add_subplot(122), "Simulated Image")
        self.figure.tight_layout()

    def _setup_axes(self, ax, title):
        theme = getattr(self.parent(), '_theme', 'dark') if self.parent() else 'dark'
        if theme == 'dark':
            ax.set_facecolor('#1e1e1e')
            ax.tick_params(colors='#e0e0e0')
            ax.xaxis.label.set_color('#e0e0e0')
            ax.yaxis.label.set_color('#e0e0e0')
            ax.title.set_color('#e0e0e0')
            for spine in ax.spines.values():
                spine.set_edgecolor('#3f3f3f')
        ax.set_title(title)
        ax.axis('off')
        return ax

    def _on_import_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Image for Simulation", "", 
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if filepath:
            try:
                from PIL import Image
                img = Image.open(filepath).convert('RGB')
                # Resize if too large for performance
                max_size = 512
                if max(img.size) > max_size:
                    img.thumbnail((max_size, max_size))
                
                self._original_image = np.array(img) / 255.0
                self._ax_orig.imshow(self._original_image)
                self._ax_orig.set_title(f"Original: {os.path.basename(filepath)}")
                self._run_btn.setEnabled(True)
                self.canvas.draw()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load image: {e}")

    def _on_run_simulation(self):
        if self._original_image is None:
            return
            
        try:
            from src.analysis.psf_mtf import ImageQualityAnalyzer
            analyzer = ImageQualityAnalyzer(self._system)
            
            # Show "Calculating..." message
            self._ax_sim.clear()
            self._setup_axes(self._ax_sim, "Calculating Simulation...")
            self.canvas.draw()
            
            # Simulate
            self._simulated_image = analyzer.simulate_image(self._original_image)
            
            # Show results
            self._ax_sim.clear()
            self._setup_axes(self._ax_sim, "Simulated Image")
            self._ax_sim.imshow(self._simulated_image)
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Simulation failed: {e}")
