Image Quality
=============

A lens prescription determines first-order properties, but two lenses with the
same focal length can form very different images. OpenLens reports both
geometric and diffraction-based measures. This page explains what each number
means and when it is trustworthy.

.. contents:: Table of Contents
   :local:
   :depth: 2

From Rays to Metrics
--------------------

The analysis starts with an exact ray trace at a requested field angle and
wavelength. Rays that miss the clear aperture or the system stop are marked
vignetted and are not treated as image points. The surviving intersections at
the image plane feed the spot diagrams, PSF, MTF, and wavefront calculations.

Two failure rules matter when reading a report:

- A failed trace returns ``None``. It is not silently replaced by zero, which
  would look like a perfect result.
- A lens with zero optical power (afocal) has no finite focal length, so
  focal-length-dependent metrics are undefined.

Seidel Aberrations
------------------

OpenLens reports the five primary (third-order) aberrations. Some are
calculator estimates from first-order parameters; field-dependent coma,
astigmatism, field curvature, and distortion use traced off-axis rays.

Spherical aberration
    Longitudinal shift between the paraxial focus and the marginal-ray focus.
    It is present on axis and grows rapidly with aperture. Stopping down
    reduces it.

Coma
    An off-axis aberration that makes a point source look like a comet.
    OpenLens estimates it from the asymmetry of the traced ray fan.

Astigmatism
    The tangential and sagittal ray fans focus at different distances. The
    reported value is the longitudinal separation of those foci.

Field curvature
    The image surface is curved rather than flat: best focus changes with
    field angle. A flat sensor therefore cannot be in focus everywhere.

Distortion
    The image height is not proportional to the ideal ``f tan θ`` mapping.
    Distortion moves points but does not by itself blur a point.

For a single spherical lens, third-order Seidel distortion is zero by
construction; the traced distortion curve is the useful measure.

Chromatic Aberration
--------------------

The refractive index depends on wavelength. OpenLens reports longitudinal
chromatic aberration as the focus shift between spectral lines. The Abbe
number is the usual first-order measure:

.. math::

   V_d = \frac{n_d - 1}{n_F - n_C}.

A low Abbe number means high dispersion and usually more chromatic
aberration. The calculation uses the material's catalog value where possible;
otherwise it falls back to a coarse estimate based on refractive index. Treat
that fallback as an estimate, not a measured glass property.

Achromatic Doublets
^^^^^^^^^^^^^^^^^^^

Combining a positive crown element with a negative flint element can bring two
wavelengths to a common focus. The cemented-doublet tools and optimizer in
OpenLens expose the element radii and glass choice as variables. A good
first-order achromat still needs a real ray check for spherical aberration and
manufacturing tolerances.

Spot Diagram
------------

A spot diagram is the scatter of ray intersections at the image plane. OpenLens
reports:

- RMS spot radius, usually in micrometres.
- Geometric spot extent.
- Encircled-energy curves when requested.
- Separate fans for field angles and wavelengths.

RMS spot size is a geometric measure. It can be made very small by choosing a
particular best-focus plane, so compare designs at a stated focus condition.
It says nothing about diffraction once the spot approaches the Airy scale.

Diffraction Limit
-----------------

For a circular aperture, the first dark ring of the Airy pattern is at

.. math::

   r_\text{Airy} = 1.22\,\lambda f/\#,

so the Airy diameter is

.. math::

   D_\text{Airy} = 2.44\,\lambda f/\#.

The diffraction-limited MTF cutoff is

.. math::

   f_\text{cutoff} = \frac{1}{\lambda f/\#}

in line pairs per millimetre when ``λ`` is in millimetres. A geometric spot
much smaller than the Airy disk is not a meaningful resolution claim.

PSF
---

The point spread function is the image of an ideal point source. OpenLens can
compute it in two ways:

Geometric PSF
    Bin traced ray intersections on a detector grid. This is cheap and shows
    the geometric blur, but it ignores diffraction and can be noisy with few
    rays. The window grows to cover the traced spot; the result reports how
    much of the traced energy was captured. A low captured fraction means the
    PSF is clipped by the detector, not that the lens is perfect.

Diffraction PSF
    Take the complex pupil function from the traced wavefront and propagate it
    with an FFT. This includes diffraction and defocus, and is the appropriate
    model near the diffraction limit. It needs ``numpy`` and a sampled pupil.

The PSF is normalized so its integral represents the captured energy. When a
metric is computed from a clipped PSF, the report should be read together with
the captured fraction.

MTF
---

The modulation transfer function describes how much contrast survives at each
spatial frequency. OpenLens reports tangential and sagittal profiles in
line pairs per millimetre. The MTF is the magnitude of the Fourier transform
of the PSF (or the autocorrelation of the pupil), normalized to 1 at zero
frequency.

Use the MTF to compare:

- A design at different field angles.
- Geometric and diffraction calculations near the limit.
- The effect of defocus or a tolerance perturbation.

An MTF computed from a clipped geometric PSF is optimistic because the missing
light is not represented. Check the captured fraction and the spot extent
before trusting a high-frequency result.

Strehl Ratio and Wavefront Error
--------------------------------

The Strehl ratio is the ratio of the aberrated peak irradiance to the ideal
peak. OpenLens obtains it from the traced pupil wavefront:

.. math::

   S = \left|\left\langle e^{i 2\pi W}\right\rangle\right|^2,

where ``W`` is the wavefront error in waves after piston and tilt are removed.
For small aberrations this is close to the Maréchal approximation

.. math::

   S \approx e^{-(2\pi\sigma)^2},

with ``σ`` the RMS wavefront error in waves. A Strehl ratio of 0.8 or above is
often treated as “diffraction limited”, but the threshold is a convention, not
a hard physical boundary.

Wavefront maps are sampled on a pupil grid. If too few rays reach the pupil,
the result is reported as unavailable rather than as a good wavefront.

Through-Focus and Tolerancing
-----------------------------

Image quality changes with focus. OpenLens can evaluate metrics at a requested
focus shift instead of assuming the paraxial image plane. Tolerancing extends
this idea to manufacturing errors: element decentre, tilt, thickness, radius,
and index perturbations are sampled, and the resulting metric distribution is
reported. A nominal design with a good spot but no tolerance margin is not a
manufacturable design.

What the Numbers Do Not Cover
-----------------------------

- Geometric ray tracing ignores diffraction until the diffraction PSF/MTF
  branch is selected.
- Scalar diffraction does not model polarization or vector pupil effects;
  those need the coating/polarization models.
- A single-wavelength MTF does not describe a broadband image. Use the
  chromatic tools and multiple wavelengths.
- Ghost analysis follows unwanted reflections but does not predict sensor
  blooming or stray light outside the modeled aperture.
- Manufacturing tolerances are statistical inputs. The output is only as good
  as the distributions and compensators supplied.

Where to Look in the Code
-------------------------

- ``openlens/aberrations.py``: Seidel estimates, chromatic, Airy, Strehl.
- ``openlens/analysis/spot_diagram.py``: spot and encircled energy.
- ``openlens/analysis/geometric.py``: field curves and distortion.
- ``openlens/analysis/psf_mtf.py``: geometric and diffraction PSF/MTF.
- ``openlens/analysis/diffraction_psf.py``: pupil wavefront propagation.
- ``openlens/tolerancing.py``: Monte Carlo and sensitivity analysis.
