#!/usr/bin/env python3

import sqlite3
from datetime import datetime, timezone
import os
import requests
from bs4 import BeautifulSoup
import re
import argparse
import calendar
import subprocess
from pprint import pprint
def url_for_date(icao, date, format="html"):
    # first day of the month
    first_day = date.replace(day=1)
    
    # last day of the month
    last_day = date.replace(day=calendar.monthrange(date.year, date.month)[1])
    
    params = {
        'lang': 'en',
        'lugar': icao,
        'tipo': 'ALL',
        'ord': 'REV',
        'nil': 'SI',
        'fmt': format,
        'ano': first_day.year,
        'mes': first_day.month,
        'day': first_day.day,
        'hora': '00',
        'anof': last_day.year,
        'mesf': last_day.month,
        'dayf': last_day.day,
        'horaf': '23',
        'minf': '59',
        'send': 'send'
    }
    
    base_url = 'https://www.ogimet.com/display_metars2.php'
    query_string = '&'.join(f'{key}={value}' for key, value in params.items())
    return f'{base_url}?{query_string}'

# Function to fetch data from the web
def get_from_web(icao, date):
    url = url_for_date(icao, date)

    # Ensure cache directory exists
    os.makedirs('cache', exist_ok=True)
    
    # Create cache filename using ICAO and date
    cache_file = f"cache/{icao}_{date.strftime('%Y%m')}.html"
    
    # Check if cache file exists
    if not os.path.exists(cache_file):
        # Use curl to fetch the data and save directly to cache file
        try:
            print(f"Fetching data from: {url}")
            subprocess.run(['curl', '-s', '-o', cache_file, url], check=True)
        except subprocess.CalledProcessError:
            print("Failed to fetch data from the web.")
            return []
    else:
        print(f"Using cached data from: {cache_file}")

    # Read the cached file
    with open(cache_file, 'r', encoding='utf-8') as f:
        content = f.read()

    soup = BeautifulSoup(content, 'html.parser')
    tables = soup.find_all('table')
    data = []
    pattern = r"from ([A-Z]{4}),"

    for table in tables:
        # Should be a nested table, not the main outer table
        if not table.find_parent('table'):
            continue
        caption = table.find("caption")
        if not caption:
            continue
        caption_text = caption.get_text()
        match = re.search(pattern, caption_text)
        if match:
            icao = match.group(1)
            if 'METAR' in caption_text or 'TAF' in caption_text:
                rows = table.find_all("tr")
                print(f'{icao} {len(rows)}')
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    row_data = [cell.get_text() for cell in cells]

                    if len(row_data) == 3:
                        type = "METAR" if "METAR" in row_data[2] else "TAF"
                        date_time_obj = datetime.strptime(row_data[1].split("->")[0], "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
                        row_data[1] = date_time_obj
                        row_data.append(type)
                        data.append(row_data)
        else:
            print("Can't process " + caption_text)

    # Transform the parsed data into the required format
    formatted_data = [
        {
            'icao': icao,
            'report_datetime': row[1].strftime("%Y-%m-%d %H:%M:%S"),
            'report_type': row[3],
            'source_type': row[0], 
            'report_data': row[2]
        }
        for row in data
    ]
    pprint(formatted_data[:5])
    pprint(len(formatted_data))
    return formatted_data

# Function to create the database if it doesn't exist
def initialize_database(db_name="metar_taf.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # Create the main table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icao TEXT NOT NULL,
            report_datetime DATETIME NOT NULL,
            report_type TEXT NOT NULL,
            source_type TEXT NOT NULL,
            report_data TEXT NOT NULL,
            UNIQUE(icao, report_datetime, report_type)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_time_specific_reports(cursor, icao, datetime_input):
    """Get TAF and subsequent METARs for a specific time."""
    cursor.execute('''
        SELECT report_datetime, report_data
        FROM reports
        WHERE icao = ? 
        AND date(report_datetime) = date(?)
        AND report_type = 'TAF'
        AND report_datetime <= ?
        ORDER BY report_datetime DESC
        LIMIT 1
    ''', (icao, datetime_input, datetime_input))
    
    taf_row = cursor.fetchone()
    
    if not taf_row:
        print("\nNo TAF found before the specified time.")
        return
        
    print("\nMost recent TAF:")
    print(f"{taf_row[0]} {taf_row[1]}")
    
    # Get all METARs between TAF time and specified time
    cursor.execute('''
        SELECT report_datetime, report_data
        FROM reports
        WHERE icao = ? 
        AND report_type = 'METAR'
        AND report_datetime BETWEEN ? AND ?
        ORDER BY report_datetime ASC
    ''', (icao, taf_row[0], datetime_input))
    
    metar_rows = cursor.fetchall()
    
    if metar_rows:
        print("\nSubsequent METARs:")
        for row in metar_rows:
            print(f"{row[0]} {row[1]}")
    else:
        print("\nNo METARs found in the specified time range.")

def get_daily_reports(cursor, icao, datetime_input):
    """Get all reports for a specific day."""
    cursor.execute('''
        SELECT report_datetime, report_type, report_data
        FROM reports
        WHERE icao = ? 
        AND date(report_datetime) = date(?)
        ORDER BY report_datetime ASC
    ''', (icao, datetime_input))
    
    rows = cursor.fetchall()
    if rows:
        print("\nAll reports for the specified date:")
        for row in rows:
            print(f"{row[0]} {row[2]}")
    else:
        print("\nNo reports found for the specified date.")

def ensure_data_exists(cursor, conn, icao, datetime_input):
    """Check if data exists for the date and fetch if needed."""
    cursor.execute('''
        SELECT COUNT(*) 
        FROM reports 
        WHERE icao = ? AND date(report_datetime) = date(?)
    ''', (icao, datetime_input))
    
    if cursor.fetchone()[0] == 0:
        print("No data found in database for the specified date. Fetching from the web...")
        new_data = get_from_web(icao, datetime_input)
        
        cursor.executemany(
            """INSERT OR IGNORE INTO reports 
               (icao, report_datetime, report_type, source_type, report_data) 
               VALUES (:icao, :report_datetime, :report_type, :source_type, :report_data)""",
            new_data
        )
        conn.commit()

def get_report(icao, datetime_input, db_name="metar_taf.db"):
    """Main function to get weather reports."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        ensure_data_exists(cursor, conn, icao, datetime_input)

        # If time was specified (has minutes), show TAF and subsequent METARs
        if datetime_input.strftime('%H:%M') != '00:00':
            get_time_specific_reports(cursor, icao, datetime_input)
        else:
            get_daily_reports(cursor, icao, datetime_input)
    finally:
        conn.close()

# Main script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and store METAR/TAF reports.")
    parser.add_argument("icao", type=str, help="The ICAO code of the airport.")
    parser.add_argument("datetime", type=str, help="The date in 'YYYYMMDD' format.")
    parser.add_argument("--time", type=str, help="Optional time in 'HH:MM' format")

    args = parser.parse_args()

    icao_input = args.icao
    date_input = args.datetime

    try:
        # Parse the YYYYMMDD format and add time if provided
        if args.time:
            report_datetime = datetime.strptime(f"{date_input} {args.time}", "%Y%m%d %H:%M")
        else:
            report_datetime = datetime.strptime(date_input, "%Y%m%d")
            
        initialize_database()
        get_report(icao_input, report_datetime)
    except ValueError:
        print("Invalid date/time format. Please use:")
        print("- Date: 'YYYYMMDD' (e.g., 20250103 for January 3rd, 2025)")
        print("- Time (optional): 'HH:MM' (e.g., 14:30)")
