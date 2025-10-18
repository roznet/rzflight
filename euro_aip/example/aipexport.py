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
    DatabaseSource, BorderCrossingSource
)
from euro_aip.sources.france_eaip_web import FranceEAIPWebSource
from euro_aip.sources.uk_eaip_web import UKEAIPWebSource
from euro_aip.models import EuroAipModel, Airport
from euro_aip.sources.base import SourceInterface
from euro_aip.utils.field_standardization_service import FieldStandardizationService
from euro_aip.storage import DatabaseStorage
from euro_aip.parsers import ProcedureParserFactory

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
        
        if getattr(self.args, 'france_web', False):
            self.sources['france_eaip_web'] = FranceEAIPWebSource(
                cache_dir=str(self.cache_dir),
                airac_date=self.args.airac_date
            )
        
        if getattr(self.args, 'uk_web', False):
            self.sources['uk_eaip_web'] = UKEAIPWebSource(
                cache_dir=str(self.cache_dir),
                airac_date=self.args.airac_date
            )
        
        if self.args.uk_eaip:
            self.sources['uk_eaip'] = UKEAIPSource(
                cache_dir=str(self.cache_dir),
                root_dir=self.args.uk_eaip
            )
        
        if self.args.autorouter:
            self.sources['autorouter'] = AutorouterSource(
                cache_dir=str(self.cache_dir),
                username=self.args.autorouter_username,
                password=self.args.autorouter_password
            )
        
        if self.args.pointdepassage:
            # Initialize border crossing source with CSV file if provided
            inputs = []
            if self.args.pointdepassage_journal:
                inputs.append(("airfield_map", self.args.pointdepassage_journal))
            
            self.sources['border_crossing'] = BorderCrossingSource(
                cache_dir=str(self.cache_dir),
                inputs=inputs if inputs else None
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
        
        # Prepare ordered sources: worldairports always last
        sources_items = list(self.sources.items())
        if 'worldairports' in self.sources:
            sources_items = [(k, v) for k, v in sources_items if k != 'worldairports'] + [
                ('worldairports', self.sources['worldairports'])
            ]
        
        for source_name, source in sources_items:
            try:
                logger.info(f"Updating model with {source_name} source")
                
                if isinstance(source, SourceInterface):
                    if source_name == 'worldairports':
                        self._update_model_with_worldairports(source, model, airports)
                    else:
                        source.update_model(model, airports)
                    logger.info(f"Updated model with {source_name}: {len(model.airports)} airports")
                else:
                    logger.warning(f"Source {source_name} doesn't implement SourceInterface, skipping")
            except Exception as e:
                logger.error(f"Error updating model with {source_name}: {e}")
        
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

    def _update_model_with_worldairports(self, source, model, airports):
        """Special update logic for WorldAirportsSource with filtering."""
        if self.args.worldairports_filter == 'required':
            existing_airports = list(model.airports.keys())
            if existing_airports:
                source.update_model(model, existing_airports)
                logger.info(f"Updated WorldAirports with {len(existing_airports)} existing airports")
            else:
                logger.warning("No existing airports in model, skipping WorldAirports default filter")
        elif self.args.worldairports_filter == 'europe':
            european_airports = self._get_european_airports(source)
            if european_airports:
                source.update_model(model, european_airports)
                logger.info(f"Updated WorldAirports with {len(european_airports)} European airports")
            else:
                logger.warning("No European airports found in WorldAirports")
        elif self.args.worldairports_filter == 'all':
            source.update_model(model, airports)
            logger.info(f"Updated WorldAirports with all airports")
        else:
            source.update_model(model, airports)
    
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
            # worldairports contains all airports in the world, so it's not useful to find available airports
            if source_name == 'worldairports' and self.args.worldairports_filter != 'all':
                continue
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


class JSONExporter:
    """Exports EuroAipModel to JSON file."""
    
    def __init__(self, json_path: str):
        """Initialize JSON exporter."""
        self.json_path = json_path
    
    def save_model(self, model: EuroAipModel):
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
        if self.args.database_storage:
            self.exporters['database_storage'] = DatabaseStorage(self.args.database_storage)
        
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
            #return
        
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
                exporter.save_model(model)
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
                       choices=['required', 'europe', 'all'], 
                       default='required',
                       help='WorldAirports filtering mode: required=only airports from other sources, europe=EU continent only, all=all airports')
    
    parser.add_argument('--france-eaip', help='France eAIP root directory')
    parser.add_argument('--france-web', help='Enable France eAIP web source (HTML index)', action='store_true')
    parser.add_argument('--uk-eaip', help='UK eAIP root directory')
    parser.add_argument('--uk-web', help='Enable UK eAIP web source (HTML index)', action='store_true')
    parser.add_argument('--airac-date', help='AIRAC effective date (YYYY-MM-DD) for web sources', required=False)
    
    parser.add_argument('--autorouter', help='Enable Autorouter source', action='store_true')
    parser.add_argument('--autorouter-username', help='Autorouter username')
    parser.add_argument('--autorouter-password', help='Autorouter password')
    
    parser.add_argument('--pointdepassage', help='Enable Point de Passage source', action='store_true')
    parser.add_argument('--pointdepassage-journal', help='Point de Passage journal PDF path')
    parser.add_argument('--pointdepassage-db', help='Point de Passage database file', default='airports.db')
    
    # Output configuration
    parser.add_argument('--database-storage', help='New unified database storage file with change tracking')
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
        args.worldairports, args.france_eaip, getattr(args, 'france_web', False), 
        args.uk_eaip, getattr(args, 'uk_web', False), args.autorouter, args.pointdepassage
    ])
    
    outputs_enabled = any([
        args.database_storage, args.json
    ])
    
    if not sources_enabled:
        logger.error("At least one data source must be enabled")
        return
    
    if not outputs_enabled:
        logger.error("At least one output format must be specified")
        return
    
    # Validate AIRAC date for web sources
    web_sources_enabled = getattr(args, 'france_web', False) or getattr(args, 'uk_web', False)
    if web_sources_enabled and not args.airac_date:
        logger.error("AIRAC date (--airac-date) is required when using web sources (--france-web or --uk-web)")
        return
    
    exporter = AIPExporter(args)
    exporter.run()

if __name__ == '__main__':
    main() 