Thermal and Mechanical Effects
==============================

An optical prescription is nominal. A real lens has a finite temperature
range, a housing that expands at a different rate, and manufacturing errors in
every radius, thickness, and air gap. OpenLens models these effects separately
so they can be inspected without silently changing the stored design.

.. contents:: Table of Contents
   :local:
   :depth: 2

Thermal Scaling
---------------

For a change in temperature ``ΔT`` from the 20 °C reference, a material with
linear coefficient of thermal expansion ``α`` changes its dimensions by

.. math::

   L(T) = L_0 \left(1 + \alpha \Delta T\right).

OpenLens applies this factor to the lens radii, centre thickness, diameter,
and - when a housing coefficient is supplied - to the air gaps. The radii and
thickness scaling preserves the shape of a homogeneous element to first order.
It is not a thermo-elastic finite-element model: it does not predict stress,
bending, or a cemented-interface failure.

The refractive index also changes. Catalog glasses can carry Schott TIE-19
coefficients ``D0``, ``D1``, ``D2``, ``E0``, ``E1`` and a thermal resonance
wavelength. When they are present, OpenLens evaluates

.. math::

   \Delta n = \frac{n^2-1}{2n}\left[
   D_0\Delta T + D_1\Delta T^2 + D_2\Delta T^3
   + \frac{E_0\Delta T + E_1\Delta T^2}{\lambda^2-\lambda_{tk}^2}
   \right],

with wavelength in micrometres. All-zero coefficients mean “no thermal data”,
and no correction is applied. A model glass defined only by ``nd``/``Vd`` has
no temperature coefficients either; its index is not invented.

Air Index and Pressure
----------------------

The refractive index of air is not exactly one. ``EnvironmentalAnalyzer`` uses
a simplified Edlen/Ciddor expression for standard air, then scales it with the
ideal-gas relation

.. math::

   n_{T,P} - 1 = (n_s - 1)\frac{P}{101325}\frac{288.15}{T},

where ``T`` is in kelvin. This matters for high-precision work and for
comparisons against a catalog measured in air. At absolute zero the model
returns vacuum rather than dividing by zero.

The stored lens model is not mutated by a temperature analysis.
``EnvironmentalAnalyzer.condition_at_temperature`` returns a conditioned copy,
or the original object at the reference condition. This keeps a simulation from
quietly rewriting the library prescription.

Housing Expansion
-----------------

The air gaps are set by the mechanical housing, not by the glass. A first-order
estimate scales every gap by

.. math::

   g(T) = g_0 \left(1 + \alpha_\text{housing}\Delta T\right).

The default housing coefficient is aluminium, ``23.6 × 10⁻⁶ /K``. Steel is
roughly ``12 × 10⁻⁶ /K``, Invar ``1 × 10⁻⁶ /K``, and common plastics can be
tens to hundreds of ``10⁻⁶ /K``. Using the wrong housing coefficient can
change focus by more than the glass expansion does, especially in a long
assembly.

This is a uniform scaling model. A real barrel has a front and rear section,
retainers, and possibly different materials; those require a mechanical model
or a tolerance sensitivity study.

Mechanical Design
-----------------

``MechanicalDesigner`` derives STEP-exportable parts from an optical system:

- one lens cell per element, with a clear bore based on diameter and
  clear-aperture data;
- one spacer per positive air gap;
- a barrel spanning the stack, including front and rear flanges;
- a selected camera mount and its flange distance.

The STEP exporter writes these as tube solids. Threads are specified in the
part name (for example ``M42x1.0``) but are not modeled as helical geometry
without a CAD kernel. A suggested housing is a starting point for mechanical
design, not a production drawing.

Mounts
------

A lens carries a ``mount_type``. The built-in catalog covers C, CS, M42, M39,
T, Fujifilm X, Leica M, Canon EF, and Nikon F. The working flange distance is
the optical back focal length plus the mount's flange distance; see
:doc:`optics`.

A lens can be at the wrong working distance even when its BFL is correct. Check
the mount and the calculated working flange before exporting a mechanical
assembly.

Tolerancing
-----------

Tolerancing perturbs the nominal model and reports the distribution of image
metrics. Inputs can include:

- radius and thickness errors;
- element decentre and tilt;
- air-gap errors;
- refractive-index or material variation;
- surface irregularity.

The analysis distinguishes nominal performance from worst-case and statistical
performance. A design that is diffraction-limited on paper but has no
compensator for a ±0.1 mm gap is not robust. Compensators and focus adjustment
should be modeled explicitly; otherwise the reported yield is pessimistic or
optimistic depending on the assumed adjustment.

What Is Not Modeled
-------------------

- Stress birefringence and photoelastic effects.
- Thermal gradients inside an element or housing.
- Cement creep or delamination.
- Mount-induced lens deformation.
- Absorption and scatter by a surrounding casing. The current mechanical
  housing is a geometry model; it is not an optical absorber in the ray trace.

These are legitimate future extensions, but treating a nominal thermal scale
as if it covered them would overstate the model.

Where to Look in the Code
-------------------------

- ``openlens/analysis/environmental.py``: CTE, dn/dT, air index, conditioning.
- ``openlens/material_database.py``: thermal coefficients and glass data.
- ``openlens/mechanical_designer.py``: cells, spacers, barrel, mounts.
- ``openlens/mounts.py``: standard and custom flange distances.
- ``openlens/tolerancing.py``: perturbation, Monte Carlo, reports.
- ``openlens/io/step_export.py``: STEP solids for lenses and housings.
