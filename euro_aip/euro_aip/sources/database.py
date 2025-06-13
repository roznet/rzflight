#!/usr/bin/env python3

import sqlite3
from pathlib import Path
from typing import Optional, Dict, List
from contextlib import contextmanager
from ..models.airport import Airport
from ..models.runway import Runway

class DatabaseSource:
    """
    A source that provides direct access to a precomputed SQLite database.
    
    This source is designed for read-only access to a precomputed database
    containing airport and navigation data. It provides direct access to the
    database connection and can be extended with specific query methods as needed.
    """
    
    def __init__(self, database_path: str):
        """
        Initialize the database source.
        
        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = Path(database_path)
        if not self.database_path.exists():
            raise FileNotFoundError(f"Database file not found: {database_path}")

    @contextmanager
    def get_connection(self):
        """
        Get a database connection.
        
        Yields:
            sqlite3.Connection: A connection to the database
            
        Example:
            with source.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM airports")
                rows = cursor.fetchall()
        """
        conn = sqlite3.connect(str(self.database_path))
        conn.row_factory = sqlite3.Row  # Enable row factory for named access
        try:
            yield conn
        finally:
            conn.close()

    def get_table_info(self, table_name: str) -> Optional[dict]:
        """
        Get information about a specific table in the database.
        
        Args:
            table_name: Name of the table to get information about
            
        Returns:
            Dictionary containing table information or None if table doesn't exist
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                return None
                
            # Get column information
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [dict(row) for row in cursor.fetchall()]
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            row_count = cursor.fetchone()['count']
            
            return {
                'name': table_name,
                'columns': columns,
                'row_count': row_count
            }

    def get_database_info(self) -> dict:
        """
        Get information about all tables in the database.
        
        Returns:
            Dictionary containing information about all tables
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row['name'] for row in cursor.fetchall()]
            
            return {
                'database': str(self.database_path),
                'tables': [self.get_table_info(table) for table in tables]
            } 
        
    def get_airports(self, where: str = None) -> List[Airport]:
        """
        Get all airports from the database.
        
        Args:
            where: SQL WHERE clause to filter the airports
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM airports"

            if where:
                query += f" WHERE {where}"
            
            cursor.execute(query)
            return [Airport.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_airports_with_runways(self, where: str = None) -> List[Airport]:
        """
        Get all airports from the database with their runways.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
            SELECT a.*, r.*
            FROM airports a
            LEFT JOIN runways r ON a.ident = r.airport_ident
            """
            if where:
                query += f" WHERE {where}"
            cursor.execute(query)

            airports : Dict[str, Airport] = {}

            for row in cursor:
                airport_id = row['ident']
                if airport_id not in airports:
                    airports[airport_id] = Airport.from_dict(dict(row))

                runway = Runway.from_dict(dict(row))
                if not runway.closed:
                    if not airports[airport_id].runways:
                        airports[airport_id].runways = []
                    airports[airport_id].runways.append(runway)

            return list(airports.values())

    def get_airports_by_icao_list(self, icao_list: List[str]) -> List[Airport]:
        """
        Efficiently query airports from database using a list of ICAO codes.
        
        Parameters
        ----------
        icao_list : List[str]
            List of ICAO airport codes to query
            
        Returns
        -------
        List[Airport]
            List of matching airports
        """
        
        # SQLite has a limit of 999 parameters, so we need to handle large lists
        CHUNK_SIZE = 900  # Leave some margin below the 999 limit
        
        if len(icao_list) > CHUNK_SIZE:
            # For large lists, we'll need to chunk the query
            all_results = []
            for i in range(0, len(icao_list), CHUNK_SIZE):
                chunk = icao_list[i:i + CHUNK_SIZE]
                # Create the WHERE clause with placeholders
                placeholders = ','.join([f"'{code}'" for code in chunk])
                where_clause = f"ident IN ({placeholders})"
                
                chunk_airports = self.get_airports(where=where_clause)
                all_results.extend(chunk_airports)
            
            return all_results
        else:
            # For smaller lists, we can do a single query
            placeholders = ','.join([f"'{code}'" for code in icao_list])
            where_clause = f"ident IN ({placeholders})"
            
            return self.get_airports(where=where_clause)

        
        
        
            