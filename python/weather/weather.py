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

def get_flight_category(metar_string):
    """
    Determine flight category (VFR, MVFR, IFR, LIFR) from METAR string
    
    Returns a dictionary containing:
    - category: Flight category (VFR, MVFR, IFR, LIFR, Unknown)
    - visibility_meters: Visibility in meters (None if not found)
    - visibility_sm: Visibility in statute miles (None if not found)
    - ceiling: Ceiling height in feet (None if not found)
    """
    
    # Check for CAVOK first
    if 'CAVOK' in metar_string:
        return {
            "category": "VFR",
            "visibility_meters": 10000,  # >10km
            "visibility_sm": 6.21371,    # >6SM
            "ceiling": None             # No significant clouds below 5000ft
        }
    
    # Extract visibility
    visibility_sm = None
    visibility_meters = None
    
    # Try US format first (SM)
    vis_pattern_sm = r'\s(\d{1,2}|\d{1,2}/\d{1,2}|M?\d{1,2})SM\s'
    vis_match = re.search(vis_pattern_sm, metar_string)
    if vis_match:
        # US format (statute miles)
        vis_str = vis_match.group(1)
        if '/' in vis_str:
            num, denom = map(int, vis_str.split('/'))
            visibility_sm = num / denom
        elif vis_str.startswith('M'):
            visibility_sm = 0  # 'M' means 'less than'
        else:
            visibility_sm = float(vis_str)
        visibility_meters = int(visibility_sm * 1609.34)  # Convert SM to meters
    else:
        # Try international format (meters)
        vis_pattern_m = r'\s(\d{4})\s'
        vis_match = re.search(vis_pattern_m, metar_string)
        if vis_match:
            visibility_meters = int(vis_match.group(1))
            if visibility_meters == 9999:
                visibility_sm = 6  # 9999 means >10km, which is >6SM
                visibility_meters = 10000  # Set to 10km
            else:
                visibility_sm = visibility_meters * 0.000621371  # Convert meters to statute miles
    
    # Extract ceiling height (lowest broken or overcast layer)
    ceiling = None
    cloud_pattern = r'(BKN|OVC)(\d{3})'
    cloud_layers = re.finditer(cloud_pattern, metar_string)
    for match in cloud_layers:
        height = int(match.group(2)) * 100  # Convert to feet
        if ceiling is None or height < ceiling:
            ceiling = height
    
    # Determine flight category
    category = "Unknown"
    if visibility_sm is not None or ceiling is not None:
        # LIFR conditions
        if (visibility_sm is not None and visibility_sm < 1) or (ceiling is not None and ceiling < 500):
            category = "LIFR"
        # IFR conditions
        elif (visibility_sm is not None and 1 <= visibility_sm < 3) or (ceiling is not None and 500 <= ceiling < 1000):
            category = "IFR"
        # MVFR conditions
        elif (visibility_sm is not None and 3 <= visibility_sm <= 5) or (ceiling is not None and 1000 <= ceiling <= 3000):
            category = "MVFR"
        # VFR conditions
        else:
            category = "VFR"
    
    return {
        "category": category,
        "visibility_meters": visibility_meters,
        "visibility_sm": visibility_sm,
        "ceiling": ceiling
    }

def format_category_info(metar_string):
    """Format flight category, visibility, and ceiling information for display."""
    wx = get_flight_category(metar_string)
    # Format visibility string
    if wx['visibility_meters']:
        if wx['visibility_meters'] % 1000 == 0:
            vis_str = f"{wx['visibility_meters']//1000}km"
        else:
            vis_str = f"{wx['visibility_meters']}m"
    else:
        vis_str = "unknown"
    ceil_str = f"{wx['ceiling']}ft" if wx['ceiling'] else "none"
    return f"[{wx['category']} vis:{vis_str} ceil:{ceil_str}]"

def get_time_specific_reports(cursor, icao, datetime_input, show_category=False):
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
        cursor.execute('''
            SELECT report_datetime, report_data
            FROM reports
            WHERE icao = ? 
            AND report_type = 'METAR'
            AND report_datetime <= ?
            AND date(report_datetime) = date(?)
            ORDER BY report_datetime DESC
            LIMIT 12
        ''', (icao, datetime_input, datetime_input))
        
        metar_rows = cursor.fetchall()
        if metar_rows:
            print("\nLast 12 METARs up to specified time:")
            for row in reversed(metar_rows):
                if show_category and "METAR" in row[1]:
                    category_info = format_category_info(row[1])
                    print(f"{row[0]} {category_info} {row[1]}")
                else:
                    print(f"{row[0]} {row[1]}")
        else:
            print("\nNo METARs found in the specified time range.")
        return
    
    print("\nMost recent TAF:")
    print(f"{taf_row[0]} {taf_row[1]}")
    
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
            if show_category and "METAR" in row[1]:
                category_info = format_category_info(row[1])
                print(f"{row[0]} {category_info} {row[1]}")
            else:
                print(f"{row[0]} {row[1]}")
    else:
        print("\nNo METARs found in the specified time range.")

def get_daily_reports(cursor, icao, datetime_input, show_category=False):
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
            if show_category and row[1] == "METAR":
                category_info = format_category_info(row[2])
                print(f"{row[0]} {category_info} {row[2]}")
            else:
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

def get_report(icao, datetime_input, show_category=False, db_name="metar_taf.db"):
    """Main function to get weather reports."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        ensure_data_exists(cursor, conn, icao, datetime_input)

        if datetime_input.strftime('%H:%M') != '00:00':
            get_time_specific_reports(cursor, icao, datetime_input, show_category)
        else:
            get_daily_reports(cursor, icao, datetime_input, show_category)
    finally:
        conn.close()

# Main script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and store METAR/TAF reports.")
    parser.add_argument("icao", type=str, help="The ICAO code of the airport.")
    parser.add_argument("date", type=str, help="The date in 'YYYYMMDD' format")
    parser.add_argument("time", type=str, nargs='?', help="Optional time in 'HHMM' format")
    parser.add_argument("--category", "-c", action="store_true", help="Show flight category for METAR reports")

    args = parser.parse_args()

    try:
        if args.time:
            time_str = f"{args.time[:2]}:{args.time[2:]}"
            report_datetime = datetime.strptime(f"{args.date} {time_str}", "%Y%m%d %H:%M")
        else:
            report_datetime = datetime.strptime(args.date, "%Y%m%d")
            
        initialize_database()
        get_report(args.icao, report_datetime, args.category)
    except ValueError:
        print("Invalid date/time format. Please use:")
        print("- Date: 'YYYYMMDD' (e.g., 20250103 for January 3rd, 2025)")
        print("- Time (optional): 'HHMM' (e.g., 1430)")
