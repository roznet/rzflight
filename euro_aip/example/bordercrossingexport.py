#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from euro_aip.sources import WorldAirportsSource, DatabaseSource
from euro_aip.sources.border_crossing import BorderCrossingSource
from euro_aip.models import EuroAipModel
from euro_aip.sources.base import SourceInterface
from euro_aip.storage import DatabaseStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BorderCrossingModelBuilder:
    """Builds EuroAipModel with border crossing data."""
    
    def __init__(self, args):
        """Initialize the model builder with configuration."""
        self.args = args
        self.cache_dir = Path(args.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize base model source
        self.base_source = None
        self._initialize_base_source()
        
        # Initialize border crossing source
        self.border_crossing_source = None
        self._initialize_border_crossing_source()
    
    def _initialize_base_source(self):
        """Initialize the base source for airport data."""
        if self.args.database:
            # Load from existing database
            logger.info(f"Loading base model from database: {self.args.database}")
            storage = DatabaseStorage(self.args.database)
            self.base_model = storage.load_model()
            logger.info(f"Loaded {len(self.base_model.airports)} airports from database")
            
        elif self.args.worldairports:
            # Build from WorldAirports source
            logger.info("Building base model from WorldAirports source")
            self.base_source = WorldAirportsSource(
                cache_dir=str(self.cache_dir),
                database=self.args.worldairports_db or 'airports.db'
            )
            
            # Configure refresh behavior
            if self.args.force_refresh:
                self.base_source.set_force_refresh()
            if self.args.never_refresh:
                self.base_source.set_never_refresh()
            
            # Create empty model to be populated
            self.base_model = EuroAipModel()
            
        else:
            raise ValueError("Either --database or --worldairports must be specified")
    
    def _initialize_border_crossing_source(self):
        """Initialize the border crossing source."""
        if self.args.border_crossing_files:
            # Use custom files
            inputs = []
            for file_path in self.args.border_crossing_files:
                # Generate name from filename
                name = Path(file_path).stem
                inputs.append((name, file_path))
            logger.info(f"Using custom border crossing files: {[name for name, _ in inputs]}")
        else:
            # Use default URLs (empty list will use defaults from BorderCrossingSource)
            inputs = []
            logger.info("Using default border crossing URLs")
        
        self.border_crossing_source = BorderCrossingSource(
            cache_dir=str(self.cache_dir),
            inputs=inputs
        )
        
        # Configure refresh behavior
        if self.args.force_refresh:
            self.border_crossing_source.set_force_refresh()
        if self.args.never_refresh:
            self.border_crossing_source.set_never_refresh()
    
    def build_model(self) -> EuroAipModel:
        """Build EuroAipModel with border crossing data."""
        
        # Step 1: Build/load base model
        if self.base_source:
            # Build from WorldAirports source
            logger.info("Building base model from WorldAirports")
            
            if self.args.airports:
                # Use specified airports
                self.base_source.update_model(self.base_model, self.args.airports)
                logger.info(f"Updated base model with {len(self.args.airports)} specified airports")
            else:
                # Get all European airports
                european_airports = self._get_european_airports()
                if european_airports:
                    self.base_source.update_model(self.base_model, european_airports)
                    logger.info(f"Updated base model with {len(european_airports)} European airports")
                else:
                    logger.warning("No European airports found in WorldAirports")
        
        # Step 2: Filter to specific airports if provided
        if self.args.airports and self.base_model.airports:
            filtered_model = EuroAipModel()
            for airport_code in self.args.airports:
                if airport_code in self.base_model.airports:
                    filtered_model.airports[airport_code] = self.base_model.airports[airport_code]
                else:
                    logger.warning(f"Airport {airport_code} not found in base model")
            self.base_model = filtered_model
        
        # Step 3: Update with border crossing data
        if self.border_crossing_source:
            logger.info("Updating model with border crossing data")
            self.border_crossing_source.update_model(self.base_model)
        
        logger.info(f"Final model contains {len(self.base_model.airports)} airports")
        return self.base_model
    
    def _get_european_airports(self) -> List[str]:
        """Get list of European airports from WorldAirports source."""
        try:
            airports_df = self.base_source.get_airports()
            european_airports = airports_df[
                (airports_df['continent'] == 'EU') & 
                (~airports_df['type'].isin(['heliport', 'closed']))
            ]['ident'].tolist()
            return european_airports
        except Exception as e:
            logger.error(f"Error getting European airports from WorldAirports: {e}")
            return []
    
    def get_all_airports(self) -> List[str]:
        """Get list of all available airports from base source."""
        if self.base_source and hasattr(self.base_source, 'get_airports'):
            try:
                airports_df = self.base_source.get_airports()
                airports = airports_df['ident'].tolist()
                logger.info(f"Found {len(airports)} airports in base source")
                return airports
            except Exception as e:
                logger.warning(f"Error getting airports from base source: {e}")
        
        elif hasattr(self, 'base_model'):
            airports = list(self.base_model.airports.keys())
            logger.info(f"Found {len(airports)} airports in base model")
            return airports
        
        return []

class BorderCrossingExporter:
    """Main exporter class for border crossing data."""
    
    def __init__(self, args):
        """Initialize the exporter."""
        self.args = args
        self.model_builder = BorderCrossingModelBuilder(args)
        self.exporters = {}
        
        # Initialize exporters based on output format
        if self.args.database_storage:
            self.exporters['database_storage'] = DatabaseStorage(
                self.args.database_storage,
                save_only_std_fields=self.args.save_all_fields
            )
        
        if self.args.json:
            self.exporters['json'] = JSONExporter(self.args.json)
    
    def run(self):
        """Run the export process."""
        # Get airports to export
        if self.args.airports:
            airports = self.args.airports
            logger.info(f"Using specified airports: {airports}")
        else:
            airports = self.model_builder.get_all_airports()
            logger.info(f"Using all available airports: {len(airports)} found")
        
        if not airports:
            logger.warning("No airports found, but proceeding with export (border crossing data may not be matched)")
        
        logger.info(f"Building model for airports: {airports if airports else 'all available'}")
        
        # Build the model
        model = self.model_builder.build_model()
        
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

def main():
    parser = argparse.ArgumentParser(description='Border Crossing Data Export Tool')
    
    # Border crossing files (positional arguments)
    parser.add_argument('border_crossing_files', help='List of border crossing HTML files to parse (or use defaults if empty)', nargs='*')
    
    # Base source configuration (mutually exclusive)
    base_group = parser.add_mutually_exclusive_group(required=True)
    base_group.add_argument('--database', help='Load base model from existing database file')
    base_group.add_argument('--worldairports', help='Build base model from WorldAirports source', action='store_true')
    
    parser.add_argument('--worldairports-db', help='WorldAirports database file', default='airports.db')
    
    # Airport filtering (optional)
    parser.add_argument('--airports', help='List of ICAO airport codes to filter (or all if not specified)', nargs='+')
    
    # Output configuration
    parser.add_argument('--database-storage', help='Database storage file with change tracking')
    parser.add_argument('--json', help='JSON output file')
    parser.add_argument('--save-all-fields', help='Save all AIP fields (not just standardized ones)', action='store_true')
    
    # General options
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('--force-refresh', help='Force refresh of cached data', action='store_true')
    parser.add_argument('--never-refresh', help='Never refresh cached data if it exists', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate that at least one output format is specified
    outputs_enabled = any([
        args.database_storage, args.json
    ])
    
    if not outputs_enabled:
        logger.error("At least one output format must be specified")
        return
    
    exporter = BorderCrossingExporter(args)
    exporter.run()

if __name__ == '__main__':
    main() 