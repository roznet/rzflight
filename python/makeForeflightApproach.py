#!/usr/bin/env python3


import sys
import os
import math
import csv
import sqlite3
import re
from pprint import pprint
import simplekml
import json
import argparse
import datetime
import pandas as pd


def new_coordinates(lat1, lon1, bearing, distance):
    R = 3440  # Earth's radius in nautical miles

    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)

    # Convert bearing to radians
    bearing = math.radians(bearing)

    # Calculate new latitude
    lat2 = math.asin(math.sin(lat1) * math.cos(distance / R) +
                     math.cos(lat1) * math.sin(distance / R) * math.cos(bearing))

    # Calculate new longitude
    lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(distance / R) * math.cos(lat1),
                             math.cos(distance / R) - math.sin(lat1) * math.sin(lat2))

    # Convert new latitude and longitude back to degrees
    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return lat2, lon2
import math

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the bearing and distance between two GPS points using the Haversine formula.
    
    Parameters:
        lat1, lon1: Latitude and longitude of the first point (in degrees).
        lat2, lon2: Latitude and longitude of the second point (in degrees).
        
    Returns:
        bearing: Bearing from the first point to the second point (in degrees).
        distance: Distance between the two points (in kilometers).
    """
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)
    
    # Calculate differences in latitude and longitude
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = 3440 * c  # Earth radius in nautical miles
    
    # Calculate initial bearing from first point to second point
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.degrees(math.atan2(y, x))
    bearing = (bearing + 360) % 360  # Normalize bearing to be in the range [0, 360)
    
    return bearing, distance

def decimal_to_dms(decimal_degrees, is_longitude=False):
    """Convert decimal degrees to degrees, minutes, seconds format"""
    # Determine direction
    direction = ''
    if isinstance(decimal_degrees, (int, float)):
        if is_longitude:
            direction = 'E' if decimal_degrees >= 0 else 'W'
        else:
            direction = 'N' if decimal_degrees >= 0 else 'S'
    
    # Convert to positive for calculation
    decimal_degrees = abs(decimal_degrees)
    degrees = int(decimal_degrees)
    decimal_minutes = (decimal_degrees - degrees) * 60
    minutes = int(decimal_minutes)
    seconds = round((decimal_minutes - minutes) * 60, 2)
    return f"{degrees}° {minutes}' {seconds}\" {direction}"

def decimal_to_dm(decimal_degrees, is_longitude=False):
    """Convert decimal degrees to degrees, decimal minutes format"""
    # Determine direction
    direction = ''
    if isinstance(decimal_degrees, (int, float)):
        if is_longitude:
            direction = 'E' if decimal_degrees >= 0 else 'W'
        else:
            direction = 'N' if decimal_degrees >= 0 else 'S'
    
    # Convert to positive for calculation
    decimal_degrees = abs(decimal_degrees)
    degrees = int(decimal_degrees)
    minutes = round((decimal_degrees - degrees) * 60, 2)
    return f"{degrees}° {minutes}' {direction}"

def coord_to_dms(lat, lon):
    """Convert latitude and longitude to DMS format"""
    lat_dms = decimal_to_dms(lat, is_longitude=False)
    lon_dms = decimal_to_dms(lon, is_longitude=True)
    return lat_dms, lon_dms

def coord_to_dm(lat, lon):
    """Convert latitude and longitude to DM format"""
    lat_dm = decimal_to_dm(lat, is_longitude=False)
    lon_dm = decimal_to_dm(lon, is_longitude=True)
    return lat_dm, lon_dm

class Command:

    def __init__(self,args):
        self.args = args

    def log(self,msg):
        print(msg)

    def openDefinitionFile(self,name):
        excelfile = f'{name}.xlsx'
        if self.args.xlsx:
            excelfile = self.args.xlsx
        if not os.path.exists(excelfile):
            self.log(f'Could not open definition file {excelfile}')
            raise

        self.log(f'Opening {excelfile}')
        self.dfs = {}
        for sheet in ['navdata','byop']:
            try:
                df = pd.read_excel(excelfile,engine='openpyxl',sheet_name=sheet)
                self.dfs[sheet] = df
                print(df)
            except:
                print(f'{excelfile} does not have a {sheet} sheet')
                sys.exit(0)


    def saveExcel(self):
        excel_file_path = f'{self.name}_updated.xlsx'
        with pd.ExcelWriter(excel_file_path) as writer:
            for sheet,df in self.dfs.items():
                if sheet == 'navdata':
                    # Add new columns for DMS and DM formats using the new coordinate functions
                    lat_dms, lon_dms = zip(*df.apply(lambda row: coord_to_dms(row['Latitude'], row['Longitude']), axis=1))
                    lat_dm, lon_dm = zip(*df.apply(lambda row: coord_to_dm(row['Latitude'], row['Longitude']), axis=1))
                    
                    df['Latitude_DMS'] = lat_dms
                    df['Longitude_DMS'] = lon_dms
                    df['Latitude_DM'] = lat_dm
                    df['Longitude_DM'] = lon_dm
                    
                    # Get all columns except Description and the new ones
                    existing_cols = [col for col in df.columns if col != 'Description' 
                                   and col not in ['Latitude_DMS', 'Longitude_DMS', 'Latitude_DM', 'Longitude_DM']]
                    
                    # Create final column order
                    columns = (existing_cols + 
                             ['Latitude_DMS', 'Longitude_DMS',
                              'Latitude_DM', 'Longitude_DM',
                              'Description'])
                    df = df[columns]
                df.to_excel(writer, sheet_name=sheet, index=False)


    def buildContentPackDirectory(self):
        name = self.name

        self.openDefinitionFile(name)

        if not os.path.exists(name):
            os.makedirs(name)
        navdir = os.path.join(name,'navdata')
        if not os.path.exists(navdir):
            os.makedirs(navdir)

        manifest = os.path.join(name,'manifest.json')
        data = {'name':'Custom Approaches','abbreviation':f'{name}.V1','version':1,'organizationName':'flyfun.aero'}
        if os.path.exists(manifest):
            with open(manifest,'r') as f:
                existing = json.load(f)
            data['version'] = existing['version']
            if self.args.next_version:
                data['version'] += 1
                data['abbreviation'] = f'{name}.V{data["version"]}'
                
                self.log(f'Incrementing version to {data["version"]}')

        data['effectiveDate'] = datetime.datetime.now().isoformat()
        days = int(self.args.expiration)
        data['expirationDate'] = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        with open(manifest,'w') as f:
            f.write(json.dumps(data))
        self.log(f'Writing {manifest}')

    def writeNavData(self):
        navdata = self.dfs['navdata']

        self.waypoints = {}
        for row in navdata.to_dict(orient='records'):
            name = row['Name']
            self.waypoints[name] = NavWaypoint(name,row)

        for key,waypoint in self.waypoints.items():
            waypoint.calculateCoordinates(self.waypoints)
            navdata.loc[navdata['Name'] == key,'Latitude'] = waypoint.definition['Latitude']
            navdata.loc[navdata['Name'] == key,'Longitude'] = waypoint.definition['Longitude']

        for key,waypoint in self.waypoints.items():
            if not waypoint.calculated:
                self.log(f'Could not calculate coordinates for {waypoint.name}')

        output = os.path.join(self.name,'navdata',f'{self.name}.csv')
        with open(output,'w') as f:
            f.write('Name,Description,Latitude,Longitude\n')
            for key,waypoint in self.waypoints.items():
                if waypoint.included:
                    f.write(waypoint.toCsv()+'\n')
       
    def describe(self):
        if self.args.describe:
            waypoints = self.args.describe.split(',')
            for name in waypoints:
                if name in self.waypoints:
                    waypoint = self.waypoints[name]
                    print(f'{waypoint.name} {waypoint.definition}')

                    for othername in waypoints:
                        if othername != name and othername in self.waypoints:
                            otherwaypoint = self.waypoints[othername]
                            bearing,distance = haversine(waypoint.definition['Latitude'],waypoint.definition['Longitude'],otherwaypoint.definition['Latitude'],otherwaypoint.definition['Longitude'])
                            print(f'{name} to {otherwaypoint.name} is {distance}nm away at {bearing} degrees')
    def run(self):
        self.name = self.args.name
        self.buildContentPackDirectory()
        self.writeNavData()

        self.describe()
        self.saveExcel()

class NavWaypoint:
    def __init__(self,name,definition):
        self.name = name
        self.definition = definition
        self.calculated = False
        self.included = definition['Include'] == 1

    def __str__(self):
        return f'{self.name}'

    def toCsv(self):
        return f'{self.name},"",{self.definition["Latitude"]},{self.definition["Longitude"]}'

    def calculateCoordinates(self,waypoints):
        reference = self.definition['Reference']
        if isinstance(reference,str) and reference in waypoints:
            ref = waypoints[reference]
            reflat = ref.definition['Latitude']
            reflon = ref.definition['Longitude']
            lat,lon = new_coordinates(reflat,reflon,self.definition['Bearing'],self.definition['Distance'])
            origlat = self.definition['Latitude']
            origlon = self.definition['Longitude']
            # check if new lat and lon are withing 0.001 of the reference
            if abs(lat - origlat) > 0.001 or abs(lon - origlon) > 0.001:
                bearing,distance = haversine(reflat,reflon,origlat,origlon)
                print(f'Calculated coordinates for {self.name} ({lat},{lon}) are not within 0.001 of reference {reference} ({origlat},{origlon}), bearing {bearing}, distance {distance}')

            self.definition['Latitude'] = lat
            self.definition['Longitude'] = lon

        self.calculated = True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create ForeFlight Custom Approach pack')
    parser.add_argument('name', type=str, help='Name of the pack')
    parser.add_argument('-n', '--next-version', action='store_true', help='Increment version')
    parser.add_argument('-d', '--describe', help='Describe information about list of waypoints')
    parser.add_argument('-x', '--xlsx', help='excel file with navdata and byop sheets')
    parser.add_argument('-e', '--expiration', help='number of days until expiration', default='90')

    args = parser.parse_args()

    cmd = Command(args)
    cmd.run()


