#!/usr/bin/env python3

import sys
import argparse
import requests
from pprint import pprint
import json
from urllib.parse import urlparse
import os
import camelot

class Autorouter:
    def __init__(self, bearer, cache, force=False):
        self.bearer = bearer
        self.cache = cache
        self.force = force

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
        if self.force:
            return None
        file = self.cacheFilePath(url,ext)
        if os.path.exists(file):
            return file
        else:
            return None

    def cachedJson(self,url):
        if self.force:
            return None
        cache = self.cacheFilePath(url,'json')
        if os.path.exists(cache):
            with open(cache) as f:
                return json.load(f)
        else:
            return None

    def json(self,url):
        rv = self.cachedJson(url)
        if rv:
            print( f'Using cached {url}')
            return rv
        
        headers = {'Authorization': f'Bearer {self.bearer}'}
        response = requests.get(self.fullUrl(url),headers=headers)
        if response.status_code == 200:
            rv = response.json()
            print(f'Writing {url} to cache')
            with open(self.cacheFilePath(url,'json'),'w') as f:
                json.dump(rv,f)
            return rv 
        else:
            print(f'Error {response.status_code} retrieving {url}')
            sys.exit(1)

    def doc(self,info): 
        docid=info['docid']
        filename=info['filename']
        basename,ext = os.path.splitext(filename)
        filename = f'docs/{basename}'

        cached = self.cachedFile(filename,'pdf')
        if cached:
            print( f'Using cached {filename}')
            return cached

        url = f'id/{docid}'
        headers = {'Authorization': f'Bearer {self.bearer}'}
        response = requests.get(self.fullUrl(url),headers=headers)
        if response.status_code == 200:
            print(f'Writing {filename} to cache')
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

    def retrieveDocList(self,api):
        url = f'airport/{self.code}'
        data = api.json(url)
        one = data[0]
        airport = one['Airport']
        doc = api.doc(airport[0])

        return doc

    def retrieveProcedures(self,api):
        url = f'procedures/{self.code}'
        cache = api.cachedJson(url)
        if cache:
            print( f'Using cached {url}')
            return cache

        dataurl = f'airport/{self.code}'
        data = api.json(dataurl)
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
            print(f'Writing {url} to cache')
            json.dump(rv,f)
        return rv

    def retrieveTable(self,api):
        url = f'aip/{self.code}'
        cache = api.cachedJson(url)
        if cache:
            print( f'Using cached {url}')
            return cache
        doc = self.retrieveDocList(api)
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

        with open(api.cacheFilePath(url,'json'),'w') as f:
            print(f'Writing {url} to cache')
            json.dump(rv,f)
        
        return rv

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

                data = {'icao':self.code,'section':section,'field': field, 'alt_field': alt_field, 'value': value, 'alt_value': alt_value}
                rv.append(data)
        return rv



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('airports', help='list of airports to query', nargs='+')
    parser.add_argument('-c', '--cache-dir', help='directory to cache files', default='cache')
    parser.add_argument('-f', '--force', help='force refresh of cache', action='store_true')
    parser.add_argument('-t', '--token', help='bearer token', required=True)
    args = parser.parse_args()

    for airport in args.airports:
        a=Airport(airport)
        api = Autorouter(args.token, args.cache_dir, args.force)
        a.retrieveTable(api)
        a.retrieveDocList(api)
        a.retrieveProcedures(api)

