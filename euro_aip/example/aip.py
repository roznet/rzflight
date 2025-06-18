#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional
from pprint import pprint
from euro_aip.sources import AutorouterSource, FranceEAIPSource, UKEAIPSource, WorldAirportsSource, PointDePassageJournalOfficiel, DatabaseSource
from euro_aip.parsers import AIPParserFactory

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
        source = PointDePassageJournalOfficiel(
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

    def run(self):
        """Run the specified command."""
        getattr(self, f'run_{self.args.command}')()

def main():
    parser = argparse.ArgumentParser(description='European AIP data management tool')
    parser.add_argument('command', help='Command to execute', choices=['autorouter', 'france_eaip', 'uk_eaip', 'worldairports', 'pointdepassage', 'querydb'])
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
    
    args = parser.parse_args()
    
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cmd = Command(args)
    cmd.run()

if __name__ == '__main__':
    main() 