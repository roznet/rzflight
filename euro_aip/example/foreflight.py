#!/usr/bin/env python3

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from pprint import pprint
import simplekml
import json
import datetime
import pandas as pd
import os
try:
    import openpyxl
except ImportError:
    print("openpyxl is required for Excel processing. Install with: pip install openpyxl")
    sys.exit(1)
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
            'ILS': simplekml.Color.yellow,    # Instrument Landing System - highest precision
            'RNP': simplekml.Color.blue,      # Required Navigation Performance
            'RNAV': simplekml.Color.blue,     # Area Navigation
            'LOC': simplekml.Color.orange,    # Localizer
            'LDA': simplekml.Color.orange,    # Localizer Directional Aid
            'SDF': simplekml.Color.orange,    # Simplified Directional Facility
            'VOR': simplekml.Color.white,     # VHF Omnidirectional Range
            'NDB': simplekml.Color.white,     # Non-Directional Beacon
        }

        # Get airports with procedures
        airports_with_procedures = self.model.get_airports_with_procedures()
        logger.info(f"Found {len(airports_with_procedures)} airports with procedures")
        
        for airport in airports_with_procedures:

            if airport.ident == 'LFBN' or airport.ident == 'LFOK':
                logger.info(f"Processing {airport.ident}")
            if not airport.runways:
                continue
                
            # Get approach procedures for this airport
            approaches = airport.get_approaches()
            if not approaches:
                continue
            
            for runway in airport.runways:
                # Get approach procedures for this runway
                runway_approaches = airport.get_approaches_by_runway(runway)
                if not runway_approaches:
                    continue
                
                # Process each runway end
                for end in ['le', 'he']:
                    other = 'he' if end == 'le' else 'le'
                    
                    # Get runway end coordinates
                    end_lat = getattr(runway, f'{end}_latitude_deg')
                    end_lon = getattr(runway, f'{end}_longitude_deg')
                    other_heading = getattr(runway, f'{other}_heading_degT')
                    current_ident = getattr(runway, f'{end}_ident')

                    if not all([end_lat, end_lon, other_heading]):
                        continue
                    
                    # Get the most precise approach for this runway end
                    most_precise_approach = airport.get_most_precise_approach_for_runway_end(runway, current_ident)
                    
                    if not most_precise_approach or not most_precise_approach.approach_type:
                        continue
                    
                    approach_type = most_precise_approach.approach_type.upper()
                    
                    # Get color for the most precise approach type
                    color = approach_colors.get(approach_type, simplekml.Color.white)
                    
                    # Log the selection for debugging
                    if airport.ident in ['LFAC', 'LFOK']:
                        logger.info(f"Selected {approach_type} approach for {airport.ident} {current_ident} "
                                  f"(precision: {most_precise_approach.get_approach_precision()})")

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
                        approach_name = most_precise_approach.name if most_precise_approach else f"RWY{current_ident}"
                        line = kml.newlinestring(
                            name=f"{airport.ident} {approach_name}",
                            description=f"{airport.ident} {current_ident} {approach_name} ({approach_type})",
                            coords=[(runway_end.longitude, runway_end.latitude),
                                  (end_point.longitude, end_point.latitude)]
                        )
                        line.style.linestyle.color = color
                        line.style.linestyle.width = 10
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Error processing approach for {airport.ident} {current_ident}: {e}")
                        continue

        logger.info(f'Writing {dest}')
        kml.save(dest)

    def build_content_pack(self):
        """Build a complete ForeFlight content pack."""
        if self.args.command == 'approach':
            self.build_approach_content_pack()
        else:
            self.build_database_content_pack()

    def build_database_content_pack(self):
        """Build a complete ForeFlight content pack from database."""
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

    def build_approach_content_pack(self):
        """Build a ForeFlight content pack from Excel approach definition."""
        name = self.args.name
        
        # Open and process the Excel file
        self.open_definition_file(name)
        
        # Create content pack directory
        pack_dir = Path(name)
        pack_dir.mkdir(exist_ok=True)
        
        nav_dir = pack_dir / 'navdata'
        nav_dir.mkdir(exist_ok=True)

        # Create or update manifest
        manifest_file = pack_dir / 'manifest.json'
        manifest_data = {
            'name': 'Custom Approaches',
            'abbreviation': f'{name}.V1',
            'version': 1,
            'organizationName': 'flyfun.aero'
        }

        if manifest_file.exists():
            with open(manifest_file, 'r') as f:
                existing = json.load(f)
            manifest_data['version'] = existing['version']
            if self.args.next_version:
                manifest_data['version'] += 1
                manifest_data['abbreviation'] = f'{name}.V{manifest_data["version"]}'
                logger.info(f'Incrementing version to {manifest_data["version"]}')

        manifest_data['effectiveDate'] = datetime.datetime.now().isoformat()
        days = int(self.args.expiration)
        manifest_data['expirationDate'] = (
            datetime.datetime.now() + datetime.timedelta(days=days)
        ).isoformat()

        with open(manifest_file, 'w') as f:
            json.dump(manifest_data, f, indent=2)
        logger.info(f'Writing {manifest_file}')

        # Process waypoints and write navdata
        self.process_waypoints()
        self.write_navdata(name, nav_dir)
        
        # Save updated Excel file
        self.save_excel(name)

    def open_definition_file(self, name: str):
        """Open the Excel definition file."""
        excel_file = f'{name}.xlsx'
        if self.args.xlsx:
            excel_file = self.args.xlsx
            
        if not os.path.exists(excel_file):
            logger.error(f'Could not open definition file {excel_file}')
            raise FileNotFoundError(f'Definition file not found: {excel_file}')

        logger.info(f'Opening {excel_file}')
        self.dfs = {}
        
        for sheet in ['navdata', 'byop']:
            try:
                df = pd.read_excel(excel_file, engine='openpyxl', sheet_name=sheet)
                self.dfs[sheet] = df
                logger.info(f'Loaded {sheet} sheet with {len(df)} rows')
            except Exception as e:
                logger.warning(f'{excel_file} does not have a {sheet} sheet: {e}')
                if sheet == 'navdata':
                    raise ValueError(f'Required navdata sheet not found in {excel_file}')

    def process_waypoints(self):
        """Process waypoints and calculate coordinates."""
        navdata = self.dfs['navdata']
        
        # Create NavPoint objects for all waypoints
        self.waypoints = {}
        for _, row in navdata.iterrows():
            name = row['Name']
            self.waypoints[name] = self.create_nav_waypoint(name, row)

        # Calculate coordinates for all waypoints
        for name, waypoint in self.waypoints.items():
            waypoint.calculate_coordinates(self.waypoints)
            
            # Update the dataframe with calculated coordinates
            navdata.loc[navdata['Name'] == name, 'Latitude'] = waypoint.navpoint.latitude
            navdata.loc[navdata['Name'] == name, 'Longitude'] = waypoint.navpoint.longitude

        # Check for calculation failures
        failed_calculations = [name for name, waypoint in self.waypoints.items() 
                             if not waypoint.calculated]
        if failed_calculations:
            logger.warning(f'Could not calculate coordinates for: {failed_calculations}')

    def create_nav_waypoint(self, name: str, row: pd.Series) -> 'NavWaypoint':
        """Create a NavWaypoint from a dataframe row."""
        return NavWaypoint(name, row, self.args)

    def write_navdata(self, name: str, nav_dir: Path):
        """Write navdata CSV file."""
        output_file = nav_dir / f'{name}.csv'
        
        with open(output_file, 'w') as f:
            f.write('Name,Description,Latitude,Longitude\n')
            for name, waypoint in self.waypoints.items():
                if waypoint.included:
                    f.write(waypoint.to_csv() + '\n')
        
        logger.info(f'Writing {output_file}')

    def save_excel(self, name: str):
        """Save updated Excel file with calculated coordinates."""
        excel_file_path = f'{name}_updated.xlsx'
        
        with pd.ExcelWriter(excel_file_path) as writer:
            for sheet, df in self.dfs.items():
                if sheet == 'navdata':
                    # Add new columns for DMS and DM formats
                    lat_dms, lon_dms = zip(*df.apply(
                        lambda row: NavPoint(row['Latitude'], row['Longitude']).to_dms(), axis=1))
                    lat_dm, lon_dm = zip(*df.apply(
                        lambda row: NavPoint(row['Latitude'], row['Longitude']).to_dm(), axis=1))
                    
                    df['Latitude_DMS'] = lat_dms
                    df['Longitude_DMS'] = lon_dms
                    df['Latitude_DM'] = lat_dm
                    df['Longitude_DM'] = lon_dm
                    
                    # Reorder columns
                    existing_cols = [col for col in df.columns if col != 'Description' 
                                   and col not in ['Latitude_DMS', 'Longitude_DMS', 'Latitude_DM', 'Longitude_DM']]
                    columns = (existing_cols + 
                             ['Latitude_DMS', 'Longitude_DMS', 'Latitude_DM', 'Longitude_DM', 'Description'])
                    df = df[columns]
                
                df.to_excel(writer, sheet_name=sheet, index=False)
        
        logger.info(f'Saving updated Excel file: {excel_file_path}')

    def describe_waypoints(self):
        """Describe information about waypoints if requested."""
        if not self.args.describe:
            return
            
        waypoint_names = self.args.describe.split(',')
        for name in waypoint_names:
            if name in self.waypoints:
                waypoint = self.waypoints[name]
                logger.info(f'{waypoint.name}: {waypoint.navpoint}')
                
                # Calculate distances to other waypoints
                for other_name in waypoint_names:
                    if other_name != name and other_name in self.waypoints:
                        other_waypoint = self.waypoints[other_name]
                        bearing, distance = waypoint.navpoint.haversine_distance(other_waypoint.navpoint)
                        logger.info(f'{name} to {other_waypoint.name}: {distance:.2f}nm at {bearing:.1f}°')

    def run(self):
        """Run the specified command."""
        if self.args.command == 'approach':
            self.build_approach_content_pack()
            self.describe_waypoints()
        else:
            self.build_database_content_pack()


class NavWaypoint:
    """A waypoint that can be calculated from a reference point."""
    
    def __init__(self, name: str, definition: pd.Series, args):
        """
        Initialize the waypoint.
        
        Args:
            name: Waypoint name
            definition: Pandas Series containing waypoint definition
            args: Command line arguments
        """
        self.name = name
        self.definition = definition
        self.args = args
        self.calculated = False
        self.included = definition.get('Include', 1) == 1
        
        # Create initial NavPoint (will be updated if calculated)
        self.navpoint = NavPoint(
            latitude=definition.get('Latitude', 0.0),
            longitude=definition.get('Longitude', 0.0),
            name=name
        )

    def calculate_coordinates(self, waypoints: Dict[str, 'NavWaypoint']):
        """Calculate coordinates from reference waypoint."""
        reference = self.definition.get('Reference')
        
        if isinstance(reference, str) and reference in waypoints:
            ref_waypoint = waypoints[reference]
            ref_navpoint = ref_waypoint.navpoint
            
            # Get bearing and distance from definition
            bearing = self.definition.get('Bearing', 0.0)
            distance = self.definition.get('Distance', 0.0)
            
            # Calculate new position using NavPoint
            new_navpoint = ref_navpoint.point_from_bearing_distance(bearing, distance, self.name)
            
            # Update our NavPoint
            self.navpoint = new_navpoint
            
            # Validate calculation
            orig_lat = self.definition.get('Latitude', 0.0)
            orig_lon = self.definition.get('Longitude', 0.0)
            
            if abs(new_navpoint.latitude - orig_lat) > 0.001 or abs(new_navpoint.longitude - orig_lon) > 0.001:
                bearing_calc, distance_calc = ref_navpoint.haversine_distance(
                    NavPoint(orig_lat, orig_lon))
                logger.warning(f'Calculated coordinates for {self.name} ({new_navpoint.latitude}, {new_navpoint.longitude}) '
                             f'are not within 0.001 of reference {reference} ({orig_lat}, {orig_lon}), '
                             f'bearing {bearing_calc}, distance {distance_calc}')
        
        self.calculated = True

    def to_csv(self) -> str:
        """Convert to CSV format."""
        return self.navpoint.to_csv()

    def __str__(self) -> str:
        return f'{self.name}'

    def __repr__(self) -> str:
        return f'NavWaypoint(name={self.name}, navpoint={self.navpoint})'

def main():
    parser = argparse.ArgumentParser(description='ForeFlight export tool')
    parser.add_argument('name', help='Name of the content pack')
    parser.add_argument('-n', '--next-version', help='Increment version', action='store_true')
    parser.add_argument('-e', '--expiration', help='Expiration in days', default=365, type=int)
    parser.add_argument('-v', '--verbose', help='Verbose output', action='store_true')
    
    # Command-specific arguments
    parser.add_argument('-c', '--command', choices=['airports', 'approach'], 
                       default='airports', help='Command to execute (default: airports)')
    parser.add_argument('-x', '--xlsx', help='Excel file with navdata and byop sheets (for approach command)')
    parser.add_argument('-d', '--database', help='SQLite database file', default='airports.db')
    parser.add_argument('--describe', help='Describe information about list of waypoints (comma-separated, for approach command)')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    cmd = Command(args)
    cmd.run()

if __name__ == '__main__':
    main() 