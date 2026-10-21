# Finding catalogue

Bug classes worth probing explicitly on the next review, with the OpenLens
issue that first exposed each one. None of these are style issues; each was
reproduced functionally.

## Persistence and round-trip

| Pattern | Example |
| --- | --- |
| Writer emits a value the reader rejects | `Lens.to_dict` writes `inf` for plano radii; `OpticalSystem.load` calls `reject_non_finite_numbers` (#601) |
| `INSERT OR REPLACE` omits a column with a non-neutral default | `_save_lens_row` omits `is_library`, so every save resets it to 1 (#602) |
| Partial-snapshot save is treated as authoritative | `save_lenses(demote=False)` cannot undo the reset, so assembly-only lenses leak into the library (#602) |

Probe: save → load → compare every field; repeat through every entry point
(API, GUI, CLI, module-level helper). Include `inf`, `NaN`, `None`, zero.

## Parameters that are accepted but ignored

| Pattern | Example |
| --- | --- |
| Function takes a metric/criterion and always computes one | `InverseSensitivityAnalyzer.calculate_sensitivities(criterion=...)` ignores it (#615) |
| Function takes a wavelength and uses the design index | `ImageSimulator._calculate_image_distance` calls `_system_focal_length()` (#612) |
| Alignment rebuild drops a constructor argument | 2D `_trace_aligned_element` builds `LensRayTracer` without `wavelength_nm` (#603) |
| Physics helper reads an attribute the model does not have | `MechanicalDesigner` checks `center_thickness`; `Lens` has `thickness` (#616) |

Probe: for every public parameter, grep the body for the parameter name. Then
call with two values that must produce different results and confirm they do.

## Units, quantities, and labels

| Pattern | Example |
| --- | --- |
| Same key means different quantities on different code paths | `field_curvature` is Petzval radius for `Lens`, focus shift for `OpticalSystem` (#604) |
| GUI label names the wrong unit/quantity | `mm (Petzval radius)` over the system-path value (#604) |
| Default plane is an arbitrary offset, not a physical plane | Beam synthesis uses `total_length + 50` while claiming paraxial focus (#611) |

Probe: compare a single lens against the same lens in a one-element system;
compare a computed value against a hand calculation or a known reference.

## Alignment and coordinate frames

| Pattern | Example |
| --- | --- |
| One tracer honours tilt/decenter, another ignores it | 3D tracer uses the node transform; `GhostAnalyzer._interact` uses `x_offset` only (#613) |
| Flat list and node tree disagree after an update | `_update_positions` re-lays flat elements from x=0, ignoring assembly offsets (#609) |

Probe: build a two-element system, tilt/decenter the second element, and compare
2D vs 3D; move a nested assembly and compare flat positions to global ones.

## Material and index resolution

| Pattern | Example |
| --- | --- |
| Two naming schemes for the same catalogue | `"FUSEDSILICA"` (catalog) vs `"Fused Silica"` (`DEFAULT_MATERIAL_INDICES`) (#607) |
| Unknown material silently becomes BK7 | `_compute_refractive_index` returns 1.5168; `update_refractive_index` then jumps (#607) |
| Importer uses a small default table instead of the catalogue | Zemax `F2` stored as 1.5168 (#610) |

Probe: for every key in the default table and every preset material, assert
`get_material(name) is not None`, `stored_index == index_at(design_wavelength)`,
and dispersion is non-zero.

## Export formats

| Pattern | Example |
| --- | --- |
| References serialized as strings | STEP emits `'#unit_mm'`, `'#application_context'`, `'#47'` (#608) |
| Referenced entity never emitted | No `LENGTH_UNIT` or `APPLICATION_CONTEXT` in the STEP file (#608) |
| Unit/context argument has the wrong type | `GEOMETRIC_REPRESENTATION_CONTEXT` receives a string (#608) |

Probe: export, then parse the file with the format's own grammar/reader and
assert every reference resolves. Round-trip through the project's importer.

## Caching and state

| Pattern | Example |
| --- | --- |
| Cache invalidation method has no production callers | `SystemRayTracer3D.invalidate()` only called in tests (#614) |
| Cache key covers parameters but not geometry | `_scene_is_current` checks lens state only (#614) |
| Mutation restored only on the happy path | Use `finally` (the wavefront sensor already does this correctly) |

Probe: hold an analyzer instance, mutate the system, call the analyzer again,
and assert the result changed. Grep for `invalidate(` outside tests.

## Degenerate inputs

| Pattern | Example |
| --- | --- |
| Fallback branch placed after the operation that crashes | Empty-system PSF crashes in FFT before the `dx_psf` guard (#605) |
| Degenerate return omits required keys | The unreachable PSF fallback lacks `captured_fraction` (#605) |
| Divide by a value that is zero for valid input | Blank-image Nyquist ratio divides by the DC bin (#612) |
| `inf + finite == inf` turns a perturbation into a no-op | Plano radius tolerances (#606) |

Probe: empty system, single element, zero thickness, zero/blank image, plano
surface, both surfaces plano, afocal system. Assert no exception and no `nan`.

## Autosave and GUI state

| Pattern | Example |
| --- | --- |
| An edit emits a signal nothing connects to | Custom refractive index emits `lens_updated`; only `lens_modified` drives autosave (#617) |
| A tab mutates model state without marking it dirty | Tolerance operands never trigger the debounced save (#618) |
| A read error is converted into a valid-looking empty state | `load_lenses()` returns `[]`; the next reconcile deletes the stored library (#619) |
| A control feeds only the report text | Entrance pupil / object distance are printed but not passed to the calculation (#620) |
| An enabled action silently returns | `Save As` is enabled but returns when an assembly is selected (#621) |

Probe: for every editor widget, change the value, wait past the debounce, close
and reopen, and assert the value persisted. For every loaded collection,
simulate a read failure and assert the UI shows an error and cannot overwrite
the store. Grep each emitted signal for a `.connect(`.

## Mechanical versus optical

| Pattern | Example |
| --- | --- |
| Mechanical model ignores the optical model's real geometry | Cells default to 10 mm; spacers ignore `air_gaps` (#616) |

Probe: build a system with non-default thicknesses and gaps, generate the
mechanical model, and assert lengths reconcile with `get_total_length()`.

## Optimizers and merit functions

| Pattern | Example |
| --- | --- |
| GUI builds a target/variable name the engine does not know | `"spot_size"` vs `"rms_spot_radius"`; unknown names are skipped (#630) |
| A valid configuration is scored as hard-infeasible | A cemented interface (gap 0) collects the air-gap and edge-clearance penalties (#631) |
| A variable writes a model field the geometry cache does not observe | `lens.thickness` is set, but `_update_positions` advances by the cached wrapper (#632) |
| A mode switch seeds only the parameter being optimised | Index variable resets `model_vd` to the BK7 default, Abbe variable resets `model_nd` (#633) |
| A constraint is evaluated at the wrong radius | Rim check at `diameter/2` instead of the clear aperture (#634) |
| Run-scoped state is not reset between runs | `_merit_cache` survives a merit-function swap; the swap is not undone on exception (#635) |
| A sensitivity model covers only part of the operand set | `RobustMeritFunction` understands 4 of 14 tolerance types; the index perturbation is overwritten (#636) |
| The success flag checks bounds but not feasibility | A design with a 1e8 geometry penalty is reported as "Converged" (#637) |
| A parameter is clamped after the live variable was initialised from it | `temperature` keeps the negative start; the anneal loop exits after one step (#638) |

Probe: apply every variable to its own current value and assert nothing
changes. Run each optimiser twice with different settings and assert the
results differ. Cancel a run and assert the instance state is restored. For
every GUI checkbox, assert the engine's dispatch table contains the name.

## Environment, thermal, and metric contracts

| Pattern | Example |
| --- | --- |
| A correction is stored in a field the next update overwrites | The pressure-corrected index is recomputed at 1 atm by every trace (#639) |
| A field is used as a proxy for a different state | `lens.temperature` is read as "geometry already expanded" (#640) |
| A metric is computed one way and documented another | Lateral color is a bundle centroid, not the documented chief ray (#641) |
| An override is forwarded to one consumer only | `entrance_pupil_diameter` reaches f/# but not NA or the Airy radius (#642) |
| A temperature is applied to the index but not to the geometry | The chromatic analyzer's defocus sign disagrees with the thermal model (#643) |
| A result depends on the order of an unordered argument | Axial colour uses `focal_lengths[0] - focal_lengths[-1]` (#644) |
| Sibling methods have different validation contracts | `calculate_abbe_number` raises `ValueError`, `calculate_partial_dispersion` raises `ZeroDivisionError` (#645) |

Probe: compare a traced result against the same model computed by a second
path (paraxial vs traced, analyzer vs environmental model, hand calculation),
and assert the two agree in sign and magnitude. Reorder list arguments and
assert the result is unchanged.

## Rejected as non-issues (do not re-file)

These were investigated and found intentional or already handled:

- Nested assembly `node_tree` survives the database round-trip (metadata blob
  carries it).
- Tolerancing RNG uses a private `random.Random(seed)`; not global state.
- GUI `workers.py` stop policy is documented and intentional.
- `spot_rms` is a system-only result key; GUI `.get()` handles its absence.
- Zemax stop/gap round-trip works for a stop at a gap start.
- Coating transfer-matrix signs and units check out against Fresnel limits.
- Mount catalogue dimensions and validation check out.
- The 0 K air-index special case is documented behaviour (return vacuum).
- Zero `dn/dT` for glasses without thermal data is documented, not a bug.
- `condition_at_temperature` never mutates the stored model (it deep-copies).
