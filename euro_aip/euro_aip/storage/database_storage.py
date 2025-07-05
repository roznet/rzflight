#!/usr/bin/env python3

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

from ..models.euro_aip_model import EuroAipModel
from ..models.airport import Airport
from ..models.runway import Runway
from ..models.procedure import Procedure
from ..models.aip_entry import AIPEntry
from ..models.border_crossing_entry import BorderCrossingEntry
from ..models.border_crossing_change import BorderCrossingChange
from .field_definitions import AirportFields, RunwayFields, SchemaManager

logger = logging.getLogger(__name__)

class DatabaseStorage:
    """
    Unified database storage for EuroAipModel with change tracking.
    
    This class provides efficient storage and retrieval of airport data with
    automatic change detection and history tracking.
    """
    
    def __init__(self, database_path: str, save_only_std_fields: bool = True):
        """
        Initialize the database storage.
        
        Args:
            database_path: Path to the SQLite database file
            save_only_std_fields: If True, only save AIP entries with std_field_id. 
                                 If False, save all AIP entries. Defaults to True.
        """
        self.database_path = Path(database_path)
        self.schema_manager = SchemaManager()
        self.save_only_std_fields = save_only_std_fields
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure the database file exists and has the correct schema."""
        if not self.database_path.exists():
            self._create_schema()
        else:
            # Check if schema needs to be updated
            self._migrate_schema_if_needed()
    
    def _create_schema(self):
        """Create the database schema using field definitions."""
        with self._get_connection() as conn:
            # Create airports table using field definitions
            airports_sql = self.schema_manager.get_create_table_sql(
                "airports", 
                AirportFields.get_all_fields(), 
                primary_key="icao_code"
            )
            conn.execute(airports_sql)
            
            # Create runways table using field definitions
            runways_sql = self.schema_manager.get_create_table_sql(
                "runways", 
                RunwayFields.get_all_fields()
            )
            # Add auto-incrementing id column
            runways_sql = runways_sql.replace(
                "CREATE TABLE runways (",
                "CREATE TABLE runways (\n    id INTEGER PRIMARY KEY AUTOINCREMENT,"
            )
            conn.execute(runways_sql)
            
            # Create procedures table (keeping existing structure for now)
            conn.execute('''
                CREATE TABLE procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    name TEXT,
                    procedure_type TEXT,
                    approach_type TEXT,
                    runway_ident TEXT,
                    runway_letter TEXT,
                    runway TEXT,
                    category TEXT,
                    minima TEXT,
                    notes TEXT,
                    source TEXT,
                    authority TEXT,
                    raw_name TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            # Create AIP entries table (keeping existing structure for now)
            conn.execute('''
                CREATE TABLE aip_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    section TEXT,
                    field TEXT,
                    value TEXT,
                    std_field TEXT,
                    std_field_id INTEGER,
                    mapping_score REAL,
                    alt_field TEXT,
                    alt_value TEXT,
                    source TEXT,
                    source_priority INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code),
                    UNIQUE(airport_icao, section, field, source)
                )
            ''')
            
            # Change tracking tables
            conn.execute('''
                CREATE TABLE aip_field_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    section TEXT,
                    field TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    std_field TEXT,
                    std_field_id INTEGER,
                    mapping_score REAL,
                    source TEXT,
                    changed_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE airport_field_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    field_type TEXT,
                    source TEXT,
                    changed_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE runway_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    runway_id INTEGER,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    field_type TEXT,
                    source TEXT,
                    changed_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code),
                    FOREIGN KEY (runway_id) REFERENCES runways (id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE procedure_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    procedure_id INTEGER,
                    field_name TEXT,
                    old_value TEXT,
                    new_value TEXT,
                    source TEXT,
                    changed_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code),
                    FOREIGN KEY (procedure_id) REFERENCES procedures (id)
                )
            ''')
            
            # Border crossing tables
            conn.execute('''
                CREATE TABLE border_crossing_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_name TEXT NOT NULL,
                    country_iso TEXT NOT NULL,
                    icao_code TEXT,
                    is_airport INTEGER,
                    source TEXT NOT NULL,
                    extraction_method TEXT,
                    metadata_json TEXT,
                    matched_airport_icao TEXT,
                    match_score REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (matched_airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE border_crossing_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_name TEXT NOT NULL,
                    country_iso TEXT NOT NULL,
                    action TEXT NOT NULL,
                    source TEXT NOT NULL,
                    changed_at TEXT
                )
            ''')
            
            # Metadata tables
            conn.execute('''
                CREATE TABLE model_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE sources (
                    name TEXT PRIMARY KEY,
                    last_updated TEXT,
                    record_count INTEGER
                )
            ''')
            
            # Indexes for performance
            conn.execute('CREATE INDEX idx_aip_changes_airport_time ON aip_field_changes (airport_icao, changed_at)')
            conn.execute('CREATE INDEX idx_aip_changes_field_time ON aip_field_changes (field, changed_at)')
            conn.execute('CREATE INDEX idx_airport_changes_airport_time ON airport_field_changes (airport_icao, changed_at)')
            conn.execute('CREATE INDEX idx_runway_changes_airport_time ON runway_changes (airport_icao, changed_at)')
            conn.execute('CREATE INDEX idx_procedure_changes_airport_time ON procedure_changes (airport_icao, changed_at)')
            conn.execute('CREATE INDEX idx_aip_entries_airport_section ON aip_entries (airport_icao, section)')
            conn.execute('CREATE INDEX idx_runways_airport ON runways (airport_icao)')
            conn.execute('CREATE INDEX idx_procedures_airport ON procedures (airport_icao)')
            
            # Border crossing indexes
            conn.execute('CREATE INDEX idx_border_crossing_matched_airport ON border_crossing_entries (matched_airport_icao)')
            conn.execute('CREATE INDEX idx_border_crossing_country ON border_crossing_entries (country_iso)')
            conn.execute('CREATE INDEX idx_border_crossing_source ON border_crossing_entries (source)')
            conn.execute('CREATE INDEX idx_border_crossing_changes_time ON border_crossing_changes (changed_at)')
            
            conn.commit()
            logger.info(f"Created database schema at {self.database_path}")
    
    def _migrate_schema_if_needed(self):
        """Migrate schema if needed using the schema manager."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if we have the basic tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='airports'")
            if not cursor.fetchone():
                logger.warning("Database exists but schema is outdated. Recreating schema.")
                self._recreate_schema()
                return
            
            # Check if we have the model_metadata table (new schema)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='model_metadata'")
            if not cursor.fetchone():
                # Old schema without metadata table - add it
                logger.info("Adding model_metadata table to existing schema")
                cursor.execute('''
                    CREATE TABLE model_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT,
                        updated_at TEXT
                    )
                ''')
                cursor.execute('''
                    INSERT INTO model_metadata (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', ('schema_version', '1', datetime.now().isoformat()))
                conn.commit()
                logger.info("Added model_metadata table to existing schema")
                return
            
            # Get current version
            cursor.execute("SELECT value FROM model_metadata WHERE key = 'schema_version'")
            row = cursor.fetchone()
            current_version = int(row['value']) if row else 1
            
            # Check if border_crossing_entries table exists and needs migration
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='border_crossing_entries'")
            if cursor.fetchone():
                # Check if is_airport column exists
                cursor.execute("PRAGMA table_info(border_crossing_entries)")
                columns = [col[1] for col in cursor.fetchall()]
                
                if 'is_airport' not in columns:
                    logger.info("Adding is_airport column to border_crossing_entries table")
                    cursor.execute('ALTER TABLE border_crossing_entries ADD COLUMN is_airport INTEGER')
                    conn.commit()
                    logger.info("Added is_airport column to border_crossing_entries table")
            
            # Migrate if needed
            new_version = self.schema_manager.migrate_schema(conn, current_version)
            
            if new_version != current_version:
                cursor.execute('''
                    INSERT OR REPLACE INTO model_metadata (key, value, updated_at)
                    VALUES (?, ?, ?)
                ''', ('schema_version', str(new_version), datetime.now().isoformat()))
                conn.commit()
                logger.info(f"Migrated schema from version {current_version} to {new_version}")
    
    def _recreate_schema(self):
        """Drop all tables and recreate the schema."""
        with self._get_connection() as conn:
            # Drop all existing tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
            
            conn.commit()
        
        # Recreate the schema
        self._create_schema()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def save_model(self, model: EuroAipModel) -> None:
        """
        Save the entire EuroAipModel to the database with change tracking.
        
        Args:
            model: The EuroAipModel to save
        """
        logger.info(f"Saving model with {len(model.airports)} airports to database")
        
        with self._get_connection() as conn:
            for airport in model.airports.values():
                self._save_airport(conn, airport)
            
            # Save border crossing data
            border_crossing_entries = model.get_all_border_crossing_entries()
            if border_crossing_entries:
                self.save_border_crossing_data(border_crossing_entries, conn)
            
            # Update metadata
            self._update_metadata(conn, model)
            conn.commit()
        
        logger.info(f"Successfully saved model to database")
    
    def _save_airport(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save a single airport with all its data."""
        # Save airport basic info
        self._save_airport_basic(conn, airport)
        
        # Save runways
        self._save_airport_runways(conn, airport)
        
        # Save procedures
        self._save_airport_procedures(conn, airport)
        
        # Save AIP entries
        self._save_airport_aip_entries(conn, airport)
    
    def _save_airport_basic(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save basic airport information using field definitions."""
        # Check for changes in basic fields
        current_airport = self._get_current_airport(conn, airport.ident)
        changes = []
        
        if current_airport is None:
            # New airport
            changes = self._detect_airport_changes(None, airport)
        else:
            # Existing airport - check for changes
            changes = self._detect_airport_changes(current_airport, airport)
        
        # Save changes to history
        for change in changes:
            conn.execute('''
                INSERT INTO airport_field_changes 
                (airport_icao, field_name, old_value, new_value, field_type, source, changed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                airport.ident, change['field_name'], change['old_value'], 
                change['new_value'], change['field_type'], change['source'], change['changed_at']
            ))
        
        # Build dynamic INSERT/REPLACE statement using field definitions
        fields = AirportFields.get_all_fields()
        field_names = [field.name for field in fields]
        placeholders = ','.join(['?' for _ in fields])
        
        # Prepare values using field definitions for proper formatting
        values = []
        for field in fields:
            if field.name == 'icao_code':
                values.append(airport.ident)
            elif field.name == 'sources':
                values.append(','.join(airport.sources))
            elif field.name == 'created_at':
                values.append(airport.created_at.isoformat())
            elif field.name == 'updated_at':
                values.append(airport.updated_at.isoformat())
            else:
                # Get value from airport object and format it
                value = getattr(airport, field.name, None)
                formatted_value = field.format_for_storage(value)
                values.append(formatted_value)
        
        # Execute INSERT OR REPLACE
        sql = f'''
            INSERT OR REPLACE INTO airports 
            ({','.join(field_names)})
            VALUES ({placeholders})
        '''
        conn.execute(sql, values)
    
    def _save_airport_runways(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save airport runways with change tracking using field definitions."""
        current_runways = self._get_current_runways(conn, airport.ident)
        
        for runway in airport.runways:
            # Find matching current runway
            current_runway = None
            for curr in current_runways:
                if (curr['le_ident'] == runway.le_ident and 
                    curr['he_ident'] == runway.he_ident):
                    current_runway = curr
                    break
            
            # Detect changes using field definitions
            changes = self._detect_runway_changes(current_runway, runway)
            
            # Save changes to history
            for change in changes:
                conn.execute('''
                    INSERT INTO runway_changes 
                    (airport_icao, runway_id, field_name, old_value, new_value, field_type, source, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, change.get('runway_id'), change['field_name'],
                    change['old_value'], change['new_value'], change['field_type'], 
                    change['source'], change['changed_at']
                ))
            
            # Insert or update runway using field definitions
            if current_runway:
                # Update existing runway
                self._update_runway(conn, current_runway['id'], runway)
            else:
                # Insert new runway
                self._insert_runway(conn, airport.ident, runway)
    
    def _insert_runway(self, conn: sqlite3.Connection, airport_icao: str, runway: Runway) -> None:
        """Insert a new runway using field definitions."""
        fields = RunwayFields.get_all_fields()
        field_names = [field.name for field in fields]
        placeholders = ','.join(['?' for _ in fields])
        
        # Prepare values using field definitions
        values = []
        for field in fields:
            if field.name == 'airport_icao':
                values.append(airport_icao)
            elif field.name == 'created_at':
                values.append(getattr(runway, 'created_at', datetime.now()).isoformat() if hasattr(runway, 'created_at') else datetime.now().isoformat())
            elif field.name == 'updated_at':
                values.append(datetime.now().isoformat())
            else:
                value = getattr(runway, field.name, None)
                values.append(field.format_for_storage(value))
        
        sql = f'''
            INSERT INTO runways 
            ({','.join(field_names)})
            VALUES ({placeholders})
        '''
        conn.execute(sql, values)
    
    def _update_runway(self, conn: sqlite3.Connection, runway_id: int, runway: Runway) -> None:
        """Update an existing runway using field definitions."""
        # Get change-tracked fields (exclude metadata and identifiers)
        fields = [f for f in RunwayFields.get_change_tracked_fields() if f.name not in ['airport_icao', 'le_ident', 'he_ident']]
        
        set_clauses = []
        values = []
        
        for field in fields:
            set_clauses.append(f"{field.name} = ?")
            value = getattr(runway, field.name, None)
            values.append(field.format_for_storage(value))
        
        # Add updated_at
        set_clauses.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        
        # Add runway_id for WHERE clause
        values.append(runway_id)
        
        sql = f'''
            UPDATE runways SET
            {', '.join(set_clauses)}
            WHERE id = ?
        '''
        conn.execute(sql, values)
    
    def _save_airport_procedures(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save airport procedures with change tracking."""
        current_procedures = self._get_current_procedures(conn, airport.ident)
        
        for procedure in airport.procedures:
            # Find matching current procedure
            current_procedure = None
            for curr in current_procedures:
                if (curr['name'] == procedure.name and 
                    curr['procedure_type'] == procedure.procedure_type):
                    current_procedure = curr
                    break
            
            # Detect changes
            changes = self._detect_procedure_changes(current_procedure, procedure)
            
            # Save changes to history
            for change in changes:
                conn.execute('''
                    INSERT INTO procedure_changes 
                    (airport_icao, procedure_id, field_name, old_value, new_value, source, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, change.get('procedure_id'), change['field_name'],
                    change['old_value'], change['new_value'], change['source'], change['changed_at']
                ))
            
            # Insert or update procedure
            if current_procedure:
                # Update existing procedure
                conn.execute('''
                    UPDATE procedures SET
                    approach_type = ?, runway_ident = ?, runway_letter = ?, runway = ?,
                    category = ?, minima = ?, notes = ?, source = ?, authority = ?,
                    raw_name = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    procedure.approach_type, procedure.runway_ident, procedure.runway_letter,
                    procedure.runway, procedure.category, procedure.minima, procedure.notes,
                    procedure.source, procedure.authority, procedure.raw_name,
                    datetime.now().isoformat(), current_procedure['id']
                ))
            else:
                # Insert new procedure
                conn.execute('''
                    INSERT INTO procedures 
                    (airport_icao, name, procedure_type, approach_type, runway_ident,
                     runway_letter, runway, category, minima, notes, source, authority,
                     raw_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, procedure.name, procedure.procedure_type,
                    procedure.approach_type, procedure.runway_ident, procedure.runway_letter,
                    procedure.runway, procedure.category, procedure.minima, procedure.notes,
                    procedure.source, procedure.authority, procedure.raw_name,
                    procedure.created_at.isoformat(), datetime.now().isoformat()
                ))
    
    def _save_airport_aip_entries(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save AIP entries with change tracking and conflict resolution."""
        current_entries = self._get_current_aip_entries(conn, airport.ident)
        
        for entry in airport.aip_entries:
            # Skip entries without std_field_id if save_only_std_fields is True
            if self.save_only_std_fields and entry.std_field_id is None:
                logger.debug(f"Skipping non-standardized AIP entry: {entry.section}.{entry.field} for {airport.ident}")
                continue
            
            # Check for existing entry
            key = (entry.section, entry.field, entry.source)
            current_entry = current_entries.get(key)
            
            if current_entry is None:
                # New entry
                self._save_new_aip_entry(conn, airport.ident, entry)
            elif current_entry['value'] != entry.value:
                # Value changed - save to history and update
                self._save_aip_change(conn, airport.ident, current_entry, entry)
                self._update_aip_entry(conn, current_entry['id'], entry)
    
    def _save_new_aip_entry(self, conn: sqlite3.Connection, airport_icao: str, entry: AIPEntry) -> None:
        """Save a new AIP entry."""
        cursor = conn.execute('''
            INSERT INTO aip_entries 
            (airport_icao, section, field, value, std_field, std_field_id,
             mapping_score, alt_field, alt_value, source, source_priority,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            airport_icao, entry.section, entry.field, entry.value,
            entry.std_field, entry.std_field_id, entry.mapping_score,
            entry.alt_field, entry.alt_value, entry.source, 0,  # Default priority
            entry.created_at.isoformat(), datetime.now().isoformat()
        ))
        
        # Save to change history as creation
        conn.execute('''
            INSERT INTO aip_field_changes 
            (airport_icao, section, field, old_value, new_value, std_field,
             std_field_id, mapping_score, source, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            airport_icao, entry.section, entry.field, None, entry.value,
            entry.std_field, entry.std_field_id, entry.mapping_score,
            entry.source, datetime.now().isoformat()
        ))
    
    def _save_aip_change(self, conn: sqlite3.Connection, airport_icao: str, 
                        old_entry: Dict, new_entry: AIPEntry) -> None:
        """Save an AIP field change to history."""
        conn.execute('''
            INSERT INTO aip_field_changes 
            (airport_icao, section, field, old_value, new_value, std_field,
             std_field_id, mapping_score, source, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            airport_icao, new_entry.section, new_entry.field,
            old_entry['value'], new_entry.value, new_entry.std_field,
            new_entry.std_field_id, new_entry.mapping_score,
            new_entry.source, datetime.now().isoformat()
        ))
    
    def _update_aip_entry(self, conn: sqlite3.Connection, entry_id: int, entry: AIPEntry) -> None:
        """Update an existing AIP entry."""
        conn.execute('''
            UPDATE aip_entries SET
            value = ?, std_field = ?, std_field_id = ?, mapping_score = ?,
            alt_field = ?, alt_value = ?, updated_at = ?
            WHERE id = ?
        ''', (
            entry.value, entry.std_field, entry.std_field_id, entry.mapping_score,
            entry.alt_field, entry.alt_value, datetime.now().isoformat(), entry_id
        ))
    
    def _detect_airport_changes(self, current: Optional[Dict], new: Airport) -> List[Dict]:
        """Detect changes in airport basic fields using field definitions."""
        changes = []
        now = datetime.now().isoformat()
        
        # Use field definitions for change tracking
        tracked_fields = AirportFields.get_change_tracked_fields()
        
        if current is None:
            # New airport - all fields are changes
            for field in tracked_fields:
                value = getattr(new, field.name, None)
                if value is not None:
                    changes.append({
                        'field_name': field.name,
                        'old_value': None,
                        'new_value': field.format_for_comparison(value),
                        'field_type': field.field_type.value,
                        'source': list(new.sources)[0] if new.sources else 'unknown',
                        'changed_at': now
                    })
        else:
            # Check for changes in existing airport
            for field in tracked_fields:
                old_value = current.get(field.name)
                new_value = getattr(new, field.name, None)
                
                # Format both values for comparison
                old_formatted = field.format_for_comparison(old_value)
                new_formatted = field.format_for_comparison(new_value)
                
                if old_formatted != new_formatted:
                    changes.append({
                        'field_name': field.name,
                        'old_value': str(old_formatted) if old_formatted is not None else None,
                        'new_value': str(new_formatted) if new_formatted is not None else None,
                        'field_type': field.field_type.value,
                        'source': list(new.sources)[0] if new.sources else 'unknown',
                        'changed_at': now
                    })
        
        return changes
    
    def _detect_runway_changes(self, current: Optional[Dict], new: Runway) -> List[Dict]:
        """Detect changes in runway fields using field definitions."""
        changes = []
        now = datetime.now().isoformat()
        
        # Use field definitions for change tracking
        tracked_fields = RunwayFields.get_change_tracked_fields()
        
        if current is None:
            # New runway - all fields are changes
            for field in tracked_fields:
                value = getattr(new, field.name, None)
                if value is not None:
                    changes.append({
                        'field_name': field.name,
                        'old_value': None,
                        'new_value': field.format_for_comparison(value),
                        'field_type': field.field_type.value,
                        'source': 'unknown',  # Runway doesn't have source tracking
                        'changed_at': now
                    })
        else:
            # Check for changes in existing runway
            for field in tracked_fields:
                old_value = current.get(field.name)
                new_value = getattr(new, field.name, None)
                
                # Format both values for comparison
                old_formatted = field.format_for_comparison(old_value)
                new_formatted = field.format_for_comparison(new_value)
                
                if old_formatted != new_formatted:
                    changes.append({
                        'field_name': field.name,
                        'old_value': str(old_formatted) if old_formatted is not None else None,
                        'new_value': str(new_formatted) if new_formatted is not None else None,
                        'field_type': field.field_type.value,
                        'source': 'unknown',
                        'changed_at': now
                    })
        
        return changes
    
    def _detect_procedure_changes(self, current: Optional[Dict], new: Procedure) -> List[Dict]:
        """Detect changes in procedure fields."""
        changes = []
        now = datetime.now().isoformat()
        
        if current is None:
            # New procedure - all fields are changes
            for field_name in ['approach_type', 'runway_ident', 'runway_letter', 'runway',
                              'category', 'minima', 'notes', 'source', 'authority', 'raw_name']:
                value = getattr(new, field_name)
                if value is not None:
                    changes.append({
                        'field_name': field_name,
                        'old_value': None,
                        'new_value': str(value),
                        'source': new.source or 'unknown',
                        'changed_at': now
                    })
        else:
            # Check for changes in existing procedure
            for field_name in ['approach_type', 'runway_ident', 'runway_letter', 'runway',
                              'category', 'minima', 'notes', 'source', 'authority', 'raw_name']:
                old_value = current.get(field_name)
                new_value = getattr(new, field_name)
                
                if old_value != new_value:
                    changes.append({
                        'field_name': field_name,
                        'old_value': str(old_value) if old_value is not None else None,
                        'new_value': str(new_value) if new_value is not None else None,
                        'source': new.source or 'unknown',
                        'changed_at': now
                    })
        
        return changes
    
    def _get_current_airport(self, conn: sqlite3.Connection, icao: str) -> Optional[Dict]:
        """Get current airport data."""
        cursor = conn.execute('SELECT * FROM airports WHERE icao_code = ?', (icao,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def _get_current_runways(self, conn: sqlite3.Connection, icao: str) -> List[Dict]:
        """Get current runways for an airport."""
        cursor = conn.execute('SELECT * FROM runways WHERE airport_icao = ?', (icao,))
        return [dict(row) for row in cursor.fetchall()]
    
    def _get_current_procedures(self, conn: sqlite3.Connection, icao: str) -> List[Dict]:
        """Get current procedures for an airport."""
        cursor = conn.execute('SELECT * FROM procedures WHERE airport_icao = ?', (icao,))
        return [dict(row) for row in cursor.fetchall()]
    
    def _get_current_aip_entries(self, conn: sqlite3.Connection, icao: str) -> Dict[Tuple, Dict]:
        """Get current AIP entries for an airport, indexed by (section, field, source)."""
        cursor = conn.execute('SELECT * FROM aip_entries WHERE airport_icao = ?', (icao,))
        entries = {}
        for row in cursor.fetchall():
            key = (row['section'], row['field'], row['source'])
            entries[key] = dict(row)
        return entries
    
    def _update_metadata(self, conn: sqlite3.Connection, model: EuroAipModel) -> None:
        """Update model metadata."""
        stats = model.get_statistics()
        
        conn.execute('''
            INSERT OR REPLACE INTO model_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', ('statistics', json.dumps(stats), datetime.now().isoformat()))
        
        # Update schema version
        conn.execute('''
            INSERT OR REPLACE INTO model_metadata (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', ('schema_version', str(self.schema_manager.version), datetime.now().isoformat()))
        
        # Update source information
        for source in model.sources_used:
            airports_from_source = len(model.get_airports_by_source(source))
            conn.execute('''
                INSERT OR REPLACE INTO sources (name, last_updated, record_count)
                VALUES (?, ?, ?)
            ''', (source, datetime.now().isoformat(), airports_from_source))
    
    def load_model(self) -> EuroAipModel:
        """
        Load the entire EuroAipModel from the database.
        
        Returns:
            EuroAipModel instance
        """
        logger.info("Loading model from database")
        
        model = EuroAipModel()
        
        with self._get_connection() as conn:
            # Load all airports
            cursor = conn.execute('SELECT icao_code FROM airports')
            airport_codes = [row['icao_code'] for row in cursor.fetchall()]
            
            for icao in airport_codes:
                airport = self._load_airport(conn, icao)
                if airport:
                    model.airports[icao] = airport
                    for source in airport.sources:
                        model.sources_used.add(source)
            
            # Load border crossing data
            border_crossing_entries = self.load_border_crossing_data()
            if border_crossing_entries:
                model.add_border_crossing_entries(border_crossing_entries)
        
        logger.info(f"Loaded model with {len(model.airports)} airports and {len(model.get_all_border_crossing_entries())} border crossing entries")
        return model
    
    def _load_airport(self, conn: sqlite3.Connection, icao: str) -> Optional[Airport]:
        """Load a single airport with all its data using field definitions."""
        # Load basic airport info
        cursor = conn.execute('SELECT * FROM airports WHERE icao_code = ?', (icao,))
        row = cursor.fetchone()
        if not row:
            return None
        
        # Create airport object using field definitions for proper type conversion
        airport_data = {}
        for field in AirportFields.get_all_fields():
            value = row[field.name]
            
            # Convert value based on field type
            if field.field_type.value == "INTEGER" and value is not None:
                if field.name in ['lighted', 'closed']:  # Boolean fields
                    airport_data[field.name] = bool(value)
                else:
                    airport_data[field.name] = int(value)
                    if field.name == 'elevation_ft':
                        logger.debug(f"Loading elevation_ft: {value} -> {airport_data[field.name]}")
            elif field.field_type.value == "REAL" and value is not None:
                airport_data[field.name] = float(value)
            elif field.field_type.value == "TEXT" and field.name in ['created_at', 'updated_at'] and value:
                # Parse datetime strings
                try:
                    airport_data[field.name] = datetime.fromisoformat(value)
                except ValueError:
                    airport_data[field.name] = value
            else:
                airport_data[field.name] = value
        
        # Create airport object
        airport = Airport(
            ident=airport_data['icao_code'],
            name=airport_data['name'],
            type=airport_data['type'],
            latitude_deg=airport_data['latitude_deg'],
            longitude_deg=airport_data['longitude_deg'],
            elevation_ft=airport_data['elevation_ft'],
            continent=airport_data['continent'],
            iso_country=airport_data['iso_country'],
            iso_region=airport_data['iso_region'],
            municipality=airport_data['municipality'],
            scheduled_service=airport_data['scheduled_service'],
            gps_code=airport_data['gps_code'],
            iata_code=airport_data['iata_code'],
            local_code=airport_data['local_code'],
            home_link=airport_data['home_link'],
            wikipedia_link=airport_data['wikipedia_link'],
            keywords=airport_data['keywords']
        )
        
        # Load sources
        if airport_data['sources']:
            for source in airport_data['sources'].split(','):
                airport.add_source(source)
        
        # Load runways using field definitions
        cursor = conn.execute('SELECT * FROM runways WHERE airport_icao = ?', (icao,))
        for row in cursor.fetchall():
            runway_data = {}
            for field in RunwayFields.get_all_fields():
                value = row[field.name]
                
                # Convert value based on field type
                if field.field_type.value == "INTEGER" and value is not None:
                    if field.name in ['lighted', 'closed']:  # Boolean fields
                        runway_data[field.name] = bool(value)
                    else:
                        runway_data[field.name] = int(value)
                elif field.field_type.value == "REAL" and value is not None:
                    runway_data[field.name] = float(value)
                else:
                    runway_data[field.name] = value
            
            runway = Runway(
                airport_ident=icao,
                le_ident=runway_data['le_ident'],
                he_ident=runway_data['he_ident'],
                length_ft=runway_data['length_ft'],
                width_ft=runway_data['width_ft'],
                surface=runway_data['surface'],
                lighted=runway_data['lighted'],
                closed=runway_data['closed'],
                le_latitude_deg=runway_data['le_latitude_deg'],
                le_longitude_deg=runway_data['le_longitude_deg'],
                le_elevation_ft=runway_data['le_elevation_ft'],
                le_heading_degT=runway_data['le_heading_degT'],
                le_displaced_threshold_ft=runway_data['le_displaced_threshold_ft'],
                he_latitude_deg=runway_data['he_latitude_deg'],
                he_longitude_deg=runway_data['he_longitude_deg'],
                he_elevation_ft=runway_data['he_elevation_ft'],
                he_heading_degT=runway_data['he_heading_degT'],
                he_displaced_threshold_ft=runway_data['he_displaced_threshold_ft']
            )
            airport.add_runway(runway)
        
        # Load procedures
        cursor = conn.execute('SELECT * FROM procedures WHERE airport_icao = ?', (icao,))
        for row in cursor.fetchall():
            procedure = Procedure(
                name=row['name'],
                procedure_type=row['procedure_type'],
                approach_type=row['approach_type'],
                runway_ident=row['runway_ident'],
                runway_letter=row['runway_letter'],
                runway=row['runway'],
                category=row['category'],
                minima=row['minima'],
                notes=row['notes'],
                source=row['source'],
                authority=row['authority'],
                raw_name=row['raw_name']
            )
            airport.add_procedure(procedure)
        
        # Load AIP entries
        cursor = conn.execute('SELECT * FROM aip_entries WHERE airport_icao = ?', (icao,))
        for row in cursor.fetchall():
            entry = AIPEntry(
                ident=icao,
                section=row['section'],
                field=row['field'],
                value=row['value'],
                std_field=row['std_field'],
                std_field_id=row['std_field_id'],
                mapping_score=row['mapping_score'],
                alt_field=row['alt_field'],
                alt_value=row['alt_value'],
                source=row['source']
            )
            airport.add_aip_entry(entry)
        
        return airport
    
    def get_changes_for_airport(self, icao: str, days: int = 30) -> Dict[str, List[Dict]]:
        """
        Get all changes for a specific airport within the last N days.
        
        Args:
            icao: Airport ICAO code
            days: Number of days to look back
            
        Returns:
            Dictionary with changes by type
        """
        changes = {
            'airport': [],
            'runways': [],
            'procedures': [],
            'aip_entries': []
        }
        
        with self._get_connection() as conn:
            # Get airport field changes
            cursor = conn.execute('''
                SELECT * FROM airport_field_changes 
                WHERE airport_icao = ? AND changed_at >= date('now', '-{} days')
                ORDER BY changed_at DESC
            '''.format(days), (icao,))
            changes['airport'] = [dict(row) for row in cursor.fetchall()]
            
            # Get AIP field changes
            cursor = conn.execute('''
                SELECT * FROM aip_field_changes 
                WHERE airport_icao = ? AND changed_at >= date('now', '-{} days')
                ORDER BY changed_at DESC
            '''.format(days), (icao,))
            changes['aip_entries'] = [dict(row) for row in cursor.fetchall()]
            
            # Get runway changes
            cursor = conn.execute('''
                SELECT rc.*, r.le_ident, r.he_ident 
                FROM runway_changes rc
                LEFT JOIN runways r ON rc.runway_id = r.id
                WHERE rc.airport_icao = ? AND rc.changed_at >= date('now', '-{} days')
                ORDER BY rc.changed_at DESC
            '''.format(days), (icao,))
            changes['runways'] = [dict(row) for row in cursor.fetchall()]
            
            # Get procedure changes
            cursor = conn.execute('''
                SELECT pc.*, p.name, p.procedure_type
                FROM procedure_changes pc
                JOIN procedures p ON pc.procedure_id = p.id
                WHERE pc.airport_icao = ? AND pc.changed_at >= date('now', '-{} days')
                ORDER BY pc.changed_at DESC
            '''.format(days), (icao,))
            changes['procedures'] = [dict(row) for row in cursor.fetchall()]
        
        return changes
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get table information
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in cursor.fetchall()]
            
            info = {
                'database_path': str(self.database_path),
                'tables': {},
                'statistics': {}
            }
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()['count']
                info['tables'][table] = count
            
            # Get metadata
            cursor.execute("SELECT * FROM model_metadata WHERE key = 'statistics'")
            row = cursor.fetchone()
            if row:
                info['statistics'] = json.loads(row['value'])
            
            return info
    
    def set_save_only_std_fields(self, save_only_std_fields: bool) -> None:
        """
        Change the setting for saving only standardized fields.
        
        Args:
            save_only_std_fields: If True, only save AIP entries with std_field_id. 
                                 If False, save all AIP entries.
        """
        self.save_only_std_fields = save_only_std_fields
        logger.info(f"Set save_only_std_fields to {save_only_std_fields}")
    
    def get_save_only_std_fields(self) -> bool:
        """
        Get the current setting for saving only standardized fields.
        
        Returns:
            Current setting for save_only_std_fields
        """
        return self.save_only_std_fields
    
    # Border crossing methods
    
    def save_border_crossing_data(self, entries: List[BorderCrossingEntry], conn: Optional[sqlite3.Connection] = None) -> None:
        """
        Save border crossing entries to the database with change tracking.
        
        Args:
            entries: List of border crossing entries to save
            conn: Optional existing database connection. If None, creates a new connection.
        """
        logger.info(f"Saving {len(entries)} border crossing entries to database")
        
        if conn is None:
            # Create our own connection
            with self._get_connection() as conn:
                self._save_border_crossing_data_internal(conn, entries)
                conn.commit()
        else:
            # Use provided connection (no commit, caller handles it)
            self._save_border_crossing_data_internal(conn, entries)
        
        logger.info(f"Successfully saved {len(entries)} border crossing entries")
    
    def _save_border_crossing_data_internal(self, conn: sqlite3.Connection, entries: List[BorderCrossingEntry]) -> None:
        """Internal method to save border crossing data using provided connection."""
        # Get current entries for change detection
        current_entries = self._get_current_border_crossing_entries(conn)
        
        # Detect changes
        changes = self._detect_border_crossing_changes(current_entries, entries)
        
        # Save changes to history
        for change in changes:
            conn.execute('''
                INSERT INTO border_crossing_changes 
                (airport_name, country_iso, action, source, changed_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                change.airport_name, change.country_iso, change.action,
                change.source, change.changed_at.isoformat()
            ))
        
        # Clear current entries and insert new ones
        conn.execute('DELETE FROM border_crossing_entries')
        
        # Insert new entries
        for entry in entries:
            data = entry.to_dict()
            conn.execute('''
                INSERT INTO border_crossing_entries 
                (airport_name, country_iso, icao_code, is_airport, source, extraction_method,
                 metadata_json, matched_airport_icao, match_score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['airport_name'], data['country_iso'], data['icao_code'],
                data.get('is_airport'), data['source'], data['extraction_method'], 
                data['metadata_json'], data['matched_airport_icao'], data['match_score'],
                data['created_at'], data['updated_at']
            ))
    
    def load_border_crossing_data(self) -> List[BorderCrossingEntry]:
        """
        Load border crossing entries from the database.
        
        Returns:
            List of border crossing entries
        """
        logger.info("Loading border crossing entries from database")
        
        entries = []
        with self._get_connection() as conn:
            cursor = conn.execute('SELECT * FROM border_crossing_entries')
            for row in cursor.fetchall():
                entry = BorderCrossingEntry.from_dict(dict(row))
                entries.append(entry)
        
        logger.info(f"Loaded {len(entries)} border crossing entries")
        return entries
    
    def get_border_crossing_changes(self, days: int = 30) -> List[BorderCrossingChange]:
        """
        Get border crossing changes within the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of border crossing changes
        """
        changes = []
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM border_crossing_changes 
                WHERE changed_at >= date('now', '-{} days')
                ORDER BY changed_at DESC
            '''.format(days))
            
            for row in cursor.fetchall():
                change = BorderCrossingChange.from_dict(dict(row))
                changes.append(change)
        
        return changes
    
    def get_border_crossing_airports(self) -> List[Dict[str, Any]]:
        """
        Get all airports that are border crossing points.
        
        Returns:
            List of dictionaries with airport and border crossing info
        """
        airports = []
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT a.*, b.airport_name as border_crossing_name, b.source, b.match_score
                FROM airports a
                JOIN border_crossing_entries b ON a.icao_code = b.matched_airport_icao
                WHERE b.matched_airport_icao IS NOT NULL
            ''')
            
            for row in cursor.fetchall():
                airports.append(dict(row))
        
        return airports
    
    def get_border_crossing_by_country(self, country_iso: str) -> List[Dict[str, Any]]:
        """
        Get border crossing entries for a specific country.
        
        Args:
            country_iso: ISO country code
            
        Returns:
            List of border crossing entries for the country
        """
        entries = []
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM border_crossing_entries 
                WHERE country_iso = ?
                ORDER BY airport_name
            ''', (country_iso,))
            
            for row in cursor.fetchall():
                entries.append(dict(row))
        
        return entries
    
    def get_border_crossing_statistics(self) -> Dict[str, Any]:
        """
        Get border crossing statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = {}
        with self._get_connection() as conn:
            # Total entries
            cursor = conn.execute('SELECT COUNT(*) as count FROM border_crossing_entries')
            stats['total_entries'] = cursor.fetchone()['count']
            
            # Matched vs unmatched
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(matched_airport_icao) as matched,
                    COUNT(*) - COUNT(matched_airport_icao) as unmatched
                FROM border_crossing_entries
            ''')
            row = cursor.fetchone()
            stats['matched_count'] = row['matched']
            stats['unmatched_count'] = row['unmatched']
            stats['match_rate'] = row['matched'] / row['total'] if row['total'] > 0 else 0
            
            # Airport vs non-airport entries
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN is_airport = 1 THEN 1 END) as airports,
                    COUNT(CASE WHEN is_airport = 0 THEN 1 END) as non_airports,
                    COUNT(CASE WHEN is_airport IS NULL THEN 1 END) as unknown
                FROM border_crossing_entries
            ''')
            row = cursor.fetchone()
            stats['airport_entries'] = row['airports']
            stats['non_airport_entries'] = row['non_airports']
            stats['unknown_type_entries'] = row['unknown']
            stats['airport_rate'] = row['airports'] / row['total'] if row['total'] > 0 else 0
            
            # By country
            cursor = conn.execute('''
                SELECT country_iso, COUNT(*) as count
                FROM border_crossing_entries
                GROUP BY country_iso
                ORDER BY count DESC
            ''')
            stats['by_country'] = {row['country_iso']: row['count'] for row in cursor.fetchall()}
            
            # By source
            cursor = conn.execute('''
                SELECT source, COUNT(*) as count
                FROM border_crossing_entries
                GROUP BY source
                ORDER BY count DESC
            ''')
            stats['by_source'] = {row['source']: row['count'] for row in cursor.fetchall()}
            
            # By extraction method
            cursor = conn.execute('''
                SELECT extraction_method, COUNT(*) as count
                FROM border_crossing_entries
                GROUP BY extraction_method
                ORDER BY count DESC
            ''')
            stats['by_extraction_method'] = {row['extraction_method']: row['count'] for row in cursor.fetchall()}
        
        return stats
    
    def get_border_crossing_airports_only(self) -> List[Dict[str, Any]]:
        """
        Get only border crossing entries that are confirmed airports.
        
        Returns:
            List of dictionaries with airport border crossing info
        """
        airports = []
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM border_crossing_entries 
                WHERE is_airport = 1
                ORDER BY airport_name
            ''')
            
            for row in cursor.fetchall():
                airports.append(dict(row))
        
        return airports
    
    def get_border_crossing_non_airports(self) -> List[Dict[str, Any]]:
        """
        Get border crossing entries that are not airports.
        
        Returns:
            List of dictionaries with non-airport border crossing info
        """
        non_airports = []
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM border_crossing_entries 
                WHERE is_airport = 0
                ORDER BY airport_name
            ''')
            
            for row in cursor.fetchall():
                non_airports.append(dict(row))
        
        return non_airports
    
    def _get_current_border_crossing_entries(self, conn: sqlite3.Connection) -> List[BorderCrossingEntry]:
        """Get current border crossing entries from database."""
        entries = []
        cursor = conn.execute('SELECT * FROM border_crossing_entries')
        for row in cursor.fetchall():
            entry = BorderCrossingEntry.from_dict(dict(row))
            entries.append(entry)
        return entries
    
    def _detect_border_crossing_changes(self, current_entries: List[BorderCrossingEntry], 
                                      new_entries: List[BorderCrossingEntry]) -> List[BorderCrossingChange]:
        """Detect changes in border crossing entries."""
        changes = []
        now = datetime.now()
        
        # Create sets for efficient comparison
        current_set = {(e.airport_name, e.country_iso, e.source) for e in current_entries}
        new_set = {(e.airport_name, e.country_iso, e.source) for e in new_entries}
        
        # Find added entries
        added = new_set - current_set
        for airport_name, country_iso, source in added:
            changes.append(BorderCrossingChange(
                airport_name=airport_name,
                country_iso=country_iso,
                action='ADDED',
                source=source,
                changed_at=now
            ))
        
        # Find removed entries
        removed = current_set - new_set
        for airport_name, country_iso, source in removed:
            changes.append(BorderCrossingChange(
                airport_name=airport_name,
                country_iso=country_iso,
                action='REMOVED',
                source=source,
                changed_at=now
            ))
        
        return changes 