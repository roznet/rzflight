#!/usr/bin/env python3
"""
Example script demonstrating the flexible parser system.

This script shows how to:
1. Get different types of parsers (HTML, PDF, dual, auto)
2. Check parser availability for authorities
3. Use the appropriate parser based on your needs

The new system allows you to:
- Register separate HTML and PDF parsers for each authority
- Request specific parser types or let the system choose automatically
- Use dual parsers that can handle both formats
"""

import sys
import logging
from pathlib import Path

# Add the parent directory to the Python path to import euro_aip
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.parsers import AIPParserFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main function demonstrating the flexible parser system."""
    
    # Example authority
    authority = 'EGC'
    
    # Check what parsers are available for this authority
    logger.info(f"Checking parser availability for {authority}...")
    parser_info = AIPParserFactory.get_parser_info(authority)
    
    logger.info(f"Parser availability for {authority}:")
    for parser_type, available in parser_info.items():
        status = "✓ Available" if available else "✗ Not available"
        logger.info(f"  {parser_type}: {status}")
    
    # Demonstrate different ways to get parsers
    logger.info("\nDemonstrating different parser types:")
    
    try:
        # 1. Get HTML parser specifically
        logger.info("1. Getting HTML parser...")
        html_parser = AIPParserFactory.get_parser(authority, 'html')
        logger.info(f"   HTML parser: {type(html_parser).__name__}")
        
    except ValueError as e:
        logger.warning(f"   HTML parser not available: {e}")
    
    try:
        # 2. Get PDF parser specifically
        logger.info("2. Getting PDF parser...")
        pdf_parser = AIPParserFactory.get_parser(authority, 'pdf')
        logger.info(f"   PDF parser: {type(pdf_parser).__name__}")
        
    except ValueError as e:
        logger.warning(f"   PDF parser not available: {e}")
    
    try:
        # 3. Get dual parser (combines HTML and PDF)
        logger.info("3. Getting dual parser...")
        dual_parser = AIPParserFactory.get_parser(authority, 'dual')
        logger.info(f"   Dual parser: {type(dual_parser).__name__}")
        
    except ValueError as e:
        logger.warning(f"   Dual parser not available: {e}")
    
    try:
        # 4. Get auto parser (system chooses best available)
        logger.info("4. Getting auto parser...")
        auto_parser = AIPParserFactory.get_parser(authority, 'auto')
        logger.info(f"   Auto parser: {type(auto_parser).__name__}")
        
    except ValueError as e:
        logger.warning(f"   Auto parser not available: {e}")
    
    # Show all supported authorities
    logger.info(f"\nAll supported authorities: {AIPParserFactory.get_supported_authorities()}")
    
    # Example usage with different parser types
    logger.info("\nExample usage patterns:")
    logger.info("1. For HTML-only sources:")
    logger.info("   parser = AIPParserFactory.get_parser('EGC', 'html')")
    
    logger.info("2. For PDF-only sources:")
    logger.info("   parser = AIPParserFactory.get_parser('EGC', 'pdf')")
    
    logger.info("3. For mixed sources (recommended):")
    logger.info("   parser = AIPParserFactory.get_parser('EGC', 'dual')")
    
    logger.info("4. Let the system choose (default):")
    logger.info("   parser = AIPParserFactory.get_parser('EGC', 'auto')")
    logger.info("   # or simply:")
    logger.info("   parser = AIPParserFactory.get_parser('EGC')")
    
    logger.info("\nExample completed!")

if __name__ == "__main__":
    main() 