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
from euro_aip.sources.database import DatabaseSource
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
        self.source = DatabaseSource(args.database)

    def build_point_of_entry(self, dest: str):
        """Build KML file for Points of Entry."""
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

        # Query for immigration points
        with self.source.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.latitude_deg, a.longitude_deg, a.ident, a.name, 
                       d.alt_field AS field, d.value, d.alt_value 
                FROM frppf f, airports a, airports_aip_details d 
                WHERE f.ident = a.ident 
                AND a.ident = d.ident 
                AND d.alt_field LIKE "%Immigr%"
            """)
            
            for row in cursor.fetchall():
                ident = row['ident']
                prefix = ident[:2]
                color = icao_to_color.get(prefix, simplekml.Color.blue)
                
                # Create NavPoint
                point = NavPoint(
                    latitude=row['latitude_deg'],
                    longitude=row['longitude_deg'],
                    name=f'POE.{ident}'
                )
                
                # Create KML point
                p = kml.newpoint(name=point.name)
                p.coords = [(point.longitude, point.latitude)]
                
                # Set style
                p.style.iconstyle.color = color
                p.style.iconstyle.icon.href = 'https://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png'
                
                # Add description
                desc = f"<h2>{row['name']} ({ident})</h2>"
                desc += f"<p>{row['field']}</p><pre>{row['value']}</pre>"
                if row['alt_value']:
                    desc += f"<p>{row['field']}</p><pre>{row['alt_value']}</pre>"
                p.description = desc

        logger.info(f'Writing {dest}')
        kml.save(dest)

    def build_approaches(self, dest: str):
        """Build KML file for Approaches."""
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

        with self.source.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM runways r, runways_procedures p, airports a 
                WHERE r.airport_ident = p.ident 
                AND p.le_ident = r.le_ident 
                AND a.ident = r.airport_ident
            """)
            
            for row in cursor.fetchall():
                for end in ['le', 'he']:
                    other = 'he' if end == 'le' else 'le'
                    procedures = json.loads(row[f'{end}_procedures'])
                    if not procedures:
                        continue

                    # Determine approach type and color
                    color = simplekml.Color.white
                    for approach in procedures:
                        for approach_type in approach_colors:
                            if approach_type in approach:
                                color = approach_colors[approach_type]
                                break

                    try:
                        # Create NavPoint for runway end
                        runway_end = NavPoint(
                            latitude=float(row[f'{end}_latitude_deg']),
                            longitude=float(row[f'{end}_longitude_deg'])
                        )
                        
                        # Calculate end point (10nm away)
                        bearing = float(row[f'{other}_heading_degT'])
                        end_point = runway_end.point_from_bearing_distance(
                            bearing,
                            10.0  # 10 nautical miles
                        )
                        
                        # Create approach line
                        line = kml.newlinestring(
                            name=f"{row['ident']} {procedures[0]}",
                            description=f"{row['airport_ident']} {row['ident']} {procedures[0]}",
                            coords=[(runway_end.longitude, runway_end.latitude),
                                  (end_point.longitude, end_point.latitude)]
                        )
                        line.style.linestyle.color = color
                        line.style.linestyle.width = 10
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error processing approach for {row['ident']}: {e}")
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
            'abbreviation': 'POE.V1',
            'version': 1,
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