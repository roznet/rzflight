#!/usr/bin/env python3
"""
Example script demonstrating how to use the UK eAIP source.

This script shows how to:
1. Initialize the UK eAIP source
2. Find available airports
3. Fetch airport AIP data from HTML or PDF files
4. Fetch procedures

Prerequisites:
1. Download the UK eAIP from: https://www.nats-uk.ead-it.com/cms-nats/opencms/en/Publications/Aeronautical-Information-Publications/
2. Extract the ZIP file to a directory
3. Update the ROOT_DIR path below to point to your extracted directory

Note: The UK eAIP source automatically detects and parses both HTML and PDF formats:
- HTML files: Looks for div elements with IDs matching {ICAO}-AD-2.[0-9] for sections 2.1, 2.2, 2.3, and 2.4
- PDF files: Uses traditional PDF parsing methods
- The source prefers HTML files when both formats are available
"""

import os
import sys
import logging
from pathlib import Path

# Add the parent directory to the Python path to import euro_aip
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.sources import UKEAIPSource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main function demonstrating UK eAIP source usage."""
    
    # Configuration
    CACHE_DIR = "/tmp/euro_aip_cache"
    ROOT_DIR = "/path/to/your/uk_eaip_extracted_directory"  # Update this path
    
    # Check if the root directory exists
    if not os.path.exists(ROOT_DIR):
        logger.error(f"Root directory does not exist: {ROOT_DIR}")
        logger.error("Please download the UK eAIP and extract it to the specified directory")
        return
    
    # Initialize the UK eAIP source
    logger.info("Initializing UK eAIP source...")
    source = UKEAIPSource(CACHE_DIR, ROOT_DIR)
    
    # Find available airports
    logger.info("Finding available airports...")
    airports = source.find_available_airports()
    logger.info(f"Found {len(airports)} airports: {airports}")
    
    if not airports:
        logger.warning("No airports found. Check your root directory path and file structure.")
        logger.warning("The source looks for:")
        logger.warning("  - HTML files: ED-AD-2.EG*-en-GB.html")
        logger.warning("  - PDF files: EG-AD-2.EG*.pdf")
        return
    
    # Example: Fetch data for the first airport
    example_icao = airports[0]
    logger.info(f"Fetching data for {example_icao}...")
    
    try:
        # Get airport AIP data
        airport_data = source.get_airport_aip(example_icao)
        if airport_data:
            logger.info(f"Successfully fetched airport data for {example_icao}")
            logger.info(f"Authority: {airport_data.get('authority')}")
            logger.info(f"Number of parsed items: {len(airport_data.get('parsed_data', []))}")
            
            # Group items by section
            sections = {}
            for item in airport_data.get('parsed_data', []):
                section = item.get('section', 'unknown')
                if section not in sections:
                    sections[section] = []
                sections[section].append(item)
            
            # Print summary by section
            for section, items in sections.items():
                logger.info(f"Section {section}: {len(items)} items")
                # Print first few items as example
                for i, item in enumerate(items[:2]):
                    logger.info(f"  {item.get('field')} = {item.get('value')}")
        else:
            logger.warning(f"No airport data found for {example_icao}")
        
        # Get procedures
        procedures = source.get_procedures(example_icao)
        if procedures:
            logger.info(f"Found {len(procedures)} procedures for {example_icao}")
            for i, proc in enumerate(procedures[:3]):  # Show first 3 procedures
                logger.info(f"Procedure {i+1}: {proc.get('name')} ({proc.get('type')})")
        else:
            logger.info(f"No procedures found for {example_icao}")
            
    except Exception as e:
        logger.error(f"Error fetching data for {example_icao}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    logger.info("Example completed!")

if __name__ == "__main__":
    main() 