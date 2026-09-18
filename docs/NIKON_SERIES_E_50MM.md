# Nikon Series E 50mm f/1.8 — Glass Prescription Reference

This note records the best publicly available optical data for the
Nikon Series E 50mm 1:1.8, for use as a modelling reference in OpenLens.

> Nikon never published factory as-built drawings (exact radii,
> center/edge thicknesses, diameters, melt-specific glass data) for this
> lens. The data below comes from the design patent the lens was built
> from. Treat it as the design prescription, not a metrology report.

## 1. Lens identification

* Name: Nikon Series E 50mm 1:1.8 (Nikon F mount, manual focus)
* Variants sharing identical optics:
  * MkI all-black, 1979–1981, ~25.2 mm long, 62.5 mm dia, ~135 g
  * MkII chrome/silver ring, 1981–1985, ~27.8 mm long, 62.5 mm dia, ~157 g
* Common specs: 50 mm, f/1.8–f/22, 6 elements in 5 groups,
  Double-Gauss, 7 straight aperture blades, 52 mm filter, 0.6 m MFD,
  ~46 deg diagonal, single-coated.
* Designer: Souichi Nakamura.
* Relation: Nikon ("Thousand and One Nights" Tale 60) states the Series E
  50/1.8 and the AI Nikkor 50/1.8S pancake are "sister lenses designed
  with the same basic optics, but different outward appearance and
  coatings". The design lived on in the AI-S pancake, AF, and AF-D 50/1.8.

## 2. Source patent

* `US4234242A — Gauss type photographic lens`
* Assignee: Nippon Kogaku K.K. (Nikon), inventor Soichi Nakamura
* Filed 1979-01-30, published 1980-11-18, expired. Prior art 1978-02-03.
* Full text: https://patents.google.com/patent/US4234242A/en
* Example 1 is f/2.0. Examples 2–4 are f/1.8, 46 deg, compact Gauss
  types. Example 2 is the most-cited match for the production 50/1.8.

Patent convention:

* `r` = surface radius of curvature (mm), `d` = center thickness or air
  separation (mm), `n` = refractive index, `nu` = Abbe number.
* Patent is normalized to `f = 100 mm`. Halve all `r` and `d` values for
  `f = 50 mm`. `n` and `nu` are unchanged.
* Layout front to back: L1 positive | L2 positive meniscus,
  convex to object | L3 negative meniscus, convex to object |
  STOP | L4 cemented negative + positive meniscus, concave to
  object | L5 positive.

## 3. Prescription: Example 2 scaled to 50 mm (recommended starting point)

| Surf | Radius [mm] | Thickness / air [mm] | Glass |
| ---- | ----------- | -------------------- | ----- |
| 1 | +45.4915 | L1 3.390 | n1 = 1.713, Vd = 53.9 |
| 2 | +612.3255 | air 0.095 | — |
| 3 | +19.0930 | L2 4.360 | n2 = 1.713, Vd = 53.9 |
| 4 | +32.0980 | air 1.550 | — |
| 5 | +88.0105 | L3 0.970 | n3 = 1.64831, Vd = 33.8 |
| 6 | +16.0455 | air + stop 8.820 | — |
| 7 | −17.5195 | L4a 0.970 | n4 = 1.64831, Vd = 33.8 |
| 8 | −65.1165 (cement) | L4b 4.845 | n5 = 1.713, Vd = 53.9 |
| 9 | −19.9610 | air 0.095 | — |
| 10 | +70.9620 | L5 2.520 | n6 = 1.713, Vd = 53.9 |
| 11 | −117.6550 | back focal length ~37.5 to film | — |

Unscaled patent values (f = 100 mm) for verification:
`r1=90.983, d1=6.78 | r2=1224.651, d2=0.19 | r3=38.186, d3=8.72 |`
`r4=64.196, d4=3.10 | r5=176.021, d5=1.94 | r6=32.091, d6=17.64 |`
`r7=-35.039, d7=1.94 | r8=-130.233, d8=9.69 | r9=-39.922, d9=0.19 |`
`r10=141.924, d10=5.04 | r11=-235.310, Bf=75.0, track=130.3`.

Derived: `f1 = 290.5 (f=100)`, `f2 = 98.1`, `D = 103.5`,
`Bf ~= 37.5 mm at 50 mm` — the long back focus required for an SLR mirror.

## 4. What the patent does NOT give

* No element clear-aperture diameters or edge thicknesses.
  Entrance pupil is ~27.8 mm (`50 / 1.8`); set apertures from that.
* No mechanical airspaces outside the glass (helicoid, mount).
* 1978 glass types are obsolete. For OpenLens simulation map
  `1.713 / 53.9` and `1.64831 / 33.8` to the closest modern
  catalog equivalents; keep `n`/`Vd` as listed for first-order checks.
* Production melt variation, coating (single vs multi), and minor
  re-optimizations for the AF/AF-D versions are not documented.

For micron-true as-built data the lens must be reverse-engineered:
disassemble, spherometer for `r`, micrometer for center/edge thickness,
refractometer/XRF for glass.

## 5. Using this in OpenLens

1. Build an `OpticalSystem` from the scaled Example 2 table above.
2. Verify EFL ~= 50 mm and BFL ~= 37.5 mm before adding stops/baffles.
3. Fit modern glass equivalents only after paraxial check passes.
4. See alternate corrections (Examples 3–4 in US4234242A) if optimizing
   for coma / lateral color trade-offs.

## 6. Built-in OpenLens example

The prescription above ships with OpenLens via `src/seed_data.py`:

* Six individual lens rows (`nikon-series-e-50mm-l1…l5`, diameters
  28/28/28/26/26/26 mm chosen so front clear aperture matches f/1.8 and
  every edge thickness stays manufacturable).
* One assembly row (`nikon-series-e-50mm-assembly`) with patent air gaps
  `[0.095, 1.55, 8.82, 0.0, 0.095]` (L4a–L4b cemented).
* Seeding is idempotent and never overwrites existing rows. It runs on
  GUI startup (`openlens.py:main`) and for the default CLI database
  (`LensManager` with `openlens.db`). Temp/test databases are untouched;
  call `ensure_nikon_series_e_example(db_or_path)` explicitly to seed
  any other file.

## 7. References

* US4234242A full text and PDF (Google Patents).
* Nikon Imaging: "NIKKOR — The Thousand and One Nights, Tale 60:
  AI NIKKOR 50mm f/1.8S" — Series E sister-lens statement and
  Nakamura design history.
* JAPB data sheet: "Nikon Series E 50mm f/1.8" — mechanical specs
  for both MkI and MkII variants.
* Richard Haw repair notes and Casual Photophile Series E review —
  6e/5g layout confirmation and variant history.
