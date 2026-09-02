#!/usr/bin/env python3
"""
openlens - Interactive Optical Lens Creation and Modification Tool
"""

import logging
from datetime import datetime
from typing import Optional, List

# Setup module logger
logger = logging.getLogger(__name__)

from .lens import Lens
from .validation import (
    ValidationError,
    validate_radius,
    validate_thickness,
    validate_diameter,
    validate_refractive_index,
    validate_lens_name,
)

try:
    from .gui.storage import load_lenses, save_lenses

    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False


class LensManager:
    """
    Manages a collection of optical lenses with persistence to SQLite.

    Attributes:
        storage_file: Path to SQLite file for lens storage
        lenses: List of Lens objects
    """

    def __init__(self, storage_file: str = "openlens.db") -> None:
        if storage_file.endswith(".json"):
            storage_file = storage_file[: -len(".json")] + ".db"
            print(f"note: storage is SQLite; using {storage_file}")

        self.storage_file = storage_file
        self.lenses = self.load_lenses()

    def load_lenses(self) -> List[Lens]:
        """
        Load lenses from storage.

        Returns:
            List of Lens objects (empty if error occurs)
        """
        if STORAGE_AVAILABLE:
            try:
                # Filter out OpticalSystem objects for the simple LensManager
                all_items = load_lenses(self.storage_file)
                return [item for item in all_items if isinstance(item, Lens)]
            except Exception as e:
                logger.error("Error loading lenses via storage: %s", e)
                return []
        return []

    def save_lenses(self) -> bool:
        """
        Save all lenses to storage.

        Returns:
            bool: True if save successful, False otherwise
        """
        if STORAGE_AVAILABLE:
            try:
                return save_lenses(self.lenses, self.storage_file)
            except Exception as e:
                logger.error("Error saving lenses via storage: %s", e)
                return False
        return False

    def create_lens(self) -> Optional[Lens]:
        """
        Interactive CLI method to create a new lens.

        Prompts user for lens parameters and creates a new Lens object.
        Adds the lens to the collection and saves to storage.

        Returns:
            Created Lens object, or None if creation fails
        """
        print("\n=== Create New Optical Lens ===")
        name = input("Lens name: ").strip() or "Untitled"

        r1 = self._prompt_float(
            "Radius of curvature 1 (mm) [100.0]: ",
            100.0,
            lambda v: validate_radius(v, param_name="Radius 1"),
        )
        r2 = self._prompt_float(
            "Radius of curvature 2 (mm) [-100.0]: ",
            -100.0,
            lambda v: validate_radius(v, param_name="Radius 2"),
        )
        thickness = self._prompt_float(
            "Center thickness (mm) [5.0]: ", 5.0, lambda v: validate_thickness(v)
        )
        diameter = self._prompt_float(
            "Diameter (mm) [50.0]: ", 50.0, lambda v: validate_diameter(v)
        )
        refractive_index = self._prompt_float(
            "Refractive index [1.5168]: ",
            1.5168,
            lambda v: validate_refractive_index(v),
        )

        lens_type = (
            input("Type (Biconvex/Biconcave/Plano-Convex/etc) [Biconvex]: ").strip()
            or "Biconvex"
        )
        material = input("Material (BK7/Fused Silica/etc) [BK7]: ").strip() or "BK7"

        lens = Lens(
            name=name,
            radius_of_curvature_1=r1,
            radius_of_curvature_2=r2,
            thickness=thickness,
            diameter=diameter,
            refractive_index=refractive_index,
            lens_type=lens_type,
            material=material,
        )
        self.lenses.append(lens)
        self.save_lenses()

        print(f"\n✓ Lens created successfully!")
        print(lens)
        return lens

    @staticmethod
    def _prompt_float(prompt: str, default: float, validator) -> float:
        """Prompt until a value passes ``validator``; empty accepts default."""
        while True:
            raw = input(prompt).strip()
            if not raw:
                return default
            try:
                return validator(float(raw))
            except ValueError:
                print(f"  not a number: {raw!r}")
            except ValidationError as e:
                print(f"  invalid: {e}")

    def list_lenses(self) -> None:
        """
        Display a summary of all lenses in the collection.

        Shows lens name, material, type, and calculated focal length.
        """
        if not self.lenses:
            print("\nNo lenses found. Create one first!")
            return

        print(f"\n=== All Optical Lenses ({len(self.lenses)}) ===")
        for idx, lens in enumerate(self.lenses, 1):
            focal = lens.calculate_focal_length()
            focal_str = f"{focal:.2f}mm" if focal is not None else "Undefined"
            print(
                f"{idx}. {lens.name} - {lens.material} ({lens.lens_type}) - f={focal_str}"
            )

    def get_lens_by_index(self, idx: int) -> Optional[Lens]:
        """
        Get a lens by its 1-based index in the collection.

        Args:
            idx: 1-based index of the lens

        Returns:
            Lens object if index is valid, None otherwise
        """
        if 1 <= idx <= len(self.lenses):
            return self.lenses[idx - 1]
        return None

    def modify_lens(self) -> None:
        """
        Interactive CLI method to modify an existing lens.

        Prompts user to select a lens and update its parameters.
        Empty input keeps current value.
        """
        if not self.lenses:
            print("\nNo lenses to modify. Create one first!")
            return

        self.list_lenses()
        try:
            idx = int(input("\nSelect lens number to modify: "))
            lens = self.get_lens_by_index(idx)

            if not lens:
                print("Invalid selection.")
                return

            print(f"\nModifying: {lens.name}")
            print("(Press Enter to keep current value)")

            new_name = input(f"Name [{lens.name}]: ").strip()
            if new_name:
                lens.name = validate_lens_name(new_name)

            def _apply(attr, prompt, validator, current):
                raw = input(prompt).strip()
                if not raw:
                    return
                try:
                    setattr(lens, attr, validator(float(raw)))
                except ValueError:
                    print(f"  not a number: {raw!r} - keeping {current}")
                except ValidationError as e:
                    print(f"  invalid: {e} - keeping {current}")

            _apply(
                "radius_of_curvature_1",
                f"Radius of curvature 1 [{lens.radius_of_curvature_1}]: ",
                lambda v: validate_radius(v, param_name="Radius 1"),
                lens.radius_of_curvature_1,
            )
            _apply(
                "radius_of_curvature_2",
                f"Radius of curvature 2 [{lens.radius_of_curvature_2}]: ",
                lambda v: validate_radius(v, param_name="Radius 2"),
                lens.radius_of_curvature_2,
            )
            _apply(
                "thickness",
                f"Thickness [{lens.thickness}]: ",
                validate_thickness,
                lens.thickness,
            )
            _apply(
                "diameter",
                f"Diameter [{lens.diameter}]: ",
                validate_diameter,
                lens.diameter,
            )
            _apply(
                "refractive_index",
                f"Refractive index [{lens.refractive_index}]: ",
                validate_refractive_index,
                lens.refractive_index,
            )

            new_type = input(f"Type [{lens.lens_type}]: ").strip()
            if new_type:
                lens.lens_type = new_type

            new_material = input(f"Material [{lens.material}]: ").strip()
            if new_material:
                lens.material = new_material

            lens.modified_at = datetime.now().isoformat()
            self.save_lenses()

            print(f"\n✓ Lens updated successfully!")
            print(lens)

        except (ValueError, IndexError):
            print("Invalid input.")

    def view_lens(self) -> None:
        """
        Interactive CLI method to view detailed information about a lens.

        Prompts user to select a lens and displays its full details.
        """
        if not self.lenses:
            print("\nNo lenses to view.")
            return

        self.list_lenses()
        try:
            idx = int(input("\nSelect lens number to view: "))
            lens = self.get_lens_by_index(idx)

            if lens:
                print(lens)
            else:
                print("Invalid selection.")
        except ValueError:
            print("Invalid input.")

    def delete_lens(self) -> None:
        """
        Interactive CLI method to delete a lens from the collection.

        Prompts user to select a lens and confirm deletion.
        Updates storage after deletion.
        """
        if not self.lenses:
            print("\nNo lenses to delete.")
            return

        self.list_lenses()
        try:
            idx = int(input("\nSelect lens number to delete: "))
            lens = self.get_lens_by_index(idx)

            if not lens:
                print("Invalid selection.")
                return

            confirm = input(f"Delete '{lens.name}'? (yes/no): ").strip().lower()
            if confirm == "yes":
                self.lenses.pop(idx - 1)
                self.save_lenses()
                print(f"✓ Lens deleted successfully!")
            else:
                print("Deletion cancelled.")

        except (ValueError, IndexError):
            print("Invalid input.")


def main() -> None:
    """Main entry point for the interactive CLI lens editor."""
    manager = LensManager()

    print("=" * 60)
    print("   openlens - Optical Lens Creation & Modification Tool")
    print("=" * 60)

    while True:
        print("\n--- Menu ---")
        print("1. Create new lens")
        print("2. List all lenses")
        print("3. View lens details")
        print("4. Modify lens")
        print("5. Delete lens")
        print("6. Exit")

        choice = input("\nSelect option: ").strip()

        if choice == "1":
            manager.create_lens()
        elif choice == "2":
            manager.list_lenses()
        elif choice == "3":
            manager.view_lens()
        elif choice == "4":
            manager.modify_lens()
        elif choice == "5":
            manager.delete_lens()
        elif choice == "6":
            print("\nGoodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
