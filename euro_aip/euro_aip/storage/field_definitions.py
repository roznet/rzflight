#!/usr/bin/env python3

from typing import Dict, List, Any, Optional, Type
from dataclasses import dataclass
from enum import Enum

class FieldType(Enum):
    """Supported field types for change tracking."""
    STRING = "TEXT"
    INTEGER = "INTEGER"
    FLOAT = "REAL"
    BOOLEAN = "INTEGER"  # SQLite doesn't have BOOLEAN, use INTEGER
    DATETIME = "TEXT"    # Store as ISO format string

@dataclass
class FieldDefinition:
    """Definition of a field for storage and change tracking."""
    name: str
    field_type: FieldType
    nullable: bool = True
    default_value: Any = None
    description: str = ""
    
    def get_sql_type(self) -> str:
        """Get SQL type for this field."""
        return self.field_type.value
    
    def format_for_storage(self, value: Any) -> Any:
        """Format value for storage in database."""
        if value is None:
            return None
        
        if self.field_type is FieldType.BOOLEAN:
            return 1 if value else 0
        elif self.field_type is FieldType.DATETIME:
            if hasattr(value, 'isoformat'):
                return value.isoformat()
            return str(value)
        elif self.field_type is FieldType.STRING:
            return str(value)
        elif self.field_type is FieldType.INTEGER:
            return int(value) if value is not None else None
        elif self.field_type is FieldType.FLOAT:
            return float(value) if value is not None else None
        
        return value
    
    def format_for_comparison(self, value: Any) -> Any:
        """Format value for change detection comparison."""
        if value is None:
            return None
        
        if self.field_type is FieldType.BOOLEAN:
            return bool(value)
        elif self.field_type is FieldType.INTEGER:
            return int(value) if value is not None else None
        elif self.field_type is FieldType.FLOAT:
            return float(value) if value is not None else None
        
        return str(value) if value is not None else None

class AirportFields:
    """Centralized definition of airport fields."""
    
    # Core fields
    ICAO_CODE = FieldDefinition("icao_code", FieldType.STRING, nullable=False, description="ICAO airport code")
    NAME = FieldDefinition("name", FieldType.STRING, description="Airport name")
    TYPE = FieldDefinition("type", FieldType.STRING, description="Airport type")
    LATITUDE_DEG = FieldDefinition("latitude_deg", FieldType.FLOAT, description="Latitude in degrees")
    LONGITUDE_DEG = FieldDefinition("longitude_deg", FieldType.FLOAT, description="Longitude in degrees")
    ELEVATION_FT = FieldDefinition("elevation_ft", FieldType.FLOAT, description="Elevation in feet")
    
    # Geographic fields
    CONTINENT = FieldDefinition("continent", FieldType.STRING, description="Continent code")
    ISO_COUNTRY = FieldDefinition("iso_country", FieldType.STRING, description="ISO country code")
    ISO_REGION = FieldDefinition("iso_region", FieldType.STRING, description="ISO region code")
    MUNICIPALITY = FieldDefinition("municipality", FieldType.STRING, description="Municipality/city")
    
    # Service fields
    SCHEDULED_SERVICE = FieldDefinition("scheduled_service", FieldType.STRING, description="Scheduled service status")
    
    # Codes
    GPS_CODE = FieldDefinition("gps_code", FieldType.STRING, description="GPS code")
    IATA_CODE = FieldDefinition("iata_code", FieldType.STRING, description="IATA code")
    LOCAL_CODE = FieldDefinition("local_code", FieldType.STRING, description="Local code")
    
    # Links
    HOME_LINK = FieldDefinition("home_link", FieldType.STRING, description="Home page URL")
    WIKIPEDIA_LINK = FieldDefinition("wikipedia_link", FieldType.STRING, description="Wikipedia URL")
    KEYWORDS = FieldDefinition("keywords", FieldType.STRING, description="Keywords")
    
    # Metadata
    SOURCES = FieldDefinition("sources", FieldType.STRING, description="Comma-separated list of sources")
    CREATED_AT = FieldDefinition("created_at", FieldType.DATETIME, description="Creation timestamp")
    UPDATED_AT = FieldDefinition("updated_at", FieldType.DATETIME, description="Last update timestamp")
    
    # New fields can be easily added here
    # WEATHER_STATION = FieldDefinition("weather_station", FieldType.STRING, description="Weather station code")
    # TIMEZONE = FieldDefinition("timezone", FieldType.STRING, description="Timezone")
    # MAGNETIC_VARIATION = FieldDefinition("magnetic_variation", FieldType.FLOAT, description="Magnetic variation in degrees")
    
    @classmethod
    def get_all_fields(cls) -> List[FieldDefinition]:
        """Get all field definitions."""
        return [
            cls.ICAO_CODE, cls.NAME, cls.TYPE, cls.LATITUDE_DEG, cls.LONGITUDE_DEG, cls.ELEVATION_FT,
            cls.CONTINENT, cls.ISO_COUNTRY, cls.ISO_REGION, cls.MUNICIPALITY, cls.SCHEDULED_SERVICE,
            cls.GPS_CODE, cls.IATA_CODE, cls.LOCAL_CODE, cls.HOME_LINK, cls.WIKIPEDIA_LINK, cls.KEYWORDS,
            cls.SOURCES, cls.CREATED_AT, cls.UPDATED_AT
        ]
    
    @classmethod
    def get_change_tracked_fields(cls) -> List[FieldDefinition]:
        """Get fields that should be tracked for changes (excludes metadata fields)."""
        return [
            cls.NAME, cls.TYPE, cls.LATITUDE_DEG, cls.LONGITUDE_DEG, cls.ELEVATION_FT,
            cls.CONTINENT, cls.ISO_COUNTRY, cls.ISO_REGION, cls.MUNICIPALITY, cls.SCHEDULED_SERVICE,
            cls.GPS_CODE, cls.IATA_CODE, cls.LOCAL_CODE, cls.HOME_LINK, cls.WIKIPEDIA_LINK, cls.KEYWORDS
        ]
    
    @classmethod
    def get_field_by_name(cls, name: str) -> Optional[FieldDefinition]:
        """Get field definition by name."""
        for field in cls.get_all_fields():
            if field.name == name:
                return field
        return None

class RunwayFields:
    """Centralized definition of runway fields."""
    
    # Identifiers
    AIRPORT_ICAO = FieldDefinition("airport_icao", FieldType.STRING, nullable=False, description="Airport ICAO code")
    LE_IDENT = FieldDefinition("le_ident", FieldType.STRING, description="Lower end identifier")
    HE_IDENT = FieldDefinition("he_ident", FieldType.STRING, description="Higher end identifier")
    
    # Physical properties
    LENGTH_FT = FieldDefinition("length_ft", FieldType.FLOAT, description="Length in feet")
    WIDTH_FT = FieldDefinition("width_ft", FieldType.FLOAT, description="Width in feet")
    SURFACE = FieldDefinition("surface", FieldType.STRING, description="Surface type")
    LIGHTED = FieldDefinition("lighted", FieldType.BOOLEAN, description="Lighting status")
    CLOSED = FieldDefinition("closed", FieldType.BOOLEAN, description="Closure status")
    
    # Lower end coordinates
    LE_LATITUDE_DEG = FieldDefinition("le_latitude_deg", FieldType.FLOAT, description="Lower end latitude")
    LE_LONGITUDE_DEG = FieldDefinition("le_longitude_deg", FieldType.FLOAT, description="Lower end longitude")
    LE_ELEVATION_FT = FieldDefinition("le_elevation_ft", FieldType.FLOAT, description="Lower end elevation")
    LE_HEADING_DEGT = FieldDefinition("le_heading_degT", FieldType.FLOAT, description="Lower end heading")
    LE_DISPLACED_THRESHOLD_FT = FieldDefinition("le_displaced_threshold_ft", FieldType.FLOAT, description="Lower end displaced threshold")
    
    # Higher end coordinates
    HE_LATITUDE_DEG = FieldDefinition("he_latitude_deg", FieldType.FLOAT, description="Higher end latitude")
    HE_LONGITUDE_DEG = FieldDefinition("he_longitude_deg", FieldType.FLOAT, description="Higher end longitude")
    HE_ELEVATION_FT = FieldDefinition("he_elevation_ft", FieldType.FLOAT, description="Higher end elevation")
    HE_HEADING_DEGT = FieldDefinition("he_heading_degT", FieldType.FLOAT, description="Higher end heading")
    HE_DISPLACED_THRESHOLD_FT = FieldDefinition("he_displaced_threshold_ft", FieldType.FLOAT, description="Higher end displaced threshold")
    
    # Metadata
    CREATED_AT = FieldDefinition("created_at", FieldType.DATETIME, description="Creation timestamp")
    UPDATED_AT = FieldDefinition("updated_at", FieldType.DATETIME, description="Last update timestamp")
    
    @classmethod
    def get_all_fields(cls) -> List[FieldDefinition]:
        """Get all field definitions."""
        return [
            cls.AIRPORT_ICAO, cls.LE_IDENT, cls.HE_IDENT, cls.LENGTH_FT, cls.WIDTH_FT, cls.SURFACE,
            cls.LIGHTED, cls.CLOSED, cls.LE_LATITUDE_DEG, cls.LE_LONGITUDE_DEG, cls.LE_ELEVATION_FT,
            cls.LE_HEADING_DEGT, cls.LE_DISPLACED_THRESHOLD_FT, cls.HE_LATITUDE_DEG, cls.HE_LONGITUDE_DEG,
            cls.HE_ELEVATION_FT, cls.HE_HEADING_DEGT, cls.HE_DISPLACED_THRESHOLD_FT,
            cls.CREATED_AT, cls.UPDATED_AT
        ]
    
    @classmethod
    def get_change_tracked_fields(cls) -> List[FieldDefinition]:
        """Get fields that should be tracked for changes."""
        return [
            cls.LENGTH_FT, cls.WIDTH_FT, cls.SURFACE, cls.LIGHTED, cls.CLOSED,
            cls.LE_LATITUDE_DEG, cls.LE_LONGITUDE_DEG, cls.LE_ELEVATION_FT, cls.LE_HEADING_DEGT, cls.LE_DISPLACED_THRESHOLD_FT,
            cls.HE_LATITUDE_DEG, cls.HE_LONGITUDE_DEG, cls.HE_ELEVATION_FT, cls.HE_HEADING_DEGT, cls.HE_DISPLACED_THRESHOLD_FT
        ]

class SchemaManager:
    """Manages database schema and migrations."""
    
    def __init__(self):
        self.version = 1  # Current schema version
    
    def get_create_table_sql(self, table_name: str, fields: List[FieldDefinition], primary_key: str = None) -> str:
        """Generate CREATE TABLE SQL from field definitions."""
        field_definitions = []
        
        for field in fields:
            field_sql = f"{field.name} {field.get_sql_type()}"
            if not field.nullable:
                field_sql += " NOT NULL"
            if field.default_value is not None:
                if field.field_type == FieldType.STRING:
                    field_sql += f" DEFAULT '{field.default_value}'"
                else:
                    field_sql += f" DEFAULT {field.default_value}"
            field_definitions.append(field_sql)
        
        if primary_key:
            field_definitions.append(f"PRIMARY KEY ({primary_key})")
        
        return f"CREATE TABLE {table_name} (\n    " + ",\n    ".join(field_definitions) + "\n)"
    
    def get_alter_table_sql(self, table_name: str, field: FieldDefinition) -> str:
        """Generate ALTER TABLE SQL to add a new field."""
        return f"ALTER TABLE {table_name} ADD COLUMN {field.name} {field.get_sql_type()}"
    
    def migrate_schema(self, conn, current_version: int) -> int:
        """Migrate schema from current version to latest version."""
        if current_version < 1:
            # Add new fields in future migrations
            # Example: Add weather_station field
            # weather_field = AirportFields.WEATHER_STATION
            # conn.execute(self.get_alter_table_sql("airports", weather_field))
            pass
        
        return self.version 