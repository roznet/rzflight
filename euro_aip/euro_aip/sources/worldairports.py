import os
import logging
import csv
import urllib.request
from typing import Dict, List, Any, Optional
from pathlib import Path
import sqlite3
import pandas as pd

from .cached import CachedSource
from .base import SourceInterface
from ..models.euro_aip_model import EuroAipModel
from ..models.airport import Airport
from ..models.runway import Runway

logger = logging.getLogger(__name__)

class WorldAirportsSource(CachedSource, SourceInterface):
    """Source implementation for World Airports data from OurAirports."""
    
    def __init__(self, cache_dir: str, database: str = 'airports.db'):
        """
        Initialize the World Airports source.
        
        Args:
            cache_dir: Base directory for caching
            database: SQLite database file path
        """
        super().__init__(cache_dir)
        self.cache_dir = Path(cache_dir)
        self.database = database
        self.airports_file = self.cache_dir / 'airports.csv'
        self.runways_file = self.cache_dir / 'runways.csv'
        
        # Known column type suffixes
        self.known_suffix_types = {
            'id': 'INT',
            '_deg': 'REAL',
            '_ft': 'REAL',
            '_degT': 'REAL',
        }
        
    def _download_file(self, url: str, target: Path) -> None:
        """Download a file if it doesn't exist."""
        if not target.exists():
            logger.info(f"Downloading {url} to {target}")
            urllib.request.urlretrieve(url, target)
            
    def _get_field_type(self, field: str) -> str:
        """Determine SQL type based on field name."""
        # Check for suffixes
        for suffix, sql_type in self.known_suffix_types.items():
            if field.endswith(suffix):
                return sql_type
        if field in ['closed', 'lighted']:
            return 'INTEGER'
                
        return 'TEXT'
        
    def _create_table_from_csv(self, table_name: str, fields: List[str], primary_key: str = 'ident') -> str:
        """Create SQL for creating a table from CSV fields."""
        sql = f'CREATE TABLE {table_name} (\n'
        for field in fields:
            if field == primary_key:
                sql += f"{field} TEXT PRIMARY KEY,\n"
            else:
                sql += f"{field} {self._get_field_type(field)},\n"
        sql = sql[:-2] + '\n)'
        return sql
        
    def _insert_table_from_csv(self, table_name: str, fields: List[str]) -> str:
        """Create SQL for inserting data from CSV."""
        sql = f'INSERT INTO {table_name} VALUES (\n'
        for field in fields:
            sql += f":{field},\n"
        sql = sql[:-2] + '\n)'
        return sql
        
    def fetch_airports(self) -> pd.DataFrame:
        """
        Fetch airports data from OurAirports.
        
        Returns:
            DataFrame containing airport data
        """
        # Download the CSV file if needed
        self._download_file(
            "https://davidmegginson.github.io/ourairports-data/airports.csv",
            self.airports_file
        )
        
        # Read and parse the CSV
        df = pd.read_csv(self.airports_file, encoding='utf-8-sig')
        return df[df['type'].isin(['heliport', 'closed']) == False]
        
    def fetch_runways(self) -> pd.DataFrame:
        """
        Fetch runways data from OurAirports.
        
        Returns:
            DataFrame containing runway data
        """
        # Download the CSV file if needed
        self._download_file(
            "https://davidmegginson.github.io/ourairports-data/runways.csv",
            self.runways_file
        )
        
        # Read and parse the CSV
        return pd.read_csv(self.runways_file, encoding='utf-8-sig')
        
    def get_airports(self, max_age_days: int = 7) -> pd.DataFrame:
        """
        Get airports data from cache or fetch it if not available.
        
        Args:
            max_age_days: Maximum age of cache in days
            
        Returns:
            DataFrame containing airport data
        """
        return self.get_data('airports', 'csv', '', max_age_days=max_age_days)
        
    def get_runways(self, max_age_days: int = 7) -> pd.DataFrame:
        """
        Get runways data from cache or fetch it if not available.
        
        Args:
            max_age_days: Maximum age of cache in days
            
        Returns:
            DataFrame containing runway data
        """
        return self.get_data('runways', 'csv', '', max_age_days=max_age_days)
        
    def _create_airports_table(self, cur: sqlite3.Cursor, airports: pd.DataFrame) -> Dict[str, Any]:
        """Create and populate the airports table."""
        cur.execute('DROP TABLE IF EXISTS airports')
        fields = airports.columns.tolist()
        sql_create = self._create_table_from_csv('airports', fields)
        sql_insert = self._insert_table_from_csv('airports', fields)
        cur.execute(sql_create)
        
        # Insert airports data
        for _, row in airports.iterrows():
            cur.execute(sql_insert, row.to_dict())
            
        return {
            'name': 'airports',
            'row_count': len(airports),
            'fields': fields
        }
        
    def _create_runways_table(self, cur: sqlite3.Cursor, runways: pd.DataFrame) -> Dict[str, Any]:
        """Create and populate the runways table."""
        cur.execute('DROP TABLE IF EXISTS runways')
        fields = runways.columns.tolist()
        sql_create = self._create_table_from_csv('runways', fields)
        sql_insert = self._insert_table_from_csv('runways', fields)
        cur.execute(sql_create)
        cur.execute('CREATE INDEX idx_airport_ident ON runways (airport_ident)')
        
        # Insert runways data
        for _, row in runways.iterrows():
            cur.execute(sql_insert, row.to_dict())
            
        return {
            'name': 'runways',
            'row_count': len(runways),
            'fields': fields
        }
        
    def _create_surface_types_table(self, cur: sqlite3.Cursor) -> Dict[str, Any]:
        """Create and populate the surface types table."""
        cur.execute('DROP TABLE IF EXISTS surface_types')
        cur.execute(self._create_table_from_csv('surface_types', ['surface', 'type']))
        
        # Define surface type mappings
        specific = {
            'hard': ['hard', 'paved', 'pem', 'asfalt', 'tarmac', 'asfalt', 'asfalto', 'ashpalt', 'ashphalt', 'surface paved'],
            'soft': ['graas', 'soft']
        }
        
        contains = {
            'hard': ['asphalt', 'concrete', 'cement'],
            'soft': ['turf', 'grass', 'dirt', 'gravel', 'soil', 'sand', 'earth']
        }
        
        startswith = {
            'hard': ['asp', 'con', 'apsh', 'bit', 'pav'],
            'soft': ['turf', 'grv', 'grav', 'grass', 'san', 'cla', 'grs', 'gra', 'gre'],
            'water': ['wat'],
            'snow': ['sno']
        }
        
        # Get all surface types first
        cur.execute('SELECT DISTINCT surface FROM runways WHERE surface != "" ORDER BY surface')
        surface_types = cur.fetchall()
        
        # Process surface types
        surface_count = 0
        for (surface,) in surface_types:
            surface_lower = surface.lower()
            surface_type = None
            
            # Check contains
            for type_, patterns in contains.items():
                if any(pattern in surface_lower for pattern in patterns):
                    surface_type = type_
                    break
                    
            # Check startswith
            if surface_type is None:
                for type_, patterns in startswith.items():
                    if any(surface_lower.startswith(pattern) for pattern in patterns):
                        surface_type = type_
                        break
                        
            # Check specific
            if surface_type is None:
                for type_, patterns in specific.items():
                    if surface_lower in patterns:
                        surface_type = type_
                        break
                        
            if surface_type is None:
                surface_type = 'other'
                
            cur.execute(
                self._insert_table_from_csv('surface_types', ['surface', 'type']),
                {'surface': surface, 'type': surface_type}
            )
            surface_count += 1
            
        return {
            'name': 'surface_types',
            'row_count': surface_count,
            'fields': ['surface', 'type']
        }
        
    def _create_airport_summary_table(self, cur: sqlite3.Cursor) -> Dict[str, Any]:
        """Create and populate the airport summary table."""
        cur.execute('DROP TABLE IF EXISTS eu_airports_runway_summary')
        fields = ['ident', 'length_ft', 'surface_type', 'surface', 'hard', 'soft', 'water', 'snow']
        cur.execute(self._create_table_from_csv('eu_airports_runway_summary', fields))
        
        # Get airport summaries
        cur.execute("""
            SELECT a.ident, r.length_ft, t.type, r.surface 
            FROM runways r, airports a, surface_types t 
            WHERE a.ident = r.airport_ident 
            AND t.surface = r.surface 
            AND r.surface != '' 
            AND a.continent = 'EU'
            AND r.closed = '0'
        """)
        
        # Process summaries
        summaries = {}
        for row in cur:
            ident, length_ft, surface_type, surface = row
            if length_ft is None:
                continue
            if ident not in summaries:
                summaries[ident] = {
                    'ident': ident,
                    'length_ft': length_ft,
                    'surface_type': surface_type,
                    'surface': surface,
                    'hard': 0,
                    'soft': 0,
                    'water': 0,
                    'snow': 0
                }
                
            summary = summaries[ident]
            if summary['length_ft'] < length_ft:
                summary['length_ft'] = length_ft
                summary['surface_type'] = surface_type
                
            if surface_type in ['hard', 'soft', 'water', 'snow']:
                summary[surface_type] += 1
                
        # Insert summaries
        sql_insert = self._insert_table_from_csv('eu_airports_runway_summary', fields)
        for summary in summaries.values():
            cur.execute(sql_insert, summary)
            
        return {
            'name': 'eu_airports_runway_summary',
            'row_count': len(summaries),
            'fields': fields
        }
        
    def fetch_airport_database(self) -> Dict[str, Any]:
        """
        Fetch and create the SQLite database with airports and runways data.
        
        Returns:
            Dictionary containing database metadata
        """
        # Connect to the database
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        
        try:
            # Get the data
            airports = self.get_airports()
            runways = self.get_runways()
            
            # Create all tables and collect their metadata
            tables_metadata = []
            
            # Create base tables
            tables_metadata.append(self._create_airports_table(cur, airports))
            tables_metadata.append(self._create_runways_table(cur, runways))
            
            # Create derived tables
            tables_metadata.append(self._create_surface_types_table(cur))
            tables_metadata.append(self._create_airport_summary_table(cur))
            
            # Commit the changes
            conn.commit()

            # Return database metadata
            return {
                'database': self.database,
                'tables': tables_metadata
            }
            
        finally:
            conn.close()
            
    def get_airport_database(self, max_age_days: int = 7) -> Dict[str, Any]:
        """
        Get airport database from cache or create it if not available.
        
        Args:
            max_age_days: Maximum age of cache in days
            
        Returns:
            Dictionary containing database metadata
        """
        # should always rebuild the database
        return self.fetch_airport_database()
            
    def get_airport_summary(self) -> List[Dict[str, Any]]:
        """
        Get a summary of airports with their runways.
        
        Returns:
            List of dictionaries containing airport summary data
        """
        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        
        try:
            # Create surface types table
            cur.execute('DROP TABLE IF EXISTS surface_types')
            cur.execute(self._create_table_from_csv('surface_types', ['surface', 'type']))
            
            # Define surface type mappings
            specific = {
                'hard': ['hard', 'paved', 'pem', 'asfalt', 'tarmac', 'asfalt', 'asfalto', 'ashpalt', 'ashphalt', 'surface paved'],
                'soft': ['graas', 'soft']
            }
            
            contains = {
                'hard': ['asphalt', 'concrete', 'cement'],
                'soft': ['turf', 'grass', 'dirt', 'gravel', 'soil', 'sand', 'earth']
            }
            
            startswith = {
                'hard': ['asp', 'con', 'apsh', 'bit', 'pav'],
                'soft': ['turf', 'grv', 'grav', 'grass', 'san', 'cla', 'grs', 'gra', 'gre'],
                'water': ['wat'],
                'snow': ['sno']
            }
            
            # Process surface types
            cur.execute('SELECT surface, count(*) FROM runways GROUP BY surface ORDER BY surface')
            for row in cur:
                surface = row[0]
                surface_lower = surface.lower()
                surface_type = None
                
                # Check contains
                for type_, patterns in contains.items():
                    if any(pattern in surface_lower for pattern in patterns):
                        surface_type = type_
                        break
                        
                # Check startswith
                if surface_type is None:
                    for type_, patterns in startswith.items():
                        if any(surface_lower.startswith(pattern) for pattern in patterns):
                            surface_type = type_
                            break
                            
                # Check specific
                if surface_type is None:
                    for type_, patterns in specific.items():
                        if surface_lower in patterns:
                            surface_type = type_
                            break
                            
                if surface_type is None:
                    surface_type = 'other'
                    
                cur.execute(
                    self._insert_table_from_csv('surface_types', ['surface', 'type']),
                    {'surface': surface, 'type': surface_type}
                )
                
            # Create airport summary
            cur.execute('DROP TABLE IF EXISTS airports_runway_summary')
            fields = ['ident', 'length_ft', 'surface_type', 'surface', 'hard', 'soft', 'water', 'snow']
            cur.execute(self._create_table_from_csv('airports_runway_summary', fields))
            
            # Get airport summaries
            cur.execute("""
                SELECT a.ident, r.length_ft, t.type, r.surface 
                FROM runways r, airports a, surface_types t 
                WHERE a.ident = r.airport_ident 
                AND t.surface = r.surface 
                AND r.surface != '' 
                AND a.continent = 'EU'
            """)
            
            # Process summaries
            summaries = {}
            for row in cur:
                ident, length_ft, surface_type, surface = row
                if ident not in summaries:
                    summaries[ident] = {
                        'ident': ident,
                        'length_ft': length_ft,
                        'surface_type': surface_type,
                        'surface': surface,
                        'hard': 0,
                        'soft': 0,
                        'water': 0,
                        'snow': 0
                    }
                    
                summary = summaries[ident]
                if summary['length_ft'] < length_ft:
                    summary['length_ft'] = length_ft
                    summary['surface_type'] = surface_type
                    
                if surface_type in ['hard', 'soft', 'water', 'snow']:
                    summary[surface_type] += 1
                    
            # Insert summaries
            sql_insert = self._insert_table_from_csv('airports_runway_summary', fields)
            for summary in summaries.values():
                cur.execute(sql_insert, summary)
                
            # Commit changes
            conn.commit()
            
            # Return the summaries
            cur.execute('SELECT * FROM airports_runway_summary')
            return [dict(row) for row in cur.fetchall()]
            
        finally:
            conn.close()

    def update_model(self, model: EuroAipModel, airports: Optional[List[str]] = None) -> None:
        """
        Update the EuroAipModel with WorldAirports data.
        
        Args:
            model: The EuroAipModel to update
            airports: Optional list of specific airports to process. If None, 
                     processes all airports in the WorldAirports database.
        """
        logger.info(f"Updating model with WorldAirports data")
        
        try:
            # Get airports data
            airports_df = self.get_airports()
            runways_df = self.get_runways()
        except Exception as e:
            logger.error(f"Error fetching WorldAirports data: {e}")
            return
        
        # Filter airports if specific list provided
        if airports:
            airports_df = airports_df[airports_df['ident'].isin(airports)]
            logger.info(f"Filtering to {len(airports_df)} specified airports")
        
        # Process each airport
        for _, airport_row in airports_df.iterrows():
            try:
                icao = airport_row['ident']
                
                # Create Airport object
                airport = Airport(
                    ident=icao,
                    name=airport_row.get('name'),
                    type=airport_row.get('type'),
                    latitude_deg=airport_row.get('latitude_deg'),
                    longitude_deg=airport_row.get('longitude_deg'),
                    elevation_ft=airport_row.get('elevation_ft'),
                    continent=airport_row.get('continent'),
                    iso_country=airport_row.get('iso_country'),
                    iso_region=airport_row.get('iso_region'),
                    municipality=airport_row.get('municipality'),
                    scheduled_service=airport_row.get('scheduled_service'),
                    gps_code=airport_row.get('gps_code'),
                    iata_code=airport_row.get('iata_code'),
                    local_code=airport_row.get('local_code'),
                    home_link=airport_row.get('home_link'),
                    wikipedia_link=airport_row.get('wikipedia_link'),
                    keywords=airport_row.get('keywords')
                )
                
                # Add source tracking
                airport.add_source(self.get_source_name())
                
                # Add runways for this airport
                airport_runways = runways_df[runways_df['airport_ident'] == icao]
                for _, runway_row in airport_runways.iterrows():
                    runway = Runway(
                        airport_ident=icao,
                        length_ft=runway_row.get('length_ft'),
                        width_ft=runway_row.get('width_ft'),
                        surface=runway_row.get('surface'),
                        lighted=runway_row.get('lighted'),
                        closed=runway_row.get('closed'),
                        le_ident=runway_row.get('le_ident'),
                        le_latitude_deg=runway_row.get('le_latitude_deg'),
                        le_longitude_deg=runway_row.get('le_longitude_deg'),
                        le_elevation_ft=runway_row.get('le_elevation_ft'),
                        le_heading_degT=runway_row.get('le_heading_degT'),
                        le_displaced_threshold_ft=runway_row.get('le_displaced_threshold_ft'),
                        he_ident=runway_row.get('he_ident'),
                        he_latitude_deg=runway_row.get('he_latitude_deg'),
                        he_longitude_deg=runway_row.get('he_longitude_deg'),
                        he_elevation_ft=runway_row.get('he_elevation_ft'),
                        he_heading_degT=runway_row.get('he_heading_degT'),
                        he_displaced_threshold_ft=runway_row.get('he_displaced_threshold_ft')
                    )
                    airport.add_runway(runway)
                
                # Add airport to model
                model.add_airport(airport)
                
            except Exception as e:
                logger.error(f"Error processing airport {icao} from WorldAirports: {e}")
                # Continue with next airport instead of failing completely
        
        logger.info(f"Added {len(airports_df)} airports from WorldAirports to model")
    
    def find_available_airports(self) -> List[str]:
        """
        Find all available airports in the WorldAirports database.
        
        Returns:
            List of ICAO airport codes available in WorldAirports
        """
        try:
            airports_df = self.get_airports()
            return airports_df['ident'].tolist()
        except Exception as e:
            logger.error(f"Error getting available airports from WorldAirports: {e}")
            return [] 