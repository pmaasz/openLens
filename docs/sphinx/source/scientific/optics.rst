Optical Model
=============

This page collects the conventions and equations that OpenLens uses for
first-order layout, surface shape, and ray refraction. It is deliberately
close to the implementation so a calculated number can be reproduced by hand.

.. contents:: Table of Contents
   :local:
   :depth: 2

Sign Convention
---------------

OpenLens uses the usual Cartesian optical convention:

- Light propagates from left to right along the positive *x* axis.
- Surface vertices are the reference points for surface coordinates.
- A radius is positive when the centre of curvature lies to the right of the
  surface vertex. For a biconvex lens in air, ``R1 > 0`` and ``R2 < 0``.
- Distances to the right of a reference are positive.
- A converging element has positive effective focal length (EFL).
- Angles are measured from the optical axis; the ray tracer stores them in
  radians internally.

The Lens model uses the helium d-line, 587.6 nm, as its default design
wavelength and for ``nd``/``Vd`` catalog data. Visualization, spot diagrams,
PSF/MTF, and resolution defaults use the photopic green line, 550 nm.

Surface Shape
-------------

Spherical sag
^^^^^^^^^^^^^

For a spherical surface of radius ``R``, the vertex-referenced sag at radial
height ``r`` is

.. math::

   z(r) = \operatorname{sgn}(R)\left(|R| - \sqrt{R^2 - r^2}\right).

Flat surfaces have ``z = 0``. OpenLens clamps ``|r|`` to the real domain so a
ray outside the sphere's cap does not produce a complex sag.

Conic sag
^^^^^^^^^

A conic surface is described by the vertex radius ``R`` and conic constant
``K``:

.. math::

   z(r) = \frac{c r^2}{1 + \sqrt{1 - (1+K)c^2 r^2}},
   \qquad c = \frac{1}{R}.

The common special cases are:

- ``K = 0``: sphere.
- ``K = -1``: paraboloid.
- ``-1 < K < 0``: prolate ellipsoid.
- ``K > 0``: oblate ellipsoid.
- ``K < -1``: hyperboloid.

OpenLens also supports the older parabolic control, which stores the sag at
the half-diameter and scales it as ``z(r) = z_{D/2}(r/(D/2))^2``. The conic
model is preferred when an exact conic constant is known.

Lensmaker's Equation
--------------------

For a thick lens in air with refractive index ``n``, centre thickness ``d``
and surface radii ``R1`` and ``R2``:

.. math::

   \frac{1}{f} = (n-1)\left(
   \frac{1}{R1} - \frac{1}{R2}
   + \frac{(n-1)d}{n R1 R2}
   \right).

A flat surface contributes ``1/R = 0``. A plane-parallel plate therefore has
zero power, as expected. For a thin lens (``d`` small compared with the
radii), the last term is omitted.

Back and Front Focal Lengths
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The back focal length (BFL) is measured from the rear vertex to the rear
paraxial focus:

.. math::

   \mathrm{BFL} = f\left(1 - \frac{d P_1}{n}\right),
   \qquad P_1 = \frac{n-1}{R1}.

The front focal length (FFL) is a signed Cartesian coordinate measured from
the front vertex. For a converging lens the front focus lies to the left, so
the coordinate is negative:

.. math::

   \mathrm{FFL} = -f\left(1 - \frac{d P_2}{n}\right),
   \qquad P_2 = \frac{1-n}{R2}.

Both return ``None`` for an afocal element where the focal length is
undefined.

Camera Mounts and Working Flange
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A camera mount fixes the sensor plane a specified flange distance behind the
mounting face. OpenLens models the mount as being at the lens rear vertex, so

.. math::

   \text{working flange distance} = \mathrm{BFL} + \text{mount flange distance}.

For example, a lens with a 27.93 mm BFL and an M42 mount (45.46 mm) has a
working flange distance of 73.39 mm. If the mount is unknown, or the lens is
afocal, the result is ``None`` rather than an assumed value.

Paraxial Matrix
---------------

For paraxial layout the code uses the ray vector ``(y, nθ)`` and the surface
power convention ``P = (n_after - n_before)/R``. One surface and one
translation are

.. math::

   M_\text{surface} =
   \begin{pmatrix} 1 & 0 \\ -P & 1 \end{pmatrix},
   \qquad
   M_\text{translation} =
   \begin{pmatrix} 1 & d/n \\ 0 & 1 \end{pmatrix}.

For a single lens in air, multiplying surface 1, the glass translation, and
surface 2 gives the system matrix ``M = [[A, B], [C, D]]``. For a system
starting and ending in air:

.. math::

   \mathrm{EFL} = -\frac{1}{C}, \qquad
   \mathrm{BFL} = -\frac{A}{C}, \qquad
   \mathrm{FFL} = \frac{D}{C}.

This matrix path is the reference for the paraxial focus used by the spot
diagram and the wavefront analysis. Exact ray traces then include spherical
aberration and the real surface profiles.

Refraction
----------

At a smooth dielectric interface the incident and refracted directions obey
Snell's law:

.. math::

   n_1 \sin\theta_1 = n_2 \sin\theta_2.

The tracer uses the surface normal at the intersection point, so curved
surfaces are handled locally rather than by a single paraxial angle. Total
internal reflection occurs when

.. math::

   \sin\theta_2 = \frac{n_1}{n_2}\sin\theta_1 > 1.

Those rays are marked as terminated/reflected according to the tracer path
instead of being silently propagated as if they refracted.

Surfaces with a coating use the coating stack to modulate reflected and
transmitted energy. The geometric direction still follows Snell's law; the
coating supplies the intensity ratio. Absorption inside a coating layer is
handled by the coating model, not by changing the ray angle.

Apertures, Bevels, and Stops
----------------------------

- The mechanical diameter is the outer lens diameter.
- A clear aperture, when set, is the polished optical aperture of that
  surface. Rays outside it are vignetted.
- Bevels model the protective chamfer at the rim and reduce the usable clear
  aperture near the edge.
- An optical system may define an aperture stop in an air gap. The stop has a
  diameter and is applied before the following element; rays outside it are
  blocked and reported as vignetted.
- Surface profiles are clamped to their real domain at the rim. A diameter
  larger than a spherical cap can support is therefore a validation issue, not
  a reason to invent a complex surface.

Ray Fans and Field Points
-------------------------

A parallel fan at angle ``θ`` is launched from a plane in front of the first
vertex. Its heights are chosen across a fraction of the semi-aperture; the
default is the full aperture so rim spherical aberration is included. Point
sources launch rays from a specified position with angles spanning a requested
range. Off-axis field analysis uses the same tracing machinery with a rotated
or displaced ray bundle.

Where to Look in the Code
-------------------------

- ``openlens/lens.py``: focal lengths, sags, edge thickness, mounts.
- ``openlens/optical_system.py``: element order, gaps, stop, system matrix.
- ``openlens/tracer_2d.py`` and ``tracer_3d.py``: exact intersections and
  refraction.
- ``openlens/analysis/paraxial.py``: paraxial focus and matrix helpers.
- ``openlens/mounts.py``: built-in and custom flange distances.
