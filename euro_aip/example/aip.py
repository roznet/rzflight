#!/usr/bin/env python3

import sys
import argparse
import logging
import json
import csv
from pathlib import Path
from typing import List, Optional, Dict, Any
from pprint import pprint
from euro_aip.sources import AutorouterSource, FranceEAIPSource, UKEAIPSource, WorldAirportsSource, PointDePassageJournalOfficielSource, DatabaseSource
from euro_aip.parsers import AIPParserFactory
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.interp import InterpreterFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Command:
    """Command-line interface for euro_aip."""
    
    def __init__(self, args):
        """
        Initialize the command interface.
        
        Args:
            args: Command line arguments
        """
        self.args = args
        self.cache_dir = Path(args.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.source = None

    def run_autorouter(self):
        """Download AIPs and procedures from Autorouter API."""
        # Initialize source
        self.source = AutorouterSource(
            cache_dir=str(self.cache_dir),
            username=self.args.username,
            password=self.args.password
        )
        if self.args.force_refresh:
            self.source.set_force_refresh()
        if self.args.never_refresh:
            self.source.set_never_refresh()
            
        for airport in self.args.airports:
            airport = airport.strip()
            logger.info(f'Processing {airport}')
            
            try:
                # Get airport data
                airport_data = self.source.get_airport_data(airport)
                if not airport_data:
                    logger.warning(f'No data found for {airport}')
                    continue
                
                # Get procedures
                procedures = self.source.get_procedures(airport)
                if procedures:
                    logger.info(f'Successfully fetched {len(procedures)} procedures for {airport}')
                else:
                    logger.warning(f'No procedures found for {airport}')
                
                # Get AIP document
                aip_data = self.source.get_airport_aip(airport)
                if aip_data:
                    logger.info(f'Successfully parsed {len(aip_data["parsed_data"])} items in AIP for {airport}')
                else:
                    logger.warning(f'No AIP document found for {airport}')

                # Get approach data
                approach_data = self.source.get_approach_data(airport)
                if approach_data:
                    logger.info(f'Successfully parsed {len(approach_data)} items in approach data for {airport}')
                else:
                    logger.warning(f'No approach data found for {airport}')
                    
            except Exception as e:
                logger.error(f'Error processing {airport}: {e}')
                if self.args.verbose:
                    import traceback
                    traceback.print_exc()

    def run_france_eaip(self):
        """Parse France eAIP data from local directories."""
        # Initialize source

        if not self.args.root_dir:
            logger.error("--root-dir is required for france_eaip command, the source can be downloaded from https://www.sia.aviation-civile.gouv.fr/produits-numeriques-en-libre-disposition/eaip.html")
            return

        self.source = FranceEAIPSource(
            cache_dir=str(self.cache_dir),
            root_dir=self.args.root_dir
        )
        if self.args.force_refresh:
            self.source.set_force_refresh()
        if self.args.never_refresh:
            self.source.set_never_refresh()
            
        logger.info(f"Using root directory: {self.args.root_dir}")

        if self.args.airports:
            airports = self.args.airports
        else:
            # get all available airports
            airports = self.source.find_available_airports()
            logger.info(f"Found {len(airports)} airports")
            if self.args.verbose:
                logger.info(f"Available airports: {airports}")
        
        for airport in airports:
            airport = airport.strip()
            logger.info(f'Processing {airport}')
            
            try:
                # Get airport data
                airport_data = self.source.get_airport_aip(airport)
                if airport_data:
                    logger.info(f'Successfully parsed {len(airport_data["parsed_data"])} items in AIP for {airport}')
                else:
                    logger.warning(f'No AIP document found for {airport}')
                    continue
                
                # Get procedures
                procedures = self.source.get_procedures(airport)
                if procedures:
                    logger.info(f'Successfully parsed {len(procedures)} procedures for {airport}')
                else:
                    logger.warning(f'No procedures found for {airport}')
                    
            except Exception as e:
                logger.error(f'Error processing {airport}: {e}')
                if self.args.verbose:
                    import traceback
                    traceback.print_exc()

    def run_uk_eaip(self):
        """Parse UK eAIP data from local directories."""

        if not self.args.root_dir:
            logger.error("--root-dir is required for uk_eaip command, the source can be downloaded from https://nats-uk.ead-it.com/cms-nats/opencms/en/Publications/AIP")
            return

        # Initialize source
        self.source = UKEAIPSource(
            cache_dir=str(self.cache_dir),
            root_dir=self.args.root_dir
        )
        if self.args.force_refresh:
            self.source.set_force_refresh()
        if self.args.never_refresh:
            self.source.set_never_refresh()
            
        logger.info(f"Using root directory: {self.args.root_dir}")

        if self.args.airports:
            airports = self.args.airports
        else:
            # get all available airports
            airports = self.source.find_available_airports()
            logger.info(f"Found {len(airports)} airports")
            if self.args.verbose:
                logger.info(f"Available airports: {airports}")
        
        for airport in airports:
            airport = airport.strip()
            logger.info(f'Processing {airport}')
            
            try:
                # Get airport data
                airport_data = self.source.get_airport_aip(airport)
                if airport_data:
                    logger.info(f'Successfully parsed {len(airport_data["parsed_data"])} items in AIP for {airport}')
                else:
                    logger.warning(f'No AIP document found for {airport}')
                    continue
                
                # Get procedures
                procedures = self.source.get_procedures(airport)
                if procedures:
                    logger.info(f'Successfully parsed {len(procedures)} procedures for {airport}')
                else:
                    logger.warning(f'No procedures found for {airport}')
                    
            except Exception as e:
                logger.error(f'Error processing {airport}: {e}')
                if self.args.verbose:
                    import traceback
                    traceback.print_exc()

    def run_worldairports(self):
        """Download and process World Airports data."""
        # Initialize source
        self.source = WorldAirportsSource(
            cache_dir=str(self.cache_dir),
            database=self.args.database
        )
        if self.args.force_refresh:
            self.source.set_force_refresh()
        if self.args.never_refresh:
            self.source.set_never_refresh()
            
        logger.info('Processing World Airports data')
        
        try:
            # Get the database
            db_metadata = self.source.get_airport_database()
            logger.info(f'Successfully created database: {db_metadata["database"]}')
            
            # Display table information
            for table in db_metadata['tables']:
                logger.info(f'Table {table["name"]}: {table["row_count"]} rows, {len(table["fields"])} fields')
            
            if self.args.verbose:
                logger.info('\nDetailed table information:')
                pprint(db_metadata)
                
        except Exception as e:
            logger.error(f'Error processing World Airports data: {e}')
            if self.args.verbose:
                import traceback
                traceback.print_exc()

    def run_pointdepassage(self):
        if not self.args.journal_path:
            logger.error("--journal-path is required for pointdepassage command, the source can be downloaded from https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009")
            return
        
        """Process Point de Passage journal PDF and store in database."""
        # Initialize database source
        database_source = DatabaseSource(
            self.args.database
        )
        
        # Initialize Point de Passage source
        source = PointDePassageJournalOfficielSource(
            pdf_path=self.args.journal_path,
            database_source=database_source
        )
            
        logger.info(f'Processing Point de Passage journal: {self.args.journal_path}')
        
        try:
            # Get points de passage
            points_de_passage = source.get_points_de_passage()
            if points_de_passage:
                logger.info(f'Successfully found {len(points_de_passage)} Points de Passage airports')
                if self.args.verbose:
                    logger.info('\nPoints de Passage airports:')
                    pprint(points_de_passage)
            else:
                logger.warning('No Points de Passage airports found in the journal')
                
        except Exception as e:
            logger.error(f'Error processing Point de Passage journal: {e}')
            if self.args.verbose:
                import traceback
                traceback.print_exc()

    def run_querydb(self):
        """Query the database with a WHERE clause."""
        if not self.args.where:
            logger.error("--where is required for querydb command")
            return
        
        # Initialize database source
        database_source = DatabaseSource(
            self.args.database
        )
            
        logger.info(f'Querying database with WHERE clause: {self.args.where}')
        
        try:
            # Get airports matching the WHERE clause
            airports = database_source.get_airports_with_runways(self.args.where)
            if airports:
                logger.info(f'Found {len(airports)} airports')
                if self.args.verbose:
                    for airport in airports:
                        logger.info(f'{str(airport)}')
            else:
                logger.warning('No airports found matching the criteria')
                
        except Exception as e:
            logger.error(f'Error querying database: {e}')
            if self.args.verbose:
                import traceback
                traceback.print_exc()

    def run_analyze(self):
        """Analyze structured information from the database using interpreters."""
        if not self.args.interpreters:
            logger.error("--interpreters is required for analyze command")
            return
        
        logger.info(f'Loading model from database: {self.args.database}')
        
        try:
            # Load model from database
            storage = DatabaseStorage(self.args.database)
            model = storage.load_model()
            
            logger.info(f'Loaded model with {len(model.airports)} airports')
            
            # Parse interpreter types
            interpreter_types = [t.strip() for t in self.args.interpreters.split(',')]
            
            # Create interpreters
            interpreters = []
            for interpreter_type in interpreter_types:
                interpreter = InterpreterFactory.create_interpreter(interpreter_type, model)
                interpreters.append(interpreter)
            
            # Run analysis using model method
            results = model.analyze_fields_with_interpreters(
                interpreters=interpreters,
                country_filter=self.args.country,
                airport_filter=self.args.airports if self.args.airports else None
            )
            
            # Prepare results for output
            all_results = {}
            all_failed = []
            all_missing = []
            
            for interpreter_name, result in results.items():
                all_results[interpreter_name] = result.successful
                all_failed.extend(result.failed)
                all_missing.extend(result.missing)
            
            # Output results
            self._output_results(all_results, all_failed, all_missing)
            
            # Save failed interpretations to separate file if requested
            if self.args.failed_output and all_failed:
                self._save_failed_interpretations(all_failed, self.args.failed_output)
                
        except Exception as e:
            logger.error(f'Error during analysis: {e}')
            if self.args.verbose:
                import traceback
                traceback.print_exc()

    def _output_results(self, results: Dict[str, Dict], failed: List[Dict], missing: List[str]):
        """Output analysis results in the specified format."""
        output_file = self.args.output
        
        if self.args.format == 'json':
            self._output_json(results, failed, missing, output_file)
        elif self.args.format == 'csv':
            self._output_csv(results, failed, missing, output_file, include_raw_values=self.args.include_raw_values)
        else:
            self._output_human_readable(results, failed, missing, output_file)
    
    def _output_json(self, results: Dict[str, Dict], failed: List[Dict], missing: List[str], output_file: Optional[str]):
        """Output results in JSON format."""
        output_data = {
            'results': results,
            'failed': failed,
            'missing': missing,
            'summary': {
                'total_successful': sum(len(r) for r in results.values()),
                'total_failed': len(failed),
                'total_missing': len(missing)
            }
        }
        
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f'Results saved to {output_file}')
        else:
            print(json.dumps(output_data, indent=2))
    
    def _output_csv(self, results: Dict[str, Dict], failed: List[Dict], missing: List[str], output_file: Optional[str], include_raw_values: bool = False):
        """Output results in CSV format."""
        # For CSV, we'll output successful results in a flattened format
        if not results:
            logger.warning('No successful results to output')
            return
        
        # Determine all possible fields across all interpreters
        all_fields = set()
        for interpreter_results in results.values():
            for airport_data in interpreter_results.values():
                all_fields.update(airport_data.keys())
        
        # Handle raw_value field based on include_raw_values option
        if include_raw_values:
            # Keep raw_value but rename it per interpreter
            all_fields.discard('raw_value')  # Remove generic raw_value
        else:
            # Remove raw_value from fields for CSV output
            all_fields.discard('raw_value')
        
        # Prepare CSV data
        csv_rows = []
        all_raw_value_columns = set()  # Track all raw value columns we might need
        
        for interpreter_type, interpreter_results in results.items():
            for airport_icao, airport_data in interpreter_results.items():
                row = {
                    'interpreter': interpreter_type,
                    'airport_icao': airport_icao
                }
                
                # Add structured fields
                for field in all_fields:
                    value = airport_data.get(field)
                    if isinstance(value, list):
                        value = ';'.join(str(v) for v in value)
                    row[field] = value
                
                # Add raw value if requested
                if include_raw_values and 'raw_value' in airport_data:
                    raw_value_column = f"{interpreter_type}_raw_value"
                    row[raw_value_column] = airport_data['raw_value']
                    all_raw_value_columns.add(raw_value_column)
                
                csv_rows.append(row)
        
        # Ensure all rows have the same columns by adding missing raw value columns
        if include_raw_values and all_raw_value_columns:
            for row in csv_rows:
                for raw_value_column in all_raw_value_columns:
                    if raw_value_column not in row:
                        row[raw_value_column] = ''  # Empty string for missing raw values
        
        if output_file:
            with open(output_file, 'w', newline='') as f:
                if csv_rows:
                    writer = csv.DictWriter(f, fieldnames=csv_rows[0].keys())
                    writer.writeheader()
                    writer.writerows(csv_rows)
            logger.info(f'Results saved to {output_file}')
        else:
            # Output to stdout
            if csv_rows:
                writer = csv.DictWriter(sys.stdout, fieldnames=csv_rows[0].keys())
                writer.writeheader()
                writer.writerows(csv_rows)
    
    def _output_human_readable(self, results: Dict[str, Dict], failed: List[Dict], missing: List[str], output_file: Optional[str]):
        """Output results in human-readable format."""
        output_lines = []
        
        # Summary
        output_lines.append("=== ANALYSIS RESULTS ===")
        output_lines.append(f"Total successful interpretations: {sum(len(r) for r in results.values())}")
        output_lines.append(f"Total failed interpretations: {len(failed)}")
        output_lines.append(f"Total missing data: {len(missing)}")
        output_lines.append("")
        
        # Results by interpreter
        for interpreter_type, interpreter_results in results.items():
            output_lines.append(f"=== {interpreter_type.upper()} INTERPRETER ===")
            output_lines.append(f"Successful: {len(interpreter_results)}")
            if interpreter_results:
                for airport_icao, data in list(interpreter_results.items())[:5]:  # Show first 5
                    output_lines.append(f"  {airport_icao}: {data}")
                if len(interpreter_results) > 5:
                    output_lines.append(f"  ... and {len(interpreter_results) - 5} more")
            output_lines.append("")
        
        # Failed interpretations (first 10)
        if failed:
            output_lines.append("=== FAILED INTERPRETATIONS ===")
            for failure in failed[:10]:
                output_lines.append(f"  {failure['airport_icao']}: {failure['reason']}")
            if len(failed) > 10:
                output_lines.append(f"  ... and {len(failed) - 10} more")
            output_lines.append("")
        
        # Missing data (first 10)
        if missing:
            output_lines.append("=== MISSING DATA ===")
            for airport_icao in missing[:10]:
                output_lines.append(f"  {airport_icao}")
            if len(missing) > 10:
                output_lines.append(f"  ... and {len(missing) - 10} more")
        
        output_text = '\n'.join(output_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output_text)
            logger.info(f'Results saved to {output_file}')
        else:
            print(output_text)

    def _save_failed_interpretations(self, failed: List[Dict], output_file: str):
        """Save failed interpretations to a separate file for review."""
        try:
            with open(output_file, 'w') as f:
                json.dump(failed, f, indent=2)
            logger.info(f'Failed interpretations saved to {output_file}')
        except Exception as e:
            logger.error(f'Error saving failed interpretations: {e}')

    def run(self):
        """Run the specified command."""
        getattr(self, f'run_{self.args.command}')()

def main():
    parser = argparse.ArgumentParser(description='European AIP data management tool')
    parser.add_argument('command', help='Command to execute', choices=['autorouter', 'france_eaip', 'uk_eaip', 'worldairports', 'pointdepassage', 'querydb', 'analyze'])
    parser.add_argument('airports', help='List of ICAO airport codes', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-u', '--username', help='Autorouter username')
    parser.add_argument('-p', '--password', help='Autorouter password')
    parser.add_argument('-r', '--root-dir', help='Root directory for eAIP data')
    parser.add_argument('-d', '--database', help='SQLite database file', default='airports.db')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    parser.add_argument('-f', '--force-refresh', help='Force refresh of cached data', action='store_true')
    parser.add_argument('-n', '--never-refresh', help='Never refresh cached data if it exists', action='store_true')
    parser.add_argument('-j', '--journal-path', help='Path to Point de Passage journal PDF file')
    parser.add_argument('-w', '--where', help='SQL WHERE clause for database query')
    
    # Analysis-specific arguments
    parser.add_argument('-i', '--interpreters', help='Comma-separated list of interpreters to run (custom,maintenance)', type=str)
    parser.add_argument('--format', help='Output format (json,csv,human)', choices=['json', 'csv', 'human'], default='human')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('--country', help='Filter by country code (e.g., GB, FR)')
    parser.add_argument('--failed-output', help='Output file for failed interpretations')
    parser.add_argument('--include-raw-values', help='Include raw field values in CSV output', action='store_true')
    
    args = parser.parse_args()
    
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cmd = Command(args)
    cmd.run()

if __name__ == '__main__':
    main() 