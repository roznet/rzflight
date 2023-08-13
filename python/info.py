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
import camelot
import getpass
import sqlite3
import pandas as pd

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
                    self.credentials['access_token'] = data['access_token']
                    expiration = datetime.datetime.now() + datetime.timedelta(seconds=data['expires_in'])
                    self.credentials['expiration'] = expiration.isoformat()

                    with open(credentialFile,'w') as f:
                        json.dump(self.credentials,f)

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
    def __init__(self, code):
        self.code = code

    def __str__(self):
        return f'{self.code}'

    def __repr__(self):
        return f'{self.code}'


    def clearCache(self,api):
        cacheUrls = [f'airport/{self.code}',f'procedures/{self.code}',f'aip/{self.code}']

        list = [x['doccachefilename'] for x in self.cachedDocList(api)]
        cacheUrls.extend(list)
        for url in cacheUrls:
            for ext in ['json','pdf']:
                cache = api.cacheFilePath(url,ext)
                if os.path.exists(cache):
                    print(f'Clear cache {cache}')
                    os.remove(cache)

    def cachedDocList(self,api):
        url = f'airport/{self.code}'
        data = api.cachedJson(url)
        if data:
            return api.extractAirportDocList(data)
        return []

    def retrieveProcedures(self,api):
        url = f'procedures/{self.code}'
        cache = api.cachedJson(url)
        if cache is not None:
            print( f'Using cached {url}')
            return cache

        dataurl = f'airport/{self.code}'
        data = api.json(dataurl)
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

        with open(api.cacheFilePath(url,'json'),'w') as f:
            print(f'Parsed {url} and saving to cache')
            json.dump(rv,f)
        return rv

    def retrieveDocList(self,api):
        url = f'airport/{self.code}'
        data = api.json(url)
        return api.extractAirportDocList(data)

    def retrieveTable(self,api):
        list = self.retrieveDocList(api)
        if list is None:
            return None
        for one in list:
            api.validate(one,['doccachefilename','filename','docid'])
            aipurl = one['aipcachefilename']
            cache = api.cachedJson(aipurl)
            if cache:
                print( f'Using cached {aipurl}')
                return cache
            doc = api.retrieveDocFile(one)
        
            if doc is None:
                print( f'No AD 2 for {self.code}')
                return None
            tables = camelot.read_pdf(doc, pages='1-2')

            if len(tables) > 1:
                admin = tables[0].df.to_dict('records')
                operational = tables[1].df.to_dict('records')

                rv = self.processTable(admin,'admin')
                rv.extend( self.processTable(operational,'operational'))

            if len(tables) > 3:
                handling = tables[2].df.to_dict('records')
                passenger = tables[3].df.to_dict('records')

                rv.extend( self.processTable(handling,'handling'))
                rv.extend( self.processTable(passenger,'passenger'))

            with open(api.cacheFilePath(aipurl,'json'),'w') as f:
                print(f'Parsed AIP and writing {aipurl} to cache')
                json.dump(rv,f)
            
            return rv

    def parseApproachProcedures(self,api):
        procs = self.retrieveProcedures(api)
        if procs is None:
            return

        regexps = ['.*(INSTRUMENT APPROACH CHART| IAC )[- ]*','[- ]*ICAO[- ]*']
        skip = [
                'CODING TABLE',
                'INSTRUMENT APPROACH PROCEDURE', 
                'APPENDIX',
                'TRANSITION',
                'APPROACH TERRAIN CHART',
                'INITIAL APPROACH PROCEDURE']
        valid = ['APPROACH CHART', ' IAC ']
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

    def processTable(self,table,section):
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

    def list(cache_dir='cache'):
        path = cache_dir+'/airport'
        files = os.listdir(path)
        rv=[]
        for one in files:
            if one.endswith('.json'):
                rv.append(one[:-5])

        return rv

class Database:
    def __init__(self, args):
        self.filename = args.database
        self.conn = sqlite3.connect(self.filename)
        self.cursor = self.conn.cursor()
        self.create()    

    def tableExists(self, table):
        sql = f'SELECT name FROM sqlite_master WHERE type="table" AND name="{table}"'
        return self.cursor.execute(sql).fetchone() is None

    def create(self):
        #make sure table info exists or create it
        if self.tableExists('info'):
            self.cursor.execute('CREATE TABLE info (ident TEXT, section TEXT, field TEXT, alt_field TEXT, value TEXT, alt_value TEXT)')
            self.conn.commit()

            self.cursor.execute('CREATE INDEX info_index ON info (ident)')
            self.conn.commit()

    # info is a list of dict with keys (ident, section, field, value, alt_field, alt_value)
    def updateInfo(self, infos):
        if len(infos) == 0:
            return
        ident = infos[0]['ident']
        self.cursor.execute("SELECT COUNT(*) FROM info WHERE ident=?", (ident,))
        already = self.cursor.fetchone()[0]
        if already == len(infos):
            print(f'Already have {already} info records for {ident}')
            return
        if already > 0:
            print(f'Clearing {already} info records for {ident}')
            self.rebuildInfo(ident)
        print(f'Updating {len(infos)} info records')
        self.cursor.executemany('INSERT INTO info (ident, section, field, alt_field, value, alt_value) VALUES (:ident, :section, :field, :alt_field, :value, :alt_value)', infos)
        self.conn.commit()

    def rebuildInfo(self,airport):
        print(f'Clearing info for {airport}')
        self.conn.execute('DELETE FROM info WHERE ident=?',(airport,))
        self.conn.commit()

class Command:
    def __init__(self,args):
        self.args = args

    def choices():
        all = dir(Command)
        rv = []
        for one in all:
            if one.startswith('run_'):
                rv.append(one[4:])

        return rv

    def run(self):
        getattr(self,f'run_{self.args.command}')()

    def run_download(self):
        api = Autorouter(args.token, args.cache_dir)
        for airport in args.airports:
            airport = airport.strip()
            print(f'Processing {airport}')
            a=Airport(airport)
            if self.args.force:
                a.clearCache(api)
            a.retrieveDocList(api)
            a.retrieveProcedures(api)
            a.retrieveTable(api)

    def run_build(self):
        db = Database(args)
        if args.airports:
            airports = args.airports
        else:
            airports = Airport.list(args.cache_dir)

        api = Autorouter(args.token, args.cache_dir )
        force = args.force
        for airport in airports:
            a=Airport(airport)
            table = a.retrieveTable(api)
            if table:
                print(f'Building db for {airport}')
                if force:
                    db.rebuildInfo(airport)
                db.updateInfo(table)
            else:
                print(f'No info to build {airport}')

            procedures = a.parseApproachProcedures(api)




    def run_list(self):
        api = Autorouter(args.token, args.cache_dir )
        if args.airports:
            airports = args.airports
        else:
            airports = Airport.list(args.cache_dir)
        for i in airports:
            a = Airport(i)
            procs = a.parseApproachProcedures(api)
            pprint(procs)



    def run_show(self):
        api = Autorouter(args.token, args.cache_dir )
        for one in self.args.airports:
            a = Airport(one)
            df = pd.DataFrame(a.retrieveTable(api))
            print(df[['section','field','value']])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', help='command to run', choices=Command.choices())
    parser.add_argument('airports', help='list of airports to query', nargs='*')
    parser.add_argument('-c', '--cache-dir', help='directory to cache files', default='cache')
    parser.add_argument('-f', '--force', help='force refresh of cache', action='store_true')
    parser.add_argument('-t', '--token', help='bearer token')
    parser.add_argument('-d', '--database', help='database file', default='airports.db')
    parser.add_argument('--table', help='table name to create', default='airport_aip_info')
    args = parser.parse_args()

    cmd = Command(args)
    cmd.run()


