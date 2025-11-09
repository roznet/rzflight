"""
Database schema for airfield.directory enrichment data.

This module defines the SQL schema for storing operational data, pricing,
pilot reviews, and fuel availability from airfield.directory.
"""

# Schema version for tracking migrations
SCHEMA_VERSION = "1.0.0"

# SQL for creating enrichment tables
CREATE_PRICING_DATA_TABLE = """
CREATE TABLE IF NOT EXISTS pricing_data (
    icao_code TEXT PRIMARY KEY,
    landing_fee_c172 REAL,
    landing_fee_da42 REAL,
    landing_fee_pc12 REAL,
    landing_fee_sr22 REAL,
    avgas_price REAL,
    jeta1_price REAL,
    superplus_price REAL,
    currency TEXT,
    fuel_provider TEXT,
    payment_available INTEGER,  -- SQLite uses INTEGER for BOOLEAN
    ppr_available INTEGER,
    last_updated TEXT,
    source TEXT DEFAULT 'airfield.directory',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (icao_code) REFERENCES airports(icao_code)
);
"""

CREATE_OPERATIONAL_FEATURES_TABLE = """
CREATE TABLE IF NOT EXISTS operational_features (
    icao_code TEXT PRIMARY KEY,
    ppr_required INTEGER,
    is_private INTEGER,
    ifr_capable INTEGER,
    runway_pcn TEXT,
    runway_condition TEXT,
    avg_community_rating REAL,
    openaip_id TEXT,
    last_updated TEXT,
    source TEXT DEFAULT 'airfield.directory',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (icao_code) REFERENCES airports(icao_code)
);
"""

CREATE_PILOT_REVIEWS_TABLE = """
CREATE TABLE IF NOT EXISTS pilot_reviews (
    review_id TEXT PRIMARY KEY,
    icao_code TEXT NOT NULL,
    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
    comment_en TEXT,
    comment_de TEXT,
    comment_fr TEXT,
    comment_it TEXT,
    comment_es TEXT,
    comment_nl TEXT,
    author_name TEXT,
    author_hash TEXT,
    is_ai_generated INTEGER,
    created_at TEXT,
    updated_at TEXT,
    source TEXT DEFAULT 'airfield.directory',
    FOREIGN KEY (icao_code) REFERENCES airports(icao_code)
);
"""

CREATE_FUEL_AVAILABILITY_TABLE = """
CREATE TABLE IF NOT EXISTS fuel_availability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    icao_code TEXT NOT NULL,
    fuel_type TEXT NOT NULL,
    available INTEGER,
    provider TEXT,
    last_updated TEXT,
    source TEXT DEFAULT 'airfield.directory',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (icao_code) REFERENCES airports(icao_code),
    UNIQUE(icao_code, fuel_type)
);
"""

# Indexes for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pricing_icao ON pricing_data(icao_code);",
    "CREATE INDEX IF NOT EXISTS idx_operational_icao ON operational_features(icao_code);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_icao ON pilot_reviews(icao_code);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_rating ON pilot_reviews(rating);",
    "CREATE INDEX IF NOT EXISTS idx_reviews_created ON pilot_reviews(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_fuel_icao ON fuel_availability(icao_code);",
]

# All tables in order
ALL_TABLES = [
    CREATE_PRICING_DATA_TABLE,
    CREATE_OPERATIONAL_FEATURES_TABLE,
    CREATE_PILOT_REVIEWS_TABLE,
    CREATE_FUEL_AVAILABILITY_TABLE,
]


def get_schema_sql() -> str:
    """
    Get complete SQL for creating all enrichment tables and indexes.

    Returns:
        str: SQL statements for schema creation
    """
    sql_statements = ALL_TABLES + CREATE_INDEXES
    return "\n\n".join(sql_statements)
