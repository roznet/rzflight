from typing import List, Type, TypeVar, Dict, Any
import json
import csv
from pathlib import Path
import sqlite3
from datetime import datetime

T = TypeVar('T')

class PersistenceManager:
    """Manager for persisting data to different formats."""
    
    @staticmethod
    def save_json(data: List[Any], filepath: str) -> None:
        """Save data to JSON file."""
        with open(filepath, 'w') as f:
            json.dump([item.to_dict() for item in data], f, indent=2)
    
    @staticmethod
    def load_json(filepath: str, cls: Type[T]) -> List[T]:
        """Load data from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return [cls.from_dict(item) for item in data]
    
    @staticmethod
    def save_csv(data: List[Any], filepath: str) -> None:
        """Save data to CSV file."""
        if not data:
            return
            
        # Get field names from first item
        fieldnames = list(data[0].to_dict().keys())
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in data:
                writer.writerow(item.to_dict())
    
    @staticmethod
    def load_csv(filepath: str, cls: Type[T]) -> List[T]:
        """Load data from CSV file."""
        with open(filepath, 'r', newline='') as f:
            reader = csv.DictReader(f)
            return [cls.from_dict(dict(row)) for row in reader]
    
    @staticmethod
    def save_sqlite(data: List[Any], db_path: str, table_name: str) -> None:
        """Save data to SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        if not data:
            return
            
        # Get field names and types from first item
        sample = data[0].to_dict()
        columns = []
        for name, value in sample.items():
            if isinstance(value, (int, float)):
                col_type = 'REAL'
            elif isinstance(value, bool):
                col_type = 'INTEGER'
            else:
                col_type = 'TEXT'
            columns.append(f"{name} {col_type}")
        
        create_table = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(columns)})"
        cursor.execute(create_table)
        
        # Insert data
        for item in data:
            data_dict = item.to_dict()
            placeholders = ', '.join(['?' for _ in data_dict])
            insert = f"INSERT INTO {table_name} VALUES ({placeholders})"
            cursor.execute(insert, list(data_dict.values()))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def load_sqlite(db_path: str, table_name: str, cls: Type[T]) -> List[T]:
        """Load data from SQLite database."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Convert rows to dictionaries
        data = []
        for row in rows:
            item_dict = dict(zip(columns, row))
            data.append(cls.from_dict(item_dict))
        
        conn.close()
        return data 