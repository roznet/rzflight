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
from metar_taf_parser.parser.parser import MetarParser, TAFParser
from metar_taf_parser.model.enum import CloudQuantity

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

def parse_metar(metar_string):
    try: 
        metar_string = re.sub(r'^(?:METAR COR|METAR)\s+', '', metar_string.strip())
        parser = MetarParser()
        metar = parser.parse(metar_string)
        return metar
    except Exception as e:
        print(f"Error parsing METAR: {e}")
        return None


def get_metar_flight_category(metar_string):
    """
    Determine flight category (VFR, MVFR, IFR, LIFR) from METAR string using metar_taf_parser
    
    Returns a dictionary containing:
    - category: Flight category (VFR, MVFR, IFR, LIFR, Unknown)
    - visibility_meters: Visibility in meters (None if not found)
    - visibility_sm: Visibility in statute miles (None if not found)
    - ceiling: Ceiling height in feet (None if not found)
    """

    metar = parse_metar(metar_string)
    if metar:
        return get_flight_category(metar)
    else:
        return {
            "category": "Unknown",
            "visibility_meters": None,
            "visibility_sm": None,
            "ceiling": None,
            "metar": None
        }

def get_flight_category(metar_object):
    """
    Determine flight category (VFR, MVFR, IFR, LIFR) from METAR string using metar_taf_parser
    
    Returns a dictionary containing:
    - category: Flight category (VFR, MVFR, IFR, LIFR, Unknown)
    - visibility_meters: Visibility in meters (None if not found)
    - visibility_sm: Visibility in statute miles (None if not found)
    - ceiling: Ceiling height in feet (None if not found)
    """
    metar = metar_object
    
    # Get visibility in meters and statute miles
    visibility_meters = None
    visibility_sm = None
    if metar.visibility:
        vis_str = metar.visibility.distance
        # Remove any "greater than" prefix and strip whitespace
        vis_str = vis_str.replace('>', '').strip()
        
        # Extract numeric value and unit
        match = re.match(r'(\d+(?:\.\d+)?)\s*(SM|km|m)?', vis_str)
        if match:
            value = float(match.group(1))
            unit = match.group(2) or 'm'  # Default to meters if no unit specified
            
            # Convert to meters first
            if unit == 'SM':
                visibility_meters = int(value * 1609.34)
                visibility_sm = value
            elif unit == 'km':
                visibility_meters = int(value * 1000)
                visibility_sm = visibility_meters * 0.000621371
            else:  # meters
                visibility_meters = int(value)
                visibility_sm = visibility_meters * 0.000621371

    # Get ceiling from cloud layers
    ceiling = None
    if metar.clouds:
        for cloud in metar.clouds:
            if cloud.quantity in [CloudQuantity.BKN, CloudQuantity.OVC] and (ceiling is None or cloud.height < ceiling):
                ceiling = cloud.height 
    
    if metar.cavok:
        visibility_meters = 10000
        visibility_sm = 6.21371
        ceiling = None
    
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
        "ceiling": ceiling,
        "metar": metar
    }
    

def calculate_wind_components(runway_heading, wind_direction, wind_speed, gust_speed=None):
    """
    Calculate headwind/tailwind and crosswind components for a given runway and wind.
    
    Args:
        runway_heading: Runway heading in degrees
        wind_direction: Wind direction in degrees
        wind_speed: Wind speed in knots
        gust_speed: Gust speed in knots (optional)
    
    Returns:
        tuple: (direct_wind, cross_wind, direct_gust, cross_gust) where:
            - direct_wind: Positive for headwind, negative for tailwind
            - cross_wind: Positive for wind from right, negative from left
            - direct_gust: Gust component along runway heading (None if no gusts)
            - cross_gust: Gust component across runway (None if no gusts)
    """
    import math
    
    # Convert angles to radians
    angle = math.radians(wind_direction - runway_heading)
    
    # Calculate components and round to integers
    direct_wind = int(round(wind_speed * math.cos(angle)))
    cross_wind = int(round(wind_speed * math.sin(angle)))
    
    # Calculate gust components if gust speed is provided
    direct_gust = None
    cross_gust = None
    if gust_speed is not None:
        direct_gust = int(round(gust_speed * math.cos(angle)))
        cross_gust = int(round(gust_speed * math.sin(angle)))
    
    return (direct_wind, cross_wind, direct_gust, cross_gust)

def format_wind_components(runway, direct_wind, cross_wind, direct_gust=None, cross_gust=None):
    """Format wind components into a display string."""
    direct_type = "HEAD" if direct_wind >= 0 else "TAIL"
    cross_type = "RIGHT" if cross_wind >= 0 else "LEFT"
    
    # Format direct wind with gusts if present
    if direct_gust is not None:
        direct_str = f"{abs(direct_wind)}G{abs(direct_gust)}"
    else:
        direct_str = str(abs(direct_wind))
    
    # Format cross wind with gusts if present
    if cross_gust is not None:
        cross_str = f"{abs(cross_wind)}G{abs(cross_gust)}"
    else:
        cross_str = str(abs(cross_wind))
    
    return f"RWY{runway:02d}: {direct_str}kt {direct_type} | {cross_str}kt {cross_type}"

def get_runway_winds(metar, runways):
    """Get wind components for each runway from METAR."""
    if not metar.wind:
        return []
    
    # Skip if wind is variable direction or missing speed
    if not hasattr(metar.wind, 'direction') or not hasattr(metar.wind, 'speed'):
        return []
    # Convert wind direction and speed to integers
    # the direction is in degrees, the speed is in knots
    try:
        wind_dir = int(metar.wind.degrees)
        wind_speed = int(metar.wind.speed)
        gust_speed = int(metar.wind.gust) if metar.wind.gust else None
    except (ValueError, TypeError):
        print(f"Error parsing wind: {metar.wind}")
        return []  # Return empty list if conversion fails
    
    # Calculate for each runway
    results = []
    for rwy in runways:
        rwy_heading = int(rwy) * 10  # Convert runway number to heading
        direct, cross, direct_gust, cross_gust = calculate_wind_components(
            rwy_heading, wind_dir, wind_speed, gust_speed)
        results.append(format_wind_components(
            int(rwy), direct, cross, direct_gust, cross_gust))
    
    return results

def format_weather_category(wx, runways=None):
    """Format weather category, visibility, ceiling, and runway winds into a display string."""
    # Start with the existing weather category format
    if wx['visibility_meters']:
        if wx['visibility_meters'] % 1000 == 0:
            vis_str = f"{wx['visibility_meters']//1000}km"
        else:
            vis_str = f"{wx['visibility_meters']}m"
    else:
        vis_str = wx['metar'].visibility.distance if wx['metar'] else "unknown"
    ceil_str = f"{wx['ceiling']}ft" if wx['ceiling'] else "unknown"
    
    # Base string
    if wx['ceiling'] == None:
        result = f"[{wx['category']} vis:{vis_str} ncd]"
    else:
        result = f"[{wx['category']} vis:{vis_str} ceil:{ceil_str}]"
    
    # Add runway winds if requested
    if runways and wx['metar']:
        wind_components = get_runway_winds(wx['metar'], runways)
        if wind_components:
            result += " " + " | ".join(wind_components)
    
    return result

def get_time_specific_reports(cursor, icao, datetime_input, show_category=False, runways=None):
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
                    wx = get_metar_flight_category(row[1])
                    print(f"{row[0]} {format_weather_category(wx, runways)} {row[1]}")
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
            if "METAR" in row[1]:  # Process all METARs for runway winds
                wx = get_metar_flight_category(row[1]) if show_category else {"metar": parse_metar(row[1])}
                if show_category:
                    print(f"{row[0]} {format_weather_category(wx, runways)} {row[1]}")
                else:
                    wind_info = ""
                    if runways:
                        wind_components = get_runway_winds(wx["metar"], runways)
                        if wind_components:
                            wind_info = " [" + " | ".join(wind_components) + "]"
                    print(f"{row[0]}{wind_info} {row[1]}")
            else:
                print(f"{row[0]} {row[1]}")
    else:
        print("\nNo METARs found in the specified time range.")

def get_daily_reports(cursor, icao, datetime_input, show_category=False, runways=None):
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
            if row[1] == "METAR":  # Process all METARs for runway winds
                wx = get_metar_flight_category(row[2]) if show_category else {"metar": parse_metar(row[2])}
                if show_category:
                    print(f"{row[0]} {format_weather_category(wx, runways)} {row[2]}")
                else:
                    wind_info = ""
                    if runways:
                        wind_components = get_runway_winds(wx["metar"], runways)
                        if wind_components:
                            wind_info = " [" + " | ".join(wind_components) + "]"
                    print(f"{row[0]}{wind_info} {row[2]}")
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

def get_report(icao, datetime_input, show_category=False, runways=None, db_name="metar_taf.db"):
    """Main function to get weather reports."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        ensure_data_exists(cursor, conn, icao, datetime_input)

        if datetime_input.strftime('%H:%M') != '00:00':
            get_time_specific_reports(cursor, icao, datetime_input, show_category, runways)
        else:
            get_daily_reports(cursor, icao, datetime_input, show_category, runways)
    finally:
        conn.close()

# Main script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and store METAR/TAF reports.")
    # Move optional arguments before positional arguments
    parser.add_argument("--category", "-c", action="store_true", help="Show flight category for METAR reports")
    parser.add_argument("--runway", "-r", type=str, help="Comma-separated list of runway numbers (e.g., '24,06')")
    # Positional arguments last
    parser.add_argument("icao", type=str, help="The ICAO code of the airport.")
    parser.add_argument("date", type=str, help="The date in 'YYYYMMDD' format")
    parser.add_argument("time", type=str, nargs='?', help="Optional time in 'HHMM' format")

    args = parser.parse_args()

    if args.time:
        time_str = f"{args.time[:2]}:{args.time[2:]}"
        report_datetime = datetime.strptime(f"{args.date} {time_str}", "%Y%m%d %H:%M")
    else:
        report_datetime = datetime.strptime(args.date, "%Y%m%d")
    
    runways = args.runway.split(',') if args.runway else None
        
    initialize_database()
    get_report(args.icao, report_datetime, args.category, runways)
