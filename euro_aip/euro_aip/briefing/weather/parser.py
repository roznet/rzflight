"""Weather report parser wrapping metar_taf_parser library."""

import re
import logging
from datetime import datetime, time as dt_time
from typing import Optional, List, Dict, Any

from euro_aip.briefing.weather.models import WeatherReport, WeatherType, FlightCategory

logger = logging.getLogger(__name__)

# Meters to statute miles conversion
_METERS_TO_SM = 0.000621371


class WeatherParser:
    """
    Parse METAR and TAF reports into WeatherReport objects.

    Uses the metar_taf_parser library for the heavy lifting, then
    extracts fields into our WeatherReport dataclass.

    Example:
        report = WeatherParser.parse_metar(
            "METAR LFPG 211230Z 24015G25KT 9999 FEW040 18/09 Q1015"
        )
    """

    @classmethod
    def parse_metar(cls, raw_text: str, source: str = "") -> Optional[WeatherReport]:
        """
        Parse a METAR string.

        Args:
            raw_text: Raw METAR text (may include "METAR" or "SPECI" prefix)
            source: Data source identifier

        Returns:
            WeatherReport or None if parsing fails
        """
        from metar_taf_parser.parser.parser import MetarParser

        text = raw_text.strip()
        if not text:
            return None

        # Detect report type from prefix
        report_type = WeatherType.METAR
        clean = text
        if clean.upper().startswith("SPECI"):
            report_type = WeatherType.SPECI
            clean = clean[5:].strip()
        elif clean.upper().startswith("METAR"):
            clean = clean[5:].strip()

        # Strip COR prefix
        if clean.upper().startswith("COR"):
            clean = clean[3:].strip()

        # Skip NIL reports
        if "NIL" in clean.upper().split():
            return None

        try:
            parsed = MetarParser().parse(clean)
        except Exception as e:
            logger.debug("Failed to parse METAR: %s - %s", raw_text[:80], e)
            return None

        if parsed.nil:
            return None

        report = cls._build_report_from_metar(parsed, report_type, raw_text, source)
        # Compute flight category
        from euro_aip.briefing.weather.analysis import WeatherAnalyzer
        report.flight_category = WeatherAnalyzer.flight_category(report)
        return report

    @classmethod
    def parse_taf(cls, raw_text: str, source: str = "") -> Optional[WeatherReport]:
        """
        Parse a TAF string.

        Args:
            raw_text: Raw TAF text (must include "TAF" prefix for the library)
            source: Data source identifier

        Returns:
            WeatherReport or None if parsing fails
        """
        from metar_taf_parser.parser.parser import TAFParser

        text = raw_text.strip()
        if not text:
            return None

        # Ensure TAF prefix for the parser
        if not text.upper().startswith("TAF"):
            text = "TAF " + text

        # Skip NIL/CNL reports
        upper = text.upper()
        if " NIL" in upper or " CNL" in upper:
            return None

        try:
            parsed = TAFParser().parse(text)
        except Exception as e:
            logger.debug("Failed to parse TAF: %s - %s", raw_text[:80], e)
            return None

        if parsed.nil or parsed.canceled:
            return None

        report = cls._build_report_from_taf(parsed, raw_text, source)
        return report

    @classmethod
    def parse_auto(cls, raw_text: str, source: str = "") -> Optional[WeatherReport]:
        """
        Auto-detect METAR vs TAF and parse accordingly.

        Args:
            raw_text: Raw weather report text
            source: Data source identifier

        Returns:
            WeatherReport or None if parsing fails
        """
        text = raw_text.strip().upper()
        if text.startswith("TAF"):
            return cls.parse_taf(raw_text, source)
        return cls.parse_metar(raw_text, source)

    # --- Internal builders ---

    @classmethod
    def _build_report_from_metar(
        cls,
        parsed,
        report_type: WeatherType,
        raw_text: str,
        source: str,
    ) -> WeatherReport:
        """Build WeatherReport from a parsed Metar object."""
        obs_time = None
        if parsed.day is not None and parsed.time is not None:
            now = datetime.now(tz=None)
            try:
                obs_time = datetime(
                    now.year, now.month, parsed.day,
                    parsed.time.hour, parsed.time.minute,
                )
            except ValueError:
                pass

        wind_dir, wind_speed, wind_gust, wind_var_from, wind_var_to, wind_unit = cls._extract_wind(parsed)
        vis_m, vis_sm = cls._extract_visibility(parsed)
        ceiling = cls._extract_ceiling(parsed)
        clouds = cls._extract_clouds(parsed)
        conditions = cls._extract_weather_conditions(parsed)

        return WeatherReport(
            icao=parsed.station or "",
            report_type=report_type,
            raw_text=raw_text.strip(),
            observation_time=obs_time,
            wind_direction=wind_dir,
            wind_speed=wind_speed,
            wind_gust=wind_gust,
            wind_variable_from=wind_var_from,
            wind_variable_to=wind_var_to,
            wind_unit=wind_unit,
            visibility_meters=vis_m,
            visibility_sm=vis_sm,
            ceiling_ft=ceiling,
            cavok=parsed.cavok,
            clouds=clouds,
            weather_conditions=conditions,
            temperature=getattr(parsed, 'temperature', None),
            dewpoint=getattr(parsed, 'dew_point', None),
            altimeter=getattr(parsed, 'altimeter', None),
            source=source,
        )

    @classmethod
    def _build_report_from_taf(
        cls,
        parsed,
        raw_text: str,
        source: str,
    ) -> WeatherReport:
        """Build WeatherReport from a parsed TAF object."""
        obs_time = None
        if parsed.day is not None and parsed.time is not None:
            now = datetime.now(tz=None)
            try:
                obs_time = datetime(
                    now.year, now.month, parsed.day,
                    parsed.time.hour, parsed.time.minute,
                )
            except ValueError:
                pass

        validity_start = None
        validity_end = None
        if hasattr(parsed, 'validity') and parsed.validity:
            validity_start, validity_end = cls._extract_validity(parsed.validity)

        wind_dir, wind_speed, wind_gust, wind_var_from, wind_var_to, wind_unit = cls._extract_wind(parsed)
        vis_m, vis_sm = cls._extract_visibility(parsed)
        ceiling = cls._extract_ceiling(parsed)
        clouds = cls._extract_clouds(parsed)
        conditions = cls._extract_weather_conditions(parsed)

        # Build trends from TAF change groups
        trends = cls._build_trends(parsed, source)

        report = WeatherReport(
            icao=parsed.station or "",
            report_type=WeatherType.TAF,
            raw_text=raw_text.strip(),
            observation_time=obs_time,
            wind_direction=wind_dir,
            wind_speed=wind_speed,
            wind_gust=wind_gust,
            wind_variable_from=wind_var_from,
            wind_variable_to=wind_var_to,
            wind_unit=wind_unit,
            visibility_meters=vis_m,
            visibility_sm=vis_sm,
            ceiling_ft=ceiling,
            cavok=parsed.cavok,
            clouds=clouds,
            weather_conditions=conditions,
            validity_start=validity_start,
            validity_end=validity_end,
            trends=trends,
            source=source,
        )

        # Compute flight category for main TAF body
        from euro_aip.briefing.weather.analysis import WeatherAnalyzer
        report.flight_category = WeatherAnalyzer.flight_category(report)
        return report

    @classmethod
    def _build_trends(cls, parsed_taf, source: str) -> List[WeatherReport]:
        """Convert TAF change groups to nested WeatherReport list."""
        trends = []
        if not hasattr(parsed_taf, 'trends') or not parsed_taf.trends:
            return trends

        for trend in parsed_taf.trends:
            trend_type = None
            if hasattr(trend, 'type') and trend.type:
                trend_type = trend.type.name  # e.g., "BECMG", "TEMPO"

            probability = getattr(trend, 'probability', None)

            # Extract validity for this trend
            val_start = None
            val_end = None
            if hasattr(trend, 'validity') and trend.validity:
                val_start, val_end = cls._extract_validity(trend.validity)

            wind_dir, wind_speed, wind_gust, wind_var_from, wind_var_to, wind_unit = cls._extract_wind(trend)
            vis_m, vis_sm = cls._extract_visibility(trend)
            ceiling = cls._extract_ceiling(trend)
            clouds = cls._extract_clouds(trend)
            conditions = cls._extract_weather_conditions(trend)

            trend_report = WeatherReport(
                icao=parsed_taf.station or "",
                report_type=WeatherType.TAF,
                raw_text="",
                wind_direction=wind_dir,
                wind_speed=wind_speed,
                wind_gust=wind_gust,
                wind_variable_from=wind_var_from,
                wind_variable_to=wind_var_to,
                wind_unit=wind_unit,
                visibility_meters=vis_m,
                visibility_sm=vis_sm,
                ceiling_ft=ceiling,
                cavok=getattr(trend, 'cavok', False),
                clouds=clouds,
                weather_conditions=conditions,
                validity_start=val_start,
                validity_end=val_end,
                trend_type=trend_type,
                probability=probability,
                source=source,
            )

            from euro_aip.briefing.weather.analysis import WeatherAnalyzer
            trend_report.flight_category = WeatherAnalyzer.flight_category(trend_report)
            trends.append(trend_report)

        return trends

    # --- Field extraction helpers ---

    @classmethod
    def _extract_wind(cls, parsed) -> tuple:
        """Extract wind data. Returns (dir, speed, gust, var_from, var_to, unit)."""
        wind = getattr(parsed, 'wind', None)
        if not wind:
            return None, None, None, None, None, "KT"

        direction = getattr(wind, 'degrees', None)
        speed = getattr(wind, 'speed', None)
        gust = getattr(wind, 'gust', None)
        var_from = getattr(wind, 'min_variation', None)
        var_to = getattr(wind, 'max_variation', None)
        unit = getattr(wind, 'unit', 'KT') or "KT"

        return direction, speed, gust, var_from, var_to, unit

    @classmethod
    def _extract_visibility(cls, parsed) -> tuple:
        """
        Extract visibility in meters and statute miles.

        Uses safe arithmetic for fraction parsing (no eval()).

        Returns:
            (visibility_meters, visibility_sm)
        """
        if getattr(parsed, 'cavok', False):
            return 10000, 10000 * _METERS_TO_SM

        vis = getattr(parsed, 'visibility', None)
        if not vis:
            return None, None

        distance = getattr(vis, 'distance', None)
        if distance is None:
            return None, None

        vis_str = str(distance).replace('>', '').replace('<', '').strip()
        if not vis_str:
            return None, None

        vis_m = None
        vis_sm = None

        upper = vis_str.upper()

        # Check if value is in statute miles (e.g. "2SM", "1/2SM")
        if upper.endswith('SM'):
            sm_str = upper[:-2].strip()
            vis_sm = cls._safe_parse_fraction(sm_str)
            if vis_sm is not None:
                vis_m = int(vis_sm * 1609.34)
        # Check for km (e.g. "10km" from metar_taf_parser)
        elif upper.endswith('KM'):
            km_str = upper[:-2].strip()
            try:
                km_val = float(km_str)
                vis_m = int(km_val * 1000)
                vis_sm = vis_m * _METERS_TO_SM
            except ValueError:
                pass
        # Check for meters suffix (e.g. "3000m")
        elif upper.endswith('M') and not upper.endswith('SM') and not upper.endswith('KM'):
            m_str = upper[:-1].strip()
            try:
                vis_m = int(float(m_str))
                vis_sm = vis_m * _METERS_TO_SM
            except ValueError:
                pass
        else:
            # Plain number — assume meters
            try:
                vis_m = int(float(vis_str))
                vis_sm = vis_m * _METERS_TO_SM
            except ValueError:
                val = cls._safe_parse_fraction(vis_str)
                if val is not None:
                    vis_m = int(val)
                    vis_sm = vis_m * _METERS_TO_SM

        return vis_m, vis_sm

    @classmethod
    def _safe_parse_fraction(cls, text: str) -> Optional[float]:
        """
        Safely parse a fractional number string.

        Handles: "1/2", "2 1/2", "1", "0.5", "M1/4" (M = less than)

        Args:
            text: String that may contain a fraction

        Returns:
            Float value or None if unparseable
        """
        text = text.strip()
        if not text:
            return None

        # Strip "M" prefix (less than indicator)
        if text.upper().startswith("M"):
            text = text[1:].strip()

        # Handle "P" prefix (more than indicator)
        if text.upper().startswith("P"):
            text = text[1:].strip()

        try:
            # Simple float
            return float(text)
        except ValueError:
            pass

        # Mixed number: "2 1/2"
        if " " in text and "/" in text:
            parts = text.split(None, 1)
            if len(parts) == 2:
                try:
                    whole = float(parts[0])
                    frac = cls._parse_simple_fraction(parts[1])
                    if frac is not None:
                        return whole + frac
                except ValueError:
                    pass

        # Simple fraction: "1/2"
        if "/" in text:
            return cls._parse_simple_fraction(text)

        return None

    @staticmethod
    def _parse_simple_fraction(text: str) -> Optional[float]:
        """Parse a simple fraction like '1/2' or '3/4'."""
        parts = text.split("/")
        if len(parts) != 2:
            return None
        try:
            num = float(parts[0])
            den = float(parts[1])
            if den == 0:
                return None
            return num / den
        except ValueError:
            return None

    @classmethod
    def _extract_ceiling(cls, parsed) -> Optional[int]:
        """
        Extract ceiling from cloud layers.

        Ceiling is the lowest BKN (broken) or OVC (overcast) layer.

        Returns:
            Ceiling in feet, or None if no ceiling
        """
        clouds = getattr(parsed, 'clouds', None)
        if not clouds:
            return None

        try:
            from metar_taf_parser.model.enum import CloudQuantity
        except ImportError:
            return None

        ceiling = None
        for cloud in clouds:
            quantity = getattr(cloud, 'quantity', None)
            height = getattr(cloud, 'height', None)
            if quantity in (CloudQuantity.BKN, CloudQuantity.OVC) and height is not None:
                if ceiling is None or height < ceiling:
                    ceiling = height

        return ceiling

    @classmethod
    def _extract_clouds(cls, parsed) -> List[Dict[str, Any]]:
        """Extract cloud layers as list of dicts."""
        clouds = getattr(parsed, 'clouds', None)
        if not clouds:
            return []

        result = []
        for cloud in clouds:
            layer = {
                'quantity': getattr(cloud.quantity, 'name', str(cloud.quantity)) if cloud.quantity else None,
                'height': getattr(cloud, 'height', None),
                'type': getattr(cloud.type, 'name', None) if getattr(cloud, 'type', None) else None,
            }
            result.append(layer)
        return result

    @classmethod
    def _extract_weather_conditions(cls, parsed) -> List[str]:
        """Extract weather conditions as human-readable strings."""
        conditions = getattr(parsed, 'weather_conditions', None)
        if not conditions:
            return []

        result = []
        for wc in conditions:
            parts = []
            intensity = getattr(wc, 'intensity', None)
            if intensity:
                parts.append(intensity.value if hasattr(intensity, 'value') else str(intensity))
            descriptive = getattr(wc, 'descriptive', None)
            if descriptive:
                parts.append(descriptive.value if hasattr(descriptive, 'value') else str(descriptive))
            phenomenons = getattr(wc, 'phenomenons', [])
            if phenomenons:
                for p in phenomenons:
                    parts.append(p.value if hasattr(p, 'value') else str(p))
            if parts:
                result.append("".join(parts))
        return result

    @classmethod
    def _extract_validity(cls, validity) -> tuple:
        """
        Extract validity period as (start_datetime, end_datetime).

        Handles hour 24 conversion and month-crossing.
        """
        now = datetime.now(tz=None)

        start_day = getattr(validity, 'start_day', None)
        start_hour = getattr(validity, 'start_hour', None)
        start_minutes = getattr(validity, 'start_minutes', 0) or 0

        if start_day is None or start_hour is None:
            return None, None

        # Handle hour 24
        if start_hour == 24:
            start_hour = 0
            start_day += 1

        try:
            val_start = datetime(now.year, now.month, start_day, start_hour, start_minutes)
        except ValueError:
            return None, None

        # End time (may not exist for FM trends)
        end_day = getattr(validity, 'end_day', None)
        end_hour = getattr(validity, 'end_hour', None)

        if end_day is None or end_hour is None:
            return val_start, None

        if end_hour == 24:
            end_hour = 0
            end_day += 1

        try:
            val_end = datetime(now.year, now.month, end_day, end_hour)
        except ValueError:
            # Likely month-crossing: end_day is in next month
            month = now.month + 1
            year = now.year
            if month > 12:
                month = 1
                year += 1
            try:
                val_end = datetime(year, month, end_day, end_hour)
            except ValueError:
                return val_start, None

        # Handle month-crossing: if end is before start, it spans months
        if val_end < val_start:
            month = now.month + 1
            year = now.year
            if month > 12:
                month = 1
                year += 1
            try:
                val_end = datetime(year, month, end_day, end_hour)
            except ValueError:
                pass

        return val_start, val_end
