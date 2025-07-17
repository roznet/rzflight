#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional
from pprint import pprint
import simplekml
import json
import datetime
from euro_aip.storage.database_storage import DatabaseStorage
from euro_aip.models.euro_aip_model import EuroAipModel
from euro_aip.models.navpoint import NavPoint

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Command:
    """Command-line interface for ForeFlight export functionality."""
    
    def __init__(self, args):
        """
        Initialize the command interface.
        
        Args:
            args: Command line arguments
        """
        self.args = args
        self.storage = DatabaseStorage(args.database)
        self.model = None

    def load_model(self):
        """Load the EuroAipModel from the database."""
        logger.info(f"Loading model from database: {self.args.database}")
        self.model = self.storage.load_model()
        logger.info(f"Loaded model with {len(self.model.airports)} airports and {len(self.model.get_all_border_crossing_points())} border crossing entries")

    def build_point_of_entry(self, dest: str):
        """Build KML file for Points of Entry."""
        if not self.model:
            self.load_model()
            
        # Create KML document
        kml = simplekml.Kml()
        
        # Define colors for different countries
        icao_to_color = {
            "LF": simplekml.Color.white,  # France
            "EG": simplekml.Color.red,    # United Kingdom
            "ED": simplekml.Color.black,  # Germany
            "LE": simplekml.Color.orange, # Spain
            "LI": simplekml.Color.green,  # Italy
            # Add more countries as needed
        }

        # Get border crossing airports from the model
        border_airports = self.model.get_border_crossing_airports()
        logger.info(f"Found {len(border_airports)} border crossing airports")
        
        for airport in border_airports:
            if not airport.latitude_deg or not airport.longitude_deg:
                logger.warning(f"Airport {airport.ident} missing coordinates, skipping")
                continue
                
            ident = airport.ident
            prefix = ident[:2]
            color = icao_to_color.get(prefix, simplekml.Color.blue)
            
            # Create NavPoint
            point = NavPoint(
                latitude=airport.latitude_deg,
                longitude=airport.longitude_deg,
                name=f'POE.{ident}'
            )
            
            # Create KML point
            p = kml.newpoint(name=point.name)
            p.coords = [(point.longitude, point.latitude)]
            
            # Set style
            p.style.iconstyle.color = color
            p.style.iconstyle.icon.href = 'https://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png'
            
            # Add description
            desc = f"<h2>{airport.name} ({ident})</h2>"
            if airport.municipality:
                desc += f"<p>Location: {airport.municipality}</p>"
            if airport.iso_country:
                desc += f"<p>Country: {airport.iso_country}</p>"
            
            # Add border Acrossing specific info if available
            custom_entry = airport.get_aip_entry_for_field(302)
            if custom_entry:
                desc += f"<p>Custom and Immigrations:</p><p>{custom_entry.value}</p>"
            p.description = desc

        logger.info(f'Writing {dest}')
        kml.save(dest)

    def build_approaches(self, dest: str):
        """Build KML file for Approaches."""
        if not self.model:
            self.load_model()
            
        # Create KML document
        kml = simplekml.Kml()
        
        # Define colors for different approach types
        approach_colors = {
            'ILS': simplekml.Color.yellow,
            'RNP': simplekml.Color.blue,
            'VOR': simplekml.Color.white,
            'NDB': simplekml.Color.white,
            'RNAV': simplekml.Color.blue
        }

        # Get airports with procedures
        airports_with_procedures = self.model.get_airports_with_procedures()
        logger.info(f"Found {len(airports_with_procedures)} airports with procedures")
        
        for airport in airports_with_procedures:
            if not airport.runways:
                continue
                
            # Get approach procedures for this airport
            approaches = airport.get_approaches()
            if not approaches:
                continue
            
            for runway in airport.runways:
                # Get approach procedures for this runway
                runway_approaches = airport.get_approaches_by_runway(runway.le_ident)
                if not runway_approaches:
                    continue
                
                # Process each runway end
                for end in ['le', 'he']:
                    other = 'he' if end == 'le' else 'le'
                    
                    # Get runway end coordinates
                    end_lat = getattr(runway, f'{end}_latitude_deg')
                    end_lon = getattr(runway, f'{end}_longitude_deg')
                    other_heading = getattr(runway, f'{other}_heading_degT')
                    
                    if not all([end_lat, end_lon, other_heading]):
                        continue
                    
                    # Determine approach type and color for this runway
                    color = simplekml.Color.white
                    for approach in runway_approaches:
                        if approach.approach_type:
                            for approach_type in approach_colors:
                                if approach_type in approach.approach_type.upper():
                                    color = approach_colors[approach_type]
                                    break
                            if color != simplekml.Color.white:
                                break

                    try:
                        # Create NavPoint for runway end
                        runway_end = NavPoint(
                            latitude=float(end_lat),
                            longitude=float(end_lon)
                        )
                        
                        # Calculate end point (10nm away)
                        bearing = float(other_heading)
                        end_point = runway_end.point_from_bearing_distance(
                            bearing,
                            10.0  # 10 nautical miles
                        )
                        
                        # Create approach line
                        approach_name = runway_approaches[0].name if runway_approaches else f"RWY{runway.le_ident}"
                        line = kml.newlinestring(
                            name=f"{airport.ident} {approach_name}",
                            description=f"{airport.ident} {runway.le_ident} {approach_name}",
                            coords=[(runway_end.longitude, runway_end.latitude),
                                  (end_point.longitude, end_point.latitude)]
                        )
                        line.style.linestyle.color = color
                        line.style.linestyle.width = 10
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error processing approach for {airport.ident} {runway.le_ident}: {e}")
                        continue

        logger.info(f'Writing {dest}')
        kml.save(dest)

    def build_content_pack(self):
        """Build a complete ForeFlight content pack."""
        name = self.args.name
        pack_dir = Path(name)
        pack_dir.mkdir(exist_ok=True)
        
        nav_dir = pack_dir / 'navdata'
        nav_dir.mkdir(exist_ok=True)

        # Create or update manifest
        manifest_file = pack_dir / 'manifest.json'
        manifest_data = {
            'name': 'Point of Entry',
            'abbreviation': 'POE.V2',
            'version': 2,
            'organizationName': 'flyfun.aero'
        }

        if manifest_file.exists():
            with open(manifest_file, 'r') as f:
                existing = json.load(f)
            manifest_data['version'] = existing['version']
            if self.args.next_version:
                manifest_data['version'] += 1
                logger.info(f'Incrementing version to {manifest_data["version"]}')

        manifest_data['effectiveDate'] = datetime.datetime.now().isoformat()
        days = int(self.args.expiration)
        manifest_data['expirationDate'] = (
            datetime.datetime.now() + datetime.timedelta(days=days)
        ).isoformat()

        with open(manifest_file, 'w') as f:
            json.dump(manifest_data, f, indent=2)
        logger.info(f'Writing {manifest_file}')

        # Build KML files
        self.build_approaches(str(nav_dir / 'Approaches.kml'))
        self.build_point_of_entry(str(nav_dir / 'PointOfEntry.kml'))

    def run(self):
        """Run the specified command."""
        self.build_content_pack()

def main():
    parser = argparse.ArgumentParser(description='ForeFlight export tool')
    parser.add_argument('name', help='Name of the content pack')
    parser.add_argument('-d', '--database', help='SQLite database file', default='airports.db')
    parser.add_argument('-n', '--next-version', help='Increment version', action='store_true')
    parser.add_argument('-e', '--expiration', help='Expiration in days', default=365, type=int)
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cmd = Command(args)
    cmd.run()

if __name__ == '__main__':
    main() 