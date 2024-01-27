#!/usr/bin/env python3


import sys
import csv
import sqlite3
import re
from pprint import pprint
import simplekml


def buildPPF():
    db = sqlite3.connect('airports.db')

    c = db.cursor()
    c.row_factory = sqlite3.Row
    rows = c.execute('SELECT a.latitude_deg AS "latitude", a.longitude_deg as "longitude", a.ident, a.name, d.alt_field AS field, d.value, d.alt_value FROM frppf f, airports a, airports_aip_details d WHERE f.ident = a.ident AND a.ident = d.ident AND d.alt_field LIKE "%Immigr%"')
    map = {}
    for row in rows:
        map[row['ident']] = dict(row)
    rows = c.execute('SELECT a.latitude_deg AS "latitude", a.longitude_deg as "longitude", a.ident, a.name, d.field, d.value, d.alt_value FROM airports_aip_summary s, airports a, airports_aip_details d WHERE s.ident = a.ident AND s.immigration == 1 AND d.ident = a.ident AND d.field LIKE "Custom%"')
    for row in rows:
        if row['ident'].startswith('LF'):
            continue
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
        "EH": simplekml.Color.maroon, # Netherlands (Maroon)
        "EB": simplekml.Color.black,   # Belgium (Black)
        "LS": simplekml.Color.red,   # Switzerland (Red)
        "LO": simplekml.Color.white,   # Austria (Red)
        "ES": simplekml.Color.yellow,   # Sweden (Blue)
        "EN": simplekml.Color.blue,   # Norway (Crimson)
        "EK": simplekml.Color.red,   # Denmark (Red)
        "EF": simplekml.Color.white,   # Finland (Blue)
        "LG": simplekml.Color.blue,   # Greece (Blue)
        "LP": simplekml.Color.green,   # Portugal (Green)
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
    for (one,row) in map.items():
        identprefix = row['ident'][:2]
        if identprefix not in count:
            count[identprefix] = 0
            if identprefix not in icao_to_color:
                print(f'Unknown {identprefix}')
                stylesmap = simplekml.StyleMap()
                stylesmap.normalstyle.labelstyle.color = simplekml.Color.blue
                stylesmap.normalstyle.iconstyle.color = simplekml.Color.blue
                stylesmap.normalstyle.iconstyle.icon.href=iconurl
                stylesmap.highlightstyle.iconstyle.color = simplekml.Color.red
                stylesmap.highlightstyle.labelstyle.color = simplekml.Color.red
                stylesmap.highlightstyle.iconstyle.icon.href=iconurl
            else:
                print(f'Prefix  {identprefix} {icao_to_color[identprefix]}')
                stylesmap = simplekml.StyleMap()
                stylesmap.normalstyle.labelstyle.color = icao_to_color[identprefix]
                stylesmap.normalstyle.iconstyle.color = icao_to_color[identprefix]
                stylesmap.normalstyle.iconstyle.icon.href=iconurl
                stylesmap.highlightstyle.iconstyle.color = icao_to_color[identprefix]
                stylesmap.highlightstyle.labelstyle.color = icao_to_color[identprefix]
                stylesmap.highlightstyle.iconstyle.icon.href=iconurl
            styles[identprefix] = stylesmap

        count[identprefix] += 1
        if smallFile and count[identprefix] > 2:
            continue

        p = kml.newpoint(name='POE.'+row['ident'])
        p.coords = [(row['longitude'], row['latitude']+lat_offset)]
        stylemap = styles[identprefix]
        p.stylemap = stylemap

    kml.save('PointOfEntry.kml')
buildPPF()
