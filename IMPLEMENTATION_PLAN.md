# OpenLens Feature Parity Implementation Plan

**Goal:** Bridge the gap between OpenLens and industry-standard optical design software (Zemax OpticStudio, Quadoa Optical CAD, Synopsys CODE V) by adding professional-grade analysis, tolerancing, and catalog capabilities.

## Phase 1: Foundation for Precision (Immediate Priority)
*Focus: Enabling real-world design capabilities by using real glass data, manufacturing simulation, and 3D ray tracing.*

### 1.1 Comprehensive Material Catalog (Completed)
*Current State:* Limited to ~7 hardcoded materials in `src/material_database.py`.
*Target:* Support standard industry catalogs (Schott, Ohara, Hoya) and internal transmission.
*Files to Modify:* `src/material_database.py`
*Tasks:*
- [x] Implement `import_agf_catalog(file_path)` parser for standard AGF format.
- [x] Implement `import_csv_catalog(file_path)` for generic CSV data.
- [x] Update `MaterialProperties` to support internal transmission data tables (normalized to specific thickness).
- [x] Implement robust Sellmeier dispersion formula handling (AGF coefficients mapped to Sellmeier 1).
- [ ] Add caching mechanism for large catalogs.

### 1.2 3D Ray Tracing Engine (Completed)
*Current State:* Full 3D ray tracing with `Ray3D`, `LensRayTracer3D`, and `SystemRayTracer3D`.
*Target:* Full 3D ray tracing (skew rays) to support Spot Diagrams, off-axis performance, and Multi-Sequential paths.
*Files to Modify:* `src/ray_tracer.py` (Major Refactor)
*Tasks:*
- [x] Create `Ray3D` class with position (x,y,z) and direction cosines (L,M,N).
- [x] Implement 3D Ray-Sphere intersection logic `(x-cx)^2 + (y-cy)^2 + (z-cz)^2 = R^2`.
- [x] Update `LensRayTracer` to handle 3D coordinates.
- [x] Implement `trace_skew_ray` methods.
- [x] Verify against 2D tracer for on-axis cases (Regression Testing).
- [ ] Add **Polarization Ray Tracing** support (Jones Matrix per ray).

### 1.3 Hierarchical Optical Model (Object-Based) (Completed)
*Current State:* `OpticalSystem` uses `OpticalNode` tree internally, synced with legacy flat lists.
*Target:* Modern object-based architecture (Quadoa style) allowing nested assemblies and local coordinate systems.
*Files to Modify:* `src/optical_system.py`, `src/optical_node.py`
*Tasks:*
- [x] Create `OpticalNode` base class with local coordinate transform (Position + Rotation).
- [x] Implement `OpticalAssembly` (container for nodes).
- [x] Implement `OpticalElement` (Lens, Mirror, Prism).
- [x] Add "Form Stack" ability: Base Surface + List of Modifiers (Asphere, Zernike, Coating).

### 1.4 Tolerancing Engine (Monte Carlo & Optimization) (Completed)
*Current State:* Fully functional Monte Carlo and Inverse Sensitivity analysis.
*Target:* Simulate manufacturing errors and optimize for yield (Pass/Fail rates).
*New Files:* `src/tolerancing.py`
*Tasks:*
- [x] Define `ToleranceOperand` class (Radius, Thickness, Index, Decenter, Tilt).
- [x] Implement `MonteCarloAnalyzer` class with Gaussian/Uniform perturbation logic.
- [x] Implement **Inverse Sensitivity** analysis (calculate required tolerances for target performance).
- [x] Generate Yield Reports (e.g., "90% of lenses have RMS Spot < 5µm").

### 1.5 Environmental Analysis (CODE V Style) (Completed)
*Current State:* Fully functional Thermal and Pressure analysis.
*Target:* Simulate performance under thermal loads and pressure changes (Crucial for aerospace/automotive).
*New Files:* `src/analysis/environmental.py`
*Tasks:*
- [x] Implement Thermal Expansion (CTE) updates for curvature and thickness.
- [x] Implement Temperature-dependent Refractive Index (`dn/dt`) updates.
- [x] Implement Pressure-dependent Index updates (Edlen equation for air gaps).

---

## Phase 2: Advanced Analysis & Visualization
*Focus: Providing professional-grade optical quality metrics.*

### 2.1 Spot Diagrams & Geometric Analysis (Completed)
*Current State:* `src/analysis/__init__.py` implements `SpotDiagram`.
*Target:* Exact ray-traced image analysis using the new 3D engine.
*New Files:* `src/analysis/__init__.py` (Refactored from `src/analysis.py`), `src/analysis/geometric.py`
*Prerequisites:* Phase 1.2 (3D Ray Tracing)
*Tasks:*
- [x] Implement `SpotDiagram` calculator (Hex/Rect grid).
- [x] Calculate **RMS Spot Radius** and **GEO Spot Radius**.
- [ ] Generate standard "Spot Diagram" plots (Matrix of field points vs. wavelengths).

### 2.2 Ghost Analysis (Multi-Sequential) (Completed)
*Current State:* Fully functional 2nd order ghost tracing with Fresnel intensity calculation.
*Target:* Detect ghost reflections (stray light) by generating secondary ray paths.
*New Files:* `src/analysis/ghost.py`
*Tasks:*
- [x] Implement `GhostAnalyzer` to generate ray paths for 2-reflection sequences.
- [x] Visualize ghost rays in 3D view (GUI integration pending).
- [x] Calculate "Ghost Irradiance" on the image plane (via Fresnel coefficients).

### 2.3 Physical Optics (BSP & Diffraction) (Completed)
*Current State:* Gaussian Beam class, Wavefront Sensor, and PSF/BSP calculators implemented.
*Target:* High-accuracy diffraction analysis (CODE V's BSP equivalent).
*Files to Modify:* `src/diffraction.py`, `src/analysis/beam_synthesis.py`
*Tasks:*
- [x] Implement **Gaussian Beam** propagation (q-parameter transformation ABCD matrix).
- [x] Implement **Beam Synthesis Propagation (BSP)**: Decompose wavefront into beamlets for accurate clipping and diffraction analysis. (Requires numpy)
- [x] Implement FFT-based **PSF** and **MTF**. (Requires numpy)

---

## Phase 3: Automated Design Optimization
*Focus: Enhancing the optimizer.*

### 3.1 Merit Function Expansion (Completed)
*Current State:* Optimizes for focal length and basic Seidel sums. Added RMS Spot and MTF.
*Target:* Optimize for real-world performance metrics (Spot Size, MTF).
*Files to Modify:* `src/optimizer.py`
*Tasks:*
- [x] Add `MeritOperand.RMS_SPOT`.
- [x] Add `MeritOperand.MTF`.

### 3.2 Advanced Optimization (Global & Desensitization) (Completed)
*Current State:* Global (Simulated Annealing) and Desensitization (Robust Optimization) implemented.
*Target:* Find global minima and optimize for manufacturability (CODE V style).
*Files to Modify:* `src/global_optimizer.py`, `src/desensitization.py`
*Tasks:*
- [x] Implement **Global Synthesis** (simplified version): Genetic Algorithm or Simulated Annealing to escape local minima.
- [x] Implement **Desensitization Optimization**: Optimize for Yield (reduce sensitivity to tolerances) rather than just nominal performance.

---

## Phase 4: Interoperability & Manufacturing
*Focus: Connecting with the real world (CAD, Drawings).*

### 4.1 CAD & Drawing Export
*Current State:* STL Export implemented. ISO 10110 SVG Generator implemented.
*Target:* Export to mechanical CAD and manufacturing drawings.
*New Files:* `src/io/export.py`
*Tasks:*
- [x] Implement **ISO 10110** Drawing Generator (SVG).
- [x] Implement **STL Export** for 3D printing/visualization.
- [ ] Implement **Step/IGES** Export (Deferred: Requires heavy dependencies not available in standard library).

---

## Implementation Sequence
1. **Material Database** (Completed Basic)
2. **3D Ray Tracing** (Critical Foundation) - *COMPLETED*
3. **Hierarchical Model** (Architecture Modernization) - *COMPLETED*
4. **Spot Diagrams** (Visual Feedback) - *COMPLETED*
5. **Ghost Analysis** (Advanced Analysis) - *COMPLETED*
6. **Tolerancing** (Professional Requirement) - *COMPLETED*
7. **Physical Optics** (Advanced Feature) - *COMPLETED*
8. **Optimization** (Global/Desensitization) - *COMPLETED*
9. **Manufacturing Export** (STL/Drawings) - *COMPLETED*
