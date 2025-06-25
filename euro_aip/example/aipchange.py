#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Set
from pprint import pprint
from collections import defaultdict
from euro_aip.sources import AutorouterSource, FranceEAIPSource, UKEAIPSource, WorldAirportsSource, PointDePassageJournalOfficiel, DatabaseSource
from euro_aip.parsers import AIPParserFactory
from euro_aip.utils.field_mapper import FieldMapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AIPChangeDetector:
    """Detect changes in AIP data between different sources."""
    
    def __init__(self, args):
        """
        Initialize the change detector.
        
        Args:
            args: Command line arguments
        """
        self.args = args
        self.cache_dir = Path(args.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.field_mapper = FieldMapper()
        
        # Initialize sources
        self.source1 = self._create_source(args, 1)
        self.source2 = self._create_source(args, 2)
        
        if not self.source1 or not self.source2:
            logger.error("Failed to initialize sources")
            return
    
    def _create_source(self, args, source_num: int) -> Optional[Any]:
        """
        Create a source based on configuration.
        
        Args:
            args: Command line arguments
            source_num: Source number (1 or 2)
            
        Returns:
            Initialized source or None if failed
        """
        source_type = getattr(args, f'source{source_num}', None)
        if not source_type:
            logger.error(f"Source {source_num} type not specified (--source{source_num})")
            return None
        
        # Get source-specific arguments
        root_dir = getattr(args, f'root_dir{source_num}', None)
        username = getattr(args, f'username{source_num}', None)
        password = getattr(args, f'password{source_num}', None)
        database = getattr(args, f'database{source_num}', None)
        journal_path = getattr(args, f'journal_path{source_num}', None)
        
        # Get refresh behavior for this source
        force_refresh = getattr(args, f'force_refresh{source_num}', False)
        never_refresh = getattr(args, f'never_refresh{source_num}', False)
        
        try:
            if source_type == 'france_eaip':
                if not root_dir:
                    logger.error(f"Source {source_num} (france_eaip) requires --root-dir{source_num}")
                    return None
                source = FranceEAIPSource(
                    cache_dir=str(self.cache_dir),
                    root_dir=root_dir
                )
                
            elif source_type == 'uk_eaip':
                if not root_dir:
                    logger.error(f"Source {source_num} (uk_eaip) requires --root-dir{source_num}")
                    return None
                source = UKEAIPSource(
                    cache_dir=str(self.cache_dir),
                    root_dir=root_dir
                )
                
            elif source_type == 'autorouter':
                source = AutorouterSource(
                    cache_dir=str(self.cache_dir),
                    username=username,
                    password=password
                )
                
            elif source_type == 'worldairports':
                source = WorldAirportsSource(
                    cache_dir=str(self.cache_dir),
                    database=database or 'airports.db'
                )
                
            elif source_type == 'pointdepassage':
                if not journal_path:
                    logger.error(f"Source {source_num} (pointdepassage) requires --journal-path{source_num}")
                    return None
                database_source = DatabaseSource(database or 'airports.db')
                source = PointDePassageJournalOfficiel(
                    pdf_path=journal_path,
                    database_source=database_source
                )
                
            else:
                logger.error(f"Unknown source type: {source_type}")
                return None
            
            # Configure refresh behavior
            if force_refresh:
                source.set_force_refresh()
            if never_refresh:
                source.set_never_refresh()
            
            logger.info(f"Initialized source {source_num}: {source_type}")
            return source
            
        except Exception as e:
            logger.error(f"Error initializing source {source_num} ({source_type}): {e}")
            return None
    
    def _get_source_name(self, source_num: int) -> str:
        """Get the name of a source for display purposes."""
        source_type = getattr(self.args, f'source{source_num}', f'source{source_num}')
        return source_type
    
    def _normalize_value(self, value: str) -> str:
        """
        Normalize a value for comparison by removing extra whitespace and converting to lowercase.
        
        Args:
            value: Value to normalize
            
        Returns:
            Normalized value
        """
        if not value:
            return ""
        return value.strip().lower()
    
    def _extract_field_data(self, aip_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract field data from AIP parsing result and standardize fields.
        
        Args:
            aip_data: AIP data from source
            
        Returns:
            Dictionary mapping standardized field names to values
        """
        field_data = {}
        
        if not aip_data or 'parsed_data' not in aip_data:
            return field_data
        
        for item in aip_data['parsed_data']:
            field_name = item.get('field', '')
            value = item.get('value', '')
            
            if not field_name:
                continue
            
            # Map field to standard field
            mapping = self.field_mapper.map_field(field_name)
            if 'Customs' in field_name:
                mapping = self.field_mapper.map_field(field_name)
            
            if mapping['mapped']:
                standardized_field = mapping['mapped_field_name']
                field_data[standardized_field] = self._normalize_value(value)
        
        return field_data
    
    def _get_airport_data(self, source, airport: str, source_name: str) -> Optional[Dict[str, Any]]:
        """
        Get airport data from a source.
        
        Args:
            source: Source object
            airport: ICAO airport code
            source_name: Name of the source for logging
            
        Returns:
            Airport data or None if not found
        """
        try:
            # Different sources have different methods
            if hasattr(source, 'get_airport_aip'):
                data = source.get_airport_aip(airport)
            elif hasattr(source, 'get_airport_data'):
                data = source.get_airport_data(airport)
            else:
                logger.warning(f"Source {source_name} doesn't have airport data method")
                return None
            
            if data:
                logger.debug(f"Found {source_name} data for {airport}: {len(data.get('parsed_data', []))} items")
            else:
                logger.warning(f"No {source_name} data found for {airport}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error getting {source_name} data for {airport}: {e}")
            return None
    
    def _compare_airport_data(self, airport: str) -> Dict[str, Any]:
        """
        Compare AIP data for a single airport between two sources.
        
        Args:
            airport: ICAO airport code
            
        Returns:
            Dictionary with comparison results
        """
        source1_name = self._get_source_name(1)
        source2_name = self._get_source_name(2)
        
        logger.info(f"Comparing data for {airport} ({source1_name} vs {source2_name})")
        
        # Get data from both sources
        source1_data = self._get_airport_data(self.source1, airport, source1_name)
        source2_data = self._get_airport_data(self.source2, airport, source2_name)
        
        # Extract and standardize field data
        source1_fields = self._extract_field_data(source1_data) if source1_data else {}
        source2_fields = self._extract_field_data(source2_data) if source2_data else {}
        
        # Find common fields
        all_fields = set(source1_fields.keys()) | set(source2_fields.keys())
        common_fields = set(source1_fields.keys()) & set(source2_fields.keys())
        
        # Filter fields if specified
        if self.args.fields:
            field_filter = set(self.args.fields)
            common_fields = common_fields & field_filter
            all_fields = all_fields & field_filter
        
        # Compare values
        changes = []
        missing_in_source1 = []
        missing_in_source2 = []
        
        for field in all_fields:
            source1_value = source1_fields.get(field, "")
            source2_value = source2_fields.get(field, "")
            
            if field in common_fields:
                if source1_value != source2_value:
                    changes.append({
                        'field': field,
                        f'{source1_name}_value': source1_value,
                        f'{source2_name}_value': source2_value
                    })
            elif field in source1_fields:
                missing_in_source2.append(field)
            else:
                missing_in_source1.append(field)
        
        return {
            'airport': airport,
            'changes': changes,
            f'missing_in_{source1_name}': missing_in_source1,
            f'missing_in_{source2_name}': missing_in_source2,
            f'total_fields_{source1_name}': len(source1_fields),
            f'total_fields_{source2_name}': len(source2_fields),
            'common_fields': len(common_fields)
        }
    
    def _get_available_airports(self) -> List[str]:
        """
        Get available airports from the first source that supports it.
        
        Returns:
            List of available airport codes
        """
        # Try source1 first, then source2
        for source_num, source in [(1, self.source1), (2, self.source2)]:
            if hasattr(source, 'find_available_airports'):
                try:
                    airports = source.find_available_airports()
                    source_name = self._get_source_name(source_num)
                    logger.info(f"Found {len(airports)} airports in {source_name}")
                    return airports
                except Exception as e:
                    logger.warning(f"Error getting airports from source {source_num}: {e}")
        
        logger.warning("Neither source supports find_available_airports, using empty list")
        return []
    
    def run_comparison(self):
        """Run the comparison between two sources."""
        if not self.source1 or not self.source2:
            logger.error("Both sources must be properly initialized")
            return
        
        source1_name = self._get_source_name(1)
        source2_name = self._get_source_name(2)
        
        logger.info(f"Starting AIP change detection")
        logger.info(f"Source 1: {source1_name}")
        logger.info(f"Source 2: {source2_name}")
        logger.info(f"Field filter: {self.args.fields if self.args.fields else 'All fields'}")
        
        # Get airports to compare
        if self.args.airports:
            airports = self.args.airports
        else:
            # Get all available airports from sources
            airports = self._get_available_airports()
        
        if not airports:
            logger.error("No airports to compare")
            return
        
        # Compare each airport
        all_changes = []
        summary = {
            'total_airports': len(airports),
            'airports_with_changes': 0,
            'total_changes': 0,
            f'airports_missing_{source1_name}': 0,
            f'airports_missing_{source2_name}': 0
        }
        
        for airport in airports:
            airport = airport.strip()
            result = self._compare_airport_data(airport)
            
            if result['changes']:
                all_changes.append(result)
                summary['airports_with_changes'] += 1
                summary['total_changes'] += len(result['changes'])
                
                logger.info(f"Changes found in {airport}: {len(result['changes'])} field(s) changed")
                
                for change in result['changes']:
                    logger.info(f"  {source1_name}.{change['field']}: '{change[f'{source1_name}_value']}'")
                    logger.info(f"  {source2_name}.{change['field']}: '{change[f'{source2_name}_value']}'")
            
            if result[f'missing_in_{source1_name}']:
                summary[f'airports_missing_{source1_name}'] += 1
                if self.args.verbose:
                    logger.info(f"  Missing in {source1_name}: {result[f'missing_in_{source1_name}']}")
            
            if result[f'missing_in_{source2_name}']:
                summary[f'airports_missing_{source2_name}'] += 1
                if self.args.verbose:
                    logger.info(f"  Missing in {source2_name}: {result[f'missing_in_{source2_name}']}")
        
        # Print summary
        logger.info("=" * 80)
        logger.info("AIP CHANGE DETECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total airports processed: {summary['total_airports']}")
        logger.info(f"Airports with changes: {summary['airports_with_changes']}")
        logger.info(f"Total field changes: {summary['total_changes']}")
        logger.info(f"Airports missing {source1_name} data: {summary[f'airports_missing_{source1_name}']}")
        logger.info(f"Airports missing {source2_name} data: {summary[f'airports_missing_{source2_name}']}")
        
        # Print detailed changes
        if all_changes:
            logger.info("\nDETAILED CHANGES:")
            logger.info("=" * 80)
            
            # Group changes by field
            field_changes = defaultdict(list)
            for result in all_changes:
                for change in result['changes']:
                    field_changes[change['field']].append({
                        'airport': result['airport'],
                        f'{source1_name}_value': change[f'{source1_name}_value'],
                        f'{source2_name}_value': change[f'{source2_name}_value']
                    })
            
            for field, changes in sorted(field_changes.items()):
                logger.info(f"\nField: {field} ({len(changes)} changes)")
                for change in changes:
                    logger.info(f"  {change['airport']}: '{change[f'{source1_name}_value']}' -> '{change[f'{source2_name}_value']}'")
        
        # Save results to file if requested
        if self.args.output:
            self._save_results(all_changes, summary, source1_name, source2_name)
    
    def _save_results(self, changes: List[Dict], summary: Dict, source1_name: str, source2_name: str):
        """Save comparison results to a file."""
        import json
        
        output_data = {
            'summary': summary,
            'changes': changes,
            'source1': source1_name,
            'source2': source2_name,
            'timestamp': str(Path().cwd()),
            'field_filter': self.args.fields
        }
        
        try:
            with open(self.args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {self.args.output}")
        except Exception as e:
            logger.error(f"Error saving results to {self.args.output}: {e}")

def add_source_arguments(parser: argparse.ArgumentParser, source_num: int):
    """
    Add arguments for a specific source.
    
    Args:
        parser: Argument parser
        source_num: Source number (1 or 2)
    """
    group = parser.add_argument_group(f'Source {source_num} Configuration')
    
    group.add_argument(f'--source{source_num}', 
                      help=f'Type of source {source_num}',
                      choices=['france_eaip', 'uk_eaip', 'autorouter', 'worldairports', 'pointdepassage'],
                      required=True)
    
    group.add_argument(f'--root-dir{source_num}', 
                      help=f'Root directory for source {source_num} (for france_eaip, uk_eaip)')
    
    group.add_argument(f'--username{source_num}', 
                      help=f'Username for source {source_num} (for autorouter)')
    
    group.add_argument(f'--password{source_num}', 
                      help=f'Password for source {source_num} (for autorouter)')
    
    group.add_argument(f'--database{source_num}', 
                      help=f'Database file for source {source_num} (for worldairports, pointdepassage)')
    
    group.add_argument(f'--journal-path{source_num}', 
                      help=f'Journal PDF path for source {source_num} (for pointdepassage)')
    
    group.add_argument(f'--force-refresh{source_num}', 
                      help=f'Force refresh cached data for source {source_num}',
                      action='store_true')
    
    group.add_argument(f'--never-refresh{source_num}', 
                      help=f'Never refresh cached data for source {source_num}',
                      action='store_true')

def main():
    parser = argparse.ArgumentParser(description='AIP Change Detection Tool')
    parser.add_argument('airports', help='List of ICAO airport codes to compare (or all if empty)', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-f', '--fields', help='Comma-separated list of fields to compare (default: all fields)', nargs='*')
    parser.add_argument('-o', '--output', help='Output file to save results (JSON format)')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    
    # Add arguments for both sources
    add_source_arguments(parser, 1)
    add_source_arguments(parser, 2)
    
    args = parser.parse_args()
    
    # Convert fields list to individual field names
    if args.fields:
        field_list = []
        for field_group in args.fields:
            field_list.extend([f.strip() for f in field_group.split(',')])
        args.fields = field_list
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    detector = AIPChangeDetector(args)
    detector.run_comparison()

if __name__ == '__main__':
    main()

