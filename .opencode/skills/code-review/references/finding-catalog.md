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

## Serialisation blobs and metadata

| Pattern | Example |
| --- | --- |
| Two writers of the same record use different shapes | The assembly writer nests `metadata`; the standalone writer flattens it, and the reader drops the nested copy (#651) |
| The reader merges the whole record into a user namespace | `_metadata_merge` returns the blob, so `row_type`/`is_library` land in `lens.metadata` (#651) |

Probe: save the same model through every writer (standalone, as an assembly
member, through the GUI service), reload it, and assert every user-facing
field survives byte-for-byte.

## Shipped data versus the application's own rules

| Pattern | Example |
| --- | --- |
| A literal data table is never validated by the app's own validator | Four presets describe lenses with crossed surfaces (#652) |
| A standards table contradicts its own stated convention | EF/F mounts are bayonet but carry a thread, so the BOM names a screw adapter (#655) |
| Seed data is re-derived by hand instead of taken from the reference | The seeded assembly stores every air gap at position 0.0 (#658) |

Probe: run `check_physical_feasibility()` (or the module's own invariant) over
every shipped preset, seed row and catalogue entry; compare the seed with
the reference object's `to_dict()`.

## Update, download, and atomic-write paths

| Pattern | Example |
| --- | --- |
| The only check on a download is a size comparison | The updater accepts any payload of the reported length and installs it over the binary (#653) |
| A temp path is derived only from the target name | `atomic_write` uses `<name>.tmp`, so concurrent writers collide and lose data (#654) |
| A created temporary directory is never owned | The updater leaves `/tmp/openlens-update-*` (and the payload) behind (#656) |

Probe: intercept the download with a fake opener that returns a payload of
the right length but the wrong content; write the same file from two threads
at once; list the temp directory after an update attempt.

## One spelling per physical quantity

| Pattern | Example |
| --- | --- |
| The model accepts a value the validator rejects | `Lens` maps radius 0 to `inf`; `validate_radius` rejects both (#657) |
| A prompt offers a default its own check refuses | The CLI's default lens fails the CLI's feasibility check (#648) |
| The same validation rule is not applied on every path | The CLI create path checks feasibility, the modify path does not (#647) |

Probe: for every validator, feed the values the model itself produces and
assert they are accepted; run every create/edit path with the defaults and
assert the result is accepted.

## Exported geometry: orientation, extents, and counts

| Pattern | Example |
| --- | --- |
| A default argument silently selects the wrong winding | The assembly STL export winds the back cap like the front, so the solid is inside-out (#660) |
| An extent is derived from every point of a block, including construction points | The STEP reader reports a lens's curvature centres as its axial extent (#661) |
| A derived count is unbounded | The Fresnel facet count follows `groove_pitch` with no cap (#664) |
| A helper's contract and its implementation disagree | `calculate_surface_profile` never returns `None` although the docstring promises it; the list input of `generate_edge_triangles` raises `IndexError` (#663) |
| The unit of a value is guessed from its magnitude | `if wavelength > 1.0: # likely nm` mis-scales every micrometre value (#665) |

Probe: for every mesh export, compute the signed volume of the result and
assert it is positive and close to the analytic volume; for every extent,
assert it matches the geometry that produced it; for every count derived from
user data, assert an upper bound; for every unit-carrying parameter, assert
an explicit unit is documented and used.

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
