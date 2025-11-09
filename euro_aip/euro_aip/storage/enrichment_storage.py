"""
Storage layer for airfield.directory enrichment data.

This module provides methods for storing and retrieving operational data,
pricing, pilot reviews, and fuel availability from airfield.directory.
"""
import sqlite3
from typing import Dict, List, Optional
from contextlib import contextmanager
from datetime import datetime

from .enrichment_schema import (
    get_schema_sql,
    SCHEMA_VERSION,
)


class EnrichmentStorage:
    """Storage manager for enrichment data from airfield.directory."""

    def __init__(self, db_path: str):
        """
        Initialize enrichment storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_tables(self) -> None:
        """
        Create all enrichment tables and indexes if they don't exist.
        This operation is idempotent.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Execute schema creation
            cursor.executescript(get_schema_sql())

            # Update schema version in metadata
            cursor.execute("""
                INSERT OR REPLACE INTO model_metadata (key, value, updated_at)
                VALUES ('enrichment_schema_version', ?, ?)
            """, (SCHEMA_VERSION, datetime.utcnow().isoformat()))

            conn.commit()

    def upsert_pricing_data(self, icao_code: str, data: Dict) -> None:
        """
        Insert or update pricing data for an airport.

        Args:
            icao_code: Airport ICAO code
            data: Dictionary containing pricing fields
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pricing_data (
                    icao_code,
                    landing_fee_c172,
                    landing_fee_da42,
                    landing_fee_pc12,
                    landing_fee_sr22,
                    avgas_price,
                    jeta1_price,
                    superplus_price,
                    currency,
                    fuel_provider,
                    payment_available,
                    ppr_available,
                    last_updated,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                icao_code,
                data.get('landing_fee_c172'),
                data.get('landing_fee_da42'),
                data.get('landing_fee_pc12'),
                data.get('landing_fee_sr22'),
                data.get('avgas_price'),
                data.get('jeta1_price'),
                data.get('superplus_price'),
                data.get('currency'),
                data.get('fuel_provider'),
                1 if data.get('payment_available') else 0,
                1 if data.get('ppr_available') else 0,
                data.get('last_updated', datetime.utcnow().isoformat()),
                data.get('source', 'airfield.directory')
            ))

    def upsert_operational_features(self, icao_code: str, data: Dict) -> None:
        """
        Insert or update operational features for an airport.

        Args:
            icao_code: Airport ICAO code
            data: Dictionary containing operational feature fields
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO operational_features (
                    icao_code,
                    ppr_required,
                    is_private,
                    ifr_capable,
                    runway_pcn,
                    runway_condition,
                    avg_community_rating,
                    openaip_id,
                    last_updated,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                icao_code,
                1 if data.get('ppr_required') else 0,
                1 if data.get('is_private') else 0,
                1 if data.get('ifr_capable') else 0,
                data.get('runway_pcn'),
                data.get('runway_condition'),
                data.get('avg_community_rating'),
                data.get('openaip_id'),
                data.get('last_updated', datetime.utcnow().isoformat()),
                data.get('source', 'airfield.directory')
            ))

    def insert_pilot_review(self, review_data: Dict) -> bool:
        """
        Insert a pilot review. Skips if review_id already exists.

        Args:
            review_data: Dictionary containing review fields

        Returns:
            bool: True if inserted, False if skipped (already exists)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO pilot_reviews (
                        review_id,
                        icao_code,
                        rating,
                        comment_en,
                        comment_de,
                        comment_fr,
                        comment_it,
                        comment_es,
                        comment_nl,
                        author_name,
                        author_hash,
                        is_ai_generated,
                        created_at,
                        updated_at,
                        source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    review_data.get('review_id'),
                    review_data.get('icao_code'),
                    review_data.get('rating'),
                    review_data.get('comment_en'),
                    review_data.get('comment_de'),
                    review_data.get('comment_fr'),
                    review_data.get('comment_it'),
                    review_data.get('comment_es'),
                    review_data.get('comment_nl'),
                    review_data.get('author_name'),
                    review_data.get('author_hash'),
                    1 if review_data.get('is_ai_generated') else 0,
                    review_data.get('created_at'),
                    review_data.get('updated_at'),
                    review_data.get('source', 'airfield.directory')
                ))
                return True
            except sqlite3.IntegrityError:
                # Review already exists, skip
                return False

    def upsert_fuel_availability(self, icao_code: str, fuel_type: str, data: Dict) -> None:
        """
        Insert or update fuel availability for an airport.

        Args:
            icao_code: Airport ICAO code
            fuel_type: Type of fuel (AVGAS, Jet A1, SuperPlus, etc.)
            data: Dictionary containing fuel availability fields
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO fuel_availability (
                    id,
                    icao_code,
                    fuel_type,
                    available,
                    provider,
                    last_updated,
                    source
                ) VALUES (
                    (SELECT id FROM fuel_availability WHERE icao_code = ? AND fuel_type = ?),
                    ?, ?, ?, ?, ?, ?
                )
            """, (
                icao_code, fuel_type,  # For SELECT
                icao_code,
                fuel_type,
                1 if data.get('available', True) else 0,
                data.get('provider'),
                data.get('last_updated', datetime.utcnow().isoformat()),
                data.get('source', 'airfield.directory')
            ))

    def get_pricing_data(self, icao_code: str) -> Optional[Dict]:
        """
        Get pricing data for an airport.

        Args:
            icao_code: Airport ICAO code

        Returns:
            Dictionary with pricing data or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pricing_data WHERE icao_code = ?", (icao_code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_operational_features(self, icao_code: str) -> Optional[Dict]:
        """
        Get operational features for an airport.

        Args:
            icao_code: Airport ICAO code

        Returns:
            Dictionary with operational features or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM operational_features WHERE icao_code = ?", (icao_code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_pilot_reviews(self, icao_code: str, limit: int = 10) -> List[Dict]:
        """
        Get pilot reviews for an airport.

        Args:
            icao_code: Airport ICAO code
            limit: Maximum number of reviews to return

        Returns:
            List of review dictionaries, sorted by created_at DESC
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pilot_reviews
                WHERE icao_code = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (icao_code, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_fuel_availability(self, icao_code: str) -> List[Dict]:
        """
        Get fuel availability for an airport.

        Args:
            icao_code: Airport ICAO code

        Returns:
            List of fuel availability dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM fuel_availability
                WHERE icao_code = ?
            """, (icao_code,))
            return [dict(row) for row in cursor.fetchall()]

    def get_enrichment_stats(self) -> Dict:
        """
        Get statistics about enrichment data coverage.

        Returns:
            Dictionary with counts for each enrichment table
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM pricing_data")
            pricing_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM operational_features")
            features_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM pilot_reviews")
            reviews_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT icao_code) FROM pilot_reviews")
            airports_with_reviews = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT icao_code) FROM fuel_availability")
            airports_with_fuel = cursor.fetchone()[0]

            return {
                'pricing_data_count': pricing_count,
                'operational_features_count': features_count,
                'pilot_reviews_count': reviews_count,
                'airports_with_reviews': airports_with_reviews,
                'airports_with_fuel': airports_with_fuel
            }
