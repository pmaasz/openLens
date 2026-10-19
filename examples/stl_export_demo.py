"""Write a single test lens to STL.

Run with ``python3 examples/stl_export_demo.py``; it writes ``test_lens.stl``
into the working directory. Moved out of ``openlens/stl_export.py`` so the
library module does not run a smoke export on import (#478).
"""

from openlens.stl_export import STLExporter


def main() -> None:
    exporter = STLExporter()
    exporter.export_lens_to_stl(100, -100, 5, 50, "test_lens.stl")
    print("Done")


if __name__ == "__main__":
    main()
