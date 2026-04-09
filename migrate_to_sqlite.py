import json
import os
import sys
from typing import List, Any

# Add src to path if needed
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from database import DatabaseManager
except ImportError:
    # If running from root
    from src.database import DatabaseManager

def migrate(json_path: str = "lenses.json", db_path: str = "openlens.db"):
    if not os.path.exists(json_path):
        print(f"JSON file {json_path} not found. Skipping migration.")
        return

    print(f"Migrating {json_path} to {db_path}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_path}: {e}")
        return

    db = DatabaseManager(db_path)
    
    count = 0
    for item in data:
        try:
            if item.get('type') == 'OpticalSystem' or 'elements' in item:
                db.save_assembly(item)
            else:
                db.save_lens(item)
            count += 1
        except Exception as e:
            print(f"Error migrating item {item.get('name', 'unknown')}: {e}")

    print(f"Successfully migrated {count} items.")
    
    # Backup JSON file
    backup_path = json_path + ".bak"
    try:
        os.rename(json_path, backup_path)
        print(f"Original file backed up to {backup_path}")
    except Exception as e:
        print(f"Could not backup {json_path}: {e}")

if __name__ == "__main__":
    migrate()
