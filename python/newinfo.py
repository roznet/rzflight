#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional
from pprint import pprint
from euro_aip import EuroAIP
from euro_aip.sources import AutorouterSource
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
        
        # Initialize the source with optional credentials
        self.source = AutorouterSource(
            cache_dir=str(self.cache_dir),
            username=args.username,
            password=args.password
        )

    def run_download(self):
        """Download AIPs and procedures for specified airports."""
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
                if not procedures:
                    logger.warning(f'No procedures found for {airport}')
                
                # Get AIP document
                aip_data = self.source.get_airport_aip(airport)
                if aip_data:
                    # Parse the AIP data if we have a parser for this authority
                    authority = aip_data.get('authority')
                    if authority:
                        try:
                            parser = AIPParserFactory.get_parser(authority)
                            parsed_data = parser.parse(aip_data['pdf_data'], airport)
                            logger.info(f'Successfully parsed AIP for {airport}')
                            pprint(parsed_data)
                        except ValueError as e:
                            logger.warning(f'No parser available for authority {authority}: {e}')
                else:
                    logger.warning(f'No AIP document found for {airport}')
                    
            except Exception as e:
                logger.error(f'Error processing {airport}: {e}')
                if self.args.verbose:
                    import traceback
                    traceback.print_exc()

    def run(self):
        """Run the specified command."""
        getattr(self, f'run_{self.args.command}')()

def main():
    parser = argparse.ArgumentParser(description='European AIP data management tool')
    parser.add_argument('command', help='Command to execute', choices=['download'])
    parser.add_argument('airports', help='List of ICAO airport codes', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='Directory to cache files', default='cache')
    parser.add_argument('-u', '--username', help='Autorouter username')
    parser.add_argument('-p', '--password', help='Autorouter password')
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cmd = Command(args)
    cmd.run()

if __name__ == '__main__':
    main() 