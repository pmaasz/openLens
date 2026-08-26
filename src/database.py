import sqlite3
import json
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Iterator

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handles SQLite database operations for Lens and OpticalSystem storage."""
    
    def __init__(self, db_path: str = "openlens.db"):
        self.db_path = db_path
        self._initialize_db()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Open a configured connection (autocommit mode).

        Callers are responsible for closing it; prefer the
        :meth:`_connection` context manager inside this class.
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.isolation_level = None  # autocommit: explicit BEGIN for atomic blocks
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA foreign_keys=ON')  # Ensure foreign keys are enforced
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection that is always closed."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _initialize_db(self):
        """Create tables if they don't exist and handle migrations.

        Runs in autocommit mode: each DDL statement is applied as it
        executes.
        """
        with self._connection() as conn:
            cursor = conn.cursor()
            
            # Check version
            cursor.execute('PRAGMA user_version')
            version = cursor.fetchone()[0]
            
            if version == 0:
                # Lenses table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS lenses (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        radius1 REAL NOT NULL,
                        radius2 REAL NOT NULL,
                        thickness REAL NOT NULL,
                        material TEXT NOT NULL,
                        refractive_index REAL,
                        diameter REAL,
                        created_at TEXT,
                        modified_at TEXT,
                        metadata TEXT
                    )
                ''')
                
                # Assemblies table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assemblies (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        created_at TEXT,
                        modified_at TEXT,
                        metadata TEXT
                    )
                ''')
                
                # Assembly Elements table (junction table)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assembly_elements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assembly_id TEXT NOT NULL,
                        lens_id TEXT NOT NULL,
                        position REAL NOT NULL,
                        order_index INTEGER NOT NULL,
                        FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE,
                        FOREIGN KEY (lens_id) REFERENCES lenses (id)
                    )
                ''')
                
                # Assembly Air Gaps table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assembly_air_gaps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        assembly_id TEXT NOT NULL,
                        thickness REAL NOT NULL,
                        position REAL NOT NULL,
                        order_index INTEGER NOT NULL,
                        FOREIGN KEY (assembly_id) REFERENCES assemblies (id) ON DELETE CASCADE
                    )
                ''')
                
                cursor.execute('PRAGMA user_version = 1')

    def save_lens(self, lens_dict: Dict[str, Any]):
        """Save or update a single lens."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO lenses 
                    (id, name, radius1, radius2, thickness, material, refractive_index, diameter, created_at, modified_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    lens_dict.get('id'),
                    lens_dict.get('name'),
                    lens_dict.get('radius_of_curvature_1', lens_dict.get('radius1')),
                    lens_dict.get('radius_of_curvature_2', lens_dict.get('radius2')),
                    lens_dict.get('thickness'),
                    lens_dict.get('material'),
                    lens_dict.get('refractive_index'),
                    lens_dict.get('diameter'),
                    lens_dict.get('created_at'),
                    lens_dict.get('modified_at'),
                    json.dumps({k: v for k, v in lens_dict.items() if k not in ['id', 'name', 'radius_of_curvature_1', 'radius_of_curvature_2', 'radius1', 'radius2', 'thickness', 'material', 'refractive_index', 'diameter', 'created_at', 'modified_at']})
                ))
                cursor.execute('COMMIT')
            except Exception as e:
                cursor.execute('ROLLBACK')
                logger.error("Failed to save lens: %s", e)
                raise

    def _save_lens_row(self, cursor: sqlite3.Cursor,
                       lens_dict: Dict[str, Any]) -> None:
        """Insert/replace one lenses row inside the caller's transaction.

        Does not manage the transaction itself; used by save_assembly so
        all writes for one assembly commit atomically.
        """
        cursor.execute('''
            INSERT OR REPLACE INTO lenses 
            (id, name, radius1, radius2, thickness, material, refractive_index, diameter, created_at, modified_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            lens_dict.get('id'),
            lens_dict.get('name'),
            lens_dict.get('radius_of_curvature_1', lens_dict.get('radius1')),
            lens_dict.get('radius_of_curvature_2', lens_dict.get('radius2')),
            lens_dict.get('thickness'),
            lens_dict.get('material'),
            lens_dict.get('refractive_index'),
            lens_dict.get('diameter'),
            lens_dict.get('created_at'),
            lens_dict.get('modified_at'),
            json.dumps({k: v for k, v in lens_dict.items() if k not in ['id', 'name', 'radius_of_curvature_1', 'radius_of_curvature_2', 'radius1', 'radius2', 'thickness', 'material', 'refractive_index', 'diameter', 'created_at', 'modified_at']})
        ))

    def save_assembly(self, assembly_dict: Dict[str, Any]):
        """Save or update an optical system assembly.

        All writes (assembly row, elements, air gaps) happen inside a
        single BEGIN IMMEDIATE ... COMMIT block.
        """
        assembly_id = assembly_dict.get('id')
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            try:
                # 1. Save assembly metadata
                cursor.execute('''
                    INSERT OR REPLACE INTO assemblies (id, name, created_at, modified_at, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    assembly_id,
                    assembly_dict.get('name'),
                    assembly_dict.get('created_at'),
                    assembly_dict.get('modified_at'),
                    json.dumps({k: v for k, v in assembly_dict.items() if k not in ['id', 'name', 'created_at', 'modified_at', 'elements', 'air_gaps']})
                ))

                # 2. Clear existing elements and gaps for this assembly
                cursor.execute('DELETE FROM assembly_elements WHERE assembly_id = ?', (assembly_id,))
                cursor.execute('DELETE FROM assembly_air_gaps WHERE assembly_id = ?', (assembly_id,))

                # 3. Save elements
                for i, elem in enumerate(assembly_dict.get('elements', [])):
                    lens_data = elem.get('lens')
                    self._save_lens_row(cursor, lens_data)

                    cursor.execute('''
                        INSERT INTO assembly_elements (assembly_id, lens_id, position, order_index)
                        VALUES (?, ?, ?, ?)
                    ''', (assembly_id, lens_data.get('id'), elem.get('position'), i))

                # 4. Save air gaps
                for i, gap in enumerate(assembly_dict.get('air_gaps', [])):
                    cursor.execute('''
                        INSERT INTO assembly_air_gaps (assembly_id, thickness, position, order_index)
                        VALUES (?, ?, ?, ?)
                    ''', (assembly_id, gap.get('thickness'), gap.get('position'), i))

                cursor.execute('COMMIT')
            except Exception as e:
                cursor.execute('ROLLBACK')
                logger.error("Failed to save assembly: %s", e)
                raise

    def load_all(self) -> List[Dict[str, Any]]:
        """Load all standalone lenses and assemblies."""
        results = []
        lenses_lookup = {}

        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Load all lenses first (including those in assemblies)
            cursor.execute('SELECT * FROM lenses')
            for row in cursor.fetchall():
                lens = dict(row)
                lens['type'] = 'Lens' # Explicitly mark as Lens
                lens['radius_of_curvature_1'] = lens['radius1']
                lens['radius_of_curvature_2'] = lens['radius2']
                del lens['radius1']
                del lens['radius2']
                if lens['metadata']:
                    meta = json.loads(lens['metadata'])
                    lens.update(meta)
                del lens['metadata']
                results.append(lens)
                lenses_lookup[lens['id']] = lens

            # 2. Load all assemblies
            cursor.execute('SELECT * FROM assemblies')
            for row in cursor.fetchall():
                assembly = dict(row)
                assembly_id = assembly['id']
                assembly['type'] = 'OpticalSystem'

                # Load metadata
                if assembly['metadata']:
                    meta = json.loads(assembly['metadata'])
                    assembly.update(meta)
                del assembly['metadata']

                # Load elements. Named columns only: both tables define an
                # 'id' column, so 'l.*' would create a duplicate key whose
                # winner depends on column order.
                cursor.execute('''
                    SELECT l.id AS lens_pk,
                           l.name AS lens_name,
                           l.radius1 AS lens_radius1,
                           l.radius2 AS lens_radius2,
                           l.thickness AS lens_thickness,
                           l.material AS lens_material,
                           l.refractive_index AS lens_refractive_index,
                           l.diameter AS lens_diameter,
                           l.created_at AS lens_created_at,
                           l.modified_at AS lens_modified_at,
                           l.metadata AS lens_metadata,
                           ae.lens_id,
                           ae.position
                    FROM assembly_elements ae
                    JOIN lenses l ON ae.lens_id = l.id
                    WHERE ae.assembly_id = ?
                    ORDER BY ae.order_index
                ''', (assembly_id,))

                elements = []
                for e_row in cursor.fetchall():
                    e_dict = dict(e_row)
                    lens_id = e_dict['lens_id']

                    # Use the lens from lookup if possible to ensure identity
                    if lens_id in lenses_lookup:
                        lens_data = lenses_lookup[lens_id]
                    else:
                        lens_data = {
                            'id': e_dict['lens_pk'],
                            'name': e_dict['lens_name'],
                            'radius_of_curvature_1': e_dict['lens_radius1'],
                            'radius_of_curvature_2': e_dict['lens_radius2'],
                            'thickness': e_dict['lens_thickness'],
                            'material': e_dict['lens_material'],
                            'refractive_index': e_dict['lens_refractive_index'],
                            'diameter': e_dict['lens_diameter'],
                            'created_at': e_dict['lens_created_at'],
                            'modified_at': e_dict['lens_modified_at']
                        }
                        if e_dict['lens_metadata']:
                            lens_data.update(json.loads(e_dict['lens_metadata']))

                    elements.append({
                        'lens': lens_data,
                        'lens_id': lens_id,
                        'position': e_dict['position']
                    })

                assembly['elements'] = elements

                # Load air gaps
                cursor.execute('SELECT * FROM assembly_air_gaps WHERE assembly_id = ? ORDER BY order_index', (assembly_id,))
                gaps = []
                for g_row in cursor.fetchall():
                    g_dict = dict(g_row)
                    gaps.append({
                        'thickness': g_dict['thickness'],
                        'position': g_dict['position']
                    })
                assembly['air_gaps'] = gaps

                results.append(assembly)

        return results

    def delete_item(self, item_id: str):
        """Delete a lens or assembly by ID (atomic)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            try:
                cursor.execute('DELETE FROM assemblies WHERE id = ?', (item_id,))
                cursor.execute('DELETE FROM lenses WHERE id = ?', (item_id,))
                cursor.execute('COMMIT')
            except Exception as e:
                cursor.execute('ROLLBACK')
                logger.error("Failed to delete item %s: %s", item_id, e)
                raise
