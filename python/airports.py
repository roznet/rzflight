#!/usr/bin/env python3
# source of data https://ourairports.com/data/
#
# Run this script to create the database

import csv
import sqlite3
import urllib.request
import os


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

    def __init__(self):
        self.airportsfile = 'cache/airports.csv'
        self.runwaysfile = 'cache/runways.csv'
        self.db = sqlite3.connect('airports.db')
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
                if row['type'] != 'heliport':
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

a = Airports()
a.create()
