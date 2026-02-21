"""Weather analysis: flight categories, wind components, TAF matching."""

from datetime import datetime
from math import cos, sin, radians
from typing import Optional, List, Dict

from euro_aip.briefing.weather.models import (
    WeatherReport,
    FlightCategory,
    WindComponents,
)


class WeatherAnalyzer:
    """
    Aviation weather analysis functions.

    All methods are static/classmethod — pure functions with no state.

    Ported from rzflight-save/python/weather/weather.py with safe replacements
    for eval() and subprocess calls.
    """

    @staticmethod
    def flight_category(report: WeatherReport) -> Optional[FlightCategory]:
        """
        Determine flight category from ceiling and visibility.

        Uses FAA thresholds:
            LIFR:  visibility < 1 SM  or  ceiling < 500 ft
            IFR:   1 <= vis < 3 SM    or  500 <= ceiling < 1000 ft
            MVFR:  3 <= vis <= 5 SM   or  1000 <= ceiling <= 3000 ft
            VFR:   visibility > 5 SM  and ceiling > 3000 ft

        The worst condition (ceiling or visibility) determines the category.

        Args:
            report: WeatherReport with visibility_sm and ceiling_ft

        Returns:
            FlightCategory or None if insufficient data
        """
        vis_sm = report.visibility_sm
        ceiling = report.ceiling_ft

        # CAVOK implies VFR
        if report.cavok:
            return FlightCategory.VFR

        if vis_sm is None and ceiling is None:
            return None

        # Determine category from visibility
        vis_cat = None
        if vis_sm is not None:
            if vis_sm < 1:
                vis_cat = FlightCategory.LIFR
            elif vis_sm < 3:
                vis_cat = FlightCategory.IFR
            elif vis_sm <= 5:
                vis_cat = FlightCategory.MVFR
            else:
                vis_cat = FlightCategory.VFR

        # Determine category from ceiling
        ceil_cat = None
        if ceiling is not None:
            if ceiling < 500:
                ceil_cat = FlightCategory.LIFR
            elif ceiling < 1000:
                ceil_cat = FlightCategory.IFR
            elif ceiling <= 3000:
                ceil_cat = FlightCategory.MVFR
            else:
                ceil_cat = FlightCategory.VFR

        # Return the worst (lowest) category
        if vis_cat is not None and ceil_cat is not None:
            return min(vis_cat, ceil_cat)
        return vis_cat if vis_cat is not None else ceil_cat

    @staticmethod
    def wind_components(
        report: WeatherReport,
        runway_heading: int,
        runway_ident: str = "",
    ) -> Optional[WindComponents]:
        """
        Calculate wind components for a runway.

        Headwind is positive when wind is from ahead.
        Crosswind is positive when wind is from the right.

        Handles:
        - Basic headwind/crosswind trigonometry
        - Gust components
        - Variable wind worst-case crosswind

        Args:
            report: WeatherReport with wind data
            runway_heading: Runway heading in degrees (0-360)
            runway_ident: Runway identifier (e.g., "27L")

        Returns:
            WindComponents or None if wind data unavailable
        """
        if report.wind_speed is None:
            return None

        wind_dir = report.wind_direction
        wind_speed = report.wind_speed

        # Calm wind
        if wind_speed == 0:
            return WindComponents(
                runway_ident=runway_ident,
                runway_heading=runway_heading,
                headwind=0.0,
                crosswind=0.0,
                crosswind_direction="",
                max_crosswind=0.0,
            )

        # Variable wind (no direction) — use full speed as worst-case crosswind
        if wind_dir is None:
            return WindComponents(
                runway_ident=runway_ident,
                runway_heading=runway_heading,
                headwind=0.0,
                crosswind=float(wind_speed),
                crosswind_direction="",
                max_crosswind=float(wind_speed),
            )

        headwind, crosswind = _compute_components(wind_dir, runway_heading, wind_speed)

        # Determine crosswind direction
        relative = (wind_dir - runway_heading) % 360
        if relative > 180:
            xwind_dir = "left"
        else:
            xwind_dir = "right"

        # Max crosswind starts with basic crosswind
        max_crosswind = abs(crosswind)

        # Variable wind range — compute worst-case crosswind
        if report.wind_variable_from is not None and report.wind_variable_to is not None:
            max_crosswind = _worst_case_crosswind(
                report.wind_variable_from,
                report.wind_variable_to,
                runway_heading,
                wind_speed,
                max_crosswind,
            )

        # Gust components
        gust_hw = None
        gust_xw = None
        if report.wind_gust is not None:
            gust_hw, gust_xw = _compute_components(wind_dir, runway_heading, report.wind_gust)
            # Gust worst-case crosswind
            gust_max_xw = abs(gust_xw)
            if report.wind_variable_from is not None and report.wind_variable_to is not None:
                gust_max_xw = _worst_case_crosswind(
                    report.wind_variable_from,
                    report.wind_variable_to,
                    runway_heading,
                    report.wind_gust,
                    gust_max_xw,
                )
            max_crosswind = max(max_crosswind, gust_max_xw)

        return WindComponents(
            runway_ident=runway_ident,
            runway_heading=runway_heading,
            headwind=headwind,
            crosswind=crosswind,
            crosswind_direction=xwind_dir,
            gust_headwind=gust_hw,
            gust_crosswind=gust_xw,
            max_crosswind=max_crosswind,
        )

    @staticmethod
    def wind_components_for_runways(
        report: WeatherReport,
        runways: Dict[str, int],
    ) -> Dict[str, WindComponents]:
        """
        Calculate wind components for multiple runways.

        Args:
            report: WeatherReport with wind data
            runways: Dict mapping runway ident to heading
                     e.g., {"27L": 270, "09R": 90}

        Returns:
            Dict mapping runway ident to WindComponents
        """
        result = {}
        for ident, heading in runways.items():
            wc = WeatherAnalyzer.wind_components(report, heading, ident)
            if wc is not None:
                result[ident] = wc
        return result

    @staticmethod
    def compare_categories(
        actual: FlightCategory,
        forecast: FlightCategory,
    ) -> str:
        """
        Compare actual vs forecast flight categories.

        Args:
            actual: Actual (observed) category
            forecast: Forecast category

        Returns:
            "exact" if same, "worse" if actual is worse, "better" if actual is better
        """
        if actual == forecast:
            return "exact"
        elif actual < forecast:
            return "worse"
        else:
            return "better"

    @staticmethod
    def find_applicable_taf(
        taf: WeatherReport,
        check_time: datetime,
    ) -> Optional[WeatherReport]:
        """
        Find the most specific applicable TAF trend for a given time.

        Checks TEMPO/BECMG trends in reverse order (last matching wins).
        Falls back to the base TAF if no trend applies.

        Args:
            taf: TAF WeatherReport with trends
            check_time: Time to check

        Returns:
            The applicable WeatherReport (trend or base TAF)
        """
        applicable = WeatherAnalyzer.applicable_trends(taf, check_time)
        if applicable:
            return applicable[-1]
        return taf

    @staticmethod
    def applicable_trends(
        taf: WeatherReport,
        check_time: datetime,
    ) -> List[WeatherReport]:
        """
        Find all TAF trends valid at a given time.

        Args:
            taf: TAF WeatherReport with trends
            check_time: Time to check

        Returns:
            List of applicable trends, in order
        """
        result = []
        for trend in taf.trends:
            if _validity_contains(trend, check_time):
                result.append(trend)
        return result


# --- Module-level helpers (pure functions) ---

def _compute_components(
    wind_dir: int,
    runway_heading: int,
    speed: float,
) -> tuple:
    """
    Compute headwind and crosswind components.

    Returns:
        (headwind, crosswind) where positive headwind = from ahead,
        positive crosswind = from the right.
    """
    angle = abs(wind_dir - runway_heading)
    if angle > 180:
        angle = 360 - angle
    headwind = round(speed * cos(radians(angle)), 1)
    crosswind = round(speed * sin(radians(angle)), 1)

    # Determine sign: crosswind positive = from right
    relative = (wind_dir - runway_heading) % 360
    if relative > 180:
        crosswind = -crosswind  # from left

    return headwind, crosswind


def _worst_case_crosswind(
    var_from: int,
    var_to: int,
    runway_heading: int,
    speed: float,
    current_max: float,
) -> float:
    """
    Compute worst-case crosswind considering variable wind directions.

    Checks if perpendicular angles fall within the variable range,
    and also checks the extremes.
    """
    max_xw = current_max

    # Normalize variable range
    min_dir = var_from
    max_dir = var_to
    if max_dir < min_dir:
        max_dir += 360

    # Check both perpendicular directions
    for perp in [(runway_heading + 90) % 360, (runway_heading + 270) % 360]:
        norm_perp = perp
        if norm_perp < min_dir:
            norm_perp += 360
        if min_dir <= norm_perp <= max_dir:
            # Perpendicular is within variable range — full crosswind
            max_xw = max(max_xw, abs(speed))
            return max_xw

    # Check extremes
    for test_dir in [min_dir, max_dir]:
        angle = abs(test_dir % 360 - runway_heading)
        if angle > 180:
            angle = 360 - angle
        test_xw = abs(speed * sin(radians(angle)))
        max_xw = max(max_xw, test_xw)

    return max_xw


def _validity_contains(trend: WeatherReport, check_time: datetime) -> bool:
    """
    Check if a TAF trend's validity period contains the given time.

    Handles month-crossing cases.
    """
    start = trend.validity_start
    end = trend.validity_end

    if start is None:
        return False

    if end is None:
        # FM trend: valid from start until superseded (always applicable after start)
        return check_time >= start

    # Handle month-crossing
    if end < start:
        if check_time < start:
            # Move start back one month
            month = start.month - 1
            year = start.year
            if month < 1:
                month = 12
                year -= 1
            try:
                start = start.replace(year=year, month=month)
            except ValueError:
                return False
        else:
            # Move end forward one month
            month = end.month + 1
            year = end.year
            if month > 12:
                month = 1
                year += 1
            try:
                end = end.replace(year=year, month=month)
            except ValueError:
                return False

    return start <= check_time <= end
