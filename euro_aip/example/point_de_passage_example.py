#!/usr/bin/env python3
"""
Example script demonstrating the refactored PointDePassageJournalOfficielSource.

This script shows how to use the new SourceInterface-based implementation
to update an EuroAipModel with Points de Passage data.
"""

import logging
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.sources.point_de_passage import PointDePassageJournalOfficielSource
from euro_aip.sources.worldairports import WorldAirportsSource

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    """Demonstrate the refactored PointDePassageJournalOfficielSource."""
    
    # Create a model
    model = EuroAipModel()
    
    # Add some French airports using WorldAirports source
    print("Loading French airports from WorldAirports...")
    worldairports = WorldAirportsSource()
    
    # Add some known French airports that might be Points de Passage
    french_airports = ['LFPG', 'LFBO', 'LFLL', 'LFML', 'LFRS', 'LFSB', 'LFST', 'LFBD']
    worldairports.update_model(model, french_airports)
    
    print(f"Loaded {len(model.airports)} airports from WorldAirports")
    
    # Check if we have a Points de Passage PDF file
    pdf_path = "points_de_passage.pdf"  # Update this path to your PDF file
    
    if not Path(pdf_path).exists():
        print(f"PDF file not found: {pdf_path}")
        print("Please download the Points de Passage PDF from:")
        print("https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009")
        print("and place it in the current directory as 'points_de_passage.pdf'")
        return
    
    # Create and use the Points de Passage source
    print(f"\nProcessing Points de Passage data from {pdf_path}...")
    points_source = PointDePassageJournalOfficielSource(pdf_path)
    
    # Update the model with Points de Passage data
    points_source.update_model(model)
    
    # Display results
    print(f"\nResults:")
    print(f"Total airports in model: {len(model.airports)}")
    
    # Show airports that are Points de Passage
    points_de_passage = [icao for icao, airport in model.airports.items() 
                        if airport.point_of_entry]
    
    print(f"Airports designated as Points de Passage: {len(points_de_passage)}")
    
    for icao in points_de_passage:
        airport = model.airports[icao]
        print(f"  - {icao}: {airport.name}")
        print(f"    Sources: {', '.join(airport.sources)}")
    
    # Show airports that are not Points de Passage
    non_points = [icao for icao, airport in model.airports.items() 
                  if not airport.point_of_entry]
    
    print(f"\nAirports NOT designated as Points de Passage: {len(non_points)}")
    for icao in non_points[:5]:  # Show first 5
        airport = model.airports[icao]
        print(f"  - {icao}: {airport.name}")
    
    if len(non_points) > 5:
        print(f"  ... and {len(non_points) - 5} more")
    
    # Show the raw names extracted from the PDF
    print(f"\nRaw airport names extracted from PDF:")
    pdf_names = points_source.get_points_de_passage()
    for i, name in enumerate(pdf_names[:10], 1):
        print(f"  {i}. {name}")
    
    if len(pdf_names) > 10:
        print(f"  ... and {len(pdf_names) - 10} more")

if __name__ == "__main__":
    main() 