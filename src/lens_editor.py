#!/usr/bin/env python3
"""
openlens - Interactive Optical Lens Creation and Modification Tool
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from .lens import Lens
except (ImportError, ValueError):
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from lens import Lens
    except ImportError:
        pass  # Will be defined below if import fails, or we can raise error

# Try to import material database
try:
    from .material_database import get_material_database
    MATERIAL_DB_AVAILABLE = True
except (ImportError, ValueError):
    # Fallback for direct script execution
    try:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        from material_database import get_material_database
        MATERIAL_DB_AVAILABLE = True
    except ImportError:
        MATERIAL_DB_AVAILABLE = False

# Try to import validation utilities
try:
    from .validation import (
        validate_json_file_path,
        validate_file_path,
        validate_lenses_json_schema,
        validate_lens_data_schema,
        ValidationError
    )
except (ImportError, ValueError):
    try:
        from validation import (
            validate_json_file_path,
            validate_file_path,
            validate_lenses_json_schema,
            validate_lens_data_schema,
            ValidationError
        )
    except ImportError:
        # Fallback if validation module not available
        from typing import Any
        ValidationError = ValueError
        def validate_json_file_path(path: Any, **kwargs: Any) -> Path:
            return Path(path)
        def validate_file_path(path: Any, **kwargs: Any) -> Path:
            return Path(path)
        def validate_lenses_json_schema(data: Any) -> Any:
            return data
        def validate_lens_data_schema(data: Any, **kwargs: Any) -> Any:
            return data


class LensManager:
    """
    Manages a collection of optical lenses with persistence to JSON.
    
    Attributes:
        storage_file: Path to JSON file for lens storage
        lenses: List of Lens objects
    """
    
    def __init__(self, storage_file: str = "lenses.json") -> None:
        try:
            self.storage_file = str(validate_json_file_path(
                storage_file, 
                must_exist=False
            ))
        except (ValidationError, Exception) as e:
            print(f"Warning: Invalid storage file path '{storage_file}': {e}")
            print(f"Using default: lenses.json")
            self.storage_file = "lenses.json"
        
        self.lenses = self.load_lenses()
    
    def load_lenses(self) -> List[Lens]:
        """
        Load lenses from JSON storage file with path and schema validation.
        
        Returns:
            List of Lens objects (empty if file doesn't exist or error occurs)
        """
        try:
            # Validate file path
            file_path = validate_file_path(
                self.storage_file,
                must_exist=True,
                create_parent=False
            )
            
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate JSON schema
            try:
                validated_data = validate_lenses_json_schema(data)
            except ValidationError as e:
                print(f"Error: Invalid JSON schema in storage file: {e}")
                return []
            
            # Load lenses from validated data
            lenses = []
            for i, lens_data in enumerate(validated_data):
                try:
                    # Additional validation happens in from_dict via Lens.__init__
                    lenses.append(Lens.from_dict(lens_data))
                except Exception as e:
                    print(f"Warning: Failed to load lens {i}: {e}")
            
            return lenses
            
        except ValidationError as e:
            # File doesn't exist or path invalid - return empty list
            return []
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in storage file: {e}")
            return []
        except Exception as e:
            print(f"Error loading lenses: {e}")
            return []
    
    def save_lenses(self) -> bool:
        """
        Save all lenses to JSON storage file with path validation.
        
        Serializes all lenses in the collection to JSON format with indentation.
        Validates file path and handles errors gracefully.
        
        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # Validate and prepare file path
            file_path = validate_json_file_path(
                self.storage_file,
                must_exist=False
            )
            
            # Ensure parent directory exists and is writable
            parent_dir = file_path.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            
            if not os.access(parent_dir, os.W_OK):
                print(f"Error: Directory is not writable: {parent_dir}")
                return False
            
            # Serialize lenses to JSON
            data = [lens.to_dict() for lens in self.lenses]
            
            # Write to file with atomic operation (write to temp, then rename)
            temp_path = file_path.with_suffix('.tmp')
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                # Atomic rename
                temp_path.replace(file_path)
                
                print(f"✓ Saved {len(self.lenses)} lens(es) to {file_path}")
                return True
                
            finally:
                # Clean up temp file if it still exists
                if temp_path.exists():
                    temp_path.unlink()
            
        except ValidationError as e:
            print(f"Error: Invalid file path: {e}")
            return False
        except PermissionError as e:
            print(f"Error: Permission denied when writing to {self.storage_file}: {e}")
            return False
        except OSError as e:
            print(f"Error: OS error when saving lenses: {e}")
            return False
        except Exception as e:
            print(f"Error saving lenses: {e}")
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
        
        try:
            r1 = float(input("Radius of curvature 1 (mm) [100.0]: ").strip() or "100.0")
            r2 = float(input("Radius of curvature 2 (mm) [-100.0]: ").strip() or "-100.0")
            thickness = float(input("Center thickness (mm) [5.0]: ").strip() or "5.0")
            diameter = float(input("Diameter (mm) [50.0]: ").strip() or "50.0")
            refractive_index = float(input("Refractive index [1.5168]: ").strip() or "1.5168")
        except ValueError:
            print("Invalid number format. Using defaults.")
            r1, r2, thickness, diameter, refractive_index = 100.0, -100.0, 5.0, 50.0, 1.5168
        
        lens_type = input("Type (Biconvex/Biconcave/Plano-Convex/etc) [Biconvex]: ").strip() or "Biconvex"
        material = input("Material (BK7/Fused Silica/etc) [BK7]: ").strip() or "BK7"
        
        lens = Lens(name, r1, r2, thickness, diameter, refractive_index, lens_type, material)
        self.lenses.append(lens)
        self.save_lenses()
        
        print(f"\n✓ Lens created successfully!")
        print(lens)
        return lens
    
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
            focal_str = f"{focal:.2f}mm" if focal else "Undefined"
            print(f"{idx}. {lens.name} - {lens.material} ({lens.lens_type}) - f={focal_str}")
    
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
                lens.name = new_name
            
            new_r1 = input(f"Radius of curvature 1 [{lens.radius_of_curvature_1}]: ").strip()
            if new_r1:
                lens.radius_of_curvature_1 = float(new_r1)
            
            new_r2 = input(f"Radius of curvature 2 [{lens.radius_of_curvature_2}]: ").strip()
            if new_r2:
                lens.radius_of_curvature_2 = float(new_r2)
            
            new_thickness = input(f"Thickness [{lens.thickness}]: ").strip()
            if new_thickness:
                lens.thickness = float(new_thickness)
            
            new_diameter = input(f"Diameter [{lens.diameter}]: ").strip()
            if new_diameter:
                lens.diameter = float(new_diameter)
            
            new_refr = input(f"Refractive index [{lens.refractive_index}]: ").strip()
            if new_refr:
                lens.refractive_index = float(new_refr)
            
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
            if confirm == 'yes':
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
        
        if choice == '1':
            manager.create_lens()
        elif choice == '2':
            manager.list_lenses()
        elif choice == '3':
            manager.view_lens()
        elif choice == '4':
            manager.modify_lens()
        elif choice == '5':
            manager.delete_lens()
        elif choice == '6':
            print("\nGoodbye!")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
