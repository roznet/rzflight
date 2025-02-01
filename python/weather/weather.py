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
from math import cos, radians, sin

class WeatherDatabase:
    def __init__(self, db_name="metar_taf.db", debug=False):
        self.db_name = db_name
        self.debug = debug
        self.initialize()
    
    def _debug_print(self, *args):
        """Helper method for debug printing"""
        if self.debug:
            print("\nDEBUG:", *args)
    
    def build_weather_query(self, query_type, params=None):
        """
        Build SQL query based on type of weather report needed.
        
        Args:
            query_type: String indicating type of query ('taf', 'metars_range', 'recent_metars', 'check_data')
            params: Dictionary of additional parameters (limit, use_date_check, etc.)
        """
        params = params or {}
        
        base_conditions = {
            'icao': 'icao = ?',
            'date': 'date(report_datetime) = date(?)',
            'before_time': 'report_datetime <= ?',
            'after_time': 'report_datetime >= ?',
            'report_type': 'report_type = ?'
        }
        
        queries = {
            'taf': {
                'select': 'report_datetime, report_data, report_type',
                'conditions': [
                    base_conditions['icao'],
                    base_conditions['date'],
                    base_conditions['before_time'],
                    "report_type = 'TAF'"
                ],
                'order': 'ORDER BY report_datetime DESC',
                'limit': 'LIMIT 1',
                'param_order': ['icao', 'datetime', 'datetime']
            },
            'metars_range': {
                'select': 'report_datetime, report_data, report_type',
                'conditions': [
                    base_conditions['icao'],
                    "report_type = 'METAR'",
                    'report_datetime BETWEEN ? AND ?'
                ],
                'order': 'ORDER BY report_datetime ASC',
                'param_order': ['icao', 'start_time', 'end_time']
            },
            'recent_metars': {
                'select': 'report_datetime, report_data, report_type',
                'conditions': [
                    base_conditions['icao'],
                    "report_type = 'METAR'",
                    base_conditions['before_time'],
                    base_conditions['date']
                ],
                'order': 'ORDER BY report_datetime DESC',
                'limit': f"LIMIT {params.get('limit', 12)}",
                'param_order': ['icao', 'datetime', 'datetime']
            },
            'check_data': {
                'select': 'COUNT(*)',
                'conditions': [
                    base_conditions['icao'],
                    base_conditions['date']
                ],
                'param_order': ['icao', 'datetime']
            },
            'all_reports': {
                'select': 'report_datetime, report_data, report_type',
                'conditions': [
                    base_conditions['icao'],
                    base_conditions['date']
                ],
                'order': 'ORDER BY report_datetime ASC',
                'param_order': ['icao', 'datetime']
            }
        }
        
        query_parts = queries[query_type]
        query = f"""
            SELECT {query_parts['select']}
            FROM reports
            WHERE {' AND '.join(query_parts['conditions'])}
            {query_parts.get('order', '')}
            {query_parts.get('limit', '')}
        """
        
        self._debug_print(f"Query type: {query_type}")
        self._debug_print(f"Query: {query.strip()}")
        self._debug_print(f"Param order: {query_parts['param_order']}")
        
        return query.strip(), query_parts['param_order']

    def _get_connection(self):
        """Get database connection with dictionary cursor"""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row
        return conn

    def get_taf(self, icao, datetime_input):
        """Get most recent TAF before given datetime"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query, param_order = self.build_weather_query('taf')
            params = {
                'icao': icao,
                'datetime': datetime_input
            }
            param_values = [params[p] for p in param_order]
            
            self._debug_print(f"Executing TAF query with params: {dict(zip(param_order, param_values))}")
            
            cursor.execute(query, param_values)
            result = cursor.fetchone()
            
            self._debug_print(f"Query returned: {result}")
            return result

    def get_metars(self, icao, start_time, end_time):
        """Get METARs between start and end times"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query, param_order = self.build_weather_query('metars_range')
            params = {
                'icao': icao,
                'start_time': start_time,
                'end_time': end_time
            }
            param_values = [params[p] for p in param_order]
            
            self._debug_print(f"Executing METARS query with params: {dict(zip(param_order, param_values))}")
            
            cursor.execute(query, param_values)
            result = cursor.fetchall()
            
            self._debug_print(f"Query returned {len(result)} rows")
            return result

    def get_recent_metars(self, icao, datetime_input, limit=12):
        """Get recent METARs up to datetime"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query, param_order = self.build_weather_query('recent_metars', {'limit': limit})
            params = {
                'icao': icao,
                'datetime': datetime_input
            }
            param_values = [params[p] for p in param_order]
            
            self._debug_print(f"Executing recent METARS query with params: {dict(zip(param_order, param_values))}")
            
            cursor.execute(query, param_values)
            result = cursor.fetchall()
            
            self._debug_print(f"Query returned {len(result)} rows")
            return result

    def has_data_for_date(self, icao, date):
        """Check if we have data for given ICAO and date"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query, param_order = self.build_weather_query('check_data')
            params = {
                'icao': icao,
                'datetime': date
            }
            param_values = [params[p] for p in param_order]
            
            self._debug_print(f"Executing check data query with params: {dict(zip(param_order, param_values))}")
            
            cursor.execute(query, param_values)
            result = cursor.fetchone()
            
            self._debug_print(f"Query returned: {result}")
            return result['COUNT(*)'] > 0

    def get_all_reports(self, icao, date):
        """Get all reports for a given date in chronological order"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query, param_order = self.build_weather_query('all_reports')
            params = {
                'icao': icao,
                'datetime': date
            }
            param_values = [params[p] for p in param_order]
            
            self._debug_print(f"Executing all reports query with params: {dict(zip(param_order, param_values))}")
            
            cursor.execute(query, param_values)
            result = cursor.fetchall()
            
            self._debug_print(f"Query returned {len(result)} rows")
            return result

    def initialize(self):
        """Create the database schema if it doesn't exist"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
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

    def store_reports(self, reports):
        """Store multiple weather reports"""
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT OR IGNORE INTO reports 
                (icao, report_datetime, report_type, source_type, report_data)
                VALUES (?, ?, ?, ?, ?)
            ''', [
                (report['icao'], 
                 report['report_datetime'],
                 report['report_type'],
                 report['source_type'],
                 report['report_data']) 
                for report in reports
            ])
            conn.commit()

class WeatherReportOptions:
    def __init__(self):
        self.show_category = False
        self.runways = None
        self.comparison_mode = False
        self.visibility_in_sm = False  # New option for visibility units

class WeatherReport:
    def __init__(self, db_name="metar_taf.db", debug=False, options=None):
        self.db = WeatherDatabase(db_name, debug=debug)
        self.debug = debug
        self.options = options or WeatherReportOptions()
        
    def _format_visibility(self, wx_info):
        """
        Format visibility in meters or statute miles based on options.
        For metric (default):
            - Show in meters if < 1000m
            - Show in km if >= 1000m
        For statute miles:
            - Always show in SM
        """
        if not wx_info or wx_info.get('visibility_meters') is None:
            return None

        if self.options.visibility_in_sm:
            visibility_sm = wx_info['visibility_sm']
            return f"{visibility_sm:.1f}SM"
        else:
            visibility_m = wx_info['visibility_meters']
            if visibility_m < 2000:
                return f"{visibility_m:.0f}m"
            else:
                return f"{(visibility_m/1000):.0f}km"

    def _format_weather_category(self, wx_info, runways=None, highlight=True):
        """Format weather category info for display"""
        if not wx_info:
            return ""
            
        category = wx_info["category"]
        colors = {
            "VFR": "\033[92m",    # Green
            "MVFR": "\033[94m",   # Blue
            "IFR": "\033[91m",    # Red
            "LIFR": "\033[95m"    # Magenta
        }
        DIM = "\033[2m"
        if highlight is False:
            colors = {
                "VFR": DIM,
                "MVFR": DIM,
                "IFR": DIM,
                "LIFR": DIM
            }
        reset = "\033[0m"
        
        # Basic category with color
        result = f"{colors.get(category, '')}{category}{reset}"
        
        # Add visibility and ceiling
        details = []
        if wx_info['visibility_meters'] is not None:
            # Convert visibility to meters for formatting
            vis_str = self._format_visibility(wx_info)
            details += [f"vis:{vis_str}"]
        if wx_info["ceiling"] is not None:
            details += [f"ceil:{wx_info['ceiling']}ft"]
        
        if details:
            result += f" {colors.get(category, '')}[{' '.join(details)}]{reset}"
        
        # Add runway winds if requested
        if runways and wx_info["metar"]:
            wind_components = self._get_runway_winds(wx_info["metar"], runways)
            if wind_components:
                result += f" [{' | '.join(wind_components)}]"
        
        return result

    def get_reports(self, icao, datetime_input):
        """Get weather reports based on current options"""
        # Ensure we have data
        if not self.db.has_data_for_date(icao, datetime_input):
            data = WebFetcher().get_data(icao, datetime_input)
            self.db.store_reports(data)
        
        # If no specific time provided (just a date), show all reports chronologically
        if datetime_input.strftime('%H:%M') == '00:00':
            reports = self.db.get_all_reports(icao, datetime_input)
            self._display_chronological_results(reports)
        else:
            # Get TAF data
            taf_data = self.db.get_taf(icao, datetime_input)
            if not taf_data and self.options.comparison_mode:
                print("\nNo TAF found before the specified time.")
                return
            
            # Get METAR data based on mode
            if taf_data:
                metar_data = self.db.get_metars(icao, taf_data['report_datetime'], datetime_input)
            else:
                metar_data = self.db.get_recent_metars(icao, datetime_input)
            
            # Format and display results
            self._display_chronological_results([taf_data]+metar_data)


    def _format_metar_line(self, row):
        """Format a single METAR line with optional category and runway info"""
        if "NIL=" in row['report_data']:
            return

        # Parse METAR and get weather info if needed
        metar = None
        wx_info = None
        if self.options.show_category or self.options.runways:
            metar = self._parse_metar(row['report_data'])
            if self.options.show_category:
                wx_info = self._get_weather_category(metar)

        # Build the display line
        metar_line = f"{row['report_datetime']}"
        
        if wx_info:
            metar_line += f" {self._format_weather_category(wx_info, self.options.runways)}"
        elif self.options.runways and metar:
            wind_components = self._get_runway_winds(metar, self.options.runways)
            if wind_components:
                metar_line += f" [{' | '.join(wind_components)}]"
                
        metar_line += f" {row['report_data']}"
        print(metar_line)
    def _format_taf_trend(self, trend, highlight=False):
        """
        Format a TAF trend into a readable string.
        
        Args:
            trend: TAFTrend object from metar_taf_parser
            highlight: Boolean to indicate if the line should be bold
        
        Returns:
            str: Formatted string with validity period and weather conditions
        """
        BOLD = "\033[1m"
        DIM = "\033[2m"
        RESET = "\033[0m"

        wrap = "" if highlight else DIM
        
        components = []
        if trend.validity.start_day == trend.validity.end_day:
            validity = f"{trend.validity.start_day:02d}/{trend.validity.start_hour:02d}:00-{trend.validity.end_hour:02d}:00"
        else:
            validity = f"{trend.validity.start_day:02d}/{trend.validity.start_hour:02d}:00-{trend.validity.end_day:02d}/{trend.validity.end_hour:02d}:00"
        validity = f"{wrap}{validity}{RESET}"
        components.append(validity)
        if hasattr(trend, 'probability') and trend.probability:
            probability = f"PROBA{trend.probability}"
            probability = f"{wrap}{probability}{RESET}"
            components.append(probability)
        if hasattr(trend,'type') and trend.type:
            type_str = trend.type.value
            type_str = f"{wrap}{type_str}{RESET}"
            components.append(type_str)
        
        # Get weather category if possible
        wx = self._get_weather_category(trend)
        category_str = self._format_weather_category(wx, highlight=highlight)
        components.append(category_str)
        
        result = " ".join(components)
        return result

    def _is_daily_report(self, datetime_str):
        """Check if this is a daily report (time = 00:00)"""
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime('%H:%M') == '00:00'

    def _parse_metar(self, metar_string):
        """Parse METAR string using metar_taf_parser"""
        try:
            if "NIL=" in metar_string:
                return None
            metar_string = re.sub(r'^(?:METAR COR|METAR)\s+', '', metar_string.strip())
            parser = MetarParser()
            return parser.parse(metar_string)
        except Exception as e:
            print(f"Error parsing METAR: {e}")
            return None

    def _parse_taf(self,taf_string):
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

    def _parse_visibility(self, visibility):
        """
        Parse visibility value from METAR into statute miles.
        
        Args:
            visibility: Visibility string from METAR parser
            
        Returns:
            float: Visibility in statute miles, or None if parsing fails
        """
        if not visibility:
            return None
        
        visibility_sm = None
        
        # Handle different visibility formats
        if isinstance(visibility, (int, float)):
            # Convert meters to statute miles
            visibility_sm = visibility * 0.000621371
        elif isinstance(visibility, str):
            # Parse string visibility (e.g., "1/2SM", "2 1/2SM", "M1/4SM")
            vis_str = visibility.upper().replace("SM", "").strip()
            try:
                if vis_str.startswith("M"):  # Less than
                    vis_str = vis_str[1:]  # Remove 'M'
                    visibility_sm = float(eval(vis_str)) * 0.99  # Slightly less than value
                elif "/" in vis_str:  # Fraction
                    if " " in vis_str:  # Mixed number (e.g., "2 1/2")
                        whole, frac = vis_str.split()
                        visibility_sm = float(whole) + float(eval(frac))
                    else:  # Simple fraction
                        visibility_sm = float(eval(vis_str))
                else:  # Whole number
                    visibility_sm = float(vis_str)
            except (ValueError, SyntaxError, ZeroDivisionError) as e:
                print(f"Error parsing visibility: {vis_str} - {str(e)}")
                visibility_sm = None
            
        return visibility_sm

    def _get_weather_category(self, metar_object):
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

    def _get_runway_winds(self, metar, runways):
        """Calculate runway wind components"""
        if not metar or not metar.wind or metar.wind.speed is None:
            return None
        
        wind_speed = metar.wind.speed
        wind_dir = metar.wind.direction
        
        if wind_dir is None:
            return None
        
        components = []
        for rwy in runways:
            try:
                rwy_heading = int(rwy) * 10
                wind_angle = abs(wind_dir - rwy_heading)
                if wind_angle > 180:
                    wind_angle = 360 - wind_angle
                
                # Calculate headwind/crosswind components
                headwind = round(wind_speed * cos(radians(wind_angle)))
                crosswind = round(wind_speed * sin(radians(wind_angle)))
                
                # Format the components
                components.append(f"{rwy}:{headwind:+d}/{crosswind:+d}")
            except ValueError:
                continue
        
        return components

    def _display_chronological_results(self, reports):
        """Display all reports in chronological order"""
        if not reports:
            print("\nNo reports found for this date.")
            return
        
        print("\nReports in chronological order:")
        current_taf = None
        for row in reports:
            if row['report_type'] == 'TAF':
                current_taf = self._parse_taf(row['report_data'])
                print(f"\nTAF: {row['report_datetime']} {row['report_data']}")
            else:  # METAR
                self._format_metar_line(row)
                if current_taf and self.options.comparison_mode:
                    current_metar = self._parse_metar(row['report_data'])
                    if not current_metar:
                        continue
                    metar_wx = self._get_weather_category(current_metar)
                    metar_time = datetime.strptime(row['report_datetime'], "%Y-%m-%d %H:%M:%S")
                    prevailing = self.create_taf_trend_from_taf(current_taf)
                    if prevailing:  # Only proceed if we have valid prevailing conditions
                        relevant = []
                        
                        # Find relevant TAF sections
                        for trend in current_taf.trends:
                            if self.is_time_in_validity_period(metar_time, trend.validity):
                                if trend.type == WeatherChangeType.BECMG:
                                    new_prevailing = self.create_taf_trend_from_taf(prevailing, trend)
                                    if new_prevailing:
                                        prevailing = new_prevailing
                                else:
                                    relevant.append(trend)
                            elif self.is_after_validity_end(metar_time, trend.validity):
                                if trend.type == WeatherChangeType.BECMG:
                                    new_prevailing = self.create_taf_trend_from_taf(prevailing, trend)
                                    if new_prevailing:
                                        prevailing = new_prevailing
                        
                        
                        # Compare with prevailing conditions
                        prevailing_wx = self._get_weather_category(prevailing)
                        comp = self.compare_weather_categories(metar_wx, prevailing_wx)
                        comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                        applicable_symbol = '*' if comp == 0 or comp == 1 else ' '

                        print(f"TAF{applicable_symbol}:   {comp_symbol} {self._format_taf_trend(prevailing)}")
                        
                        # Compare with each relevant trend
                        for trend in relevant:
                            trend_wx = self._get_weather_category(trend)
                            comp = self.compare_weather_categories(metar_wx, trend_wx)
                            comp_symbol = '<' if comp < 0 else ('>' if comp > 0 else '=')
                            highlight = comp == 0 or comp == 1
                            applicable_symbol = '*' if comp == 0 or comp == 1 else ' '

                            
                            print(f"   {applicable_symbol}:   {comp_symbol} {self._format_taf_trend(trend, highlight)}")

    def is_time_in_validity_period(self, check_time, validity):
        """
        Check if a given time falls within a TAF validity period.
        
        Args:
            check_time: datetime object to check
            validity: TAF validity object with start_day, start_hour, end_day, end_hour
        
        Returns:
            bool: True if time falls within validity period, False otherwise
        """
        # Adjust for hour 24 -> 0 next day
        start_day = validity.start_day
        start_hour = validity.start_hour
        end_day = validity.end_day
        end_hour = validity.end_hour
        
        if start_hour == 24:
            start_hour = 0
            start_day += 1
        if end_hour == 24:
            end_hour = 0
            end_day += 1
        
        # Create datetime objects for trend start and end times
        trend_start = datetime(
            check_time.year,
            check_time.month,
            start_day,
            start_hour,
            tzinfo=check_time.tzinfo
        )
        trend_end = datetime(
            check_time.year,
            check_time.month,
            end_day,
            end_hour,
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

    def is_after_validity_end(self, check_time, validity):
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

    def create_taf_trend_from_taf(self, taf, trend = None):
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

    def compare_weather_categories(self, wx1, wx2):
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


    # Add other helper methods as needed...

class WebFetcher:
    def __init__(self):
        self.cache_dir = 'cache'
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def get_data(self, icao, date):
        """Fetch weather data from web or cache"""
        url = self._url_for_date(icao, date)
        cache_file = self._get_cache_path(icao, date)
        
        if not os.path.exists(cache_file):
            self._fetch_from_web(url, cache_file)
        else:
            print(f"Using cached data from: {cache_file}")
        
        return self._parse_cached_data(cache_file)

    def _url_for_date(self, icao, date):
        """Generate URL for fetching weather data"""
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
            'fmt': 'html',
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

    def _get_cache_path(self, icao, date):
        """Get path for cache file"""
        return f"{self.cache_dir}/{icao}_{date.strftime('%Y%m')}.html"

    def _fetch_from_web(self, url, cache_file):
        """Fetch data from web and save to cache"""
        print(f"Fetching data from: {url}")
        try:
            subprocess.run(['curl', '-s', '-o', cache_file, url], check=True)
        except subprocess.CalledProcessError:
            print("Failed to fetch data from the web.")
            raise

    def _parse_cached_data(self, cache_file):
        """Parse cached HTML file into weather report data"""
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
        return [
            {
                'icao': icao,
                'report_datetime': row[1].strftime("%Y-%m-%d %H:%M:%S"),
                'report_type': row[3],
                'source_type': row[0], 
                'report_data': row[2]
            }
            for row in data
        ]

# Example usage in main:
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch and store METAR/TAF reports.")
    
    # Add debug option
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    # Move optional arguments before positional arguments
    parser.add_argument("--category", "-c", action="store_true", help="Show flight category for METAR reports")
    parser.add_argument("--runway", "-r", type=str, help="Comma-separated list of runway numbers (e.g., '24,06')")
    parser.add_argument("--diff", "-d", action="store_true", help="Compare METARs with corresponding TAF sections")
    parser.add_argument("--statute-miles", "-sm", action="store_true", help="Display visibility in statute miles")
    # Positional arguments last
    parser.add_argument("icao", type=str, help="The ICAO code of the airport.")
    parser.add_argument("date", type=str, help="The date in 'YYYYMMDD' format")
    parser.add_argument("time", type=str, nargs='?', help="Optional time in 'HHMM' format")

    args = parser.parse_args()

    # Parse the datetime
    if args.time:
        time_str = f"{args.time[:2]}:{args.time[2:]}"
        report_datetime = datetime.strptime(f"{args.date} {time_str}", "%Y%m%d %H:%M")
    else:
        report_datetime = datetime.strptime(args.date, "%Y%m%d")

    # Set up options
    options = WeatherReportOptions()
    options.show_category = args.category
    options.runways = args.runway.split(',') if args.runway else None 
    options.comparison_mode = args.diff
    options.visibility_in_sm = args.statute_miles

    # Create WeatherReport with options
    weather = WeatherReport(debug=args.debug, options=options)
    weather.get_reports(args.icao, report_datetime)
