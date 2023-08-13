#!/usr/bin/env python3
# source of data https://ourairports.com/data/
#
# Run this script to create the database

import argparse
import csv
import sqlite3
import urllib.request
import os
from pprint import pprint


knownSuffixColumnTypes = {
        'id': 'INT',
        '_deg': 'REAL',
        '_ft': 'REAL',
        '_degT': 'REAL',
        }

def sql_create_table_from_csv(tablename,fields,primarykey='ident'):
    sql = 'CREATE TABLE ' + tablename + ' (\n'
    for field in fields:
        if field == primarykey:
            sql += field + ' TEXT PRIMARY KEY,\n'
        else:
            sql += field + ' ' + knownSuffixColumnTypes.get(field[-4:], 'TEXT') + ',\n'
    sql = sql[:-2] + '\n)'
    return sql

def sql_insert_table_from_csv(tablename,fields):
    sql = 'INSERT INTO ' + tablename + ' VALUES (\n'
    for field in fields:
        sql += ':' + field + ',\n'
    sql = sql[:-2] + '\n)'
    return sql

class Airports:
    def __init__(self,args):
        self.args = args
        cache = args.cache_dir
        database = args.database
        self.airportsfile = f'{cache}/airports.csv'
        self.runwaysfile = f'{cache}/runways.csv'
        self.db = sqlite3.connect(database)
        self.cur = self.db.cursor()

    def download(self):
        if not os.path.exists(self.airportsfile):
            urllib.request.urlretrieve("https://davidmegginson.github.io/ourairports-data/airports.csv", self.airportsfile)
        if not os.path.exists(self.runwaysfile):
            urllib.request.urlretrieve("https://davidmegginson.github.io/ourairports-data/runways.csv", self.runwaysfile)


    def createAirportsTable(self):
        self.cur.execute( 'DROP TABLE IF EXISTS airports' )
        self.db.commit()

        with open(self.airportsfile, encoding='utf-8-sig') as csvf:
            csvReader = csv.DictReader(csvf)

            fields = csvReader.fieldnames
            sql_create_airports = sql_create_table_from_csv('airports',fields);
            sql_insert_airports = sql_insert_table_from_csv('airports',fields);
            self.cur.execute(sql_create_airports)
            self.db.commit()

            for row in csvReader:
                if row['type'] != 'heliport' and row['type'] != 'closed':
                    self.db.execute(sql_insert_airports,row)
        self.db.commit()

    def createRunwaysTable(self):
        self.cur.execute( 'DROP TABLE IF EXISTS runways' )
        self.db.commit()
        with open(self.runwaysfile, encoding='utf-8-sig') as csvf:
            csvReader = csv.DictReader(csvf)

            fields = csvReader.fieldnames
            sql_create_runways = sql_create_table_from_csv('runways',fields);
            sql_insert_runways = sql_insert_table_from_csv('runways',fields);
            
            self.cur.execute(sql_create_runways)
            self.cur.execute( 'CREATE INDEX idx_airport_ident ON runways (airport_ident)' )
            self.db.commit()

            for row in csvReader:
                self.db.execute(sql_insert_runways,row)
        self.db.commit()

    def create(self):
        self.download()
        self.createAirportsTable()
        self.createRunwaysTable()

    def process(self):
        # https://en.wikipedia.org/wiki/Runway#Surface_type_codes

        sql = sql_create_table_from_csv('surface_types',['surface','type'])
        self.cur.execute( 'DROP TABLE IF EXISTS surface_types' )
        self.cur.execute(sql)
        self.db.commit()

        sqlinsert = sql_insert_table_from_csv('surface_types',['surface','type'])

        self.cur.execute( 'SELECT surface,count(*) FROM runways GROUP BY surface ORDER BY surface' )
        n = 0
        u = 0
        uc = 0
        specific = {'hard': ['hard','paved','pem','asfalt','tarmac','asfalt','asfalto','ashpalt','ashphalt','surface paved'], 
                    'soft': ['graas','soft']
                    }

        contains = {'hard': ['asphalt','concrete','cement'],
                    'soft': ['turf','grass','dirt','gravel','soil','sand','earth']
                    }

        startswith = {'hard': ['asp','con','apsh','bit','pav'], 
                    'soft': ['turf','grv','grav','grass','san','cla','grs','gra','gre'],
                      'water': ['wat'],
                      'snow': ['sno']
                      }
        for row in self.cur:
            surface = row[0]
            surfaceLower = surface.lower()
            type = None
            for t in contains:
                for c in contains[t]:
                    if c in surfaceLower:
                        type = t
            for t in startswith:
                for s in startswith[t]:
                    if surfaceLower.startswith(s):
                        type = t
            if type is None:
                for t in specific:
                    if surfaceLower in specific[t]:
                        type = t

            n += 1
            if type is None:
                u += 1
                uc += row[1]
                print('Unknown surface type: ' + surface + ' (' + str(row[1]) + ')')
                type = 'other'

            self.db.execute(sqlinsert,{'surface': surface, 'type': type})
        self.db.commit()

        print('Total surface types: ' + str(n))
        print('Unknown surface types: ' + str(u), ' (' + str(uc) + ')')

        self.airportSummary()

    def airportSummary(self):
        self.cur.execute( "SELECT a.ident,r.length_ft,t.type,r.surface FROM runways r, airports a, surface_types t WHERE a.ident = r.airport_ident AND t.surface = r.surface AND r.surface != '' AND a.continent = 'EU'")

        collect = {}
        for row in self.cur:
            (ident,length_ft,surface_type,surface) = row
            previous = collect.get(ident, {'ident': ident, 'length_ft': length_ft, 'surface_type': surface_type, 'surface': surface, 'hard': 0, 'soft': 0, 'water': 0, 'snow': 0})
           
            if previous['length_ft'] < length_ft:
                previous['length_ft'] = length_ft
                previous['surface_type'] = surface_type
            if surface_type in ['hard','soft','water','snow']:
                previous[surface_type] += 1
            collect[ident] = previous


        self.db.execute( 'DROP TABLE IF EXISTS airports_runway_summary' )
        self.db.commit()
        sql_create = sql_create_table_from_csv('airports_runway_summary',['ident','length_ft','surface_type','surface','hard','soft','water','snow'])
        self.db.execute(sql_create)
        self.db.commit()
        sql_insert = sql_insert_table_from_csv('airports_runway_summary',['ident','length_ft','surface_type','surface','hard','soft','water','snow'])
        for ident in collect:
            self.db.execute(sql_insert,collect[ident])
        self.db.commit()

class Command:
    def __init__(self, args):
        self.args = args
        self.airports = Airports(args)

    def run(self):
        method = f'run_{self.args.command}'
        getattr(self, method)()

    def run_create(self):
        self.airports.create()

    def run_process(self):
        self.airports.process()

    def run_test(self):
        print(f'test {self.args.airports}')

    def choices():
        all = dir(Command)
        rv = []
        for one in all:
            if one.startswith('run_'):
                rv.append(one[4:])
        return rv

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', help='command to execute', choices=Command.choices())
    parser.add_argument('airports', help='list of airports to query', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='directory to cache files', default='cache')
    parser.add_argument('-f', '--force', help='force refresh of cache', action='store_true')
    parser.add_argument('-d', '--database', help='database file', default='airports.db')
    args = parser.parse_args()

    command = Command(args)
    command.run()

