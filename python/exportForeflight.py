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
    iconurl = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

    icao_to_color = {
        "LF": "#EEEEEE",  # France (White)
        "EG": "#021f66",  # United Kingdom (Red)
        "ED": "#f6c800",  # Germany (Black)
        "LE": "#FF6600",  # Spain (Orange)
        "LI": "#009246",   # Italy (Green)
        "EH": "#AE1C28", # Netherlands (Maroon)
        "EB": "#000000",   # Belgium (Black)
        "LS": "#f70000",   # Switzerland (Red)
        "LO": "#d81013",   # Austria (Red)
        "ES": "#0051BA",   # Sweden (Blue)
        "EN": "#EF3340",   # Norway (Crimson)
        "EK": "#C60C30",   # Denmark (Red)
        "EF": "#003580",   # Finland (Blue)
        "LG": "#0D5EAF",   # Greece (Blue)
        "LP": "#009639",   # Portugal (Green)
        "EI": "#039547",    # Ireland (Green)
        "EP": "#DC143C",   # Poland (Crimson)
        "LH": "#ED3340",   # Hungary (Vivid Red)
        "LK": "#D41E35",   # Czech Republic (Red)
        "LZ": "#D52B1E",   # Slovakia (Red)
        "LJ": "#FFFFFF",   # Slovenia (White)
        "LD": "#003DAA",   # Croatia (Blue)
        "LR": "#0055A4",   # Romania (Blue)
        "LB": "#008751",   # Bulgaria (Green)
        "LT": "#E30A17",   # Turkey (Red)
    }

    lat_offset = 0.0045  # about 500m
    count={}
    for (one,row) in map.items():
        identprefix = row['ident'][:2]
        if identprefix not in count:
            count[identprefix] = 0
            if identprefix not in icao_to_color:
                print(f'Unknown {identprefix}')
            else:
                print(f'Prefix  {identprefix} {icao_to_color[identprefix]}')
        count[identprefix] += 1
        if False and count[identprefix] > 2:
            continue

        p = kml.newpoint(name='POE.'+row['ident'])
        p.coords = [(row['longitude'], row['latitude']+lat_offset)]
        if row['ident'][:2] in icao_to_color:
            c = icao_to_color[row['ident'][:2]]
            p.stylemap.normalstyle.labelstyle.color = c
            p.stylemap.normalstyle.iconstyle.icon.href=iconurl
            p.stylemap.normalstyle.iconstyle.color = c
            p.stylemap.highlightstyle.iconstyle.color = simplekml.Color.red
            p.stylemap.highlightstyle.labelstyle.color = simplekml.Color.red
        else:
            p.stylemap.normalstyle.iconstyle.icon.href=iconurl
            p.stylemap.normalstyle.labelstyle.color = simplekml.Color.blue
            p.stylemap.highlightstyle.labelstyle.color = simplekml.Color.red
            p.stylemap.normalstyle.iconstyle.color = simplekml.Color.blue
            p.stylemap.highlightstyle.iconstyle.color = simplekml.Color.red


    kml.save('PointOfEntry.kml')
buildPPF()
