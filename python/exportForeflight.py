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


class Command:

    def __init__(self,args):
        self.args = args

    def log(self,msg):
        print(msg)

    def description(self,row):
        rv = [ f'<h2>{row["name"]} ({row["ident"]})</h2>' ]
        value = row['value']
        alt_value = row['alt_value']
        field = row['field']

        rv += [ f'<p>{field}</p><pre>{value}</pre>' ]
        if alt_value:
            rv += [ f'<p>{field}</p><pre>{alt_value}</pre>' ]

        return '\n'.join(rv)

    def buildPointOfEntry(self,dest):
        db = sqlite3.connect('airports.db')

        c = db.cursor()
        c.row_factory = sqlite3.Row
        rows = c.execute('SELECT a.latitude_deg AS "latitude", a.longitude_deg as "longitude", a.ident, a.name, d.alt_field AS field, d.value, d.alt_value FROM frppf f, airports a, airports_aip_details d WHERE f.ident = a.ident AND a.ident = d.ident AND d.alt_field LIKE "%Immigr%"')
        map = {}
        for row in rows:
            map[row['ident']] = dict(row)
        rows = c.execute('SELECT a.latitude_deg AS "latitude", a.longitude_deg as "longitude", a.ident, a.name, d.field, d.value, d.alt_value FROM airports_aip_summary s, airports a, airports_aip_details d WHERE s.ident = a.ident AND s.immigration == 1 AND d.ident = a.ident')
        for row in rows:
            if row['ident'].startswith('LF'):
                continue
            if row['ident'] == 'LEJR':
                print(row)
                
            map[row['ident']] = dict(row)

        kml = simplekml.Kml()
        iconurl = 'https://www.gstatic.com/mapspro/images/stock/503-wht-blank_maps.png'
        #iconurl = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

        icao_to_color = {
            "LF": simplekml.Color.white,  # France (White)
            "EG": simplekml.Color.red,  # United Kingdom (Red)
            "ED": simplekml.Color.black,  # Germany (Black)
            "LE": simplekml.Color.orange,  # Spain (Orange)
            "LI": simplekml.Color.green,   # Italy (Green)
            "EH": simplekml.Color.red, # Netherlands (Maroon)
            "EB": simplekml.Color.yellow,   # Belgium (Black)
            "LS": simplekml.Color.red,   # Switzerland (Red)
            "LO": simplekml.Color.white,   # Austria (Red)
            "ES": simplekml.Color.yellow,   # Sweden (Blue)
            "EN": simplekml.Color.blue,   # Norway (Crimson)
            "EK": simplekml.Color.red,   # Denmark (Red)
            "EF": simplekml.Color.white,   # Finland (Blue)
            "LG": simplekml.Color.blue,   # Greece (Blue)
            "LP": simplekml.Color.green,   # Portugal (Green)
            "LQ": simplekml.Color.red,   # Bosnia and Herzegovina (Red)
            "LD": simplekml.Color.white,   # Croatia (Blue)
            "EI": simplekml.Color.green,    # Ireland (Green)
            "EP": simplekml.Color.crimson,   # Poland (Crimson)
            "LH": simplekml.Color.red,   # Hungary (Vivid Red)
            "LK": simplekml.Color.red,   # Czech Republic (Red)
            "LZ": simplekml.Color.red,   # Slovakia (Red)
            "LJ": simplekml.Color.white,   # Slovenia (White)
            "LD": simplekml.Color.blue,   # Croatia (Blue)
            "LR": simplekml.Color.blue,   # Romania (Blue)
            "LB": simplekml.Color.green,   # Bulgaria (Green)
            "LT": simplekml.Color.red,   # Turkey (Red)
        }


        lat_offset = 0.0045  # about 500m
        count={}

        styles = {}
        smallFile = False
        unknown = {}
        for (one,row) in map.items():
            identprefix = row['ident'][:2]
            if identprefix not in count:
                count[identprefix] = 0
                if identprefix not in icao_to_color:
                    if identprefix not in unknown:
                        unknown[identprefix] = 1
                        print(f'Unknown {identprefix}')
                    stylesmap = simplekml.StyleMap()
                    stylesmap.normalstyle.labelstyle.color = simplekml.Color.blue
                    stylesmap.normalstyle.iconstyle.color = simplekml.Color.blue
                    stylesmap.normalstyle.iconstyle.icon.href=iconurl
                else:
                    stylesmap = simplekml.StyleMap()
                    stylesmap.normalstyle.labelstyle.color = icao_to_color[identprefix]
                    stylesmap.normalstyle.iconstyle.color = icao_to_color[identprefix]
                    stylesmap.normalstyle.iconstyle.icon.href=iconurl
                styles[identprefix] = stylesmap
            count[identprefix] += 1
            if smallFile and count[identprefix] > 2:
                continue

            p = kml.newpoint(name='POE.'+row['ident'],description=self.description(row))
            p.coords = [(row['longitude'], row['latitude']+lat_offset)]
            stylemap = styles[identprefix]
            p.stylemap = stylemap

        self.log(f'Writing {dest}')
        kml.save(dest)


    def buildApproaches(self,dest):
        lat_offset = 0.0045  # about 500m
        db = sqlite3.connect('airports.db')

        sql = 'SELECT * FROM runways r, runways_procedures p, airports a WHERE r.airport_ident = p.ident AND p.le_ident = r.le_ident AND a.ident = r.airport_ident'

        colors = { 0: simplekml.Color.white, 1: simplekml.Color.blue, 2: simplekml.Color.yellow }

        c = db.cursor()
        c.row_factory = sqlite3.Row
        rows = c.execute(sql)
        map = {}
        doFew = False
        count = 0
        kml = simplekml.Kml()
        airports = {}
        for row in rows:
            if doFew and count > 5:
                break
            count += 1
            data = dict(row)
            highest,coords = airports.get(data['airport_ident'],(0,[])) 
            for which in ['le','he']:
                other = 'he' if which == 'le' else 'le'
                procedure = json.loads(data[f'{which}_procedures'])
                if not procedure:
                    continue
                color = simplekml.Color.white
                procname = None
                for approach in procedure:
                    if procname is None:
                        procname = approach
                    if 'ILS' in approach:
                        highest = 2
                        procname = approach
                        color = simplekml.Color.yellow
                        break
                    if 'RNP' in approach:
                        if highest < 1:
                            highest = 1
                        procname = approach
                        color = simplekml.Color.blue
                try:
                    lat,lon = float(data[f'{which}_latitude_deg']),float(data[f'{which}_longitude_deg'])
                except:
                    lat,lon = float(data[f'latitude_deg']),float(data[f'longitude_deg'])
                try:
                    bearing = float(data[f'{other}_heading_degT'])
                except:
                    num = ''.join(c for c in data[f'{which}_ident'] if c.isdigit())
                    bearing = float(num) * 10

                end_lat,end_lon = new_coordinates(lat,lon,bearing,10)
                line = kml.newlinestring(name=f'{data["ident"]} {procname}',description=f'{data["airport_ident"]} {data["ident"]} {procname}',coords=[(lon,lat),(end_lon,end_lat)])
                line.style.linestyle.color = color
                line.style.linestyle.width = 10
            airports[data['airport_ident']] = (highest,[(row['longitude_deg'], row['latitude_deg']+lat_offset)])

        for (ident,(highest,coords)) in airports.items():
            p = kml.newpoint(name='IAP.'+ident)
            p.coords = coords
            p.style.iconstyle.color = colors[highest]

        self.log(f'Writing {dest}')
        kml.save(dest)

    def buildContentPackDirectory(self):
        name = self.args.name
        if not os.path.exists(name):
            os.makedirs(name)
        navdir = os.path.join(name,'navdata')
        if not os.path.exists(navdir):
            os.makedirs(navdir)

        manifest = os.path.join(name,'manifest.json')
        data = {'name':'Point of Entry','abbreviation':'POE.V1','version':1,'organizationName':'flyfun.aero'}
        if os.path.exists(manifest):
            with open(manifest,'r') as f:
                existing = json.load(f)
            data['version'] = existing['version']
            if self.args.next_version:
                data['version'] += 1
                
                self.log(f'Incrementing version to {data["version"]}')

        data['effectiveDate'] = datetime.datetime.now().isoformat()
        days = int(self.args.expiration)
        data['expirationDate'] = (datetime.datetime.now() + datetime.timedelta(days=days)).isoformat()
        with open(manifest,'w') as f:
            f.write(json.dumps(data))
        self.log(f'Writing {manifest}')

        self.buildApproaches(os.path.join(navdir,'Approaches.kml'))
        self.buildPointOfEntry(os.path.join(navdir,'PointOfEntry.kml'))


    def run(self):
        self.buildContentPackDirectory()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create ForeFlight Custom Pack for Point of Entry and Approaches')
    parser.add_argument('name', type=str, help='Name of the pack')
    parser.add_argument('-n', '--next-version', action='store_true', help='Increment version')
    parser.add_argument('-e', '--expiration', default=365, type=int, help='Expiration in days')

    args = parser.parse_args()

    cmd = Command(args)
    cmd.run()


