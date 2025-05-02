#!/usr/bin/env python3

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

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