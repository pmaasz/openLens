# OpenLens Production-Readiness Gaps

Goal: a user can build a lens on their own in OpenLens and take it through
CAD to a producible, quotable, inspectable package. This note lists what is
missing for that workflow, checked against the actual code.

Reference example throughout: Nikon Series E 50mm f/1.8
(`docs/NIKON_SERIES_E_50MM.md`, seed data in `src/seed_data.py`).

## 1. Surface definition (optics)

- **No real aspheres.** `src/lens.py` supports spherical surfaces plus a
  parabolic-sag flag per surface (`is_parabolic_1/2`) and a crude Fresnel
  flag. There is no conic constant, no even/odd asphere coefficients, no
  Q-type, toric/cylindrical, diffractive, or GRIN surfaces.
- **STEP ignores even the parabolic sag.** `src/io/step_export.py:278-316`
  writes only `SPHERICAL_SURFACE` / `PLANE` for optics (plus a
  `CYLINDRICAL_SURFACE` rim). An aspheric design exports as spheres.
- **One diameter per element, no clear aperture.** No separate clear vs.
  mechanical aperture, no chamfer/bevel/edge-blackening parameters.
  `LensMount.clear_aperture` exists in `src/mechanical_designer.py:20` but
  is disconnected from `Lens` and from all exports.

## 2. System mechanics

- **No stop surface entity.** The Series E stop between L3/L4a is just an
  air-gap number; there is no aperture-stop object (diameter, position,
  shape) in `OpticalSystem`.
- **Tilts/decenters do not persist.** Tolerancing knows `DECENTER_X/Y` and
  `TILT_X/Y` (`src/tolerancing.py:35-46`), but `assembly_elements` in
  `src/database.py` stores only 1-D `position` plus order. A real
  decentered/tilted assembly cannot be saved or rebuilt.
- **Cement is zero-gap only.** Cemented doublets (L4a/L4b) are two lenses
  with gap 0. No cement material, bondline thickness, or bonding spec.
- **Housing is decorative.** `LensCell` / `LensMount` / `Spacer` in
  `src/mechanical_designer.py` compute weights and specs but are not part
  of `OpticalSystem`, the database, or any export. No seats, threads,
  retainers, shims, or spacers appear in CAD output — STEP exports bare
  glass solids only.

## 3. Glass and coatings

- **Custom/patent glass has no dispersion** unless `model_glass_mode`
  (nd/Vd estimate) is enabled. The material database
  (`src/material_database.py`) carries Sellmeier plus thermal data for
  built-ins, but there is no preferred-glass / moldability /
  transmission-vs-thickness / cost check, and no grade specs (bubbles,
  inclusions, birefringence, homogeneity).
- **Coatings are not part of the model.** `CoatingDesigner`
  (`src/coating_designer.py`) is a standalone calculator. No per-surface
  coating is stored on `Lens`, there is no coating column in the database,
  and nothing flows into STEP / ISO / Zemax output.

## 4. Tolerancing and manufacturability

- Monte Carlo covers radius, thickness, index, Abbe, air gap, and
  decenter/tilt (`src/tolerancing.py`), but is missing: surface
  irregularity (fringes/power), wedge, edge-thickness runout, coating
  tolerance, and thermal/defocus over temperature.
- No compensator workflow (which element or focus adjusts at assembly), no
  inverse tolerancing / tolerance budgeting, no
  commercial-to-precision-to-high-precision grade presets, and no mapping
  to ISO 10110 tolerance callouts (3/, 4/, 5/).

## 5. Drawings (ISO 10110)

- `ISO10110Generator` (`src/io/export.py:126-193`) draws a profile outline
  plus a `Surf/Radius/Thick/Mat/Diam` table. That is not an ISO 10110
  drawing: no 1/–7/ callouts (bubbles, roughness, surface form, centering,
  coating, laser damage), no dimensions with tolerances, no title block or
  revision, no section/detail views.

## 6. CAD export quality

- **STEP is hand-written minimal AP203/AP214** with self-admitted
  shortcuts (`src/io/step_export.py:169-170` "we cheat a bit",
  `:129-132` "for simplicity…"). Single-edge circular loops, no validated
  import in SolidWorks / FreeCAD / NX, no assembly hierarchy with mates,
  no threads or housing, no material/coating metadata, no stated
  units/accuracy. Good enough for viewing, not for a machine shop.
- **STL is a print mesh** (`src/stl_export.py`), faceted by construction —
  fine for prototyping, useless as a production master.
- **No STEP import**, so vendor models cannot be round-tripped or verified.

## 7. Interchange

- `ZemaxExporter` (`src/export_formats.py:17-61`) writes a single lens with
  `STANDARD` surfaces only. No multi-element system `.zmx`, no importer
  (Zemax / Code V / `.len` / `.dat`), so a design cannot be cross-checked
  in production-standard tools.

## 8. Production planning and QA

- No BOM, cost/weight roll-up, vendor-catalog matching, test-plate
  fitting, measured-surface (interferogram) import, or assembly-procedure
  output (build order, shimming, spacing verification).

## Suggested build order

1. ~~Per-surface clear aperture + bevel/chamfer fields, persisted and exported.~~
   DONE: `Lens.clear_aperture_1/2` (None = full diameter) and `bevel_1/2`
   (45° face width, 0 = sharp) with `get_clear_aperture_1/2()` fallbacks,
   `validate_clear_aperture` / `validate_bevel`, DB schema v3 with v1→v2→v3
   migration, GUI editor fields, ISO table CA column, STEP solid-name
   labels, and Zemax per-surface DIAM. Ray tracers and f-number math still
   use the mechanical OD — clipping ray fans at the CA is follow-up work,
   as are modeled bevel chamfer faces in STEP (B-rep stays on the OD).
2. Stop surface entity + tilt/decenter persistence in the DB schema.
3. Per-surface coating field end-to-end (model → DB → ISO/STEP/Zemax).
4. Real ISO 10110 callouts + dimensioned drawing with title block.
5. Production STEP via a real kernel (e.g. pythonocc) with
   housing/spacers/threads, plus an import-back verification test.
6. Tolerance grades + compensators + irregularity/wedge operands.
7. Full-system Zemax export and a Zemax importer.

Each item above is tracked as a prioritized todo in the current session.

## Status log

- Item 1 DONE (see above).
- Item 2 DONE: `OpticalSystem.aperture_stop_gap/diameter` with
  `set/clear/get_aperture_stop()` (stale indices read as unset),
  per-element `decenter_y/z` + `tilt_x/y/z` synced between the tree nodes
  and the flat records (`set_element_alignment`, `add_lens` params,
  `_update_positions` preserves lateral offsets), DB schema v4 with
  chained v1→v2→v3→v4 migration, assembly-tab stop editor (gap combo,
  diameter, set/clear) plus per-element alignment editor, ISO STOP plane
  marker, and the Series E seed carrying the L3–L4a stop (gap 2, Ø20 mm,
  backfilled onto pre-existing seed assemblies). Ray tracers still trace
  centered systems — physically stopping rays at decentered elements and
  the stop diameter is follow-up work.
- Follow-up DONE (physical vignetting in tracers): 2D/3D element tracers
  clip at per-surface clear apertures; both system tracers vignette rays
  at the aperture-stop plane (stop point appended, ray terminated;
  diameter-None stops are position-only and never clip); 2D traces
  decenter_y/tilt_z elements through their local frame using the tree
  pivot convention (front vertex), verified to agree with the 3D
  transform path to 1e-9, with an identity fast path when alignment is
  zero. Known pre-existing limits (unchanged): exact on-axis rays can
  terminate at sphere vertices, and the 2D sequential tracer does not
  complete very fast double-Gauss designs at full aperture.
