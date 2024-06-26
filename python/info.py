#!/usr/bin/env python3

import sys
import argparse
import datetime
import requests
from pprint import pprint
import json
from urllib.parse import urlparse
import os
import re
import getpass
import sqlite3
import pandas as pd
import re
from io import StringIO

class Autorouter:
    def __init__(self, token, cache):
        self.token = token
        self.cache = cache
        self.checkToken()

    def checkToken(self):
        if self.token is None:
            credentialFile = os.path.join(self.cache,'credentials.json')
            self.credentials = None
            if os.path.exists(credentialFile):
                with open(credentialFile) as f:
                    credentials = json.load(f)
                    self.credentials = credentials

            if self.credentials is None:
                username = input('Username: ')
                self.credentials = {'username':username}

            print( f'Using username {self.credentials["username"]}')

            exp = datetime.datetime.fromisoformat( self.credentials.get('expiration') )
            isExpired = exp < datetime.datetime.now()
            if isExpired:
                print( f'Token expired at {exp}')
            if self.credentials.get('access_token') is None or isExpired:
                pw=getpass.getpass()
                postdata = {'client_id':self.credentials['username'],'client_secret':pw,'grant_type':'client_credentials'}
                response = requests.post('https://api.autorouter.aero/v1.0/oauth2/token',data=postdata)
                if response.status_code == 200:
                    data = response.json()
                    pprint(data)
                    self.credentials['access_token'] = data['access_token']
                    expiration = datetime.datetime.now() + datetime.timedelta(seconds=data['expires_in'])
                    self.credentials['expiration'] = expiration.isoformat()
                    pprint(self.credentials)

                    with open(credentialFile,'w') as f:
                        json.dump(self.credentials,f)
                else:
                    print(f'Error {response.status_code} retrieving token')
                    sys.exit(1)

            self.token = self.credentials['access_token']
            print(f'Using token {self.token} valid until {self.credentials["expiration"]}')


    def fullUrl(self, url):
        return f'https://api.autorouter.aero/v1.0/pams/{url}'

    def cacheFilePath(self,url,ext):
        sp = os.path.split(url)
        file=sp[-1]
        dir=os.path.join(*sp[:-1])
        if not os.path.exists(f'{self.cache}/{dir}'):
            os.makedirs(f'{self.cache}/{dir}')
        rv = f'{self.cache}/{dir}/{file}.{ext}'     
        return rv

    def cachedFile(self,url,ext):
        file = self.cacheFilePath(url,ext)
        if os.path.exists(file):
            return file
        else:
            return None

    def cachedJson(self,url):
        cache = self.cacheFilePath(url,'json')
        if os.path.exists(cache):
            with open(cache) as f:
                try:
                    return json.load(f)
                except:
                    print(f'Error parsing json for file {cache}')
                    return None
        else:
            return None

    def json(self,url):
        rv = self.cachedJson(url)
        if rv is not None:
            print( f'Using cached {url}')
            return rv

        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(self.fullUrl(url),headers=headers)
        if response.status_code == 200:
            rv = response.json()
            print(f'Retrieved and writing {url} to cache')
            with open(self.cacheFilePath(url,'json'),'w') as f:
                json.dump(rv,f)
            return rv 
        else:
            print(f'Error {response.status_code} retrieving {url}')
            sys.exit(1)

    def extractAirportDocList(self,data):
        if len(data) == 0:
            return None
        rv = [] 
        for info in data:
            icao = info['icao']
            airport = info['Airport']

            for one in airport:
                if one['section'] == 'AD 2':
                    filename = one['filename']
                    basename,ext = os.path.splitext(filename)
                    one['doccachefilename'] = f'docs/{basename}'
                    one['aipcachefilename'] = f'aip/{icao}'
                    one['icao'] = icao
                    rv.append(one)
                    break
        return rv

    def validate(self,info,required):
        for one in required:
            if one not in info:
                print(f'Error: {one} is required but missing from {info}')
                return False
        return True

    def retrieveDocFile(self,info):
        if not self.validate(info,['doccachefilename','filename','docid']):
            return None

        filename = info['doccachefilename']

        cached = self.cachedFile(filename,'pdf')
        if cached:
            print( f'Using cached {filename}')
            return cached

        docid = info['docid']
        url = f'id/{docid}'
        headers = {'Authorization': f'Bearer {self.token}'}
        response = requests.get(self.fullUrl(url),headers=headers)
        if response.status_code == 200:
            print(f'Retrieved {filename} and saving to cache')
            cached = self.cacheFilePath(filename,'pdf')
            with open(cached,'wb') as f:
                f.write(response.content)
            return cached
        else:
            print(f'Error {response.status_code} retrieving {url}')
            sys.exit(1)


class Airport:
    def __init__(self, code, env):
        self.code = code
        self.env = env
        self.api = env.api

    def __str__(self):
        return f'{self.code}'

    def __repr__(self):
        return f'{self.code}'

    def clearCache(self):
        cacheUrls = [f'airport/{self.code}',f'procedures/{self.code}',f'aip/{self.code}']

        list = [x['doccachefilename'] for x in self.cachedDocList(api)]
        cacheUrls.extend(list)
        for url in cacheUrls:
            for ext in ['json','pdf']:
                cache = self.api.cacheFilePath(url,ext)
                if os.path.exists(cache):
                    self.env.log(f'Clear cache {cache}')
                    os.remove(cache)

    def cachedDocList(self):
        url = f'airport/{self.code}'
        data = self.api.cachedJson(url)
        if data:
            return self.api.extractAirportDocList(data)
        return []

    def retrieveProcedures(self):
        url = f'procedures/{self.code}'
        cache = self.api.cachedJson(url)
        if cache is not None:
            self.env.log( f'Using cached {url}')
            return cache

        dataurl = f'airport/{self.code}'
        data = self.api.json(dataurl)
        if len(data) == 0:
            return []
        one = data[0]
        rv = []
        for section in ['Arrival','Departure','Approach']:
            lst = one[section]
            for x in lst: 
                proc = {'airport':self.code,'type':section.lower()}
                for field in ['heading']:
                    proc[field] = x[field]
                rv.append(proc)

        with open(self.api.cacheFilePath(url,'json'),'w') as f:
            print(f'Parsed {url} and saving to cache')
            json.dump(rv,f)
        return rv

    def retrieveDocList(self):
        url = f'airport/{self.code}'
        data = self.api.json(url)
        return self.api.extractAirportDocList(data)


    ###PDF Parsing
    ### These function read the AIP pdf file and return a list of dictionaries representing
    ### the different section, and fields extracted from the pages
    def parsePdfTableLI(self,doc):
        '''
        Parsing LI style table, where the table are vertical and span multiple pages
        Identify the section by looking up fields
        '''
        import camelot
        rv = []
        try:
            # for italy process more pages as they are much longer and arranged vertically
            tables = camelot.read_pdf(doc, pages='1-3')
        except:
            print( f'Error parsing {doc}')
            return None
        section = 'admin'
        for table in tables:
            one = table.df.to_dict('records')
            (proc,section) = self.processTableLI(one,section)
            rv.extend(proc)
            
        if len(rv) == 0:
            return  [{'ident':self.code,'section':'admin','field':'Observations','value':'empty file', 'alt_value':''}]

        return rv

    def parsePdfTableDefault(self,doc):
        '''
        Default PDF parsing suitable for most countries, like France, Germany, UK
        It assumes that each table has been parsed in the right expected
        Order
        '''
        import camelot
        rv = []
        try:
            tables = camelot.read_pdf(doc, pages='1-2')
        except:
            print( f'Error parsing {doc}')
            return None
        if len(tables) > 1:
            admin = tables[0].df.to_dict('records')
            operational = tables[1].df.to_dict('records')

            rv = self.processTableDefault(admin,'admin')
            rv.extend( self.processTableDefault(operational,'operational'))
            
        if len(tables) > 3:
            handling = tables[2].df.to_dict('records')
            passenger = tables[3].df.to_dict('records')

            rv.extend( self.processTableDefault(handling,'handling'))
            rv.extend( self.processTableDefault(passenger,'passenger'))
        if len(rv) == 0:
            return  [{'ident':self.code,'section':'admin','field':'Observations','value':'empty file', 'alt_value':''}]

        return rv

    def parsePdfTableLE(self,doc):
        '''
        Parsing LE style table, where the table are horizontal and span multiple pages
        '''
        print( f'Parsing {doc} as text')
        txt = f'{doc}.txt'
        if not os.path.exists(txt):
            os.system(f'ps2ascii {doc} {txt}')
        with open(txt,'r') as f:
            lines = f.readlines()

        chunks = {} 
        current = []
        section = None
        section_re = re.compile( ' +([0-9]+)\. +[A-Z]+')
        for line in lines:
            m = section_re.match(line)
            if m:
                if section and section in ['2','3','4','5']:
                    if section not in chunks:
                        one = pd.read_fwf(StringIO('\n'.join(current)))
                        #chunks[section] = ''.join(current) 
                        chunks[section] = one
                section = m.group(1)
                current = []
            else:
                current.append(line)

        rv = []

        for (index,section) in zip(['2','3','4','5'],['admin', 'operational', 'handling', 'passenger']):
            df = chunks[index]
            
            for line in df.itertuples():
                (c1,c2) = (line[1], line[-1])
                processed = False
                remarks = False
                data = None
                if type(c1) == str:
                    res1 = re.match(r'^([\w\s]+):\s(.+)',c1)
                    if res1:
                        (field,value) = res1.groups()
                        data = {'ident':self.code,'section':section,'field': field, 'alt_field': field, 'value': value, 'alt_value': value}
                        processed = True
                if data and type(c2) == str:
                    res2 = re.match(r'^([\w\s]+):\s(.+)',c2)
                    if res2:
                        (alt_field,alt_value) = res2.groups()
                        if alt_field.lower().startswith('remarks'):
                            remarks = True
                        data['alt_field'] = alt_field
                        data['alt_value'] = alt_value

                if processed and not remarks:
                    rv.append(data)
                    continue

        return rv 

    ###Table Parsing
    def processTableLI(self,table,section):
        header = None
        curfield = None
        fieldvalues = []
        rv = []
        for row in table:
            if 1 in row:
                # non '', then new field
                if row[1]:
                    fields = row[1].split('\n')
                    if len(fields) == 2:
                        field = fields[0]
                        alt_field = fields[1]
                    else:
                        field = fields[0]
                        alt_field = fields[0]

                    if 'ARP' in field:
                        section = 'admin'
                    if 'custom' in alt_field.lower():
                        section = 'operational'
                    if 'handling facilities' in alt_field.lower():
                        section = 'handling'
                    if 'hotel' in alt_field.lower():
                        section = 'passenger'

                    if curfield:
                        (old_section,old_field, old_alt_field) = curfield
                        val = '\n'.join(fieldvalues)
                        data = {'ident':self.code,'section':old_section,'field': old_field, 'alt_field': old_alt_field, 'value': val, 'alt_value': ''}
                        rv.append(data)
                    fieldvalues = []
                    curfield = (section,field,alt_field)
                
            if 2 in row:
                fieldvalues.append(row[2])

        # if leftover
        if curfield:
            (old_section,old_field, old_alt_field) = curfield
            val = '\n'.join(fieldvalues)
            data = {'ident':self.code,'section':old_section,'field': old_field, 'alt_field': old_alt_field, 'value': val, 'alt_value': ''}
            rv.append(data)
        return (rv,section)

    def processTableDefault(self,table,section):
        if self.code.startswith('LI'):
            return self.processTableLI(table,section)
        header = None
        rv = []
        for row in table:
            fieldSepLine = False
            if 1 in row:
                fields = row[1.].split(' / ')
                if len(fields) == 2:
                    field = fields[0]
                    alt_field = fields[1]
                else:
                    sp = row[1].splitlines()
                    if len(sp) == 2:
                        fieldSepLine = True
                        field = sp[0]
                        alt_field = sp[1]
                    else:
                        field = row[1]
                        alt_field = None

                if 2 in row:
                    value = row[2]
                else:
                    value = None
                if 3 in row:
                    alt_value = row[3]
                else:
                    alt_value = None
                if alt_field and not alt_value:
                    sp = value.splitlines()
                    if len(sp) % 2 == 0:
                        half = len(sp) // 2
                        value = '\n'.join(sp[:half])
                        alt_value = '\n'.join(sp[half:])
                if 3 in row and alt_value == '':
                    sp = value.splitlines()
                    if len(sp) == 2:
                        value = sp[0]
                        alt_value = sp[1]

                data = {'ident':self.code,'section':section,'field': field, 'alt_field': alt_field, 'value': value, 'alt_value': alt_value}
                rv.append(data)
        return rv


    ###API 
    def retrieveTable(self):
        '''
        Main entry function to access table data
        '''
        list = self.retrieveDocList()
        if list is None:
            return None
        for one in list:
            rv = None
            self.api.validate(one,['doccachefilename','filename','docid','authority'])
            aipurl = one['aipcachefilename']
            cache = self.api.cachedJson(aipurl)
            if cache and not self.env.force_parse_aip:
                print( f'Using cached {aipurl}')
                return cache
            doc = self.api.retrieveDocFile(one)
            if doc is None:
                print( f'No AD 2 for {self.code}')
                return None
            authority = one['authority']
            if authority == 'LEC':
                rv = self.parsePdfTableLE(doc)
            elif authority == 'LIC':
                rv = self.parsePdfTableLI(doc)
            else:
                rv = self.parsePdfTableDefault(doc)

            if rv:
                with open(self.api.cacheFilePath(aipurl,'json'),'w') as f:
                    print(f'Parsed AIP and writing {aipurl} to cache')
                    json.dump(rv,f)
            
            return rv


    def parseApproachProcedures(self):
        procs = self.retrieveProcedures()
        if procs is None:
            return

        regexps = ['.*(INSTRUMENT APPROACH CHART| IAC[ /])[- ]*','[- ]*ICAO[- ]*']
        skip = [
                'CODING TABLE',
                'INSTRUMENT APPROACH PROCEDURE', 
                'APPENDIX',
                'TRANSITION',
                'APPROACH TERRAIN CHART',
                'INITIAL APPROACH PROCEDURE']
        valid = ['APPROACH CHART', ' IAC ', ' IAC/']
        approaches = []
        for proc in procs:
            heading = proc['heading']
            icao = proc['airport']
            type = proc['type']
            if type == 'approach':
                iac = False
                for v in valid:
                    if v in heading.upper():
                        iac = True
                known = False
                for i in skip:
                    if i in heading.upper():
                        known = True
                if known and iac:
                    print( f'{icao}: SKIP ambigous {heading}')
                    continue
                if not iac:
                    if not known:
                        print( f'{icao}: SKIP {heading}')
                    continue
                rv = heading.upper()
                for r in regexps:
                    rv = re.sub(r,'',rv)
                approaches.append(rv)

        return approaches

    def rowIsField(self,row,needle):
        for f in ['field','alt_field']:
            v = row.get(f)
            if v and re.match(needle,v.lower()):
                return True
        return False
            
    def summaryFromTable(self):
        table = self.retrieveTable()
        approaches = self.parseApproachProcedures()
        
        rv = {'ident':self.code,'immigration':0,'avgas':0,'jeta1':0,'approaches':0}
        rv['approaches'] = len(approaches)

        if not table:
            return
        for row in table:

            if self.rowIsField(row,'custom|zoll\-|aduanas'):
                if row['value'] and not row['value'].lower().startswith('nil'):
                    rv['immigration'] = 1
            if self.rowIsField(row,'fuel.*type'):
                val = row['value'].lower()
                if 'avgas' in val or '100ll' in val:
                    rv['avgas'] = 1 
                if 'jet' in val or 'a1' in val:
                    rv['jeta1'] = 1
                if not rv['avgas'] and not rv['jeta1']:
                    if val and not 'nil' in val:
                        print( f'{self.code}: Unknown fuel type {val}')
        return rv


    def list(cache_dir='cache'):
        path = cache_dir+'/airport'
        files = os.listdir(path)
        rv=[]
        for one in files:
            if one.endswith('.json'):
                rv.append(one[:-5])

        return rv

class Database:
    def __init__(self, env):
        self.env = env
        self.filename = env.args.database
        self.tableDetails = f'{args.table_prefix}_details'
        self.tableSummary = f'{args.table_prefix}_summary'
        self.tableProcedures = f'runways_procedures'
        self.conn = sqlite3.connect(self.filename)
        self.cursor = self.conn.cursor()

    def tableExists(self, table):
        sql = f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table}"'
        return self.cursor.execute(sql).fetchone() is not None

    def sql_create_table_from_csv(tablename,fields,primarykey=None,knownSuffixColumnTypes={}):
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


    def createDetailsTable(self):
        #make sure table info exists or create it
        if self.tableExists(self.tableDetails):
            return

        fields = ['ident','section','field','alt_field','value','alt_value']
        sql = Database.sql_create_table_from_csv(f'{self.tableDetails}',fields)
        self.cursor.execute(sql)
        self.conn.commit()

        self.cursor.execute(f'CREATE INDEX {self.tableDetails}_index ON {self.tableDetails} (ident)')
        self.conn.commit()

    # info is a list of dict with keys (ident, section, field, value, alt_field, alt_value)
    def updateDetails(self, infos):
        if len(infos) == 0:
            return

        sample = infos[0]
        self.createDetailsTable()

        ident = sample['ident']
        self.cursor.execute(f"SELECT COUNT(*) FROM {self.tableDetails} WHERE ident=?", (ident,))
        already = self.cursor.fetchone()[0]
        if already == len(infos):
            print(f'Already have {already} records for {ident}')
            return
        if already > 0:
            print(f'Clearing {already} records for {ident} (we should have {len(infos)}')
            self.rebuildDetails(ident)
        print(f'Updating {len(infos)} records')
        sql = Database.sql_insert_table_from_csv(self.tableDetails, sample.keys())
        self.cursor.executemany(sql, infos)
        self.conn.commit()

    def rebuildDetails(self,airport):
        print(f'Clearing {self.tableDetails} for {airport}')
        self.conn.execute(f'DELETE FROM {self.tableDetails} WHERE ident=?',(airport,))
        self.conn.commit()

    def createSummaryTable(self,fields,knownSuffixColumnTypes={}):
        if self.tableExists(self.tableSummary):
            return
        sql = Database.sql_create_table_from_csv(self.tableSummary,fields,primarykey='ident',knownSuffixColumnTypes=knownSuffixColumnTypes)
        self.conn.execute(sql)
        self.conn.commit()

    def updateSummary(self, summary):
        if not summary or len(summary) == 0:
            return
        ident = summary['ident'] 
        knownSuffixColumnTypes = {x:'INT' for x in summary.keys() if x != 'ident'}
        self.createSummaryTable(summary.keys(), knownSuffixColumnTypes=knownSuffixColumnTypes)
        self.cursor.execute(f"SELECT COUNT(*) FROM {self.tableSummary} WHERE ident=?", (ident,))
        already = self.cursor.fetchone()[0]
        if already == 1:
            print(f'Already have {already} records for {ident}')
            return
        print(f'Updating summary for {ident} with {summary}')
        sql = Database.sql_insert_table_from_csv(self.tableSummary, summary.keys())
        self.cursor.execute(sql, summary)
        self.conn.commit()

    def rebuildSummary(self,airport):
        print(f'Clearing {self.tableSummary} for {airport}')
        self.conn.execute(f'DELETE FROM {self.tableSummary} WHERE ident=?',(airport,))
        self.conn.commit()

    def updateRunwayProcedures(self,airport,procedures):
        if not procedures or len(procedures) == 0:
            return
        self.cursor.execute(f'SELECT id,le_ident,he_ident FROM runways WHERE airport_ident=?',(airport,))
        runways = self.cursor.fetchall()
        if len(runways) == 0:
            print(f'No runways for {airport}')
            return

        rv = []
        for runway in runways:
            (id,le_ident,he_ident) = runway
            if self.cursor.execute(f'SELECT COUNT(*) FROM {self.tableProcedures} WHERE id=?',(id,)).fetchone()[0] > 0:
                print(f'Already have procedures for {airport} {le_ident} {he_ident}')
                continue

            has = False
            one = {'ident':airport,'id':id,'le_ident':le_ident,'he_ident':he_ident,'he_procedures':[],'le_procedures':[]}
            for procedure in procedures:
                if le_ident in procedure:
                    one['le_procedures'].append(procedure)
                    has = True
                elif he_ident in procedure:
                    one['he_procedures'].append(procedure)
                    has = True
            if has:
                one['le_procedures_count'] = len(one['le_procedures'])
                one['he_procedures_count'] = len(one['he_procedures'])
                one['le_procedures'] = json.dumps(one['le_procedures'])
                one['he_procedures'] = json.dumps(one['he_procedures'])
                rv.append(one)
        if len(rv) == 0:
            print(f'No procedures for {airport}')
            return
        if not self.tableExists(self.tableProcedures):
            print(f'Creating {self.tableProcedures}')
            knownSuffixColumnTypes = {'_count':'INT','id':'INT'}
            sql = Database.sql_create_table_from_csv(self.tableProcedures,rv[0].keys(),primarykey='id',knownSuffixColumnTypes=knownSuffixColumnTypes)
            self.conn.execute(sql)
            self.conn.commit()

        sql_insert = Database.sql_insert_table_from_csv(self.tableProcedures,rv[0].keys())
        self.cursor.executemany(sql_insert, rv)
        self.conn.commit()
            
class Environment:
    def __init__(self,args):
        self.args = args
        self.api = Autorouter(args.token, args.cache_dir)

        self.force_download = args.force
        self.force_parse_aip = args.force
        self.force_parse_procedures = args.force

        self.force_db_details = args.force
        self.force_db_summary = args.force

        self.force_parse_aip = True
        self.force_db_summary = True


    def log(self,message):
        if self.args.verbose:
            print(message)

class Command:
    def __init__(self,args):
        self.args = args
        self.env = Environment(args)

    def choices():
        all = dir(Command)
        rv = []
        for one in all:
            if one.startswith('run_'):
                rv.append(one[4:])

        return rv

    def choicesDescription():
        all = dir(Command)
        cmd = []
        for one in all:
            if one.startswith('run_'):
                name = one[4:]
                doc = getattr(Command,one).__doc__
                cmd.append( f'{name}: {doc}' )

        return ';\n'.join(cmd)

    def run(self):
        getattr(self,f'run_{self.args.command}')()

    def run_download(self):
        '''Download AIPs and procedures'''
        for airport in args.airports:
            airport = airport.strip()
            self.env.log(f'Processing {airport}')
            a=Airport(airport,self.env)
            if self.args.force:
                a.clearCache()
            a.retrieveDocList()
            a.retrieveProcedures()
            a.retrieveTable()

    def run_build(self):
        '''Build the database'''
        db = Database(self.env)
        if args.airports:
            airports = args.airports
        else:
            airports = Airport.list(args.cache_dir)

        api = self.env.api
        for airport in airports:
            a=Airport(airport,self.env)
            table = a.retrieveTable()
            if table:
                self.env.log(f'Building db for {airport}')
                if self.env.force_db_details:
                    db.rebuildDetails(airport)
                db.updateDetails(table)
            else:
                self.env.log(f'No info to build {airport}')

            approaches = a.parseApproachProcedures()
            db.updateRunwayProcedures(airport,approaches)
            if self.env.force_db_summary:
                db.rebuildSummary(airport)
            summary = a.summaryFromTable()
            db.updateSummary(summary)

    def run_list(self):
        '''List summary for airports'''
        api = self.env.api
        all = []
        if args.airports:
            airports = args.airports
        else:
            airports = Airport.list(args.cache_dir)
        for i in airports:
            a = Airport(i,self.env)
            p = a.summaryFromTable()
            all.append( p ) 

        df = pd.DataFrame(all)
        print(df)

    def run_show(self):
        '''Detail information for an airport'''
        for one in self.args.airports:
            a = Airport(one,self.env)
            df = pd.DataFrame(a.retrieveTable())
            print(df[['section','field','value','alt_field','alt_value']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', help=Command.choicesDescription(), choices=Command.choices())
    parser.add_argument('airports', help='list of airports to query', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='directory to cache files', default='cache')
    parser.add_argument('-f', '--force', help='force refresh of cache', action='store_true')
    parser.add_argument('-v', '--verbose', help='verbose output', action='store_true')
    parser.add_argument('-t', '--token', help='bearer token')
    parser.add_argument('-d', '--database', help='database file', default='airports.db')
    parser.add_argument('--table-prefix', help='table name to create', default='airports_aip')
    args = parser.parse_args()

    cmd = Command(args)
    cmd.run()


