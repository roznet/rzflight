from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
import logging
from pathlib import Path
import json

from .airport import Airport
from .runway import Runway
from .aip_entry import AIPEntry
from .procedure import Procedure

logger = logging.getLogger(__name__)

@dataclass
class EuroAipModel:
    """
    Main model class that maintains the overall model of all airports and their derived information.
    
    This class serves as the central data store for all airport information collected from
    various sources. It provides methods for adding, updating, and querying airport data.
    """
    
    # Main data store: map from ICAO code to Airport object
    airports: Dict[str, Airport] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    sources_used: Set[str] = field(default_factory=set)
    
    # Field standardization service
    field_service: Optional['FieldStandardizationService'] = None
    
    def __post_init__(self):
        """Initialize field standardization service if not provided."""
        if self.field_service is None:
            from ..utils.field_standardization_service import FieldStandardizationService
            self.field_service = FieldStandardizationService()
    
    def add_airport(self, airport: Airport) -> None:
        """
        Add or update an airport in the model.
        
        Args:
            airport: Airport object to add or update
        """
        if airport.ident in self.airports:
            # Update existing airport
            existing = self.airports[airport.ident]
            
            # Update basic fields if new data is available
            for field_name, value in airport.__dict__.items():
                if value is not None and field_name not in ['runways', 'aip_entries', 'procedures', 'sources', 'created_at', 'updated_at']:
                    setattr(existing, field_name, value)
            
            # Add runways
            for runway in airport.runways:
                existing.add_runway(runway)
            
            # Add AIP entries
            for entry in airport.aip_entries:
                existing.add_aip_entry(entry)
            
            # Add procedures
            for procedure in airport.procedures:
                existing.add_procedure(procedure)
            
            # Add sources
            for source in airport.sources:
                existing.add_source(source)
                self.sources_used.add(source)
            
            existing.updated_at = datetime.now()
            logger.debug(f"Updated airport {airport.ident} with data from {list(airport.sources)}")
        else:
            # Add new airport
            self.airports[airport.ident] = airport
            for source in airport.sources:
                self.sources_used.add(source)
            logger.debug(f"Added new airport {airport.ident} with data from {list(airport.sources)}")
        
        self.updated_at = datetime.now()
    
    def add_aip_entries_to_airport(self, icao: str, entries: List[AIPEntry], standardize: bool = True) -> None:
        """
        Add AIP entries to a specific airport with optional standardization.
        
        Args:
            icao: ICAO airport code
            entries: List of AIPEntry objects to add
            standardize: Whether to standardize the entries using field service
        """
        if icao not in self.airports:
            logger.warning(f"Airport {icao} not found in model, creating new airport")
            airport = Airport(ident=icao)
            self.airports[icao] = airport
        
        airport = self.airports[icao]
        
        if standardize and self.field_service:
            entries = self.field_service.standardize_aip_entries(entries)
        
        airport.add_aip_entries(entries)
        logger.debug(f"Added {len(entries)} AIP entries to {icao}")
    
    def get_airports_with_standardized_aip_data(self) -> List[Airport]:
        """
        Get all airports that have standardized AIP data.
        
        Returns:
            List of airports with standardized AIP data
        """
        return [airport for airport in self.airports.values() 
                if airport.get_standardized_entries()]
    
    def get_field_mapping_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about field mapping across all airports.
        
        Returns:
            Dictionary with field mapping statistics
        """
        all_entries = []
        for airport in self.airports.values():
            all_entries.extend(airport.aip_entries)
        
        if self.field_service:
            return self.field_service.get_mapping_statistics(all_entries)
        else:
            return {
                'total_fields': len(all_entries),
                'mapped_fields': 0,
                'unmapped_fields': len(all_entries),
                'mapping_rate': 0.0,
                'average_mapping_score': 0.0,
                'section_counts': {}
            }
    
    def get_airport(self, icao: str) -> Optional[Airport]:
        """
        Get an airport by ICAO code.
        
        Args:
            icao: ICAO airport code
            
        Returns:
            Airport object or None if not found
        """
        return self.airports.get(icao)
    
    def get_airports_by_country(self, country_code: str) -> List[Airport]:
        """
        Get all airports in a specific country.
        
        Args:
            country_code: ISO country code
            
        Returns:
            List of airports in the country
        """
        return [airport for airport in self.airports.values() 
                if airport.iso_country == country_code]
    
    def get_airports_by_source(self, source_name: str) -> List[Airport]:
        """
        Get all airports that have data from a specific source.
        
        Args:
            source_name: Name of the source
            
        Returns:
            List of airports with data from the source
        """
        return [airport for airport in self.airports.values() 
                if source_name in airport.sources]
    
    def get_airports_with_procedures(self, procedure_type: Optional[str] = None) -> List[Airport]:
        """
        Get all airports that have procedures.
        
        Args:
            procedure_type: Optional procedure type filter
            
        Returns:
            List of airports with procedures
        """
        if procedure_type:
            return [airport for airport in self.airports.values() 
                    if airport.get_procedures_by_type(procedure_type)]
        else:
            return [airport for airport in self.airports.values() 
                    if airport.procedures]
    
    def get_airports_with_runways(self) -> List[Airport]:
        """
        Get all airports that have runway information.
        
        Returns:
            List of airports with runways
        """
        return [airport for airport in self.airports.values() 
                if airport.runways]
    
    def get_airports_with_aip_data(self) -> List[Airport]:
        """
        Get all airports that have AIP data.
        
        Returns:
            List of airports with AIP data
        """
        return [airport for airport in self.airports.values() 
                if airport.aip_entries]
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get statistics about the model.
        
        Returns:
            Dictionary with model statistics
        """
        total_airports = len(self.airports)
        airports_with_runways = len(self.get_airports_with_runways())
        airports_with_procedures = len(self.get_airports_with_procedures())
        airports_with_aip_data = len(self.get_airports_with_aip_data())
        
        total_runways = sum(len(airport.runways) for airport in self.airports.values())
        total_procedures = sum(len(airport.procedures) for airport in self.airports.values())
        total_aip_entries = sum(len(airport.aip_entries) for airport in self.airports.values())
        
        # Count procedures by type
        procedure_types = {}
        for airport in self.airports.values():
            for procedure in airport.procedures:
                proc_type = procedure.procedure_type.lower()
                procedure_types[proc_type] = procedure_types.get(proc_type, 0) + 1
        
        return {
            'total_airports': total_airports,
            'airports_with_runways': airports_with_runways,
            'airports_with_procedures': airports_with_procedures,
            'airports_with_aip_data': airports_with_aip_data,
            'total_runways': total_runways,
            'total_procedures': total_procedures,
            'total_aip_entries': total_aip_entries,
            'procedure_types': procedure_types,
            'sources_used': list(self.sources_used),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def save_to_json(self, file_path: str) -> None:
        """
        Save the model to a JSON file.
        
        Args:
            file_path: Path to save the JSON file
        """
        data = {
            'airports': {icao: airport.to_dict() for icao, airport in self.airports.items()},
            'statistics': self.get_statistics()
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Model saved to {file_path}")
    
    def to_dict(self) -> Dict[str, any]:
        """
        Convert the model to a dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the model
        """
        return {
            'airports': {icao: airport.to_dict() for icao, airport in self.airports.items()},
            'statistics': self.get_statistics()
        }
    
    @classmethod
    def load_from_json(cls, file_path: str) -> 'EuroAipModel':
        """
        Load the model from a JSON file.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            EuroAipModel instance
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        model = cls()
        
        # Load airports
        for icao, airport_data in data['airports'].items():
            airport = Airport.from_dict(airport_data)
            model.airports[icao] = airport
            for source in airport.sources:
                model.sources_used.add(source)
        
        logger.info(f"Model loaded from {file_path} with {len(model.airports)} airports")
        return model
    
    def export_to_sqlite(self, db_path: str) -> None:
        """
        Export the model to a SQLite database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        import sqlite3
        
        conn = sqlite3.connect(db_path)
        
        try:
            # Create tables
            conn.execute('''
                CREATE TABLE IF NOT EXISTS airports (
                    icao_code TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    latitude_deg REAL,
                    longitude_deg REAL,
                    elevation_ft TEXT,
                    continent TEXT,
                    iso_country TEXT,
                    iso_region TEXT,
                    municipality TEXT,
                    iata_code TEXT,
                    sources TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS runways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    le_ident TEXT,
                    he_ident TEXT,
                    length_ft REAL,
                    width_ft REAL,
                    surface TEXT,
                    lighted INTEGER,
                    closed INTEGER,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS aip_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    section TEXT,
                    field TEXT,
                    value TEXT,
                    alt_field TEXT,
                    alt_value TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    airport_icao TEXT,
                    name TEXT,
                    type TEXT,
                    runway TEXT,
                    source TEXT,
                    authority TEXT,
                    category TEXT,
                    minima TEXT,
                    notes TEXT,
                    FOREIGN KEY (airport_icao) REFERENCES airports (icao_code)
                )
            ''')
            
            # Insert data
            for airport in self.airports.values():
                # Insert airport
                conn.execute('''
                    INSERT OR REPLACE INTO airports 
                    (icao_code, name, type, latitude_deg, longitude_deg, elevation_ft,
                     continent, iso_country, iso_region, municipality, iata_code,
                     sources, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident, airport.name, airport.type,
                    airport.latitude_deg, airport.longitude_deg, airport.elevation_ft,
                    airport.continent, airport.iso_country, airport.iso_region,
                    airport.municipality, airport.iata_code,
                    ','.join(airport.sources),
                    airport.created_at.isoformat(), airport.updated_at.isoformat()
                ))
                
                # Insert runways
                for runway in airport.runways:
                    conn.execute('''
                        INSERT INTO runways 
                        (airport_icao, le_ident, he_ident, length_ft, width_ft,
                         surface, lighted, closed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        airport.ident, runway.le_ident, runway.he_ident,
                        runway.length_ft, runway.width_ft, runway.surface,
                        runway.lighted, runway.closed
                    ))
                
                # Insert AIP entries
                for entry in airport.aip_entries:
                    conn.execute('''
                        INSERT INTO aip_entries 
                        (airport_icao, section, field, value, alt_field, alt_value)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        airport.ident, entry.section, entry.field, entry.value,
                        entry.alt_field, entry.alt_value
                    ))
                
                # Insert procedures
                for procedure in airport.procedures:
                    conn.execute('''
                        INSERT INTO procedures 
                        (airport_icao, name, type, runway, source, authority,
                         category, minima, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        airport.ident, procedure.name, procedure.procedure_type,
                        procedure.runway, procedure.source, procedure.authority,
                        procedure.category, procedure.minima, procedure.notes
                    ))
            
            conn.commit()
            logger.info(f"Model exported to SQLite database: {db_path}")
            
        finally:
            conn.close()
    
    def __repr__(self):
        return f"EuroAipModel(airports={len(self.airports)}, sources={list(self.sources_used)})"
    
    def __str__(self):
        stats = self.get_statistics()
        return f"""EuroAipModel:
- Total airports: {stats['total_airports']}
- Airports with runways: {stats['airports_with_runways']}
- Airports with procedures: {stats['airports_with_procedures']}
- Airports with AIP data: {stats['airports_with_aip_data']}
- Total runways: {stats['total_runways']}
- Total procedures: {stats['total_procedures']}
- Total AIP entries: {stats['total_aip_entries']}
- Sources used: {', '.join(stats['sources_used'])}
- Created: {stats['created_at']}
- Updated: {stats['updated_at']}"""
    
    def get_procedures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_procedures_by_runway(runway_ident)
    
    def get_approaches_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all approach procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_approaches_by_runway(runway_ident)
    
    def get_departures_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all departure procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_departures_by_runway(runway_ident)
    
    def get_arrivals_by_runway(self, airport_icao: str, runway_ident: str) -> List['Procedure']:
        """Get all arrival procedures for a specific runway at an airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return []
        return airport.get_arrivals_by_runway(runway_ident)
    
    def get_all_approaches(self) -> Dict[str, List['Procedure']]:
        """Get all approach procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            approaches = airport.get_approaches()
            if approaches:
                result[icao] = approaches
        return result
    
    def get_all_departures(self) -> Dict[str, List['Procedure']]:
        """Get all departure procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            departures = airport.get_departures()
            if departures:
                result[icao] = departures
        return result
    
    def get_all_arrivals(self) -> Dict[str, List['Procedure']]:
        """Get all arrival procedures across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            arrivals = airport.get_arrivals()
            if arrivals:
                result[icao] = arrivals
        return result
    
    def get_procedures_by_source(self, source: str) -> Dict[str, List['Procedure']]:
        """Get all procedures from a specific source across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            procedures = airport.get_procedures_by_source(source)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_procedures_by_authority(self, authority: str) -> Dict[str, List['Procedure']]:
        """Get all procedures from a specific authority across all airports."""
        result = {}
        for icao, airport in self.airports.items():
            procedures = airport.get_procedures_by_authority(authority)
            if procedures:
                result[icao] = procedures
        return result
    
    def get_runway_procedures_summary(self, airport_icao: str) -> Dict[str, Dict[str, List[str]]]:
        """Get a summary of procedures by runway and type for a specific airport."""
        airport = self.get_airport(airport_icao)
        if not airport:
            return {}
        return airport.get_runway_procedures_summary()
    
    def get_all_runway_procedures_summary(self) -> Dict[str, Dict[str, Dict[str, List[str]]]]:
        """Get a summary of procedures by runway and type for all airports."""
        result = {}
        for icao, airport in self.airports.items():
            summary = airport.get_runway_procedures_summary()
            if summary:
                result[icao] = summary
        return result 