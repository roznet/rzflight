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
        self.france_source = FranceEAIPSource(
            cache_dir=str(self.cache_dir),
            root_dir=args.root_dir
        )
        
        self.autorouter_source = AutorouterSource(
            cache_dir=str(self.cache_dir),
            username=args.username,
            password=args.password
        )
        
        # Configure refresh behavior
        if args.force_refresh:
            self.france_source.set_force_refresh()
            self.autorouter_source.set_force_refresh()
        if args.never_refresh:
            self.france_source.set_never_refresh()
            self.autorouter_source.set_never_refresh()
    
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
            
            if not field_name or not value:
                continue
            
            # Map field to standard field
            mapping = self.field_mapper.map_field(field_name, item.get('section'))
            
            if mapping['mapped']:
                standardized_field = mapping['mapped_field_name']
                field_data[standardized_field] = self._normalize_value(value)
            else:
                # Keep original field name if not mapped
                field_data[field_name] = self._normalize_value(value)
        
        return field_data
    
    def _compare_airport_data(self, airport: str) -> Dict[str, Any]:
        """
        Compare AIP data for a single airport between France eAIP and Autorouter.
        
        Args:
            airport: ICAO airport code
            
        Returns:
            Dictionary with comparison results
        """
        logger.info(f"Comparing data for {airport}")
        
        # Get France eAIP data
        france_data = None
        try:
            france_data = self.france_source.get_airport_aip(airport)
            if france_data:
                logger.debug(f"Found France eAIP data for {airport}: {len(france_data.get('parsed_data', []))} items")
            else:
                logger.warning(f"No France eAIP data found for {airport}")
        except Exception as e:
            logger.error(f"Error getting France eAIP data for {airport}: {e}")
        
        # Get Autorouter data
        autorouter_data = None
        try:
            autorouter_data = self.autorouter_source.get_airport_aip(airport)
            if autorouter_data:
                logger.debug(f"Found Autorouter data for {airport}: {len(autorouter_data.get('parsed_data', []))} items")
            else:
                logger.warning(f"No Autorouter data found for {airport}")
        except Exception as e:
            logger.error(f"Error getting Autorouter data for {airport}: {e}")
        
        # Extract and standardize field data
        france_fields = self._extract_field_data(france_data) if france_data else {}
        autorouter_fields = self._extract_field_data(autorouter_data) if autorouter_data else {}
        
        # Find common fields
        all_fields = set(france_fields.keys()) | set(autorouter_fields.keys())
        common_fields = set(france_fields.keys()) & set(autorouter_fields.keys())
        
        # Filter fields if specified
        if self.args.fields:
            field_filter = set(self.args.fields)
            common_fields = common_fields & field_filter
            all_fields = all_fields & field_filter
        
        # Compare values
        changes = []
        missing_in_france = []
        missing_in_autorouter = []
        
        for field in all_fields:
            france_value = france_fields.get(field, "")
            autorouter_value = autorouter_fields.get(field, "")
            
            if field in common_fields:
                if france_value != autorouter_value:
                    changes.append({
                        'field': field,
                        'france_value': france_value,
                        'autorouter_value': autorouter_value
                    })
            elif field in france_fields:
                missing_in_autorouter.append(field)
            else:
                missing_in_france.append(field)
        
        return {
            'airport': airport,
            'changes': changes,
            'missing_in_france': missing_in_france,
            'missing_in_autorouter': missing_in_autorouter,
            'total_fields_france': len(france_fields),
            'total_fields_autorouter': len(autorouter_fields),
            'common_fields': len(common_fields)
        }
    
    def run_comparison(self):
        """Run the comparison between France eAIP and Autorouter data."""
        if not self.args.root_dir:
            logger.error("--root-dir is required for france_eaip comparison")
            return
        
        
        logger.info(f"Starting AIP change detection")
        logger.info(f"France eAIP root directory: {self.args.root_dir}")
        logger.info(f"Field filter: {self.args.fields if self.args.fields else 'All fields'}")
        
        # Get airports to compare
        if self.args.airports:
            airports = self.args.airports
        else:
            # Get all available airports from France eAIP
            airports = self.france_source.find_available_airports()
            logger.info(f"Found {len(airports)} airports in France eAIP")
        
        # Compare each airport
        all_changes = []
        summary = {
            'total_airports': len(airports),
            'airports_with_changes': 0,
            'total_changes': 0,
            'airports_missing_france': 0,
            'airports_missing_autorouter': 0
        }
        
        for airport in airports:
            airport = airport.strip()
            result = self._compare_airport_data(airport)
            
            if result['changes']:
                all_changes.append(result)
                summary['airports_with_changes'] += 1
                summary['total_changes'] += len(result['changes'])
                
                logger.info(f"Changes found in {airport}: {len(result['changes'])} field(s) changed")
                
                if self.args.verbose:
                    for change in result['changes']:
                        logger.info(f"  {change['field']}: '{change['france_value']}' -> '{change['autorouter_value']}'")
            
            if result['missing_in_france']:
                summary['airports_missing_france'] += 1
                if self.args.verbose:
                    logger.info(f"  Missing in France eAIP: {result['missing_in_france']}")
            
            if result['missing_in_autorouter']:
                summary['airports_missing_autorouter'] += 1
                if self.args.verbose:
                    logger.info(f"  Missing in Autorouter: {result['missing_in_autorouter']}")
        
        # Print summary
        logger.info("=" * 80)
        logger.info("AIP CHANGE DETECTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total airports processed: {summary['total_airports']}")
        logger.info(f"Airports with changes: {summary['airports_with_changes']}")
        logger.info(f"Total field changes: {summary['total_changes']}")
        logger.info(f"Airports missing France eAIP data: {summary['airports_missing_france']}")
        logger.info(f"Airports missing Autorouter data: {summary['airports_missing_autorouter']}")
        
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
                        'france_value': change['france_value'],
                        'autorouter_value': change['autorouter_value']
                    })
            
            for field, changes in sorted(field_changes.items()):
                logger.info(f"\nField: {field} ({len(changes)} changes)")
                for change in changes:
                    logger.info(f"  {change['airport']}: '{change['france_value']}' -> '{change['autorouter_value']}'")
        
        # Save results to file if requested
        if self.args.output:
            self._save_results(all_changes, summary)
    
    def _save_results(self, changes: List[Dict], summary: Dict):
        """Save comparison results to a file."""
        import json
        
        output_data = {
            'summary': summary,
            'changes': changes,
            'timestamp': str(Path().cwd()),
            'field_filter': self.args.fields
        }
        
        try:
            with open(self.args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Results saved to {self.args.output}")
        except Exception as e:
            logger.error(f"Error saving results to {self.args.output}: {e}")

def main():
    parser = argparse.ArgumentParser(description='AIP Change Detection Tool')
    parser.add_argument('airports', help='List of ICAO airport codes to compare (or all if empty)', nargs='*')
    parser.add_argument('-r', '--root-dir', help='Root directory for France eAIP data', required=True)
    parser.add_argument('-u', '--username', help='Autorouter username', required=False)
    parser.add_argument('-p', '--password', help='Autorouter password', required=False)
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-f', '--fields', help='Comma-separated list of fields to compare (default: all fields)', nargs='*')
    parser.add_argument('-o', '--output', help='Output file to save results (JSON format)')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('--force-refresh', help='Force refresh of cached data', action='store_true')
    parser.add_argument('--never-refresh', help='Never refresh cached data if it exists', action='store_true')
    
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

