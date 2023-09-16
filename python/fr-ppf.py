#!/usr/bin/env python3

# This script is used to import the french PPR into the airports.db database
# the source for the list is https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000043547009


import sys
import csv
import sqlite3
import re
from pprint import pprint

db = sqlite3.connect('airports.db')
c = db.cursor()
rows = c.execute('SELECT ident,name FROM airports WHERE ident LIKE "LF%"')
map = {}
for row in rows:
    map[row[1]] = {'ident':row[0], 'name':row[1]}

def find_ident(name):
    for k in map:
        if name in k:
            return map[k]

    simplified = name.replace(' ', '').replace('-', '')
    for k in map:
        simplifiedk = k.replace(' ', '').replace('-', '')
        if simplified in simplifiedk:
            return map[k]

    subs = [x for x in re.split('[- ]+', name) if len(x) > 3]
    maxfound = 0
    found = None
    for k in map:
        count = 0
        for sub in subs:
            if sub in k:
                count += 1
        if count > maxfound:
            found = map[k]
            maxfound = count

    return found

def score(needle, haystack):
    subs = [x for x in re.split('[- ]+', needle) if len(x) > 3]
    count = 0
    for sub in subs:
        if sub in haystack:
            count += 1
    return count 

with open('fr-ppf-2023.csv') as csvfile:
    ppfcsv = csv.reader(csvfile)
    ppf = {}
    ppfident = {}
    for row in ppfcsv:
        name = row[1]
        if name == 'name':
            continue
        if 'Tropez' in name:
            # special case, as saint tropez is not matching
            found = find_ident('La Môle Airport')
        else:
            found = find_ident(name)
        res = {'ppfname': name, 'restriction': row[2], 'rank':row[0]}
        if found:
            res.update(found)
            ident = res['ident']
            if ident in ppfident:
                other = ppfident[ident]
                if score(res['ppfname'], res['name']) > score(other['ppfname'], res['name']):
                    ppfident[ident] = res
                    ppf[name] = res
                else:
                    print( f'not found (conflict) {row[0]}, {row[1]}, {find_ident(row[1])}' )
            else:
                ppf[name] = res
                ppfident[ident] = res
        else:
            print( f'not found {row[0]}, {row[1]}, {find_ident(row[1])}' )


c.execute('DROP TABLE IF EXISTS frppf');
c.execute('CREATE TABLE frppf (ident TEXT PRIMARY KEY, name TEXT, ppfname TEXT, restriction TEXT, rank INTEGER)');
for k in ppf:
    res = ppf[k]
    c.execute('INSERT INTO frppf VALUES (?,?,?,?,?)', (res['ident'], res['name'], res['ppfname'], res['restriction'], res['rank']))
db.commit()

db.close()

