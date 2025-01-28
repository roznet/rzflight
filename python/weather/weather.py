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
from metar_taf_parser.model.enum import CloudQuantity, WeatherChangeType
from metar_taf_parser.model.model import TAFTrend

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
        if "NIL=" in metar_string:
            return None
        metar_string = re.sub(r'^(?:METAR COR|METAR)\s+', '', metar_string.strip())
        parser = MetarParser()
        metar = parser.parse(metar_string)
        return metar
    except Exception as e:
        print(f"Error parsing METAR: {e}")
        return None

def parse_taf(taf_string):
    """
    Parse a TAF string using metar_taf_parser.
    
    Args:
        taf_string: String containing the TAF report
    
    Returns:
        TAF object if parsing successful, None if NIL TAF or parsing fails
    """
    try:
        if "NIL=" in taf_string:
            return None
        parser = TAFParser()
        taf = parser.parse(taf_string)
        return taf
    except Exception as e:
        print(f"Error parsing TAF: {e}")
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
    if not hasattr(metar.wind, 'degrees') or not hasattr(metar.wind, 'speed'):
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
        if wx['metar'] and hasattr(wx['metar'], 'visibility') and wx['metar'].visibility:
            vis_str = wx['metar'].visibility.distance 
        else:
            vis_str = "unknown"
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
        current_taf = None
        for row in rows:
            if row[1] == "TAF":
                current_taf = parse_taf(row[2])
                if current_taf:
                    print(f"\nTAF: {row[0]} {row[2]}")
            elif row[1] == "METAR":  # Process all METARs for runway winds
                if "NIL=" in row[2]:
                    continue
                wx = get_metar_flight_category(row[2]) if show_category else {"metar": parse_metar(row[2])}
                
                # Print METAR line
                metar_line = f"\nMETAR: {row[0]}"
                if show_category:
                    metar_line += f" {format_weather_category(wx, runways)}"
                elif runways:
                    wind_components = get_runway_winds(wx["metar"], runways)
                    if wind_components:
                        metar_line += f" [{' | '.join(wind_components)}]"
                metar_line += f" {row[2]}"
                print(metar_line)
                
                # If we have a current TAF, show the comparison
                if current_taf:
                    metar_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    prevailing = create_taf_trend_from_taf(current_taf)
                    if prevailing:  # Only proceed if we have valid prevailing conditions
                        relevant = []
                        
                        # Find relevant TAF sections
                        for trend in current_taf.trends:
                            if is_time_in_validity_period(metar_time, trend.validity):
                                if trend.type == WeatherChangeType.BECMG:
                                    new_prevailing = create_taf_trend_from_taf(prevailing, trend)
                                    if new_prevailing:
                                        prevailing = new_prevailing
                                else:
                                    relevant.append(trend)
                            elif is_after_validity_end(metar_time, trend.validity):
                                if trend.type == WeatherChangeType.BECMG:
                                    new_prevailing = create_taf_trend_from_taf(prevailing, trend)
                                    if new_prevailing:
                                        prevailing = new_prevailing
                        
                        # Get weather category for METAR
                        metar_wx = get_flight_category(wx["metar"])
                        
                        # Compare with prevailing conditions
                        prevailing_wx = get_flight_category(prevailing)
                        comp = compare_weather_categories(metar_wx, prevailing_wx)
                        comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                        applicable_symbol = '*' if comp == 0 or comp == 1 else ' '

                        print(f"TAF{applicable_symbol}:   {comp_symbol} {format_taf_trend(prevailing)}")
                        
                        # Compare with each relevant trend
                        for trend in relevant:
                            trend_wx = get_flight_category(trend)
                            comp = compare_weather_categories(metar_wx, trend_wx)
                            comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                            applicable_symbol = '*' if comp == 0 or comp == 1 else ' '
                            print(f"   {applicable_symbol}:   {comp_symbol} {format_taf_trend(trend)}")
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

def format_taf_trend(trend):
    """
    Format a TAF trend into a readable string.
    
    Args:
        trend: TAFTrend object from metar_taf_parser
    
    Returns:
        str: Formatted string with validity period and weather conditions
    """
    components = []
    if trend.validity.start_day == trend.validity.end_day:
        validity = f"{trend.validity.start_day:02d}/{trend.validity.start_hour:02d}:00-{trend.validity.end_hour:02d}:00"
    else:
        validity = f"{trend.validity.start_day:02d}/{trend.validity.start_hour:02d}:00-{trend.validity.end_day:02d}/{trend.validity.end_hour:02d}:00"

    components.append(validity)
    if hasattr(trend, 'probability') and trend.probability:
        probability = f" PROBA{trend.probability}"
        components.append(probability)
    if hasattr(trend,'type') and  trend.type:
        # Get the string value from the enum instead of the enum object itself
        type_str = trend.type.value
        components.append(type_str)
    
    # Get weather category if possible
    wx = get_flight_category(trend)
    category_str = format_weather_category(wx)
    components.append(category_str)
    return " ".join(components)


def get_comparison_reports(icao, datetime_input, show_category=False, runways=None, db_name="metar_taf.db"):
    """Get TAF sections alongside corresponding METARs."""
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

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
        print("\nComparison of METARs with TAF:")
        taf = parse_taf(taf_row[1])
        if taf:
            for row in metar_rows:
                if "METAR" in row[1]:
                    wx = get_metar_flight_category(row[1]) if show_category else {"metar": parse_metar(row[1])}
                    
                    # Format METAR line
                    metar_line = f"{row[0]}"
                    if show_category:
                        metar_line += f" {format_weather_category(wx, runways)}"
                    elif runways:
                        wind_components = get_runway_winds(wx["metar"], runways)
                        if wind_components:
                            metar_line += f" [{' | '.join(wind_components)}]"
                    metar_line += f" {row[1]}"
                    print(f"\nMETAR: {metar_line}")
                    
                    # Find and display relevant TAF section
                    metar_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    prevailing = create_taf_trend_from_taf(taf)
                    if prevailing:
                        relevant = []
                        for trend in taf.trends:
                            if is_time_in_validity_period(metar_time, trend.validity):
                                if trend.type == WeatherChangeType.BECMG:
                                    new_prevailing = create_taf_trend_from_taf(prevailing, trend)
                                    if new_prevailing:
                                        prevailing = new_prevailing
                                else:
                                    relevant.append(trend)
                        
                        # Get weather category for METAR
                        metar_wx = get_flight_category(wx["metar"])
                        
                        # Compare with prevailing conditions
                        prevailing_wx = get_flight_category(prevailing)
                        comp = compare_weather_categories(metar_wx, prevailing_wx)
                        comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                        print(f"TAF:   {comp_symbol} {format_taf_trend(prevailing)}")
                        
                        # Compare with each relevant trend
                        for trend in relevant:
                            trend_wx = get_flight_category(trend)
                            comp = compare_weather_categories(metar_wx, trend_wx)
                            comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                            print(f"  +:   {comp_symbol} {format_taf_trend(trend)}")
                
    else:
        print("\nNo METARs found in the specified time range.")

def is_time_in_validity_period(check_time, validity):
    """
    Check if a given time falls within a TAF validity period.
    
    Args:
        check_time: datetime object to check
        validity: TAF validity object with start_day, start_hour, end_day, end_hour
    
    Returns:
        bool: True if time falls within validity period, False otherwise
    """
    # Create datetime objects for trend start and end times
    trend_start = datetime(
        check_time.year,
        check_time.month,
        validity.start_day,
        validity.start_hour,
        tzinfo=check_time.tzinfo
    )
    trend_end = datetime(
        check_time.year,
        check_time.month,
        validity.end_day,
        validity.end_hour,
        tzinfo=check_time.tzinfo
    )
    
    # Handle case where trend ends in next month
    if trend_end < trend_start:
        if check_time < trend_start:
            # If check_time is before start, move start back one month
            if trend_start.month == 1:
                trend_start = trend_start.replace(year=trend_start.year-1, month=12)
            else:
                trend_start = trend_start.replace(month=trend_start.month-1)
        else:
            # If check_time is after start, move end forward one month
            if trend_end.month == 12:
                trend_end = trend_end.replace(year=trend_end.year+1, month=1)
            else:
                trend_end = trend_end.replace(month=trend_end.month+1)
    
    return trend_start <= check_time <= trend_end

def is_after_validity_end(check_time, validity):
    """
    Check if a given time is after a TAF validity period end.
    
    Args:
        check_time: datetime object to check
        validity: TAF validity object with end_day, end_hour
    
    Returns:
        bool: True if time is after validity end, False otherwise
    """
    # Create datetime object for trend end time
    trend_end = datetime(
        check_time.year,
        check_time.month,
        validity.end_day,
        validity.end_hour,
        tzinfo=check_time.tzinfo
    )
    
    # Handle case where trend ends in next month
    if trend_end.day < check_time.day:
        if trend_end.month == 12:
            trend_end = trend_end.replace(year=trend_end.year+1, month=1)
        else:
            trend_end = trend_end.replace(month=trend_end.month+1)
    
    return check_time > trend_end

def create_taf_trend_from_taf(taf, trend = None):
    """
    Create a TAFTrend object from a TAF object by copying matching non-None attributes.
    Only copies attributes that don't start with underscore.
    
    Args:
        trend: Existing TAFTrend object to update
        taf: TAF object from metar_taf_parser
    
    Returns:
        TAFTrend: Updated TAFTrend object with copied attributes
    """
    # Handle NIL TAFs
    if not taf or getattr(taf, 'nil', False):
        return None

    # Get all public attributes of the TAFTrend object
    new_trend = TAFTrend(weather_change_type=trend.type if trend else None)

    trend_attrs =  ['validity', 'wind', 'visibility', 'cavok', 'probability', 'wind_shear','vertical_visibility']
    # For each public attribute in the trend
    for attr_name in trend_attrs:
        # Check if the TAF has the same attribute
        if hasattr(taf, attr_name):
            # Get the value from the TAF
            taf_value = getattr(taf, attr_name)
            # Only copy if the value is not None
            if taf_value is not None:
                setattr(new_trend, attr_name, taf_value)
        # if trend overrides the TAF value, use the trend value
        if trend: 
            trend_attr = getattr(trend, attr_name)
            if trend_attr is not None:
                setattr(new_trend, attr_name, trend_attr)

    add_attrs = ["cloud", "icing", "turbulence", "weather_condition"]
    for attr_name in add_attrs:
        copy_from = taf
        attr_get = f'{attr_name}s' if attr_name != 'turbulence' else 'turbulence'
        attr_add = f'add_{attr_name}'
        # if trend overrides the TAF value, use the trend value
        if trend and getattr(trend, attr_get):
            copy_from = trend
        if hasattr(copy_from, attr_get):
            taf_value = getattr(copy_from, attr_get)
            if taf_value:
                for item in taf_value:
                    getattr(new_trend, attr_add)(item)
    if False:
        print("----------")
        print(f"From: {taf}")
        print(f"With: {trend}")
        print(f"To: {new_trend}")
    return new_trend

def compare_weather_categories(wx1, wx2):
    """
    Compare two weather category dictionaries returned from get_flight_category.
    
    Args:
        wx1: First weather category dictionary
        wx2: Second weather category dictionary
    
    Returns:
        int: -1 if wx1 < wx2, 0 if wx1 == wx2, 1 if wx1 > wx2
        Categories are ordered from worst to best: LIFR < IFR < MVFR < VFR
        For equal LIFR conditions, compares visibility and ceiling to determine worse conditions
    """
    # Define category order (from worst to best)
    category_order = {
        'LIFR': 0,
        'IFR': 1,
        'MVFR': 2,
        'VFR': 3,
        'Unknown': -1  # Place Unknown at the bottom
    }
    
    cat1 = wx1['category']
    cat2 = wx2['category']
    
    # Get numeric values for categories
    val1 = category_order.get(cat1, -1)
    val2 = category_order.get(cat2, -1)
    
    # If categories are different, compare them directly
    if val1 != val2:
        if val1 < val2:
            return -1
        else:
            return 1
    
    # For equal LIFR conditions, compare visibility and ceiling
    if cat1 == 'LIFR' and cat2 == 'LIFR':
        # Convert visibility to meters if in statute miles
        vis1 = wx1['visibility_meters']
        vis2 = wx2['visibility_meters']
        ceil1 = wx1['ceiling']
        ceil2 = wx2['ceiling']
        
        # If either has worse visibility
        if vis1 is not None and vis2 is not None and vis1 != vis2:
            return -1 if vis1 < vis2 else 1
            
        # If visibilities are equal or unknown, check ceiling
        if ceil1 is not None and ceil2 is not None and ceil1 != ceil2:
            return -1 if ceil1 < ceil2 else 1
    
    # If we get here, conditions are equal
    return 0

# Main script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and store METAR/TAF reports.")

    # Move optional arguments before positional arguments
    parser.add_argument("--category", "-c", action="store_true", help="Show flight category for METAR reports")
    parser.add_argument("--runway", "-r", type=str, help="Comma-separated list of runway numbers (e.g., '24,06')")
    parser.add_argument("--compare", action="store_true", help="Compare METARs with corresponding TAF sections")
    # Positional arguments last
    parser.add_argument("icao", type=str, help="The ICAO code of the airport.")
    parser.add_argument("date", type=str, help="The date in 'YYYYMMDD' format")
    parser.add_argument("time", type=str, nargs='?', help="Optional time in 'HHMM' format")

    args = parser.parse_args()

    try:
        if args.time:
            time_str = f"{args.time[:2]}:{args.time[2:]}"
            report_datetime = datetime.strptime(f"{args.date} {time_str}", "%Y%m%d %H:%M")
        else:
            report_datetime = datetime.strptime(args.date, "%Y%m%d")
        
        runways = args.runway.split(',') if args.runway else None
        initialize_database()
        if args.compare and args.time:
            get_comparison_reports(args.icao, report_datetime, args.category, runways)
        elif args.compare:
            print("\nError: --compare option requires a specific time")
        else:
            get_report(args.icao, report_datetime, args.category, runways)
    except ValueError as e:
        print(f"Error: {e}")
        print("\nPlease use:")
        print("- Date: 'YYYYMMDD' (e.g., 20250103 for January 3rd, 2025)")
        print("- Time (optional): 'HHMM' (e.g., 1430)")
        print("- Runway: --runway 24 or --runway 24,06 (comma-separated, no spaces)")
