#!/usr/bin/env python3
"""
openlens - Interactive Optical Lens Creation and Modification Tool
"""

import json
import os
from datetime import datetime

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


class Lens:
    def __init__(self, name="Untitled", radius_of_curvature_1=100.0, radius_of_curvature_2=-100.0,
                 thickness=5.0, diameter=50.0, refractive_index=1.5168, 
                 lens_type="Biconvex", material="BK7", wavelength=587.6, temperature=20.0):
        self.id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.name = name
        self.radius_of_curvature_1 = radius_of_curvature_1
        self.radius_of_curvature_2 = radius_of_curvature_2
        self.thickness = thickness
        self.diameter = diameter
        self.material = material
        self.wavelength = wavelength  # Design wavelength in nm
        self.temperature = temperature  # Operating temperature in °C
        
        # Get refractive index from material database if available
        if MATERIAL_DB_AVAILABLE:
            db = get_material_database()
            mat = db.get_material(material)
            if mat:
                self.refractive_index = db.get_refractive_index(material, wavelength, temperature)
            else:
                self.refractive_index = refractive_index
        else:
            self.refractive_index = refractive_index
        
        self.lens_type = lens_type
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def update_refractive_index(self, wavelength=None, temperature=None):
        """Update refractive index for new wavelength/temperature"""
        if wavelength is not None:
            self.wavelength = wavelength
        if temperature is not None:
            self.temperature = temperature
        
        if MATERIAL_DB_AVAILABLE:
            db = get_material_database()
            self.refractive_index = db.get_refractive_index(
                self.material, self.wavelength, self.temperature
            )
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "radius_of_curvature_1": self.radius_of_curvature_1,
            "radius_of_curvature_2": self.radius_of_curvature_2,
            "thickness": self.thickness,
            "diameter": self.diameter,
            "refractive_index": self.refractive_index,
            "type": self.lens_type,
            "material": self.material,
            "wavelength": self.wavelength,
            "temperature": self.temperature,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data):
        lens = cls(
            name=data.get("name", "Untitled"),
            radius_of_curvature_1=data.get("radius_of_curvature_1", 100.0),
            radius_of_curvature_2=data.get("radius_of_curvature_2", -100.0),
            thickness=data.get("thickness", 5.0),
            diameter=data.get("diameter", 50.0),
            refractive_index=data.get("refractive_index", 1.5168),
            lens_type=data.get("type", "Biconvex"),
            material=data.get("material", "BK7"),
            wavelength=data.get("wavelength", 587.6),
            temperature=data.get("temperature", 20.0)
        )
        lens.id = data.get("id", lens.id)
        lens.created_at = data.get("created_at", lens.created_at)
        lens.modified_at = data.get("modified_at", lens.modified_at)
        return lens
    
    def calculate_focal_length(self):
        """Calculate focal length using the lensmaker's equation"""
        n = self.refractive_index
        R1 = self.radius_of_curvature_1
        R2 = self.radius_of_curvature_2
        d = self.thickness
        
        if R1 == 0 or R2 == 0:
            return None
        
        power = (n - 1) * ((1/R1) - (1/R2) + ((n - 1) * d) / (n * R1 * R2))
        
        if power == 0:
            return None
        
        return 1 / power
    
    def __str__(self):
        focal_length = self.calculate_focal_length()
        focal_str = f"{focal_length:.2f}mm" if focal_length else "Undefined"
        
        return f"""
Optical Lens Details:
  ID: {self.id}
  Name: {self.name}
  Radius of Curvature 1: {self.radius_of_curvature_1}mm
  Radius of Curvature 2: {self.radius_of_curvature_2}mm
  Center Thickness: {self.thickness}mm
  Diameter: {self.diameter}mm
  Refractive Index: {self.refractive_index}
  Type: {self.lens_type}
  Material: {self.material}
  Calculated Focal Length: {focal_str}
  Created: {self.created_at}
  Modified: {self.modified_at}
"""


class LensManager:
    def __init__(self, storage_file="lenses.json"):
        self.storage_file = storage_file
        self.lenses = self.load_lenses()
    
    def load_lenses(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    return [Lens.from_dict(lens_data) for lens_data in data]
            except Exception as e:
                print(f"Error loading lenses: {e}")
                return []
        return []
    
    def save_lenses(self):
        try:
            with open(self.storage_file, 'w') as f:
                json.dump([lens.to_dict() for lens in self.lenses], f, indent=2)
            print(f"✓ Saved {len(self.lenses)} lens(es)")
        except Exception as e:
            print(f"Error saving lenses: {e}")
    
    def create_lens(self):
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
    
    def list_lenses(self):
        if not self.lenses:
            print("\nNo lenses found. Create one first!")
            return
        
        print(f"\n=== All Optical Lenses ({len(self.lenses)}) ===")
        for idx, lens in enumerate(self.lenses, 1):
            focal = lens.calculate_focal_length()
            focal_str = f"{focal:.2f}mm" if focal else "Undefined"
            print(f"{idx}. {lens.name} - {lens.material} ({lens.lens_type}) - f={focal_str}")
    
    def get_lens_by_index(self, idx):
        if 1 <= idx <= len(self.lenses):
            return self.lenses[idx - 1]
        return None
    
    def modify_lens(self):
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
    
    def view_lens(self):
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
    
    def delete_lens(self):
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


def main():
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
