#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import sqlite3
import json
from datetime import datetime

from euro_aip.sources import (
    AutorouterSource, FranceEAIPSource, UKEAIPSource, WorldAirportsSource, 
    PointDePassageJournalOfficiel, DatabaseSource
)
from euro_aip.models import EuroAipModel, Airport
from euro_aip.sources.base import SourceInterface
from euro_aip.utils.field_standardization_service import FieldStandardizationService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelBuilder:
    """Builds EuroAipModel from multiple sources."""
    
    def __init__(self, args):
        """Initialize the model builder with configuration."""
        self.args = args
        self.cache_dir = Path(args.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize field standardization service
        self.field_service = FieldStandardizationService()
        
        # Initialize sources
        self.sources = {}
        self._initialize_sources()
    
    def _initialize_sources(self):
        """Initialize all configured sources."""
        if self.args.worldairports:
            self.sources['worldairports'] = WorldAirportsSource(
                cache_dir=str(self.cache_dir),
                database=self.args.worldairports_db or 'airports.db'
            )
        
        if self.args.france_eaip:
            self.sources['france_eaip'] = FranceEAIPSource(
                cache_dir=str(self.cache_dir),
                root_dir=self.args.france_eaip
            )
        
        if self.args.uk_eaip:
            self.sources['uk_eaip'] = UKEAIPSource(
                cache_dir=str(self.cache_dir),
                root_dir=self.args.uk_eaip
            )
        
        if self.args.autorouter:
            if not self.args.autorouter_username or not self.args.autorouter_password:
                logger.warning("Autorouter source requires username and password")
            else:
                self.sources['autorouter'] = AutorouterSource(
                    cache_dir=str(self.cache_dir),
                    username=self.args.autorouter_username,
                    password=self.args.autorouter_password
                )
        
        if self.args.pointdepassage:
            if not self.args.pointdepassage_journal:
                logger.warning("Point de Passage source requires journal path")
            else:
                database_source = DatabaseSource(self.args.pointdepassage_db or 'airports.db')
                self.sources['pointdepassage'] = PointDePassageJournalOfficiel(
                    pdf_path=self.args.pointdepassage_journal,
                    database_source=database_source
                )
        
        # Configure refresh behavior
        if self.args.force_refresh:
            for source in self.sources.values():
                source.set_force_refresh()
        if self.args.never_refresh:
            for source in self.sources.values():
                source.set_never_refresh()
        
        logger.info(f"Initialized {len(self.sources)} sources: {list(self.sources.keys())}")
    
    def build_model(self, airports: Optional[List[str]] = None) -> EuroAipModel:
        """Build EuroAipModel from all configured sources."""
        model = EuroAipModel()
        
        # Separate WorldAirports source to process it last
        worldairports_source = self.sources.pop('worldairports', None) if 'worldairports' in self.sources else None
        
        # Update model with each source (excluding WorldAirports for now)
        for source_name, source in self.sources.items():
            try:
                logger.info(f"Updating model with {source_name} source")
                
                if isinstance(source, SourceInterface):
                    # Use the new update_model interface
                    source.update_model(model, airports)
                    logger.info(f"Updated model with {source_name}: {len(model.airports)} airports")
                else:
                    # Fallback for sources that don't implement SourceInterface
                    logger.warning(f"Source {source_name} doesn't implement SourceInterface, skipping")
                    
            except Exception as e:
                logger.error(f"Error updating model with {source_name}: {e}")
        
        # Process WorldAirports source last with appropriate filtering
        if worldairports_source:
            try:
                logger.info(f"Updating model with worldairports source (filter: {self.args.worldairports_filter})")
                
                if self.args.worldairports_filter == 'default':
                    # Only add airports that already exist in the model (from other sources)
                    existing_airports = list(model.airports.keys())
                    if existing_airports:
                        worldairports_source.update_model(model, existing_airports)
                        logger.info(f"Updated WorldAirports with {len(existing_airports)} existing airports")
                    else:
                        logger.warning("No existing airports in model, skipping WorldAirports default filter")
                
                elif self.args.worldairports_filter == 'europe':
                    # Filter to European airports only
                    european_airports = self._get_european_airports(worldairports_source)
                    if european_airports:
                        worldairports_source.update_model(model, european_airports)
                        logger.info(f"Updated WorldAirports with {len(european_airports)} European airports")
                    else:
                        logger.warning("No European airports found in WorldAirports")
                
                elif self.args.worldairports_filter == 'all':
                    # Add all airports from WorldAirports
                    worldairports_source.update_model(model, airports)
                    logger.info(f"Updated WorldAirports with all airports")
                
                logger.info(f"Final model after WorldAirports: {len(model.airports)} airports")
                
            except Exception as e:
                logger.error(f"Error updating model with worldairports: {e}")
        
        # Filter to specific airports if provided
        if airports:
            filtered_model = EuroAipModel()
            for airport_code in airports:
                if airport_code in model.airports:
                    filtered_model.airports[airport_code] = model.airports[airport_code]
                else:
                    logger.warning(f"Airport {airport_code} not found in model")
            model = filtered_model
        
        # Log field mapping statistics
        mapping_stats = model.get_field_mapping_statistics()
        logger.info(f"Field mapping statistics: {mapping_stats['mapped_fields']}/{mapping_stats['total_fields']} fields mapped ({mapping_stats['mapping_rate']:.1%})")
        logger.info(f"Average mapping score: {mapping_stats['average_mapping_score']:.2f}")
        
        logger.info(f"Final model contains {len(model.airports)} airports")
        return model
    
    def _get_european_airports(self, worldairports_source) -> List[str]:
        """Get list of European airports from WorldAirports source."""
        try:
            airports_df = worldairports_source.get_airports()
            european_airports = airports_df[
                (airports_df['continent'] == 'EU') & 
                (~airports_df['type'].isin(['heliport', 'closed']))
            ]['ident'].tolist()
            return european_airports
        except Exception as e:
            logger.error(f"Error getting European airports from WorldAirports: {e}")
            return []
    
    def get_all_airports(self) -> List[str]:
        """Get list of all available airports from all sources that support it."""
        all_airports = set()
        
        for source_name, source in self.sources.items():
            if hasattr(source, 'find_available_airports'):
                try:
                    airports = source.find_available_airports()
                    all_airports.update(airports)
                    logger.info(f"Found {len(airports)} airports in {source_name}")
                except Exception as e:
                    logger.warning(f"Error getting airports from {source_name}: {e}")
            else:
                logger.debug(f"Source {source_name} does not support find_available_airports")
        
        if not all_airports:
            logger.warning("No airports found from any source that supports find_available_airports")
            return []
        
        sorted_airports = sorted(list(all_airports))
        logger.info(f"Total unique airports found across all sources: {len(sorted_airports)}")
        return sorted_airports

class SQLiteExporter:
    """Exports EuroAipModel to SQLite database."""
    
    def __init__(self, db_path: str):
        """Initialize SQLite exporter."""
        self.db_path = db_path
        self.conn = None
    
    def create_tables(self):
        """Create the database schema."""
        self.conn = sqlite3.connect(self.db_path)
        
        # Main airports table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS airports (
                icao_code TEXT PRIMARY KEY,
                iata_code TEXT,
                name TEXT,
                country TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                elevation REAL,
                timezone TEXT,
                sources TEXT,
                last_updated TEXT
            )
        ''')
        
        # AIP data table (key-value pairs)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS aip_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao_code TEXT,
                source TEXT,
                field_name TEXT,
                field_value TEXT,
                std_field_name TEXT,
                std_field_id INTEGER,
                mapping_score REAL,
                section TEXT,
                FOREIGN KEY (icao_code) REFERENCES airports (icao_code),
                UNIQUE(icao_code, source, field_name)
            )
        ''')
        
        # Runways table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS runways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao_code TEXT,
                runway_identifier TEXT,
                length REAL,
                width REAL,
                surface TEXT,
                FOREIGN KEY (icao_code) REFERENCES airports (icao_code)
            )
        ''')
        
        # Procedures table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                icao_code TEXT,
                procedure_type TEXT,
                procedure_name TEXT,
                procedure_data TEXT,
                FOREIGN KEY (icao_code) REFERENCES airports (icao_code)
            )
        ''')
        
        self.conn.commit()
        logger.info(f"Created SQLite database schema at {self.db_path}")
    
    def export_model(self, model: EuroAipModel):
        """Export the entire model to the database."""
        if not self.conn:
            self.create_tables()
        
        logger.info(f"Exporting {len(model.airports)} airports to SQLite")
        
        for airport_code, airport in model.airports.items():
            # Insert/update main airport record
            self.conn.execute('''
                INSERT OR REPLACE INTO airports 
                (icao_code, iata_code, name, country, city, latitude, longitude, elevation, timezone, sources, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                airport.ident,
                airport.iata_code,
                airport.name,
                airport.iso_country,
                airport.municipality,
                airport.latitude_deg,
                airport.longitude_deg,
                airport.elevation_ft,
                None,
                ','.join(airport.sources),
                airport.updated_at.isoformat() if airport.updated_at else None
            ))
            
            # Insert AIP data
            for entry in airport.aip_entries:
                self.conn.execute('''
                    INSERT OR REPLACE INTO aip_data 
                    (icao_code, source, field_name, field_value, std_field_name, std_field_id, mapping_score, section)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    airport.ident,
                    'aip_entries',  # Source is now 'aip_entries' since we're using the unified structure
                    entry.field,
                    entry.value,
                    entry.std_field,
                    entry.std_field_id,
                    entry.mapping_score,
                    entry.section
                ))
            
            # Insert runway data
            for runway in airport.runways:
                self.conn.execute('''
                    INSERT INTO runways (icao_code, runway_identifier, length, width, surface)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    airport.ident,
                    runway.le_ident,  # Use le_ident as primary identifier
                    runway.length_ft,
                    runway.width_ft,
                    runway.surface
                ))
            
            # Insert procedure data
            for procedure in airport.procedures:
                self.conn.execute('''
                    INSERT INTO procedures (icao_code, procedure_type, procedure_name, procedure_data)
                    VALUES (?, ?, ?, ?)
                ''', (
                    airport.ident,
                    procedure.procedure_type,
                    procedure.name,
                    json.dumps(procedure.data) if procedure.data else None
                ))
        
        self.conn.commit()
        logger.info(f"Successfully exported {len(model.airports)} airports to SQLite")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()

class JSONExporter:
    """Exports EuroAipModel to JSON file."""
    
    def __init__(self, json_path: str):
        """Initialize JSON exporter."""
        self.json_path = json_path
    
    def export_model(self, model: EuroAipModel):
        """Export the entire model to JSON."""
        logger.info(f"Exporting {len(model.airports)} airports to JSON")
        
        # Convert model to dictionary
        model_data = model.to_dict()
        
        # Write to file
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(model_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Successfully exported model to {self.json_path}")

class AIPExporter:
    """Main exporter class that coordinates model building and export."""
    
    def __init__(self, args):
        """Initialize the exporter."""
        self.args = args
        self.model_builder = ModelBuilder(args)
        self.exporters = {}
        
        # Initialize exporters based on output format
        if self.args.sqlite:
            self.exporters['sqlite'] = SQLiteExporter(self.args.sqlite)
        
        if self.args.json:
            self.exporters['json'] = JSONExporter(self.args.json)
    
    def run(self):
        """Run the export process."""
        # Get airports to export
        if self.args.airports:
            airports = self.args.airports
        else:
            airports = self.model_builder.get_all_airports()
        
        if not airports:
            logger.error("No airports to export")
            return
        
        logger.info(f"Building model for {len(airports)} airports")
        
        # Build the model
        model = self.model_builder.build_model(airports)
        
        if not model.airports:
            logger.error("No airport data found in model")
            return
        
        # Export to all configured formats
        for exporter_name, exporter in self.exporters.items():
            try:
                logger.info(f"Exporting to {exporter_name}")
                exporter.export_model(model)
            except Exception as e:
                logger.error(f"Error exporting to {exporter_name}: {e}")
        
        # Close exporters that need cleanup
        for exporter in self.exporters.values():
            if hasattr(exporter, 'close'):
                exporter.close()
        
        logger.info(f"Export completed successfully")

def main():
    parser = argparse.ArgumentParser(description='AIP Data Export Tool using EuroAipModel')
    
    # Airport selection
    parser.add_argument('airports', help='List of ICAO airport codes to export (or all if empty)', nargs='*')
    
    # Source configuration
    parser.add_argument('--worldairports', help='Enable WorldAirports source', action='store_true')
    parser.add_argument('--worldairports-db', help='WorldAirports database file', default='airports.db')
    parser.add_argument('--worldairports-filter', 
                       choices=['default', 'europe', 'all'], 
                       default='default',
                       help='WorldAirports filtering mode: default=only airports from other sources, europe=EU continent only, all=all airports')
    
    parser.add_argument('--france-eaip', help='France eAIP root directory')
    parser.add_argument('--uk-eaip', help='UK eAIP root directory')
    
    parser.add_argument('--autorouter', help='Enable Autorouter source', action='store_true')
    parser.add_argument('--autorouter-username', help='Autorouter username')
    parser.add_argument('--autorouter-password', help='Autorouter password')
    
    parser.add_argument('--pointdepassage', help='Enable Point de Passage source', action='store_true')
    parser.add_argument('--pointdepassage-journal', help='Point de Passage journal PDF path')
    parser.add_argument('--pointdepassage-db', help='Point de Passage database file', default='airports.db')
    
    # Output configuration
    parser.add_argument('--sqlite', help='SQLite output database file')
    parser.add_argument('--json', help='JSON output file')
    
    # General options
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('--force-refresh', help='Force refresh of cached data', action='store_true')
    parser.add_argument('--never-refresh', help='Never refresh cached data if it exists', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate that at least one source and one output format are specified
    sources_enabled = any([
        args.worldairports, args.france_eaip, args.uk_eaip, 
        args.autorouter, args.pointdepassage
    ])
    
    outputs_enabled = any([
        args.sqlite, args.json
    ])
    
    if not sources_enabled:
        logger.error("At least one data source must be enabled")
        return
    
    if not outputs_enabled:
        logger.error("At least one output format must be specified")
        return
    
    exporter = AIPExporter(args)
    exporter.run()

if __name__ == '__main__':
    main() 