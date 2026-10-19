"""Regression: the AGF importer must read the real Zemax file format.

Every defect here made imported glasses optically wrong rather than merely
untidy. `tests/data/test_catalog.agf` was itself written to match the buggy
parser - an NM line with no MIL field - so the existing test asserted the
mistake back at us.

Real AGF field layouts:

    NM <name> <formula> <MIL#> <Nd> <Vd> <TCE> <DP> <ignore...>
    CD <K1> <L1> <K2> <L2> <K3> <L3>          (interleaved pairs)
    IT <lambda_nm> <T> <thickness_mm>         (one line per wavelength)
    ED <TCE> <dT/dP> <dPg/dT> <DP> <ignore...>

The previous importer read parts[3] as Nd - which is the MIL number - so an
imported N-BK7 came out with nd 517642.251. It also mapped the interleaved
coefficients as B1 B2 B3 C1 C2 C3, and read all internal transmission as one
line that each subsequent IT line overwrote.

The reference glass below is Schott N-BK7; its Sellmeier coefficients give
n(587.6 nm) = 1.51688, i.e. the published Nd of 1.5168. That round trip is the
test: a mis-mapped coefficient does not reproduce it.

Note on isolation: every test here passes an explicit temp ``db_path``.
``MaterialDatabase(None)`` falls back to the real ``data/materials.json`` and
``add_material`` writes to it, so a test that uses it persists whatever glasses
it imported into the user's catalog - which is how a mis-parsed N-BK7 and a
fabricated ``UNKNOWN_F`` ended up in a real materials file while this bug was
being investigated. Filed as #490.
"""

import os
import tempfile
import unittest

from openlens.material_database import MaterialDatabase

# Schott N-BK7, AGF formula 2 (Sellmeier 1), interleaved B1 C1 B2 C2 B3 C3.
N_BK7 = """
NM N-BK7 2 517642 1.5168 64.17 7.1 2.51 0 0 0 0 0 0
CD 1.03961212 0.00600069867 0.231792344 0.0200179144 1.01046945 103.560653
IT 400.0 0.980 10.0
IT 500.0 0.995 10.0
IT 600.0 0.993 10.0
IT 700.0 0.975 10.0
"""

# A glass at a different reference thickness, to prove thickness is read from
# the IT lines rather than assumed.
SF11 = """
NM SF11 2 462384 1.7847 25.68 6.1 3.22 0 0 0 0 0 0
CD 1.73759695 0.013188707 0.313747346 0.0623068142 1.89877801 155.23629
IT 480.0 0.90 5.0
IT 550.0 0.92 5.0
IT 650.0 0.88 5.0
"""

# Thermal data refined by an ED line.
N_SF5 = """
NM N-SF5 2 48718 1.6727 32.25 0.0 2.86 0 0 0 0 0 0
CD 1.52481889 0.011254756 0.187085527 0.0588995392 1.42729015 129.141675
ED 8.2 1.0e-7 -1.0e-7 2.86 0 0 0 0
IT 550.0 0.95 10.0
"""


class _AgfCase(unittest.TestCase):
    """An isolated MaterialDatabase fed a temporary AGF file."""

    def setUp(self):
        # db_path must be a real temp file: MaterialDatabase(None) falls back
        # to the real data/materials.json, so a test using it writes parsed
        # glasses into the user's catalog. See the module docstring.
        self.catalog = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.catalog.close()
        self.addCleanup(os.unlink, self.catalog.name)
        self.db = MaterialDatabase(db_path=self.catalog.name)

        handle = tempfile.NamedTemporaryFile("w", suffix=".agf", delete=False)
        handle.write(self.agf_text())
        handle.close()
        self.path = handle.name
        self.addCleanup(os.unlink, self.path)

    def agf_text(self):
        return N_BK7

    def _import(self):
        return self.db.import_agf_catalog(self.path)


class TestNmLineFieldPositions(_AgfCase):
    """parts[3] is the MIL number, not Nd."""

    def test_nd_is_not_the_mil_number(self):
        """The headline defect: nd 517642.251 instead of 1.5168."""
        self._import()

        mat = self.db.get_material("N-BK7")
        self.assertIsNotNone(mat)
        self.assertAlmostEqual(mat.nd, 1.5168, places=4)

    def test_vd_is_read_from_the_right_field(self):
        self._import()

        self.assertAlmostEqual(self.db.get_material("N-BK7").vd, 64.17, places=2)

    def test_thermal_expansion_comes_from_its_own_field(self):
        """TCE is in units of 1e-6/K on the NM line."""
        self._import()

        self.assertAlmostEqual(self.db.get_material("N-BK7").thermal_expansion, 7.1e-6, places=9)

    def test_density_comes_from_its_own_field(self):
        self._import()

        self.assertAlmostEqual(self.db.get_material("N-BK7").density, 2.51, places=2)

    def test_the_glass_is_still_named_from_the_name_field(self):
        self._import()

        self.assertIsNotNone(self.db.get_material("N-BK7"))


class TestSellmeierDeinterleaving(_AgfCase):
    """CD holds K1 L1 K2 L2 K3 L3, not B1 B2 B3 C1 C2 C3."""

    def test_coefficients_are_mapped_as_pairs(self):
        self._import()

        mat = self.db.get_material("N-BK7")
        self.assertAlmostEqual(mat.B1, 1.03961212, places=8)
        self.assertAlmostEqual(mat.C1, 0.00600069867, places=10)
        self.assertAlmostEqual(mat.B2, 0.231792344, places=9)
        self.assertAlmostEqual(mat.C2, 0.0200179144, places=10)
        self.assertAlmostEqual(mat.B3, 1.01046945, places=8)
        self.assertAlmostEqual(mat.C3, 103.560653, places=6)

    def test_the_referenced_index_is_reproduced(self):
        """n at the d-line must come out at the glass's own Nd.

        This is the check that a mis-mapped coefficient cannot pass: the wrong
        pairing produces a wildly different index.
        """
        self._import()

        n_d = self.db.get_refractive_index("N-BK7", 587.6, 20.0)

        self.assertAlmostEqual(n_d, 1.5168, places=3)

    def test_index_is_monotonic_in_the_expected_direction(self):
        """Blue refracts more than red - a sanity check on the dispersion."""
        self._import()

        blue = self.db.get_refractive_index("N-BK7", 486.1, 20.0)
        red = self.db.get_refractive_index("N-BK7", 656.3, 20.0)

        self.assertGreater(blue, red)
        # n_F - n_C = (Nd - 1) / Vd
        expected = (1.5168 - 1.0) / 64.17
        self.assertAlmostEqual(blue - red, expected, delta=expected * 0.05)


class TestInternalTransmissionLines(_AgfCase):
    """IT is one wavelength per line, not a packed line."""

    def test_every_it_line_is_kept(self):
        """Previously each line overwrote the previous one."""
        self._import()

        data = self.db.get_material("N-BK7").transmission_data

        self.assertEqual(
            sorted(wavelength for wavelength, _ in data),
            [400.0, 500.0, 600.0, 700.0],
        )

    def test_each_wavelength_keeps_its_own_value(self):
        self._import()

        data = dict(self.db.get_material("N-BK7").transmission_data)

        self.assertAlmostEqual(data[400.0], 0.980, places=6)
        self.assertAlmostEqual(data[500.0], 0.995, places=6)
        self.assertAlmostEqual(data[700.0], 0.975, places=6)


class TestTransmissionThickness(_AgfCase):
    """The thickness is a field on the IT line, not the first number."""

    def agf_text(self):
        return SF11

    def test_thickness_is_read_from_the_it_line(self):
        """Previously the thickness was read as a wavelength."""
        self._import()

        mat = self.db.get_material("SF11")
        self.assertAlmostEqual(mat.transmission_thickness, 5.0, places=6)

    def test_wavelengths_are_not_the_thickness(self):
        self._import()

        data = dict(self.db.get_material("SF11").transmission_data)

        self.assertEqual(sorted(data), [480.0, 550.0, 650.0])
        self.assertNotIn(5.0, data, "the thickness leaked in as a wavelength")


class TestTransmissionIsValidated(_AgfCase):
    """Transmission is a fraction; a catalog with a stray value must not win."""

    def agf_text(self):
        return """
NM BAD_T 2 1 1.5000 60.0 7.1 2.5 0 0 0 0 0 0
CD 1.0 0.007 0.2 0.02 1.0 100.0
IT 550.0 9.09e+27 10.0
"""

    def test_an_out_of_range_transmission_is_dropped(self):
        """T = 9.09e+27 is not a fraction and must not be stored."""
        self._import()

        data = self.db.get_material("BAD_T").transmission_data

        self.assertEqual(data, [], "an impossible transmission was imported")


class TestUnsupportedFormulas(_AgfCase):
    """A formula the importer cannot map must not be silently mis-mapped."""

    def agf_text(self):
        return """
NM UNKNOWN_F 99 4242 1.7000 50.0 7.1 2.5 0 0 0 0 0 0
CD 1.0 0.007 0.2 0.02 1.0 100.0
IT 550.0 0.95 10.0
"""

    def test_an_unknown_formula_is_skipped(self):
        self._import()

        self.assertIsNone(self.db.get_material("UNKNOWN_F"))


class TestEdLineRefinesThermalData(_AgfCase):
    """ED carries a more precise TCE than the NM line's placeholder 0.0."""

    def agf_text(self):
        return N_SF5

    def test_ed_supplies_the_thermal_expansion(self):
        self._import()

        self.assertAlmostEqual(self.db.get_material("N-SF5").thermal_expansion, 8.2e-6, places=9)

    def test_ed_does_not_disturb_the_optics(self):
        self._import()

        mat = self.db.get_material("N-SF5")
        self.assertAlmostEqual(mat.nd, 1.6727, places=4)
        self.assertAlmostEqual(mat.C3, 129.141675, places=6)


class TestExistingFixtureIsRealAgf(unittest.TestCase):
    """The shipped fixture must not encode the bug it let through.

    ``tests/data/test_catalog.agf`` used to omit the MIL field, matching the
    parser instead of the format, so ``test_material_database.py`` asserted
    the misparse back at the importer.
    """

    @property
    def fixture(self):
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "data", "test_catalog.agf")

    def test_fixture_exists(self):
        self.assertTrue(os.path.exists(self.fixture))

    def test_every_nm_line_carries_a_mil_field(self):
        with open(self.fixture) as handle:
            nm_lines = [ln for ln in handle if ln.startswith("NM ")]
        self.assertTrue(nm_lines, "the fixture has no NM lines")

        for line in nm_lines:
            parts = line.split()
            # NM name formula mil nd vd tce density ...
            self.assertGreaterEqual(
                len(parts), 8, f"NM line too short to hold a MIL number: {line!r}"
            )
            float(parts[3])  # MIL number
            self.assertGreater(float(parts[4]), 1.0, f"nd looks like a MIL number: {line!r}")
            self.assertGreater(float(parts[5]), 1.0, f"vd looks like an nd: {line!r}")

    def test_fixture_imports_to_the_declared_indices(self):
        handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        db = MaterialDatabase(db_path=handle.name)

        count = db.import_agf_catalog(self.fixture)

        self.assertGreaterEqual(count, 2)
        mat = db.get_material("TEST_GLASS")
        self.assertIsNotNone(mat)
        self.assertAlmostEqual(mat.nd, 1.5168, places=3)
        self.assertAlmostEqual(mat.vd, 64.17, places=1)
        # The invariant that matters: the declared Nd is only reproducible from
        # the coefficients if they were de-interleaved correctly.
        self.assertAlmostEqual(
            db.get_refractive_index("TEST_GLASS", 587.56, 20.0), 1.5168, places=3
        )


if __name__ == "__main__":
    unittest.main()
