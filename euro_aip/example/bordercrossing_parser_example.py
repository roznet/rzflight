#!/usr/bin/env python3
"""
Example script demonstrating the BorderCrossingParser.

This script shows how to use the BorderCrossingParser to extract airport names
from HTML documents that contain numbered lists in the format "(number) airport name" in tables.

Usage:
    python bordercrossing_parser_example.py <html_file>
    
Example:
    python bordercrossing_parser_example.py border_crossing_document.html
"""

import logging
import sys
import argparse
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.parsers.bordercrossing import BorderCrossingParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def parse_html_file(html_path: str) -> dict:
    """
    Parse an HTML file using the BorderCrossingParser.
    
    Args:
        html_path: Path to the HTML file
        
    Returns:
        Dictionary containing parsing results
    """
    # Create the parser
    parser = BorderCrossingParser()
    
    # Read the HTML file
    try:
        with open(html_path, 'rb') as f:
            html_data = f.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"HTML file not found: {html_path}")
    except PermissionError:
        raise PermissionError(f"Permission denied reading file: {html_path}")
    except Exception as e:
        raise Exception(f"Error reading HTML file: {e}")
    
    # Parse the HTML
    print(f"Parsing HTML: {html_path}")
    results = parser.parse(html_data, "HTML_FILE")
    
    return {
        'results': results,
        'names_only': parser.extract_airport_names_only(html_data),
        'metadata': parser.extract_airport_names_with_metadata(html_data, "HTML_FILE")
    }

def display_results(results: dict, html_path: str):
    """
    Display the parsing results in a formatted way.
    
    Args:
        results: Dictionary containing parsing results
        html_path: Path to the HTML file that was parsed
    """
    print(f"\n{'='*60}")
    print(f"BORDER CROSSING PARSER RESULTS")
    print(f"File: {html_path}")
    print(f"{'='*60}")
    
    # Display basic statistics
    total_names = len(results['results'])
    print(f"\n📊 SUMMARY:")
    print(f"   Total airport names extracted: {total_names}")
    
    if total_names == 0:
        print("\n❌ No airport names found in the HTML.")
        print("   This could mean:")
        print("   - The HTML doesn't contain numbered airport lists in tables")
        print("   - The table format doesn't match expected patterns")
        print("   - The HTML is corrupted or unreadable")
        print("   - No country sections were found to start parsing")
        return
    
    # Group results by country
    countries = {}
    for result in results['results']:
        country = result.get('country', 'Unknown')
        if country not in countries:
            countries[country] = []
        countries[country].append(result)
    
    # Display results grouped by country
    print(f"\n🏢 EXTRACTED AIRPORT NAMES BY COUNTRY:")
    for country, country_results in sorted(countries.items()):
        print(f"\n   📍 {country} ({len(country_results)} airports):")
        for result in sorted(country_results, key=lambda x: int(x.get('number', 0))):
            name = result['airport_name']
            number = result.get('number', 'N/A')
            print(f"      {number:>3}. {name}")
    
    # Display metadata
    metadata = results['metadata']
    print(f"\n📋 METADATA:")
    print(f"   Source: {metadata['source']}")
    print(f"   Total count: {metadata['total_count']}")
    print(f"   ICAO code: {metadata['icao']}")
    print(f"   Countries found: {len(countries)}")
    
    # Display detailed metadata for first few entries
    if results['results']:
        print(f"\n🔍 DETAILED METADATA (first 3 entries):")
        for i, result in enumerate(results['results'][:3]):
            print(f"\n   Entry {i+1}:")
            print(f"      Airport: {result['airport_name']}")
            print(f"      Country: {result.get('country', 'Unknown')}")
            print(f"      Number: {result.get('number', 'N/A')}")
            
            # Show paragraph metadata
            if 'metadata' in result and result['metadata']:
                print(f"      Paragraph metadata:")
                for style_key, meta in result['metadata'].items():
                    if isinstance(meta, dict) and 'text' in meta:
                        print(f"         {style_key}: {meta['text'][:50]}...")
                        print(f"           - Bold: {meta.get('is_bold', False)}")
                        print(f"           - Italic: {meta.get('is_italic', False)}")
                        print(f"           - Uppercase: {meta.get('is_uppercase', False)}")
    
    # Display names only (for easy copying)
    print(f"\n📝 NAMES ONLY (for easy copying):")
    names = results['names_only']
    for name in names:
        print(f"   {name}")
    
    # Display summary by country
    print(f"\n📈 SUMMARY BY COUNTRY:")
    for country, country_results in sorted(countries.items()):
        print(f"   {country}: {len(country_results)} airports")

def main():
    """Main function to handle command line arguments and run the parser."""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Extract airport names from border crossing HTML documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bordercrossing_parser_example.py document.html
  python bordercrossing_parser_example.py /path/to/border_crossing.html
        """
    )
    
    parser.add_argument(
        'html_file',
        help='Path to the HTML file to parse'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate HTML file
    html_path = Path(args.html_file)
    if not html_path.exists():
        print(f"❌ Error: HTML file not found: {html_path}")
        print(f"   Please check the file path and try again.")
        sys.exit(1)
    
    if not html_path.is_file():
        print(f"❌ Error: Path is not a file: {html_path}")
        sys.exit(1)
    
    if html_path.suffix.lower() not in ['.html', '.htm']:
        print(f"⚠️  Warning: File doesn't have .html or .htm extension: {html_path}")
        print(f"   The parser will still attempt to process it as HTML.")
    
    # Run the parser
    try:
        results = parse_html_file(str(html_path))
        display_results(results, str(html_path))
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except PermissionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error parsing HTML: {e}")
        print(f"   This could be due to:")
        print(f"   - Corrupted HTML file")
        print(f"   - Invalid HTML format")
        print(f"   - Encoding issues")
        sys.exit(1)

if __name__ == "__main__":
    main() 