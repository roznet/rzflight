#!/usr/bin/env python3

# This script is used to import the french instrument procedure into the database
# the source for the list is from the french eAIP download, searching for file with IAC in the name `find . -name "*_IAC_*pdf"`


import sys
import json
import csv
import sqlite3
import re
from pprint import pprint

db = sqlite3.connect('airports.db')
c = db.cursor()
rows = c.execute('SELECT airport_ident as ident,id,le_ident,he_ident FROM runways WHERE ident LIKE "LF%"')
map = {}
for row in rows:
    info = {'ident':row[0], 'id':row[1],'le_ident':row[2],'he_ident':row[3], 'le_procedures':'[]', 'he_procedures':'[]', 'le_procedures_count':0, 'he_procedures_count':0} 
    if row[0] not in map:
        map[row[0]] = [info] 
    else:
        map[row[0]].append(info)

# example: 
# AD_2_LFQQ_IAC_RWY26_INA_RNAV_ILS_Z.pdf
# AD_2_LFQB_IAC_RWY35_RNP.pdf
override = {'LFAQ26': '27', 'LFAQ08': '09',
            'LFSD35':'36', 'LFSD17':'18',
            'LFOH04': '05', 'LFOH22': '23',
            'LFBF29': '30', 'LFBF11': '12',
            }
iac_re = re.compile(r'AD_2_(\w+)_IAC_RWY_?(\d+[LRC]?)[_ ]([-A-Za-z0-9_ ]+)\.pdf')

withprocs = {}
with open('fr-iac.csv') as csvfile:
    ppfcsv = csv.reader(csvfile, delimiter='/')
    ppf = {}
    ppfident = {}
    for row in ppfcsv:
        ident = row[1]
        m = iac_re.match(row[2])
        if m is None:
            #print('No match for', row[2])
            continue
        rwy = m.group(2)
        proc = m.group(3)
        # replace _ by space
        proc = proc.replace('_', ' ')
        if f'{ident}{rwy}' in override:
            rwy = override[f'{ident}{rwy}']

        if ident not in map:
            print('No runway found for', ident)
            continue
        found = False
        updated = []
        for runway in map[ident]:
            if rwy == runway['le_ident'] or rwy+'R' == runway['he_ident']:
                procs = json.loads(runway['le_procedures'])
                procs.append(f'RWY{rwy} {proc}')
                runway['le_procedures'] = json.dumps(procs)
                runway['le_procedures_count'] += 1
                found = True
            elif rwy == runway['he_ident'] or rwy+'R' == runway['le_ident']:
                procs = json.loads(runway['he_procedures'])
                procs.append(f'RWY{rwy} {proc}')
                runway['he_procedures'] = json.dumps(procs)
                runway['he_procedures_count'] += 1
                found = True
            updated.append(runway)
        if not found:
            existings = [r['le_ident'] for r in map[ident]] + [r['he_ident'] for r in map[ident]]
            print(f'No runway {rwy} found for {ident} in {existings}')
        else:
            print(f'Added {proc} to {ident} {rwy}')
            withprocs[ident] = updated

if True:
    for ident, runways in withprocs.items():
         
        c.executemany('INSERT OR REPLACE INTO runways_procedures (ident, id, le_ident, he_ident, le_procedures, he_procedures, le_procedures_count, he_procedures_count) VALUES (:ident, :id, :le_ident, :he_ident, :le_procedures, :he_procedures, :le_procedures_count, :he_procedures_count)', runways)
    db.commit()
else:
    pprint(withprocs)
