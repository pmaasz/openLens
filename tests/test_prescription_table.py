#!/usr/bin/env python3
"""Read-only prescription table and CSV export (#784)."""

import csv
import io
import unittest

from openlens.lens import Lens
from openlens.optical_system import create_doublet
from openlens.prescription import COLUMNS, build_prescription_rows, rows_to_csv


class TestPrescriptionRows(unittest.TestCase):
    def test_plano_and_conic_single_lens(self):
        lens = Lens(
            name="Plano-conic",
            radius_of_curvature_1=75.0,
            radius_of_curvature_2=float("inf"),
            thickness=4.0,
            diameter=20.0,
            material="BK7",
            conic_constant_1=-0.25,
            clear_aperture_1=18.0,
            clear_aperture_2=19.0,
        )

        rows = build_prescription_rows(lens)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["surface"], "1")
        self.assertEqual(rows[0]["radius"], "75")
        self.assertEqual(rows[0]["conic_parabolic"], "-0.25")
        self.assertEqual(rows[0]["thickness"], "4")
        self.assertEqual(rows[0]["material"], "BK7")
        self.assertEqual(rows[0]["clear_semi_diameter"], "9")
        self.assertEqual(rows[0]["mech_semi_diameter"], "10")
        self.assertEqual(rows[0]["coating"], "Uncoated")
        self.assertEqual(rows[0]["stop"], "")

        self.assertEqual(rows[1]["surface"], "2")
        self.assertEqual(rows[1]["radius"], "Infinity")
        self.assertEqual(rows[1]["conic_parabolic"], "0")
        self.assertEqual(rows[1]["material"], "AIR")
        self.assertEqual(rows[1]["clear_semi_diameter"], "9.5")
        self.assertEqual(rows[1]["mech_semi_diameter"], "10")
        self.assertNotEqual(rows[1]["thickness"], "")

    def test_assembly_rows_include_stop(self):
        system = create_doublet(diameter=25.0)
        system.set_aperture_stop(0, diameter=20.0)

        rows = build_prescription_rows(system)

        # Two elements -> 4 element surfaces plus 1 stop surface.
        self.assertEqual(len(rows), 5)
        self.assertEqual([r["surface"] for r in rows], ["1", "2", "3", "4", "5"])

        stop_rows = [r for r in rows if r["stop"] == "STOP"]
        self.assertEqual(len(stop_rows), 1)
        stop = stop_rows[0]
        self.assertEqual(stop["radius"], "Infinity")
        self.assertEqual(stop["material"], "AIR")
        self.assertEqual(stop["clear_semi_diameter"], "10")
        self.assertEqual(stop["mech_semi_diameter"], "10")
        self.assertEqual(stop["conic_parabolic"], "0")

        # Element materials and sequence are preserved.
        self.assertEqual(rows[0]["material"], "BK7")
        self.assertEqual(rows[3]["material"], "SF11")
        self.assertEqual(rows[4]["material"], "AIR")

    def test_csv_output_matches_rows_and_is_safe(self):
        rows = [
            {
                "surface": "1",
                "radius": "Infinity",
                "conic_parabolic": "0",
                "thickness": "5",
                "material": 'Glass, "special"',
                "clear_semi_diameter": "10",
                "mech_semi_diameter": "12.5",
                "coating": "Uncoated",
                "stop": "",
            }
        ]

        text = rows_to_csv(rows)
        parsed = list(csv.DictReader(io.StringIO(text)))

        self.assertEqual(list(parsed[0].keys()), COLUMNS)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["radius"], "Infinity")
        self.assertEqual(parsed[0]["material"], 'Glass, "special"')

    def test_no_target_returns_empty(self):
        self.assertEqual(build_prescription_rows(None), [])
        self.assertEqual(
            rows_to_csv([]),
            (
                "surface,radius,conic_parabolic,thickness,material,"
                "clear_semi_diameter,mech_semi_diameter,coating,stop\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
