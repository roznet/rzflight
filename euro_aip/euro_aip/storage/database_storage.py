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

logger = logging.getLogger(__name__)

class DatabaseStorage:
    """
    Unified database storage for EuroAipModel with change tracking.
    
    This class provides efficient storage and retrieval of airport data with
    automatic change detection and history tracking.
    """
    
    def __init__(self, database_path: str):
        """
        Initialize the database storage.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = Path(database_path)
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure the database file exists and has the correct schema."""
        if not self.database_path.exists():
            self._create_schema()
        else:
            # Check if schema needs to be updated
            self._migrate_schema_if_needed()
    
    def _create_schema(self):
        """Create the database schema."""
        with self._get_connection() as conn:
            # Core tables (current state)
            conn.execute('''
                CREATE TABLE airports (
                    icao_code TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    latitude_deg REAL,
                    longitude_deg REAL,
                    elevation_ft REAL,
                    continent TEXT,
                    iso_country TEXT,
                    iso_region TEXT,
                    municipality TEXT,
                    scheduled_service TEXT,
                    gps_code TEXT,
                    iata_code TEXT,
                    local_code TEXT,
                    home_link TEXT,
                    wikipedia_link TEXT,
                    keywords TEXT,
                    sources TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE runways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    le_ident TEXT,
                    he_ident TEXT,
                    length_ft REAL,
                    width_ft REAL,
                    surface TEXT,
                    lighted INTEGER,
                    closed INTEGER,
                    le_latitude_deg REAL,
                    le_longitude_deg REAL,
                    le_elevation_ft REAL,
                    le_heading_degT REAL,
                    le_displaced_threshold_ft REAL,
                    he_latitude_deg REAL,
                    he_longitude_deg REAL,
                    he_elevation_ft REAL,
                    he_heading_degT REAL,
                    he_displaced_threshold_ft REAL,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
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
            
            conn.commit()
            logger.info(f"Created database schema at {self.database_path}")
    
    def _migrate_schema_if_needed(self):
        """Migrate schema if needed (placeholder for future migrations)."""
        # For now, just check if we have the basic tables
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='airports'")
            if not cursor.fetchone():
                logger.warning("Database exists but schema is outdated. Recreating schema.")
                # Drop all existing tables and recreate
                self._recreate_schema()
    
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
        """Save basic airport information."""
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
                (airport_icao, field_name, old_value, new_value, source, changed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                airport.ident, change['field_name'], change['old_value'], 
                change['new_value'], change['source'], change['changed_at']
            ))
        
        # Update or insert airport record
        conn.execute('''
            INSERT OR REPLACE INTO airports 
            (icao_code, name, type, latitude_deg, longitude_deg, elevation_ft,
             continent, iso_country, iso_region, municipality, scheduled_service,
             gps_code, iata_code, local_code, home_link, wikipedia_link, keywords,
             sources, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            airport.ident, airport.name, airport.type,
            airport.latitude_deg, airport.longitude_deg, airport.elevation_ft,
            airport.continent, airport.iso_country, airport.iso_region,
            airport.municipality, airport.scheduled_service, airport.gps_code,
            airport.iata_code, airport.local_code, airport.home_link,
            airport.wikipedia_link, airport.keywords, ','.join(airport.sources),
            airport.created_at.isoformat(), airport.updated_at.isoformat()
        ))
    
    def _save_airport_runways(self, conn: sqlite3.Connection, airport: Airport) -> None:
        """Save airport runways with change tracking."""
        current_runways = self._get_current_runways(conn, airport.ident)
        
        for runway in airport.runways:
            # Find matching current runway
            current_runway = None
            for curr in current_runways:
                if (curr['le_ident'] == runway.le_ident and 
                    curr['he_ident'] == runway.he_ident):
                    current_runway = curr
                    break
            
            # Detect changes
            changes = self._detect_runway_changes(current_runway, runway)
            
            # Save changes to history
            for change in changes:
                conn.execute('''
                    INSERT INTO runway_changes 
                    (airport_icao, runway_id, field_name, old_value, new_value, source, changed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, change.get('runway_id'), change['field_name'],
                    change['old_value'], change['new_value'], change['source'], change['changed_at']
                ))
            
            # Insert or update runway
            if current_runway:
                # Update existing runway
                conn.execute('''
                    UPDATE runways SET
                    length_ft = ?, width_ft = ?, surface = ?, lighted = ?, closed = ?,
                    le_latitude_deg = ?, le_longitude_deg = ?, le_elevation_ft = ?,
                    le_heading_degT = ?, le_displaced_threshold_ft = ?,
                    he_latitude_deg = ?, he_longitude_deg = ?, he_elevation_ft = ?,
                    he_heading_degT = ?, he_displaced_threshold_ft = ?, updated_at = ?
                    WHERE id = ?
                ''', (
                    runway.length_ft, runway.width_ft, runway.surface, runway.lighted, runway.closed,
                    runway.le_latitude_deg, runway.le_longitude_deg, runway.le_elevation_ft,
                    runway.le_heading_degT, runway.le_displaced_threshold_ft,
                    runway.he_latitude_deg, runway.he_longitude_deg, runway.he_elevation_ft,
                    runway.he_heading_degT, runway.he_displaced_threshold_ft,
                    datetime.now().isoformat(), current_runway['id']
                ))
            else:
                # Insert new runway
                cursor = conn.execute('''
                    INSERT INTO runways 
                    (airport_icao, le_ident, he_ident, length_ft, width_ft, surface,
                     lighted, closed, le_latitude_deg, le_longitude_deg, le_elevation_ft,
                     le_heading_degT, le_displaced_threshold_ft, he_latitude_deg,
                     he_longitude_deg, he_elevation_ft, he_heading_degT,
                     he_displaced_threshold_ft, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, runway.le_ident, runway.he_ident,
                    runway.length_ft, runway.width_ft, runway.surface,
                    runway.lighted, runway.closed, runway.le_latitude_deg,
                    runway.le_longitude_deg, runway.le_elevation_ft,
                    runway.le_heading_degT, runway.le_displaced_threshold_ft,
                    runway.he_latitude_deg, runway.he_longitude_deg,
                    runway.he_elevation_ft, runway.he_heading_degT,
                    runway.he_displaced_threshold_ft,
                    getattr(runway, 'created_at', datetime.now()).isoformat() if hasattr(runway, 'created_at') else datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
    
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
        """Detect changes in airport basic fields."""
        changes = []
        now = datetime.now().isoformat()
        
        if current is None:
            # New airport - all fields are changes
            for field_name in ['name', 'type', 'latitude_deg', 'longitude_deg', 'elevation_ft',
                              'continent', 'iso_country', 'iso_region', 'municipality',
                              'scheduled_service', 'gps_code', 'iata_code', 'local_code',
                              'home_link', 'wikipedia_link', 'keywords']:
                value = getattr(new, field_name)
                if value is not None:
                    changes.append({
                        'field_name': field_name,
                        'old_value': None,
                        'new_value': str(value),
                        'source': list(new.sources)[0] if new.sources else 'unknown',
                        'changed_at': now
                    })
        else:
            # Check for changes in existing airport
            for field_name in ['name', 'type', 'latitude_deg', 'longitude_deg', 'elevation_ft',
                              'continent', 'iso_country', 'iso_region', 'municipality',
                              'scheduled_service', 'gps_code', 'iata_code', 'local_code',
                              'home_link', 'wikipedia_link', 'keywords']:
                old_value = current.get(field_name)
                new_value = getattr(new, field_name)
                
                if old_value != new_value:
                    changes.append({
                        'field_name': field_name,
                        'old_value': str(old_value) if old_value is not None else None,
                        'new_value': str(new_value) if new_value is not None else None,
                        'source': list(new.sources)[0] if new.sources else 'unknown',
                        'changed_at': now
                    })
        
        return changes
    
    def _detect_runway_changes(self, current: Optional[Dict], new: Runway) -> List[Dict]:
        """Detect changes in runway fields."""
        changes = []
        now = datetime.now().isoformat()
        
        if current is None:
            # New runway - all fields are changes
            for field_name in ['length_ft', 'width_ft', 'surface', 'lighted', 'closed',
                              'le_latitude_deg', 'le_longitude_deg', 'le_elevation_ft',
                              'le_heading_degT', 'le_displaced_threshold_ft',
                              'he_latitude_deg', 'he_longitude_deg', 'he_elevation_ft',
                              'he_heading_degT', 'he_displaced_threshold_ft']:
                value = getattr(new, field_name)
                if value is not None:
                    changes.append({
                        'field_name': field_name,
                        'old_value': None,
                        'new_value': str(value),
                        'source': 'unknown',  # Runway doesn't have source tracking
                        'changed_at': now
                    })
        else:
            # Check for changes in existing runway
            for field_name in ['length_ft', 'width_ft', 'surface', 'lighted', 'closed',
                              'le_latitude_deg', 'le_longitude_deg', 'le_elevation_ft',
                              'le_heading_degT', 'le_displaced_threshold_ft',
                              'he_latitude_deg', 'he_longitude_deg', 'he_elevation_ft',
                              'he_heading_degT', 'he_displaced_threshold_ft']:
                old_value = current.get(field_name)
                new_value = getattr(new, field_name)
                
                if old_value != new_value:
                    changes.append({
                        'field_name': field_name,
                        'old_value': str(old_value) if old_value is not None else None,
                        'new_value': str(new_value) if new_value is not None else None,
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
        
        logger.info(f"Loaded model with {len(model.airports)} airports")
        return model
    
    def _load_airport(self, conn: sqlite3.Connection, icao: str) -> Optional[Airport]:
        """Load a single airport with all its data."""
        # Load basic airport info
        cursor = conn.execute('SELECT * FROM airports WHERE icao_code = ?', (icao,))
        row = cursor.fetchone()
        if not row:
            return None
        
        # Create airport object
        airport = Airport(
            ident=row['icao_code'],
            name=row['name'],
            type=row['type'],
            latitude_deg=row['latitude_deg'],
            longitude_deg=row['longitude_deg'],
            elevation_ft=row['elevation_ft'],
            continent=row['continent'],
            iso_country=row['iso_country'],
            iso_region=row['iso_region'],
            municipality=row['municipality'],
            scheduled_service=row['scheduled_service'],
            gps_code=row['gps_code'],
            iata_code=row['iata_code'],
            local_code=row['local_code'],
            home_link=row['home_link'],
            wikipedia_link=row['wikipedia_link'],
            keywords=row['keywords']
        )
        
        # Load sources
        if row['sources']:
            for source in row['sources'].split(','):
                airport.add_source(source)
        
        # Load runways
        cursor = conn.execute('SELECT * FROM runways WHERE airport_icao = ?', (icao,))
        for row in cursor.fetchall():
            runway = Runway(
                airport_ident=icao,
                le_ident=row['le_ident'],
                he_ident=row['he_ident'],
                length_ft=row['length_ft'],
                width_ft=row['width_ft'],
                surface=row['surface'],
                lighted=bool(row['lighted']) if row['lighted'] is not None else None,
                closed=bool(row['closed']) if row['closed'] is not None else None,
                le_latitude_deg=row['le_latitude_deg'],
                le_longitude_deg=row['le_longitude_deg'],
                le_elevation_ft=row['le_elevation_ft'],
                le_heading_degT=row['le_heading_degT'],
                le_displaced_threshold_ft=row['le_displaced_threshold_ft'],
                he_latitude_deg=row['he_latitude_deg'],
                he_longitude_deg=row['he_longitude_deg'],
                he_elevation_ft=row['he_elevation_ft'],
                he_heading_degT=row['he_heading_degT'],
                he_displaced_threshold_ft=row['he_displaced_threshold_ft']
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
                JOIN runways r ON rc.runway_id = r.id
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